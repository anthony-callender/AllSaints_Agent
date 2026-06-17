from __future__ import annotations

import os
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VIDEOS = [
    "AllSaintsYouTube.mp4",
    "AllSaintsSermons-1.mp4",
    "AllSaintsSermons-2.mp4",
    "AllSaintsSermons-3.mp4",
    "AllSaintsSermons-4.mp4",
]


def main() -> int:
    local_bin = ROOT / ".bin"
    if local_bin.exists():
        os.environ["PATH"] = f"{local_bin}{os.pathsep}{os.environ.get('PATH', '')}"

    print("All Saints automation environment check")
    print(f"Workspace: {ROOT}")
    print()

    for name in ("python", "whisper", "ffmpeg", "yt-dlp"):
        path = shutil.which(name)
        status = path if path else "missing"
        print(f"{name:8} {status}")

    print()
    for video in VIDEOS:
        path = ROOT / video
        if path.exists():
            size_mb = path.stat().st_size / (1024 * 1024)
            print(f"video    {video} ({size_mb:.1f} MB)")
        else:
            print(f"video    missing: {video}")

    print()
    if not shutil.which("ffmpeg"):
        print("Blocker: ffmpeg is required before Whisper can transcribe MP4 files.")
        print("Run: python .\\automation\\setup_ffmpeg.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
