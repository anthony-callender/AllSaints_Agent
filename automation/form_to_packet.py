from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from weekly_packet import ROOT, packet_text, slugify


FIELD_PATTERNS = {
    "service_date": [
        r"^(?:service\s+date|sermon\s+date|date)\s*[:\-]\s*(.+)$",
    ],
    "sermon_title": [
        r"^(?:sermon\s+title|title)\s*[:\-]\s*(.+)$",
    ],
    "preacher": [
        r"^(?:preacher|speaker|clergy)\s*[:\-]\s*(.+)$",
    ],
    "scripture_reference": [
        r"^(?:scripture|scripture\s+reference|passage|text)\s*[:\-]\s*(.+)$",
    ],
    "service_title": [
        r"^(?:service\s+title|sunday|occasion)\s*[:\-]\s*(.+)$",
    ],
    "audio_file": [
        r"^(?:audio|audio\s+file|recording)\s*[:\-]\s*(.+)$",
    ],
}


def normalize_date(value: str) -> str:
    value = value.strip()
    match = re.search(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})", value)
    if match:
        year, month, day = match.groups()
        return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"
    match = re.search(r"(\d{1,2})[-/](\d{1,2})[-/](\d{4})", value)
    if match:
        month, day, year = match.groups()
        return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"
    return value


def parse_form(text: str) -> dict:
    data = {
        "service_date": "",
        "service_title": "",
        "sermon_title": "",
        "preacher": "",
        "scripture_reference": "",
        "scripture_text": "",
        "audio_file": "",
        "youtube_video_url": "",
        "youtube_thumbnail_file": "",
        "notes": "",
    }
    lines = [line.rstrip() for line in text.splitlines()]

    scripture_start = None
    notes_start = None
    for index, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue
        lower = stripped.lower()
        if lower in {"scripture text:", "scripture reading:", "reading text:"}:
            scripture_start = index + 1
            continue
        if lower in {"notes:", "comments:", "additional notes:"}:
            notes_start = index + 1
            continue
        for field, patterns in FIELD_PATTERNS.items():
            if data[field]:
                continue
            for pattern in patterns:
                match = re.match(pattern, stripped, flags=re.IGNORECASE)
                if match:
                    data[field] = match.group(1).strip()
                    break

    if data["service_date"]:
        data["service_date"] = normalize_date(data["service_date"])

    if scripture_start is not None:
        end = notes_start - 1 if notes_start and notes_start > scripture_start else len(lines)
        scripture_lines = [line.strip() for line in lines[scripture_start:end]]
        data["scripture_text"] = "\n".join(line for line in scripture_lines if line).strip()

    if notes_start is not None:
        note_lines = [line.strip() for line in lines[notes_start:]]
        data["notes"] = "\n".join(line for line in note_lines if line).strip()

    return data


def main() -> int:
    parser = argparse.ArgumentParser(description="Parse a sermon form text file into a weekly packet.")
    parser.add_argument("--input", required=True, type=Path, help="Plain text sermon form or email body.")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "work", help="Output directory.")
    args = parser.parse_args()

    data = parse_form(args.input.read_text(encoding="utf-8"))
    args.output_dir.mkdir(parents=True, exist_ok=True)

    service_date = data.get("service_date") or "undated"
    title = data.get("sermon_title") or data.get("service_title") or "sermon"
    stem = f"{service_date}-{slugify(title)}"

    json_path = args.output_dir / f"{stem}.json"
    packet_path = args.output_dir / f"{stem}.md"
    json_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    packet_path.write_text(packet_text(data), encoding="utf-8")
    print(json_path)
    print(packet_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

