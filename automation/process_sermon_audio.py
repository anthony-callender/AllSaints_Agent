from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from weekly_packet import ROOT, packet_text, slugify


DOWNLOADS = ROOT / "downloads"
WORK = ROOT / "work"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def local_ffmpeg() -> str:
    local_bin = ROOT / ".bin"
    if local_bin.exists():
        os.environ["PATH"] = f"{local_bin}{os.pathsep}{os.environ.get('PATH', '')}"
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise SystemExit("ffmpeg is missing. Run: python .\\automation\\setup_ffmpeg.py")
    return ffmpeg


def seconds(value: str | int | float | None) -> float | None:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if re.fullmatch(r"\d+(?:\.\d+)?", text):
        return float(text)
    parts = text.split(":")
    if len(parts) > 3:
        raise ValueError(f"Invalid timestamp: {value}")
    total = 0.0
    for part in parts:
        total = total * 60 + float(part)
    return total


def timestamp(value: str | int | float | None) -> str | None:
    parsed = seconds(value)
    if parsed is None:
        return None
    whole = int(parsed)
    frac = parsed - whole
    hours = whole // 3600
    minutes = (whole % 3600) // 60
    secs = whole % 60
    if frac:
        return f"{hours:02d}:{minutes:02d}:{secs + frac:06.3f}"
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def download_youtube_audio(url: str) -> Path:
    try:
        import yt_dlp
    except ImportError as exc:
        raise SystemExit("yt-dlp is missing. Run: python -m pip install yt-dlp") from exc

    DOWNLOADS.mkdir(exist_ok=True)
    options = {
        "format": "bestaudio/best",
        "outtmpl": str(DOWNLOADS / "%(upload_date)s-%(id)s.%(ext)s"),
        "quiet": False,
        "noplaylist": True,
    }
    with yt_dlp.YoutubeDL(options) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = Path(ydl.prepare_filename(info))
    if not filename.exists():
        requested = info.get("requested_downloads") or []
        if requested and requested[0].get("filepath"):
            filename = Path(requested[0]["filepath"])
    if not filename.exists():
        raise SystemExit("yt-dlp completed, but the downloaded file path could not be found.")
    return filename


def output_name(data: dict) -> str:
    service_date = (data.get("service_date") or "").replace("-", "")
    if not service_date:
        service_date = "undated"
    title = data.get("sermon_title") or data.get("service_title") or "sermon"
    return f"{service_date}-{slugify(title)}.mp3"


def audio_filter(filter_mode: str) -> str:
    if filter_mode == "standard":
        return "pan=mono|c0=0.5*c0+0.5*c1,acompressor=threshold=-18dB:ratio=3:attack=5:release=200,loudnorm=I=-16:TP=-2:LRA=11"
    if filter_mode == "dialogue":
        return "dialoguenhance=original=0.7:enhance=2.0:voice=8,pan=mono|c0=0.5*c0+0.5*c1,highpass=f=80,lowpass=f=9000,loudnorm=I=-16:TP=-2:LRA=11"
    return "pan=mono|c0=c0,highpass=f=80,lowpass=f=9000,loudnorm=I=-16:TP=-2:LRA=11"


def build_audio(data: dict, source: Path, ffmpeg: str, output_dir: Path, filter_mode: str) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / output_name(data)

    start = timestamp(data.get("start_time"))
    start_seconds = seconds(data.get("start_time")) or 0.0
    end_seconds = seconds(data.get("end_time"))
    duration = None
    if end_seconds is not None:
        duration = max(0.0, end_seconds - start_seconds)
        if duration <= 0:
            raise SystemExit("end_time must be later than start_time.")

    command = [ffmpeg, "-y", "-hide_banner", "-loglevel", "error"]
    if start:
        command.extend(["-ss", start])
    if duration is not None:
        command.extend(["-t", f"{duration:.3f}"])
    command.extend(["-i", str(source)])
    command.extend(
        [
            "-vn",
            "-af",
            audio_filter(filter_mode),
            "-codec:a",
            "libmp3lame",
            "-b:a",
            "128k",
            "-map_metadata",
            "-1",
            "-metadata",
            f"title={data.get('sermon_title') or data.get('service_title') or ''}",
            "-metadata",
            f"artist={data.get('preacher') or ''}",
            "-metadata",
            "album=All Saints' Church Sermons",
            "-metadata",
            f"date={data.get('service_date') or ''}",
            str(output),
        ]
    )
    subprocess.run(command, check=True)
    return output


def write_outputs(data: dict, mp3_path: Path, output_dir: Path) -> tuple[Path, Path]:
    updated = dict(data)
    updated["audio_file"] = str(mp3_path)
    service_date = updated.get("service_date") or "undated"
    title = updated.get("sermon_title") or updated.get("service_title") or "sermon"
    stem = f"{service_date}-{slugify(title)}"
    json_path = output_dir / f"{stem}.json"
    packet_path = output_dir / f"{stem}.md"
    json_path.write_text(json.dumps(updated, indent=2), encoding="utf-8")
    packet_path.write_text(packet_text(updated), encoding="utf-8")
    return json_path, packet_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Download/trim/process sermon audio into a publish-ready MP3.")
    parser.add_argument("--job", required=True, type=Path, help="Sermon job JSON.")
    parser.add_argument("--source-file", help="Override source_file from the job JSON.")
    parser.add_argument("--youtube-url", help="Override youtube_url from the job JSON.")
    parser.add_argument("--start-time", help="Override start_time from the job JSON.")
    parser.add_argument("--end-time", help="Override end_time from the job JSON.")
    parser.add_argument("--transcript", type=Path, help="Whisper .json/.tsv transcript for automatic bounds.")
    parser.add_argument("--detect-times", action="store_true", help="Detect start/end times from --transcript.")
    parser.add_argument(
        "--filter-mode",
        choices=["clean", "dialogue", "standard"],
        default="clean",
        help="Audio cleanup chain to use. clean is the default for sermon speech.",
    )
    parser.add_argument("--output-dir", type=Path, default=WORK, help="Output directory.")
    args = parser.parse_args()

    data = load_json(args.job)
    for key, value in {
        "source_file": args.source_file,
        "youtube_url": args.youtube_url,
        "start_time": args.start_time,
        "end_time": args.end_time,
    }.items():
        if value:
            data[key] = value

    if args.detect_times:
        if not args.transcript:
            raise SystemExit("--detect-times requires --transcript.")
        from detect_sermon_bounds import detect, load_segments

        detection = detect(load_segments(args.transcript))
        data["start_time"] = detection.start_time
        data["end_time"] = detection.end_time
        data["boundary_detection"] = {
            "confidence": detection.confidence,
            "start_reason": detection.start_reason,
            "end_reason": detection.end_reason,
        }

    ffmpeg = local_ffmpeg()

    source_file = data.get("source_file")
    youtube_url = data.get("youtube_url")
    if source_file:
        source = Path(source_file)
        if not source.is_absolute():
            source = ROOT / source
        if not source.exists():
            raise SystemExit(f"source_file does not exist: {source}")
    elif youtube_url:
        source = download_youtube_audio(youtube_url)
    else:
        raise SystemExit("Set either source_file or youtube_url in the job JSON.")

    data["audio_filter_mode"] = args.filter_mode
    mp3_path = build_audio(data, source, ffmpeg, args.output_dir, args.filter_mode)
    json_path, packet_path = write_outputs(data, mp3_path, args.output_dir)
    print(mp3_path)
    print(json_path)
    print(packet_path)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as exc:
        print(f"Command failed: {' '.join(str(part) for part in exc.cmd)}", file=sys.stderr)
        raise
