"""
Build gesture_review UI JSON from captured Aria SDK events.

Input:
- Events JSON from capture_sdk_events.py
- Transcript JSON containing timed transcript segments

Output:
- review_data JSON that can be loaded with the "Load SDK JSON" button
"""

import argparse
import json
import math
from pathlib import Path


STATIC_REGION_MIN_SECONDS = 10
STATIC_REGION_SPREAD_METERS = 0.08
LOW_GESTURE_MOVEMENT_METERS = 0.08
PPG_SPIKE_THRESHOLD = 5000.0


def parse_time(value):
    if isinstance(value, (int, float)):
        return float(value)

    minutes, seconds = value.split(":")
    return int(minutes) * 60 + float(seconds)


def format_time(seconds):
    minutes = int(seconds // 60)
    remaining = int(round(seconds % 60))
    return f"{minutes:02d}:{remaining:02d}"


def segment_text(segment):
    if "text" in segment:
        return segment["text"]

    return "".join(part.get("text", "") for part in segment.get("parts", []))


def samples_in_window(samples, start_s, end_s):
    return [sample for sample in samples if start_s <= sample["time_s"] <= end_s]


def average(values):
    values = list(values)
    if not values:
        return 0.0
    return sum(values) / len(values)


def standard_deviation(values):
    values = list(values)
    if len(values) < 2:
        return 0.0

    mean = average(values)
    return math.sqrt(average((value - mean) ** 2 for value in values))


def distance(a, b):
    if a is None or b is None:
        return 0.0
    return math.sqrt(sum((a[index] - b[index]) ** 2 for index in range(3)))


def hand_visibility_ratio(samples):
    if not samples:
        return 0.0

    visible = sum(1 for sample in samples if sample["left_visible"] or sample["right_visible"])
    return visible / len(samples)


def hand_movement(samples):
    return path_movement(hand_centers(samples))


def hand_centers(samples):
    centers = []
    for sample in samples:
        positions = []
        for side in ("left", "right"):
            hand = sample.get(side)
            if hand and hand.get("palm_position_device"):
                positions.append(hand["palm_position_device"])

        if positions:
            centers.append(
                [
                    average(position[axis] for position in positions)
                    for axis in range(3)
                ]
            )

    return centers


def path_movement(positions):
    if len(positions) < 2:
        return 0.0

    movement = 0.0
    for index in range(1, len(positions)):
        movement += distance(positions[index - 1], positions[index])
    return movement


def position_spread(positions):
    if len(positions) < 2:
        return 0.0

    center = [
        average(position[axis] for position in positions)
        for axis in range(3)
    ]
    return max(distance(position, center) for position in positions)


def ppg_baseline(ppg_samples, baseline_seconds):
    baseline = [
        sample["value"]
        for sample in ppg_samples
        if sample["time_s"] <= baseline_seconds
    ]
    return average(baseline)


def ppg_baseline_stats(ppg_samples, baseline_seconds):
    baseline = [
        sample["value"]
        for sample in ppg_samples
        if sample["time_s"] <= baseline_seconds
    ]
    return {
        "mean": average(baseline),
        "std": standard_deviation(baseline),
    }


def segment_words(segment):
    words = []
    for word in segment.get("words", []):
        text = word.get("text") or word.get("word")
        if not text:
            continue

        words.append(
            {
                "text": text,
                "start": parse_time(word["start"]),
                "end": parse_time(word["end"]),
            }
        )

    if words:
        return words

    text = segment_text(segment)
    raw_words = text.split()
    if not raw_words:
        return []

    start_s = parse_time(segment["start"])
    end_s = parse_time(segment["end"])
    duration_s = max(0.1, end_s - start_s)
    total_units = sum(len(word) for word in raw_words) + max(0, len(raw_words) - 1)
    cursor_units = 0

    for raw_word in raw_words:
        word_units = len(raw_word)
        word_start = start_s + (cursor_units / total_units) * duration_s
        word_end = start_s + ((cursor_units + word_units) / total_units) * duration_s
        words.append(
            {
                "text": raw_word,
                "start": word_start,
                "end": word_end,
            }
        )
        cursor_units += word_units + 1

    return words


def join_words(words):
    return " ".join(word["text"] for word in words)


def window_around(time_s, start_s, end_s, radius_s=0.9):
    return {
        "highlight_start_s": round(max(start_s, time_s - radius_s), 3),
        "highlight_end_s": round(min(end_s, time_s + radius_s), 3),
        "event_time_s": round(time_s, 3),
    }


def best_run(samples, predicate):
    best = None
    current = None

    for sample in samples:
        if predicate(sample):
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


def representative_visible_time(samples):
    run = best_run(samples, lambda sample: sample["left_visible"] or sample["right_visible"])
    if not run:
        return None
    return average(run)


def representative_hidden_window(samples, start_s, end_s):
    run = best_run(
        samples,
        lambda sample: not (sample["left_visible"] or sample["right_visible"]),
    )
    if not run:
        return window_around(average([start_s, end_s]), start_s, end_s)

    return {
        "highlight_start_s": round(max(start_s, run[0]), 3),
        "highlight_end_s": round(min(end_s, run[1]), 3),
        "event_time_s": round(average(run), 3),
    }


def issue_priority(issue):
    priority = {
        "stress": 0,
        "gesture": 1,
        "eye": 2,
        "voice": 3,
        "good": 4,
    }
    return (
        priority.get(issue["type"], 99),
        issue.get("event_time_s", issue.get("highlight_start_s", 0)),
    )


def word_span_for_issue(words, issue, used_indices):
    if not words:
        return None

    start_s = issue.get("highlight_start_s", issue.get("event_time_s"))
    end_s = issue.get("highlight_end_s", issue.get("event_time_s"))
    event_time_s = issue.get("event_time_s", average([start_s, end_s]))

    indices = []
    if start_s is not None and end_s is not None:
        for index, word in enumerate(words):
            midpoint = average([word["start"], word["end"]])
            if start_s <= midpoint <= end_s and index not in used_indices:
                indices.append(index)

    if not indices:
        available = [
            index
            for index in range(len(words))
            if index not in used_indices
        ]
        if not available:
            return None

        nearest = min(
            available,
            key=lambda index: abs(
                average([words[index]["start"], words[index]["end"]]) - event_time_s
            ),
        )
        indices = [nearest]

    first = min(indices)
    last = max(indices)
    while last - first + 1 < 3:
        expanded = False
        if first > 0 and first - 1 not in used_indices:
            first -= 1
            expanded = True
        if last - first + 1 >= 3:
            break
        if last < len(words) - 1 and last + 1 not in used_indices:
            last += 1
            expanded = True
        if not expanded:
            break

    return first, last


def build_word_level_parts(words, issues):
    ordered_issues = sorted(issues, key=issue_priority)
    spans = []
    used_indices = set()
    badges = []

    for issue in ordered_issues:
        span = word_span_for_issue(words, issue, used_indices)
        if span is None:
            badges.append({**issue, "text": issue["label"]})
            continue

        first, last = span
        for index in range(first, last + 1):
            used_indices.add(index)
        spans.append((first, last, issue))

    spans.sort(key=lambda item: item[0])
    parts = []
    cursor = 0
    for first, last, issue in spans:
        if cursor < first:
            parts.append({"text": join_words(words[cursor:first]) + " "})

        highlighted_text = join_words(words[first : last + 1])
        parts.append({**issue, "text": highlighted_text})
        cursor = last + 1

    if cursor < len(words):
        parts.append({"text": join_words(words[cursor:])})

    return [part for part in parts if part["text"]] + badges


def build_segment_parts(text, issues, words=None):
    if not issues:
        if words:
            return [{"text": join_words(words)}]
        return [{"text": text}]

    if words:
        return build_word_level_parts(words, issues)

    ordered_issues = sorted(issues, key=issue_priority)
    primary_issue = {**ordered_issues[0], "text": text}

    badges = []
    for issue in ordered_issues[1:]:
        badges.append({**issue, "text": issue["label"]})

    return [primary_issue, *badges]


def analyze_segment(
    segment,
    hand_samples,
    ppg_samples,
    baseline_ppg,
    baseline_ppg_std=0.0,
    ppg_spike_threshold=PPG_SPIKE_THRESHOLD,
    ppg_variability_threshold=None,
    vocal_issues=None,
):
    start_s = parse_time(segment["start"])
    end_s = parse_time(segment["end"])
    text = segment_text(segment)
    words = segment_words(segment)

    hands = samples_in_window(hand_samples, start_s, end_s)
    ppg = samples_in_window(ppg_samples, start_s, end_s)
    visibility = hand_visibility_ratio(hands)
    centers = hand_centers(hands)
    movement = hand_movement(hands)
    spread = position_spread(centers)
    avg_ppg = average(sample["value"] for sample in ppg)
    ppg_std = standard_deviation(sample["value"] for sample in ppg)
    max_ppg_sample = max(ppg, key=lambda sample: sample["value"], default=None)
    max_ppg = max_ppg_sample["value"] if max_ppg_sample else 0.0
    ppg_spike = max_ppg - baseline_ppg if ppg and baseline_ppg else 0.0
    duration_s = end_s - start_s

    issues = []
    if vocal_issues:
        issues.extend(vocal_issues)

    if ppg and baseline_ppg:
        level_signal = ppg_spike >= ppg_spike_threshold
        variability_signal = (
            ppg_variability_threshold is not None
            and ppg_std >= ppg_variability_threshold
        )
        if level_signal or variability_signal:
            evidence_parts = []
            if level_signal:
                evidence_parts.append(
                    f"The PPG signal rose {ppg_spike:.1f} above the baseline"
                )
            if variability_signal:
                evidence_parts.append(
                    f"PPG signal variability was high in this section (std {ppg_std:.1f})"
                )

            issues.append(
                {
                    **window_around(max_ppg_sample["time_s"], start_s, end_s),
                    "text": text,
                    "type": "stress",
                    "title": "Increased heart rate",
                    "label": "Increased heart rate",
                    "evidence": "; ".join(evidence_parts) + ".",
                    "meaning": "This can indicate elevated arousal or nervousness, but it should not be treated as a definite emotion.",
                    "suggestion": "Try one short pause and a slower first phrase when reaching this point next time.",
                }
            )

    if hands and visibility < 0.35:
        issues.append(
            {
                **representative_hidden_window(hands, start_s, end_s),
                "text": text,
                "type": "gesture",
                "title": "Hands out of view",
                "label": "Gesture improvement",
                "evidence": f"Hands were visible in only {visibility:.0%} of Aria hand tracking samples.",
                "meaning": "Your gestures may have been too low, too wide, or outside the camera field of view.",
                "suggestion": "Keep gestures closer to chest level during key explanations.",
            }
        )
    elif (
        hands
        and len(centers) >= 2
        and visibility >= 0.65
        and duration_s >= STATIC_REGION_MIN_SECONDS
        and spread <= STATIC_REGION_SPREAD_METERS
    ):
        event_time_s = average([start_s, end_s])
        issues.append(
            {
                **window_around(event_time_s, start_s, end_s, radius_s=1.2),
                "text": text,
                "type": "gesture",
                "title": "Hands stayed in one area",
                "label": "Gesture improvement",
                "evidence": f"Hand position stayed within about {spread:.2f} m of the same region for this section.",
                "meaning": "Your hands were visible, but the gesture range may have felt too fixed or held.",
                "suggestion": "Use one purposeful gesture change when moving to a new idea, such as opening your hands or shifting slightly upward.",
            }
        )
    elif hands and movement < LOW_GESTURE_MOVEMENT_METERS and duration_s >= 8:
        event_time_s = average([start_s, end_s])
        issues.append(
            {
                **window_around(event_time_s, start_s, end_s, radius_s=1.2),
                "text": text,
                "type": "gesture",
                "title": "Low gesture activity",
                "label": "Gesture improvement",
                "evidence": "Hand tracking showed very little movement of the hand region during this section.",
                "meaning": "This part may feel less expressive to the audience.",
                "suggestion": "Use one small open-hand gesture to support the main idea.",
            }
        )
    elif hands and visibility >= 0.65:
        event_time_s = representative_visible_time(hands) or average([start_s, end_s])
        issues.append(
            {
                **window_around(event_time_s, start_s, end_s),
                "text": text,
                "type": "good",
                "title": "Good gesture support",
                "label": "Good moment",
                "evidence": f"Hands were visible in {visibility:.0%} of Aria hand tracking samples.",
                "meaning": "Your gestures were available to the audience and supported your delivery.",
                "suggestion": "Keep this gesture range for important points.",
            }
        )

    return {
        "id": segment.get("id", f"seg-{int(start_s):03d}"),
        "start": format_time(start_s),
        "end": format_time(end_s),
        "words": words,
        "parts": build_segment_parts(text, issues, words),
    }


def build_summary(segments):
    highlighted = [
        part
        for segment in segments
        for part in segment["parts"]
        if part.get("type")
    ]
    stress_count = sum(1 for part in highlighted if part["type"] == "stress")
    gesture_count = sum(1 for part in highlighted if part["type"] == "gesture")
    eye_count = sum(1 for part in highlighted if part["type"] == "eye")
    voice_count = sum(1 for part in highlighted if part["type"] == "voice")
    good_count = sum(1 for part in highlighted if part["type"] == "good")
    total = max(1, stress_count + gesture_count + good_count)
    gesture_score = round((good_count / total) * 100)

    return [
        {"label": "Gesture Score", "value": f"{gesture_score}%", "note": "Estimated from Aria hand tracking"},
        {"label": "Gesture Issues", "value": str(gesture_count), "note": "Hands or movement sections"},
        {"label": "Eye Contact", "value": str(eye_count), "note": "Gaze and audience coverage"},
        {"label": "Increased Heart Rate", "value": str(stress_count), "note": "Elevated heart-rate moments"},
        {"label": "Vocal Notes", "value": str(voice_count), "note": "Pace or tone variation"},
        {"label": "Good Moments", "value": str(good_count), "note": "Confident delivery signals"},
    ]


def build_review_data(
    events_path,
    transcript_path,
    output_path,
    baseline_seconds,
    ppg_spike_threshold,
    ppg_variability_threshold,
):
    events = json.loads(events_path.read_text(encoding="utf-8"))
    transcript = json.loads(transcript_path.read_text(encoding="utf-8"))
    source_segments = transcript.get("segments", transcript)

    baseline_stats = ppg_baseline_stats(events.get("ppg_samples", []), baseline_seconds)
    segments = [
        analyze_segment(
            segment,
            events.get("hand_samples", []),
            events.get("ppg_samples", []),
            baseline_stats["mean"],
            baseline_stats["std"],
            ppg_spike_threshold,
            ppg_variability_threshold,
            None,
        )
        for segment in source_segments
    ]

    review_data = {
        "metadata": {
            "source": "meta_aria_gen2_sdk",
            "events_file": str(events_path),
            "transcript_file": str(transcript_path),
            "baseline_seconds": baseline_seconds,
            "ppg_spike_threshold": ppg_spike_threshold,
            "ppg_variability_threshold": ppg_variability_threshold,
        },
        "summary": build_summary(segments),
        "segments": segments,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(review_data, indent=2), encoding="utf-8")
    print(f"Wrote review data to {output_path}")


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--events", type=Path, required=True)
    parser.add_argument("--transcript", type=Path, default=Path("gesture_review/review_sample.json"))
    parser.add_argument("--output", type=Path, default=Path("data/processed/review_data.json"))
    parser.add_argument("--baseline-seconds", type=int, default=30)
    parser.add_argument("--ppg-spike-threshold", type=float, default=PPG_SPIKE_THRESHOLD)
    parser.add_argument("--ppg-variability-threshold", type=float, default=None)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    build_review_data(
        args.events,
        args.transcript,
        args.output,
        args.baseline_seconds,
        args.ppg_spike_threshold,
        args.ppg_variability_threshold,
    )
