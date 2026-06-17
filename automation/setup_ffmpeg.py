from __future__ import annotations

import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BIN = ROOT / ".bin"
TARGET = BIN / "ffmpeg.exe"


def main() -> int:
    try:
        import imageio_ffmpeg
    except ImportError as exc:
        raise SystemExit("Install imageio-ffmpeg first: python -m pip install imageio-ffmpeg") from exc

    source = Path(imageio_ffmpeg.get_ffmpeg_exe())
    if not source.exists():
        raise SystemExit(f"Bundled ffmpeg was not found: {source}")

    BIN.mkdir(exist_ok=True)
    if TARGET.exists() and TARGET.stat().st_size == source.stat().st_size:
        print(TARGET)
        return 0

    shutil.copy2(source, TARGET)
    print(TARGET)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

