from __future__ import annotations

import argparse
import html
import json
import re
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from html.parser import HTMLParser
from pathlib import Path
from urllib.request import Request, urlopen

from weekly_packet import ROOT


DEFAULT_CHANNEL = "https://www.youtube.com/channel/UCOouhW9_VVwiVODtl0gDvVA/streams"
DEFAULT_CHANNEL_ID = "UCOouhW9_VVwiVODtl0gDvVA"
DEFAULT_SERMONS = "https://www.allsaintswoodbridge.org/latest-sermons"
WORK = ROOT / "work"

MONTHS = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}
DATE_RE = re.compile(
    r"\b("
    + "|".join(month.capitalize() for month in MONTHS)
    + r")\s+(\d{1,2}),\s+(\d{4})\b"
)


@dataclass
class Video:
    title: str
    url: str
    video_id: str
    upload_date: str


@dataclass
class SermonPost:
    title: str
    service_date: str
    preacher: str
    url: str


@dataclass
class DiscoveryItem:
    service_date: str
    video_title: str
    video_url: str
    status: str
    reason: str
    matching_sermon_title: str = ""


class TextAndLinksParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.text: list[str] = []
        self.links: list[tuple[str, str]] = []
        self._href_stack: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        href = ""
        for name, value in attrs:
            if name == "href" and value:
                href = value
                break
        self._href_stack.append(href)

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._href_stack:
            self._href_stack.pop()

    def handle_data(self, data: str) -> None:
        value = " ".join(html.unescape(data).split())
        if not value:
            return
        self.text.append(value)
        if self._href_stack:
            self.links.append((value, self._href_stack[-1]))


def fetch_text(url: str) -> str:
    request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8", errors="replace")


def parse_date(value: str) -> str:
    match = DATE_RE.search(value)
    if not match:
        return ""
    month_name, day, year = match.groups()
    return date(int(year), MONTHS[month_name.lower()], int(day)).isoformat()


def parse_yyyymmdd(value: str | None) -> str:
    if not value or not re.fullmatch(r"\d{8}", value):
        return ""
    return f"{value[0:4]}-{value[4:6]}-{value[6:8]}"


def parse_iso_date(value: str | None) -> str:
    if not value:
        return ""
    match = re.match(r"(\d{4}-\d{2}-\d{2})", value)
    return match.group(1) if match else ""


def channel_id_from_url(value: str) -> str:
    match = re.search(r"/channel/([^/?#]+)", value)
    if match:
        return match.group(1)
    if value.startswith("UC") and "/" not in value:
        return value
    return DEFAULT_CHANNEL_ID if value == DEFAULT_CHANNEL else ""


def looks_like_sermon_title(value: str) -> bool:
    lowered = value.lower()
    if len(value) < 4:
        return False
    if lowered.startswith("the rev."):
        return False
    if parse_date(value):
        return False
    if "(esv)" in lowered:
        return False
    if "scripture quotations" in lowered:
        return False
    if lowered in {"sermons", "older posts", "back to top"}:
        return False
    return True


def fetch_sermon_posts(url: str, limit: int) -> list[SermonPost]:
    parser = TextAndLinksParser()
    parser.feed(fetch_text(url))

    link_by_text: dict[str, str] = {}
    for text, href in parser.links:
        link_by_text.setdefault(text, href)

    posts: list[SermonPost] = []
    seen: set[tuple[str, str]] = set()
    text = parser.text
    for index, value in enumerate(text):
        service_date = parse_date(value)
        if not service_date:
            continue

        preacher = ""
        if index > 0 and text[index - 1].lower().startswith("the rev."):
            preacher = text[index - 1]

        title = ""
        for next_value in text[index + 1 : index + 8]:
            if looks_like_sermon_title(next_value):
                title = next_value.lstrip("# ").strip()
                break
        if not title:
            continue

        key = (service_date, title)
        if key in seen:
            continue
        seen.add(key)
        posts.append(
            SermonPost(
                title=title,
                service_date=service_date,
                preacher=preacher,
                url=link_by_text.get(title, ""),
            )
        )
        if len(posts) >= limit:
            break
    return posts


def fetch_youtube_videos(channel_url: str, limit: int) -> list[Video]:
    channel_id = channel_id_from_url(channel_url)
    if channel_id:
        try:
            return fetch_youtube_rss(channel_id, limit)
        except Exception:
            pass

    try:
        import yt_dlp
    except ImportError as exc:
        raise SystemExit("yt-dlp is missing. Run: python -m pip install yt-dlp") from exc

    options = {
        "extract_flat": True,
        "playlistend": limit,
        "quiet": True,
        "skip_download": True,
    }
    with yt_dlp.YoutubeDL(options) as ydl:
        info = ydl.extract_info(channel_url, download=False)

    entries = info.get("entries") or []
    videos: list[Video] = []
    for entry in entries[:limit]:
        video_id = entry.get("id") or ""
        url = entry.get("url") or ""
        if video_id and "youtube" not in url:
            url = f"https://www.youtube.com/watch?v={video_id}"
        upload_date = parse_yyyymmdd(entry.get("upload_date"))
        if not upload_date and entry.get("timestamp"):
            upload_date = datetime.fromtimestamp(entry["timestamp"]).date().isoformat()
        videos.append(
            Video(
                title=entry.get("title") or "",
                url=url,
                video_id=video_id,
                upload_date=upload_date,
            )
        )
    return videos


def fetch_youtube_rss(channel_id: str, limit: int) -> list[Video]:
    feed_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
    root = ET.fromstring(fetch_text(feed_url))
    ns = {
        "atom": "http://www.w3.org/2005/Atom",
        "yt": "http://www.youtube.com/xml/schemas/2015",
    }
    videos: list[Video] = []
    for entry in root.findall("atom:entry", ns)[:limit]:
        title = entry.findtext("atom:title", default="", namespaces=ns)
        video_id = entry.findtext("yt:videoId", default="", namespaces=ns)
        published = entry.findtext("atom:published", default="", namespaces=ns)
        link = entry.find("atom:link", ns)
        url = link.attrib.get("href", "") if link is not None else ""
        if video_id and not url:
            url = f"https://www.youtube.com/watch?v={video_id}"
        videos.append(
            Video(
                title=title,
                url=url,
                video_id=video_id,
                upload_date=parse_iso_date(published),
            )
        )
    return videos


def compare(videos: list[Video], sermons: list[SermonPost]) -> list[DiscoveryItem]:
    sermon_by_date: dict[str, SermonPost] = {}
    for sermon in sermons:
        sermon_by_date.setdefault(sermon.service_date, sermon)

    title_counts: dict[str, int] = {}
    for video in videos:
        title_counts[video.title.strip().lower()] = title_counts.get(video.title.strip().lower(), 0) + 1

    items: list[DiscoveryItem] = []
    for video in videos:
        service_date, date_reason = infer_service_date(video)
        if not service_date:
            items.append(
                DiscoveryItem(
                    service_date="",
                    video_title=video.title,
                    video_url=video.url,
                    status="review",
                    reason="No upload date was available from YouTube metadata.",
                )
            )
            continue

        matching = sermon_by_date.get(service_date)
        lowered = video.title.lower()
        if matching:
            status = "already_posted"
            reason = f"Website has a sermon post for {service_date}."
        elif "sunday" in lowered or "service" in lowered or "livestream" in lowered:
            status = "needs_sermon_post"
            reason = "Public website has no matching sermon post for this service date."
        else:
            status = "review"
            reason = "Video does not clearly look like a Sunday service."

        if title_counts.get(video.title.strip().lower(), 0) > 1:
            if status == "already_posted":
                status = "review"
            reason += " Recent YouTube videos share this same title; title cleanup may be needed."

        if date_reason:
            reason += f" {date_reason}"

        items.append(
            DiscoveryItem(
                service_date=service_date,
                video_title=video.title,
                video_url=video.url,
                status=status,
                reason=reason,
                matching_sermon_title=matching.title if matching else "",
            )
        )
    return items


def infer_service_date(video: Video) -> tuple[str, str]:
    if not video.upload_date:
        return "", ""
    try:
        published = date.fromisoformat(video.upload_date)
    except ValueError:
        return video.upload_date, ""

    lowered = video.title.lower()
    sunday_title = any(
        marker in lowered
        for marker in (
            "sunday",
            "easter",
            "pentecost",
            "epiphany",
            "advent",
            "christmas",
            "lent",
            "trinity",
        )
    )
    if sunday_title and published.weekday() == 0:
        service = published - timedelta(days=1)
        return service.isoformat(), f"Inferred Sunday service date from Monday YouTube publish date {video.upload_date}."
    if "ascension day" in lowered and published.weekday() == 4:
        service = published - timedelta(days=1)
        return service.isoformat(), f"Inferred Ascension service date from Friday YouTube publish date {video.upload_date}."
    return video.upload_date, ""


def report_text(items: list[DiscoveryItem], sermons: list[SermonPost]) -> str:
    lines = [
        "# Sermon Work Discovery",
        "",
        "## Candidate Services",
        "",
    ]
    for item in items:
        lines.extend(
            [
                f"- {item.service_date or 'unknown date'} | {item.status} | {item.video_title}",
                f"  URL: {item.video_url}",
                f"  Reason: {item.reason}",
            ]
        )
        if item.matching_sermon_title:
            lines.append(f"  Matching sermon: {item.matching_sermon_title}")
    lines.extend(["", "## Recent Website Sermons", ""])
    for sermon in sermons:
        lines.append(f"- {sermon.service_date} | {sermon.title} | {sermon.preacher}")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Find candidate YouTube services that may need sermon processing.")
    parser.add_argument("--youtube", default=DEFAULT_CHANNEL, help="YouTube channel/streams/videos URL.")
    parser.add_argument("--sermons", default=DEFAULT_SERMONS, help="Public sermons page URL.")
    parser.add_argument("--limit", type=int, default=12, help="Number of recent videos/posts to inspect.")
    parser.add_argument("--output-dir", type=Path, default=WORK, help="Output directory.")
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    videos = fetch_youtube_videos(args.youtube, args.limit)
    sermons = fetch_sermon_posts(args.sermons, args.limit)
    items = compare(videos, sermons)

    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "youtube_source": args.youtube,
        "sermons_source": args.sermons,
        "items": [asdict(item) for item in items],
        "recent_sermons": [asdict(sermon) for sermon in sermons],
    }
    json_path = args.output_dir / "sermon-discovery.json"
    md_path = args.output_dir / "sermon-discovery.md"
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    md_path.write_text(report_text(items, sermons), encoding="utf-8")
    print(json_path)
    print(md_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
