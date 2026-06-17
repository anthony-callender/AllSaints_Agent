from __future__ import annotations

import argparse
import json
import re
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def slugify(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-") or "sermon"


def format_scripture_markdown(reference: str, text: str) -> str:
    if not text.strip():
        return "[paste scripture text here]"

    formatted_lines = []
    if reference:
        formatted_lines.extend([f"**{reference} (ESV)**", ""])

    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            formatted_lines.append("")
            continue
        stripped = re.sub(r"^\^?\{?(\d{1,3})\}?\s+", r"<sup>\1</sup> ", stripped)
        stripped = re.sub(r"(?<=\s)\^?\{(\d{1,3})\}", r"<sup>\1</sup>", stripped)
        formatted_lines.append(stripped)

    return "\n".join(formatted_lines).strip()


def read_payload(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def packet_text(data: dict) -> str:
    service_date = data.get("service_date", "").strip()
    sermon_title = data.get("sermon_title", "").strip()
    service_title = data.get("service_title", "").strip()
    preacher = data.get("preacher", "").strip()
    scripture_reference = data.get("scripture_reference", "").strip()
    scripture_text = data.get("scripture_text", "").strip()
    audio_file = data.get("audio_file", "").strip()
    youtube_url = data.get("youtube_video_url", "").strip()
    thumbnail = data.get("youtube_thumbnail_file", "").strip()
    start_time = data.get("start_time", "").strip()
    end_time = data.get("end_time", "").strip()
    boundary_detection = data.get("boundary_detection") or {}
    notes = data.get("notes", "").strip()

    display_title = sermon_title or service_title or "Untitled sermon"
    lines = [
        f"# Weekly Sermon Packet - {service_date or date.today().isoformat()}",
        "",
        "## Website Post Fields",
        "",
        f"Title: {display_title}",
        f"Preacher: {preacher}",
        f"Date: {service_date}",
        f"Scripture: {scripture_reference}",
        "",
        "Body:",
        "",
        format_scripture_markdown(scripture_reference, scripture_text),
        "",
        "Standard footer:",
        "",
        "Scripture quotations are from the ESV Bible. Used by permission. All rights reserved.",
        "",
        "## Assets",
        "",
        f"Audio file: {audio_file or '[attach sermon audio]'}",
        "Image: sermon.png",
    ]
    if start_time or end_time:
        lines.extend(
            [
                "",
                "## Sermon Bounds",
                "",
                f"Start: {start_time or '[not set]'}",
                f"End: {end_time or '[not set]'}",
            ]
        )
        if boundary_detection:
            lines.extend(
                [
                    f"Confidence: {boundary_detection.get('confidence', '')}",
                    f"Start reason: {boundary_detection.get('start_reason', '')}",
                    f"End reason: {boundary_detection.get('end_reason', '')}",
                ]
            )
    lines.extend(
        [
        "",
        "## YouTube Live Cleanup",
        "",
        f"Video URL: {youtube_url or '[paste YouTube Studio/live video URL]'}",
        f"Correct video title: {service_title or display_title}",
        f"Thumbnail file: {thumbnail or '[download title slide from Planning Center]'}",
        "",
        "Checklist:",
        "",
        "- Confirm service title/date in Planning Center.",
        "- Download the YouTube title slide from Plan Files.",
        "- In YouTube Studio > Content > Live, match the livestream by date.",
        "- Update the title if needed.",
        "- Upload the title slide as thumbnail.",
        "- Save and verify on the public channel Live tab.",
        "- Publish or verify the sermon post on the website.",
        ]
    )
    if notes:
        lines.extend(["", "## Notes", "", notes])
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a copy-ready weekly sermon workflow packet.")
    parser.add_argument("--input", required=True, type=Path, help="Path to sermon metadata JSON.")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "work", help="Output directory.")
    args = parser.parse_args()

    data = read_payload(args.input)
    service_date = data.get("service_date") or date.today().isoformat()
    title = data.get("sermon_title") or data.get("service_title") or "sermon"
    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{service_date}-{slugify(title)}.md"
    output_path.write_text(packet_text(data), encoding="utf-8")
    print(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
