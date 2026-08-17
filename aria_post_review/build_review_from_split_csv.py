"""
Build the gesture_review dashboard from separate hand gesture and PPG CSV files.

This matches the current VRS extraction output:
- hand_gesture.csv has timestamp_ns, confidence, wrist, and palm columns.
- ppg.csv has timestamp_ns and raw PPG value columns.
- voice.csv has timestamp_ns, num_samples, and raw audio_samples.

If no transcript JSON is provided, the script creates review sections in fixed
time windows so the dashboard can still show post-session feedback.
"""

import argparse
import csv
import json
import math
import os
import re
from collections import Counter
from pathlib import Path

from build_review_data import (
    PPG_SPIKE_THRESHOLD,
    analyze_segment,
    build_summary,
    format_time,
    parse_time,
    ppg_baseline_stats,
)
from eye_features import read_eye_samples
from vocal_features import analyze_vocal_features


FILLER_WORDS = {
    "ah",
    "actually",
    "basically",
    "er",
    "literally",
    "like",
    "so",
    "uh",
    "um",
}
FILLER_PHRASES = {
    ("i", "mean"),
    ("kind", "of"),
    ("sort", "of"),
    ("you", "know"),
}


def parse_float(value, default=None):
    if value in (None, ""):
        return default
    try:
        return float(value)
    except ValueError:
        return default


def parse_int(value, default=None):
    if value in (None, ""):
        return default
    try:
        return int(float(value))
    except ValueError:
        return default


def read_rows(path):
    with path.open(newline="", encoding="utf-8-sig") as csv_file:
        return list(csv.DictReader(csv_file))


def position(row, prefix):
    x = parse_float(row.get(f"{prefix}_x"))
    y = parse_float(row.get(f"{prefix}_y"))
    z = parse_float(row.get(f"{prefix}_z"))
    if x is None or y is None or z is None:
        return None
    return [x, y, z]


def hand_from_row(row, side):
    confidence = parse_float(row.get(f"{side}_confidence"), default=0.0)
    palm = position(row, f"{side}_palm")
    wrist = position(row, f"{side}_wrist")
    if confidence <= 0.0 or (palm is None and wrist is None):
        return None

    return {
        "confidence": confidence,
        "wrist_position_device": wrist,
        "palm_position_device": palm,
    }


def detect_global_start_ns(hand_rows, ppg_rows):
    timestamps = []
    for row in hand_rows:
        timestamp = parse_int(row.get("timestamp_ns"))
        if timestamp is not None:
            timestamps.append(timestamp)
    for row in ppg_rows:
        timestamp = parse_int(row.get("timestamp_ns"))
        if timestamp is not None:
            timestamps.append(timestamp)

    if not timestamps:
        raise ValueError("Could not find timestamp_ns values in either CSV file.")
    return min(timestamps)


def voice_metadata(voice_csv):
    if voice_csv is None:
        return None

    first_timestamp_ns = None
    last_timestamp_ns = None
    row_count = 0
    sample_count = 0

    with voice_csv.open(newline="", encoding="utf-8-sig") as csv_file:
        reader = csv.DictReader(csv_file)
        for row in reader:
            row_count += 1
            timestamp = parse_int(row.get("timestamp_ns"))
            if timestamp is not None:
                first_timestamp_ns = timestamp if first_timestamp_ns is None else first_timestamp_ns
                last_timestamp_ns = timestamp

            sample_count += parse_int(row.get("num_samples"), default=0) or 0

    duration_s = 0.0
    if first_timestamp_ns is not None and last_timestamp_ns is not None:
        duration_s = (last_timestamp_ns - first_timestamp_ns) / 1_000_000_000

    return {
        "path": voice_csv,
        "first_timestamp_ns": first_timestamp_ns,
        "last_timestamp_ns": last_timestamp_ns,
        "row_count": row_count,
        "sample_count": sample_count,
        "duration_s": duration_s,
    }


def build_hand_samples(hand_rows, start_ns, confidence_threshold):
    samples = []
    for row in hand_rows:
        timestamp = parse_int(row.get("timestamp_ns"))
        if timestamp is None:
            continue

        left = hand_from_row(row, "left")
        right = hand_from_row(row, "right")
        left_visible = bool(left and left["confidence"] >= confidence_threshold)
        right_visible = bool(right and right["confidence"] >= confidence_threshold)

        samples.append(
            {
                "time_s": round((timestamp - start_ns) / 1_000_000_000, 3),
                "left_visible": left_visible,
                "right_visible": right_visible,
                "left": left if left_visible else None,
                "right": right if right_visible else None,
            }
        )
    return samples


def build_ppg_samples(ppg_rows, start_ns):
    samples = []
    for row in ppg_rows:
        timestamp = parse_int(row.get("timestamp_ns"))
        value = parse_float(row.get("value"))
        if timestamp is None or value is None:
            continue

        samples.append(
            {
                "time_s": round((timestamp - start_ns) / 1_000_000_000, 3),
                "value": value,
            }
        )
    return samples


def load_transcript(transcript_path):
    if transcript_path is None:
        return None

    transcript = json.loads(transcript_path.read_text(encoding="utf-8"))
    return transcript.get("segments", transcript)


def auto_segments(duration_s, window_seconds):
    segments = []
    count = max(1, math.ceil(duration_s / window_seconds))
    for index in range(count):
        start = index * window_seconds
        end = min(duration_s, (index + 1) * window_seconds)
        segments.append(
            {
                "id": f"window-{index + 1:03d}",
                "start": format_time(start),
                "end": format_time(end),
                "text": f"Speech section {index + 1} ({format_time(start)} - {format_time(end)})",
            }
        )
    return segments


def segment_key(segment):
    return segment.get("id", f"seg-{int(parse_time(segment['start'])):03d}")


def clean_word(text):
    return re.sub(r"[^a-z0-9']", "", str(text).lower())


def transcript_word_rows(transcript_segments):
    rows = []
    for segment in transcript_segments:
        words = segment.get("words") or [
            {"text": word}
            for word in re.findall(r"[A-Za-z0-9']+", segment.get("text", ""))
        ]
        for index, word in enumerate(words):
            text = word.get("text") or word.get("word")
            clean = clean_word(text)
            if not clean:
                continue

            rows.append(
                {
                    "text": text,
                    "clean": clean,
                    "segment_id": segment_key(segment),
                    "segment_start": segment.get("start"),
                    "segment_end": segment.get("end"),
                    "start": word.get("start"),
                    "end": word.get("end"),
                    "index": index,
                }
            )
    return rows


def summarize_counter(counter, limit=8):
    return [
        {"text": text, "count": count}
        for text, count in counter.most_common(limit)
    ]


def build_filler_report(transcript_segments, duration_s):
    rows = transcript_word_rows(transcript_segments)
    filler_occurrences = []
    repeated_occurrences = []
    filler_counts = Counter()
    repeated_counts = Counter()

    for index, row in enumerate(rows):
        if row["clean"] in FILLER_WORDS:
            filler_counts[row["clean"]] += 1
            filler_occurrences.append({**row, "kind": "filler", "word_count": 1})

        if index + 1 < len(rows):
            phrase = (row["clean"], rows[index + 1]["clean"])
            if phrase in FILLER_PHRASES:
                phrase_text = " ".join(phrase)
                filler_counts[phrase_text] += 1
                filler_occurrences.append(
                    {
                        **row,
                        "text": phrase_text,
                        "end": rows[index + 1].get("end"),
                        "kind": "filler",
                        "word_count": 2,
                    }
                )

        if index > 0 and row["clean"] == rows[index - 1]["clean"]:
            repeated_counts[row["clean"]] += 1
            repeated_occurrences.append({**row, "kind": "repeat", "word_count": 1})

        if index > 2:
            previous_phrase = (rows[index - 3]["clean"], rows[index - 2]["clean"])
            current_phrase = (rows[index - 1]["clean"], row["clean"])
            if previous_phrase == current_phrase:
                phrase_text = " ".join(current_phrase)
                repeated_counts[phrase_text] += 1
                repeated_occurrences.append(
                    {
                        **rows[index - 1],
                        "text": phrase_text,
                        "end": row.get("end"),
                        "kind": "repeat",
                        "word_count": 2,
                    }
                )

    filler_count = sum(filler_counts.values())
    repeated_count = sum(repeated_counts.values())
    total_count = filler_count + repeated_count
    minutes = max(duration_s / 60, 0.01)

    return {
        "total_count": total_count,
        "filler_count": filler_count,
        "repeated_count": repeated_count,
        "per_minute": round(total_count / minutes, 1),
        "filler_words": summarize_counter(filler_counts),
        "repeated_words": summarize_counter(repeated_counts),
        "occurrences": {
            "fillers": filler_occurrences[:30],
            "repeats": repeated_occurrences[:30],
        },
    }


def dashboard_asset_path(asset_path, web_output_path):
    if not asset_path:
        return None

    if not web_output_path:
        return str(asset_path).replace("\\", "/")

    try:
        relative_path = os.path.relpath(
            Path(asset_path).resolve(),
            start=Path(web_output_path).parent.resolve(),
        )
        return Path(relative_path).as_posix()
    except ValueError:
        return str(asset_path).replace("\\", "/")


def build_dashboard_summary(segments, eye_report):
    summary = build_summary(segments)
    if not eye_report:
        return summary

    zones = eye_report.get("zone_percentages", {})
    if zones:
        zone_name, pct = max(zones.items(), key=lambda item: item[1])
        eye_value = f"{pct:.1f}%"
        eye_note = f"Mostly {zone_name.lower()}"
    else:
        eye_value = str(eye_report.get("valid_sample_count", 0))
        eye_note = "Valid gaze samples"

    for item in summary:
        if item["label"] == "Eye Contact":
            item["value"] = eye_value
            item["note"] = eye_note
            break

    return summary


def dashboard_eye_images(eye_report, eye_image, web_output_path):
    images = {}
    if eye_report:
        for key, value in eye_report.get("images", {}).items():
            images[key] = dashboard_asset_path(Path(value), web_output_path)

    if eye_image and "heatmap" not in images:
        images["heatmap"] = dashboard_asset_path(eye_image, web_output_path)

    return images


def build_review_from_split_csv(
    hand_csv,
    ppg_csv,
    voice_csv,
    eye_csv,
    transcript_path,
    output_path,
    web_output_path,
    baseline_seconds,
    window_seconds,
    confidence_threshold,
    ppg_spike_threshold,
    ppg_variability_threshold,
    audio_path,
    fast_wpm,
    slow_wpm,
    min_pitch_std_hz,
    min_volume_std_db,
    eye_image,
    eye_report=None,
):
    hand_rows = read_rows(hand_csv)
    ppg_rows = read_rows(ppg_csv)
    voice = voice_metadata(voice_csv)
    start_ns = (
        voice["first_timestamp_ns"]
        if voice and voice["first_timestamp_ns"] is not None
        else detect_global_start_ns(hand_rows, ppg_rows)
    )
    hand_samples = build_hand_samples(hand_rows, start_ns, confidence_threshold)
    ppg_samples = build_ppg_samples(ppg_rows, start_ns)
    eye_samples = read_eye_samples(eye_csv, start_ns) if eye_csv else []
    duration_s = max(
        [sample["time_s"] for sample in hand_samples + ppg_samples],
        default=0.0,
    )
    if voice:
        duration_s = max(duration_s, voice["duration_s"])

    transcript_segments = load_transcript(transcript_path) or auto_segments(
        duration_s,
        window_seconds,
    )
    filler_report = build_filler_report(transcript_segments, duration_s)
    baseline_stats = ppg_baseline_stats(ppg_samples, baseline_seconds)
    vocal_issues_by_segment = analyze_vocal_features(
        transcript_segments,
        audio_path,
        fast_wpm=fast_wpm,
        slow_wpm=slow_wpm,
        min_pitch_std_hz=min_pitch_std_hz,
        min_volume_std_db=min_volume_std_db,
    )

    segments = [
        analyze_segment(
            segment,
            hand_samples,
            ppg_samples,
            baseline_stats["mean"],
            baseline_stats["std"],
            ppg_spike_threshold,
            ppg_variability_threshold,
            [
                *vocal_issues_by_segment.get(segment_key(segment), []),
            ],
        )
        for segment in transcript_segments
    ]

    eye_images = dashboard_eye_images(eye_report, eye_image, web_output_path)

    review_data = {
        "metadata": {
            "source": "split_csv_features",
            "hand_csv": str(hand_csv),
            "ppg_csv": str(ppg_csv),
            "voice_csv": str(voice_csv) if voice_csv else None,
            "eye_csv": str(eye_csv) if eye_csv else None,
            "transcript_file": str(transcript_path) if transcript_path else None,
            "hand_sample_count": len(hand_samples),
            "ppg_sample_count": len(ppg_samples),
            "eye_sample_count": len(eye_samples),
            "voice_sample_count": voice["sample_count"] if voice else None,
            "voice_row_count": voice["row_count"] if voice else None,
            "duration_s": round(duration_s, 2),
            "voice_duration_s": round(voice["duration_s"], 2) if voice else None,
            "baseline_seconds": baseline_seconds,
            "confidence_threshold": confidence_threshold,
            "ppg_spike_threshold": ppg_spike_threshold,
            "ppg_variability_threshold": ppg_variability_threshold,
            "audio_file": str(audio_path) if audio_path else None,
            "fast_wpm_threshold": fast_wpm,
            "slow_wpm_threshold": slow_wpm,
            "min_pitch_std_hz": min_pitch_std_hz,
            "min_volume_std_db": min_volume_std_db,
            "eye_tracking_image": eye_images.get("heatmap"),
            "eye_tracking_images": eye_images,
            "eye_tracking_report": eye_report,
            "filler_report": filler_report,
        },
        "summary": build_dashboard_summary(segments, eye_report),
        "segments": segments,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(review_data, indent=2), encoding="utf-8")
    print(f"Wrote review data to {output_path}")

    if web_output_path:
        web_output_path.parent.mkdir(parents=True, exist_ok=True)
        web_output_path.write_text(
            "window.generatedReviewData = "
            + json.dumps(review_data, indent=2)
            + ";\n",
            encoding="utf-8",
        )
        print(f"Wrote dashboard data to {web_output_path}")


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--hand-csv", type=Path, required=True)
    parser.add_argument("--ppg-csv", type=Path, required=True)
    parser.add_argument("--voice-csv", type=Path, default=None)
    parser.add_argument("--eye-csv", type=Path, default=None)
    parser.add_argument("--transcript", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=Path("data/processed/review_data.json"))
    parser.add_argument("--web-output", type=Path, default=Path("gesture_review/review_data.generated.js"))
    parser.add_argument("--baseline-seconds", type=int, default=10)
    parser.add_argument("--window-seconds", type=int, default=10)
    parser.add_argument("--confidence-threshold", type=float, default=0.5)
    parser.add_argument("--ppg-spike-threshold", type=float, default=PPG_SPIKE_THRESHOLD)
    parser.add_argument("--ppg-variability-threshold", type=float, default=None)
    parser.add_argument("--audio", type=Path, default=None)
    parser.add_argument("--fast-wpm", type=float, default=175)
    parser.add_argument("--slow-wpm", type=float, default=95)
    parser.add_argument("--min-pitch-std-hz", type=float, default=18)
    parser.add_argument("--min-volume-std-db", type=float, default=3.0)
    parser.add_argument("--eye-image", type=Path, default=None)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    build_review_from_split_csv(
        args.hand_csv,
        args.ppg_csv,
        args.voice_csv,
        args.eye_csv,
        args.transcript,
        args.output,
        args.web_output,
        args.baseline_seconds,
        args.window_seconds,
        args.confidence_threshold,
        args.ppg_spike_threshold,
        args.ppg_variability_threshold,
        args.audio,
        args.fast_wpm,
        args.slow_wpm,
        args.min_pitch_std_hz,
        args.min_volume_std_db,
        args.eye_image,
        None,
    )
