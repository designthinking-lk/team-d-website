"""
Build gesture_review UI JSON from a CSV exported from processed VRS data.

The CSV can be frame/sample-level data with one row per timestamp. The parser is
intentionally flexible so it can work with different extraction pipelines.

Supported common columns:
- time_s, timestamp_s, seconds, sec, time, t
- ppg, ppg_value, ppg_raw, heart_rate, hr, bpm
- left_visible, right_visible, hands_visible, hand_visible
- left_palm_x/y/z, right_palm_x/y/z, palm_x/y/z, hand_x/y/z
"""

import argparse
import csv
import json
from pathlib import Path

from build_review_data import (
    analyze_segment,
    build_summary,
    ppg_baseline,
)


TIME_COLUMNS = ("time_s", "timestamp_s", "seconds", "sec", "time", "t")
PPG_COLUMNS = ("ppg", "ppg_value", "ppg_raw", "ppg_signal", "ppg_mean")
HR_COLUMNS = ("heart_rate", "hr", "bpm", "heart_rate_bpm")
LEFT_VISIBLE_COLUMNS = ("left_visible", "left_hand_visible", "left_detected")
RIGHT_VISIBLE_COLUMNS = ("right_visible", "right_hand_visible", "right_detected")
HANDS_VISIBLE_COLUMNS = ("hands_visible", "hand_visible", "any_hand_visible")
HAND_COUNT_COLUMNS = ("hand_count", "num_hands", "hands_detected")


def clean_key(key):
    return key.strip().lower().replace(" ", "_").replace("-", "_")


def clean_row(row):
    return {clean_key(key): (value or "").strip() for key, value in row.items() if key}


def first_value(row, names):
    for name in names:
        value = row.get(name)
        if value not in (None, ""):
            return value
    return None


def parse_float(value, default=None):
    if value in (None, ""):
        return default
    try:
        return float(value)
    except ValueError:
        return default


def parse_bool(value):
    if value is None:
        return None

    normalized = str(value).strip().lower()
    if normalized in ("1", "true", "yes", "y", "detected", "visible"):
        return True
    if normalized in ("0", "false", "no", "n", "none", "missing", "not_detected"):
        return False
    return None


def parse_time(value):
    if value is None:
        return None

    if ":" not in value:
        return parse_float(value)

    parts = [float(part) for part in value.split(":")]
    if len(parts) == 2:
        minutes, seconds = parts
        return minutes * 60 + seconds
    if len(parts) == 3:
        hours, minutes, seconds = parts
        return hours * 3600 + minutes * 60 + seconds
    return None


def parse_position(row, prefix):
    x = parse_float(row.get(f"{prefix}_x"))
    y = parse_float(row.get(f"{prefix}_y"))
    z = parse_float(row.get(f"{prefix}_z"))
    if x is None or y is None or z is None:
        return None
    return [x, y, z]


def parse_hand(row, side):
    palm = (
        parse_position(row, f"{side}_palm")
        or parse_position(row, f"{side}_hand")
        or parse_position(row, side)
    )
    wrist = parse_position(row, f"{side}_wrist")
    confidence = parse_float(
        row.get(f"{side}_confidence") or row.get(f"{side}_hand_confidence"),
        default=1.0,
    )

    if palm is None and wrist is None:
        return None

    return {
        "confidence": confidence,
        "wrist_position_device": wrist,
        "palm_position_device": palm,
    }


def infer_visibility(row, side):
    if side == "left":
        side_visible = parse_bool(first_value(row, LEFT_VISIBLE_COLUMNS))
    else:
        side_visible = parse_bool(first_value(row, RIGHT_VISIBLE_COLUMNS))

    if side_visible is not None:
        return side_visible

    hands_visible = parse_bool(first_value(row, HANDS_VISIBLE_COLUMNS))
    if hands_visible is not None:
        return hands_visible

    hand_count = parse_float(first_value(row, HAND_COUNT_COLUMNS))
    if hand_count is not None:
        return hand_count > 0

    return parse_hand(row, side) is not None


def csv_to_events(csv_path, ppg_column=None, time_column=None):
    hand_samples = []
    ppg_samples = []

    with csv_path.open(newline="", encoding="utf-8-sig") as csv_file:
        reader = csv.DictReader(csv_file)
        if not reader.fieldnames:
            raise ValueError("CSV file does not have a header row.")

        for raw_row in reader:
            row = clean_row(raw_row)
            time_value = row.get(clean_key(time_column)) if time_column else first_value(row, TIME_COLUMNS)
            time_s = parse_time(time_value)
            if time_s is None:
                continue

            ppg_value = parse_float(row.get(clean_key(ppg_column))) if ppg_column else None
            ppg_value = ppg_value if ppg_value is not None else parse_float(first_value(row, PPG_COLUMNS))
            heart_rate = parse_float(first_value(row, HR_COLUMNS))
            if ppg_value is None and heart_rate is not None:
                ppg_value = heart_rate

            if ppg_value is not None:
                ppg_samples.append({"time_s": round(time_s, 3), "value": ppg_value})

            left = parse_hand(row, "left")
            right = parse_hand(row, "right")
            generic_hand = parse_position(row, "palm") or parse_position(row, "hand")
            if left is None and right is None and generic_hand is not None:
                right = {
                    "confidence": parse_float(row.get("confidence") or row.get("hand_confidence"), default=1.0),
                    "wrist_position_device": None,
                    "palm_position_device": generic_hand,
                }

            left_visible = infer_visibility(row, "left")
            right_visible = infer_visibility(row, "right")
            if left or right or left_visible or right_visible:
                hand_samples.append(
                    {
                        "time_s": round(time_s, 3),
                        "left_visible": bool(left_visible),
                        "right_visible": bool(right_visible),
                        "left": left,
                        "right": right,
                    }
                )

    return {
        "metadata": {
            "source": "csv_features",
            "csv_file": str(csv_path),
            "hand_sample_count": len(hand_samples),
            "ppg_sample_count": len(ppg_samples),
        },
        "hand_samples": hand_samples,
        "ppg_samples": ppg_samples,
    }


def load_transcript(transcript_path):
    transcript = json.loads(transcript_path.read_text(encoding="utf-8"))
    return transcript.get("segments", transcript)


def build_review_from_csv(csv_path, transcript_path, output_path, baseline_seconds, ppg_column, time_column):
    events = csv_to_events(csv_path, ppg_column=ppg_column, time_column=time_column)
    transcript_segments = load_transcript(transcript_path)
    baseline = ppg_baseline(events["ppg_samples"], baseline_seconds)

    segments = [
        analyze_segment(
            segment,
            events["hand_samples"],
            events["ppg_samples"],
            baseline,
        )
        for segment in transcript_segments
    ]

    review_data = {
        "metadata": {
            **events["metadata"],
            "transcript_file": str(transcript_path),
            "baseline_seconds": baseline_seconds,
        },
        "summary": build_summary(segments),
        "segments": segments,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(review_data, indent=2), encoding="utf-8")
    print(f"Wrote review data to {output_path}")


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", type=Path, required=True, help="Processed VRS feature CSV.")
    parser.add_argument("--transcript", type=Path, default=Path("gesture_review/review_sample.json"))
    parser.add_argument("--output", type=Path, default=Path("data/processed/review_data.json"))
    parser.add_argument("--baseline-seconds", type=int, default=30)
    parser.add_argument("--ppg-column", default=None, help="Override the PPG/heart-rate column name.")
    parser.add_argument("--time-column", default=None, help="Override the timestamp column name.")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    build_review_from_csv(
        args.csv,
        args.transcript,
        args.output,
        args.baseline_seconds,
        args.ppg_column,
        args.time_column,
    )
