from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from process_sermon_audio import download_youtube_audio, local_ffmpeg
from weekly_packet import ROOT


WORK = ROOT / "work"


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a Whisper transcript for a service video/audio source.")
    parser.add_argument("--job", type=Path, help="Job JSON containing source_file or youtube_url.")
    parser.add_argument("--source-file", help="Local service video/audio file.")
    parser.add_argument("--youtube-url", help="YouTube video URL to download/transcribe.")
    parser.add_argument("--detect-bounds", action="store_true", help="Update --job with detected sermon bounds.")
    parser.add_argument("--model", default="base", help="Whisper model to use.")
    parser.add_argument("--output-dir", type=Path, default=WORK, help="Output directory.")
    args = parser.parse_args()

    local_ffmpeg()
    job_data = {}
    if args.job and args.job.exists():
        job_data = json.loads(args.job.read_text(encoding="utf-8"))

    source_file = args.source_file or job_data.get("source_file")
    youtube_url = args.youtube_url or job_data.get("youtube_url")

    if source_file:
        source = Path(source_file)
        if not source.is_absolute():
            source = ROOT / source
        if not source.exists():
            raise SystemExit(f"source_file does not exist: {source}")
    elif youtube_url:
        source = download_youtube_audio(youtube_url)
    else:
        raise SystemExit("Set --job, --source-file, or --youtube-url.")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    command = [
        "whisper",
        str(source),
        "--model",
        args.model,
        "--language",
        "English",
        "--verbose",
        "False",
        "--output_dir",
        str(args.output_dir),
    ]
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    subprocess.run(command, check=True, env=env)
    json_path = args.output_dir / f"{source.stem}.json"
    if args.job:
        job_data["source_file"] = str(source)
        job_data["transcript_file"] = str(json_path)
        if args.detect_bounds:
            from detect_sermon_bounds import detect, load_segments

            detection = detect(load_segments(json_path))
            job_data["start_time"] = detection.start_time
            job_data["end_time"] = detection.end_time
            job_data["boundary_detection"] = {
                "confidence": detection.confidence,
                "start_reason": detection.start_reason,
                "end_reason": detection.end_reason,
            }
            print(f"start_time={detection.start_time}")
            print(f"end_time={detection.end_time}")
            print(f"confidence={detection.confidence}")
        args.job.write_text(json.dumps(job_data, indent=2), encoding="utf-8")
    print(json_path)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as exc:
        print(f"Command failed: {' '.join(str(part) for part in exc.cmd)}", file=sys.stderr)
        raise
