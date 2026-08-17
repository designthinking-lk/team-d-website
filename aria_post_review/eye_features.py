"""
Post-speech eye tracking feedback.

This turns exported Aria eye tracking CSV rows into transcript-level feedback:
- looking at notes/floor for a large part of a section
- staying fixed on one audience zone for too long
- balanced audience-facing gaze as a positive note
"""

import csv
from collections import Counter
from pathlib import Path

from build_review_data import average, parse_time


def parse_bool(value):
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"true", "1", "yes"}


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


def gaze_zone(row):
    pitch = parse_float(row.get("pitch"))
    yaw = parse_float(row.get("yaw"))
    depth = parse_float(row.get("depth"))
    if pitch is None or yaw is None:
        return None

    pitch_deg = pitch * 57.2958
    yaw_deg = yaw * 57.2958
    if pitch_deg < -15.0 or (depth is not None and depth < 0.8):
        return "Notes/Floor"
    if yaw_deg < -12.0:
        return "Left Audience"
    if yaw_deg > 12.0:
        return "Right Audience"
    return "Center Audience"


def read_eye_samples(eye_csv, start_ns):
    if not eye_csv:
        return []

    samples = []
    with Path(eye_csv).open(newline="", encoding="utf-8-sig") as csv_file:
        reader = csv.DictReader(csv_file)
        for row in reader:
            timestamp = parse_int(row.get("timestamp_ns"))
            if timestamp is None or not parse_bool(row.get("combined_gaze_valid")):
                continue

            zone = gaze_zone(row)
            if not zone:
                continue

            samples.append(
                {
                    "time_s": round((timestamp - start_ns) / 1_000_000_000, 3),
                    "zone": zone,
                }
            )
    return samples


def samples_in_window(samples, start_s, end_s):
    return [sample for sample in samples if start_s <= sample["time_s"] <= end_s]


def ratio(count, total):
    if total == 0:
        return 0.0
    return count / total


def window_around(time_s, start_s, end_s, radius_s=1.0):
    return {
        "highlight_start_s": round(max(start_s, time_s - radius_s), 3),
        "highlight_end_s": round(min(end_s, time_s + radius_s), 3),
        "event_time_s": round(time_s, 3),
    }


def longest_zone_run(samples, target_zone):
    best = None
    current = None
    for sample in samples:
        if sample["zone"] == target_zone:
            if current is None:
                current = [sample["time_s"], sample["time_s"]]
            current[1] = sample["time_s"]
        elif current is not None:
            if best is None or (current[1] - current[0]) > (best[1] - best[0]):
                best = current
            current = None

    if current is not None and (
        best is None or (current[1] - current[0]) > (best[1] - best[0])
    ):
        best = current
    return best


def eye_issue_for_segment(segment, eye_samples):
    start_s = parse_time(segment["start"])
    end_s = parse_time(segment["end"])
    duration_s = end_s - start_s
    samples = samples_in_window(eye_samples, start_s, end_s)
    if len(samples) < 4:
        return []

    counts = Counter(sample["zone"] for sample in samples)
    total = len(samples)
    notes_ratio = ratio(counts["Notes/Floor"], total)
    audience_count = total - counts["Notes/Floor"]
    audience_ratio = ratio(audience_count, total)
    top_zone, top_count = counts.most_common(1)[0]
    top_ratio = ratio(top_count, total)

    issues = []
    if notes_ratio >= 0.35:
        run = longest_zone_run(samples, "Notes/Floor")
        event_time = average(run) if run else average([start_s, end_s])
        issues.append(
            {
                **window_around(event_time, start_s, end_s, radius_s=1.2),
                "type": "eye",
                "title": "Looking down too often",
                "label": "Eye contact",
                "evidence": f"Gaze was in the notes/floor zone for {notes_ratio:.0%} of this section.",
                "meaning": "The audience may feel less directly addressed during this part.",
                "suggestion": "Glance down briefly, then return your gaze to the audience before the next key phrase.",
            }
        )
    elif duration_s >= 8 and top_zone != "Notes/Floor" and top_ratio >= 0.85:
        event_time = average([start_s, end_s])
        issues.append(
            {
                **window_around(event_time, start_s, end_s, radius_s=1.2),
                "type": "eye",
                "title": "Gaze stayed in one audience zone",
                "label": "Eye contact",
                "evidence": f"Gaze stayed on {top_zone.lower()} for {top_ratio:.0%} of this section.",
                "meaning": "This can make the room feel less evenly included.",
                "suggestion": "Sweep your gaze once toward another side of the audience when moving to the next idea.",
            }
        )
    elif duration_s >= 5 and audience_ratio >= 0.75:
        event_time = average([sample["time_s"] for sample in samples if sample["zone"] != "Notes/Floor"])
        issues.append(
            {
                **window_around(event_time, start_s, end_s, radius_s=0.9),
                "type": "eye",
                "title": "Good audience-facing gaze",
                "label": "Eye contact",
                "evidence": f"Gaze was audience-facing for {audience_ratio:.0%} of this section.",
                "meaning": "This supports connection with the audience while speaking.",
                "suggestion": "Keep this pattern for important explanations.",
            }
        )

    return issues


def analyze_eye_features(transcript_segments, eye_samples):
    if not eye_samples:
        return {}

    issues_by_segment = {}
    for segment in transcript_segments:
        issues = eye_issue_for_segment(segment, eye_samples)
        if issues:
            key = segment.get("id", f"seg-{int(parse_time(segment['start'])):03d}")
            issues_by_segment[key] = issues
    return issues_by_segment
