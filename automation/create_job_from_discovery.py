from __future__ import annotations

import argparse
import json
from pathlib import Path

from weekly_packet import ROOT, slugify


WORK = ROOT / "work"


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a sermon job JSON from sermon-discovery.json.")
    parser.add_argument("--discovery", type=Path, default=WORK / "sermon-discovery.json")
    parser.add_argument("--date", help="Use a specific service date from discovery.")
    parser.add_argument("--status", default="needs_sermon_post", help="Discovery status to select.")
    parser.add_argument("--index", type=int, default=0, help="Zero-based item index after filtering.")
    parser.add_argument("--output-dir", type=Path, default=WORK)
    args = parser.parse_args()

    payload = json.loads(args.discovery.read_text(encoding="utf-8"))
    items = payload.get("items") or []
    if args.date:
        candidates = [item for item in items if item.get("service_date") == args.date]
    else:
        candidates = [item for item in items if item.get("status") == args.status]

    if not candidates:
        raise SystemExit("No matching discovery item found.")
    if args.index >= len(candidates):
        raise SystemExit(f"Index {args.index} is out of range; {len(candidates)} candidates found.")

    item = candidates[args.index]
    service_date = item.get("service_date") or "undated"
    service_title = item.get("video_title") or "Service"
    job = {
        "service_date": service_date,
        "service_title": service_title,
        "sermon_title": "",
        "preacher": "",
        "scripture_reference": "",
        "scripture_text": "",
        "youtube_url": item.get("video_url") or "",
        "source_file": "",
        "start_time": "",
        "end_time": "",
        "youtube_video_url": item.get("video_url") or "",
        "youtube_thumbnail_file": "",
        "notes": f"Created from discovery status: {item.get('status')}. {item.get('reason', '')}".strip(),
    }

    args.output_dir.mkdir(parents=True, exist_ok=True)
    output = args.output_dir / f"{service_date}-{slugify(service_title)}.json"
    output.write_text(json.dumps(job, indent=2), encoding="utf-8")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

