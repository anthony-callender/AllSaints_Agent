from __future__ import annotations

import argparse
import html
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

from process_sermon_audio import timestamp
from weekly_packet import ROOT


WORK = ROOT / "work"

START_CUES = [
    ("please be seated", 4),
    ("you may be seated", 4),
    ("may be seated", 3),
    ("good morning", 2),
    ("in the name of the father", 4),
    ("let us pray", 1),
    ("gracious god", 1),
    ("heavenly father", 1),
]
PRE_START_CUES = [
    ("the gospel of the lord", 5),
    ("praise to you lord christ", 5),
    ("this is the gospel of the lord", 5),
    ("the holy gospel", 3),
    ("glory to you lord christ", 3),
]
END_CUES = [
    ("let us stand", 5),
    ("please stand", 4),
    ("standing let us", 4),
    ("nicene creed", 7),
    ("nice scene creed", 7),
    ("we believe in one god", 7),
    ("let us confess our faith", 7),
    ("confess our faith", 6),
    ("prayers of the people", 4),
]


@dataclass
class Segment:
    start: float
    end: float
    text: str


@dataclass
class CueHit:
    cue: str
    start: float
    end: float
    text: str
    score: int


@dataclass
class Detection:
    start_time: str
    end_time: str
    confidence: str
    start_reason: str
    end_reason: str
    start_candidates: list[dict]
    end_candidates: list[dict]


def normalize(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s']", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def parse_json(path: Path) -> list[Segment]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return [
        Segment(float(item["start"]), float(item["end"]), item.get("text", ""))
        for item in payload.get("segments", [])
        if "start" in item and "end" in item
    ]


def parse_tsv(path: Path) -> list[Segment]:
    lines = path.read_text(encoding="utf-8").splitlines()
    segments: list[Segment] = []
    for line in lines[1:]:
        parts = line.split("\t", 2)
        if len(parts) != 3:
            continue
        start_ms, end_ms, text = parts
        if not start_ms.isdigit() or not end_ms.isdigit():
            continue
        segments.append(Segment(int(start_ms) / 1000, int(end_ms) / 1000, text))
    return segments


def parse_vtt_timestamp(value: str) -> float:
    value = value.strip().split()[0]
    parts = value.split(":")
    if len(parts) == 2:
        minutes, seconds = parts
        return int(minutes) * 60 + float(seconds)
    if len(parts) == 3:
        hours, minutes, seconds = parts
        return int(hours) * 3600 + int(minutes) * 60 + float(seconds)
    raise ValueError(f"Invalid VTT timestamp: {value}")


def clean_vtt_text(value: str) -> str:
    value = html.unescape(value)
    value = re.sub(r"<\d{2}:\d{2}:\d{2}\.\d{3}>", " ", value)
    value = re.sub(r"<\d{2}:\d{2}\.\d{3}>", " ", value)
    value = re.sub(r"</?c[^>]*>", " ", value)
    value = re.sub(r"<[^>]+>", " ", value)
    value = value.replace(">>", " ")
    return re.sub(r"\s+", " ", value).strip()


def parse_vtt(path: Path) -> list[Segment]:
    lines = path.read_text(encoding="utf-8").splitlines()
    segments: list[Segment] = []
    index = 0
    while index < len(lines):
        line = lines[index].strip()
        if "-->" not in line:
            index += 1
            continue
        start_text, end_text = line.split("-->", 1)
        start = parse_vtt_timestamp(start_text)
        end = parse_vtt_timestamp(end_text)
        index += 1
        cue_lines = []
        while index < len(lines) and lines[index].strip():
            cue_lines.append(lines[index])
            index += 1
        text = clean_vtt_text(" ".join(cue_lines))
        if text:
            segments.append(Segment(start, end, text))
        index += 1
    return segments


def load_segments(path: Path) -> list[Segment]:
    suffix = path.suffix.lower()
    if suffix == ".json":
        return parse_json(path)
    if suffix == ".tsv":
        return parse_tsv(path)
    if suffix == ".vtt":
        return parse_vtt(path)
    raise SystemExit("Use a Whisper .json, .tsv, or .vtt transcript for sermon boundary detection.")


def find_hits(segments: list[Segment], cues: list[tuple[str, int]]) -> list[CueHit]:
    hits: list[CueHit] = []
    for segment in segments:
        text = normalize(segment.text)
        for cue, score in cues:
            if cue in text:
                hits.append(CueHit(cue, segment.start, segment.end, segment.text.strip(), score))
    return hits


def surrounding_text(segments: list[Segment], start: float, window: float = 90) -> str:
    chunks = [
        segment.text.strip()
        for segment in segments
        if start <= segment.start <= start + window and segment.text.strip()
    ]
    return " ".join(chunks)


def candidate_starts(segments: list[Segment]) -> list[CueHit]:
    pre_hits = find_hits(segments, PRE_START_CUES)
    start_hits = find_hits(segments, START_CUES)
    candidates: list[CueHit] = []

    last_gospel = max(pre_hits, key=lambda hit: hit.start, default=None)
    for hit in start_hits:
        score = hit.score
        if last_gospel and 0 <= hit.start - last_gospel.start <= 900:
            score += last_gospel.score
        if hit.start < 120:
            score -= 2
        candidates.append(CueHit(hit.cue, hit.start, hit.end, hit.text, score))

    if last_gospel:
        after = [segment for segment in segments if segment.start > last_gospel.end + 5]
        if after:
            first_after = after[0]
            candidates.append(
                CueHit(
                    "after gospel reading",
                    first_after.start,
                    first_after.end,
                    first_after.text.strip(),
                    last_gospel.score,
                )
            )
    return sorted(candidates, key=lambda hit: (hit.score, -hit.start), reverse=True)


def candidate_ends(segments: list[Segment], start_time: float) -> list[CueHit]:
    end_hits = [
        hit
        for hit in find_hits(segments, END_CUES)
        if hit.start > start_time + 240
    ]
    return sorted(end_hits, key=lambda hit: (hit.score, -hit.start), reverse=True)


def choose_end(segments: list[Segment], start_time: float, end_hits: list[CueHit]) -> tuple[float, str, int]:
    if end_hits:
        hit = end_hits[0]
        preceding = [segment for segment in segments if start_time < segment.end <= hit.start]
        end_time = preceding[-1].end if preceding else max(hit.start - 2, start_time + 60)
        return end_time, f"Found post-sermon cue '{hit.cue}' at {timestamp(hit.start)}.", hit.score

    amen_segments = [
        segment
        for segment in segments
        if segment.start > start_time + 480 and normalize(segment.text).endswith("amen")
    ]
    if amen_segments:
        hit = amen_segments[-1]
        return hit.end, "No Creed/prayers cue found; used the last later segment ending in 'Amen'.", 2

    last = segments[-1] if segments else Segment(start_time + 60, start_time + 60, "")
    return last.end, "No end cue found; used transcript end.", 0


def detect(segments: list[Segment]) -> Detection:
    if not segments:
        raise SystemExit("Transcript has no segments.")

    starts = candidate_starts(segments)
    if starts:
        start = starts[0]
        start_time = max(0.0, start.start - 1)
        start_reason = f"Found sermon-start cue '{start.cue}' at {timestamp(start.start)}."
        start_score = start.score
    else:
        first = segments[0]
        start_time = first.start
        start_reason = "No sermon-start cue found; used transcript start."
        start_score = 0

    ends = candidate_ends(segments, start_time)
    end_time, end_reason, end_score = choose_end(segments, start_time, ends)
    if end_time <= start_time:
        end_time = max(segment.end for segment in segments)

    total_score = start_score + end_score
    if total_score >= 11:
        confidence = "high"
    elif total_score >= 6:
        confidence = "medium"
    else:
        confidence = "low"

    return Detection(
        start_time=timestamp(start_time) or "00:00:00",
        end_time=timestamp(end_time) or "00:00:00",
        confidence=confidence,
        start_reason=start_reason,
        end_reason=end_reason,
        start_candidates=[asdict(hit) for hit in starts[:5]],
        end_candidates=[asdict(hit) for hit in ends[:5]],
    )


def update_job(job_path: Path, detection: Detection) -> None:
    payload = json.loads(job_path.read_text(encoding="utf-8"))
    payload["start_time"] = detection.start_time
    payload["end_time"] = detection.end_time
    payload["boundary_detection"] = {
        "confidence": detection.confidence,
        "start_reason": detection.start_reason,
        "end_reason": detection.end_reason,
    }
    job_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Suggest sermon start/end times from a Whisper transcript.")
    parser.add_argument("--transcript", required=True, type=Path, help="Whisper .json or .tsv transcript.")
    parser.add_argument("--job", type=Path, help="Optional job JSON to update.")
    parser.add_argument("--write", action="store_true", help="Write detected times into --job.")
    parser.add_argument("--output", type=Path, default=WORK / "sermon-boundaries.json")
    args = parser.parse_args()

    segments = load_segments(args.transcript)
    detection = detect(segments)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(asdict(detection), indent=2), encoding="utf-8")
    if args.write:
        if not args.job:
            raise SystemExit("--write requires --job.")
        update_job(args.job, detection)
    print(args.output)
    print(f"start_time={detection.start_time}")
    print(f"end_time={detection.end_time}")
    print(f"confidence={detection.confidence}")
    print(detection.start_reason)
    print(detection.end_reason)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
