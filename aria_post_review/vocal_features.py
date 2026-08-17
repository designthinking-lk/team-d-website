"""
Post-speech vocal delivery analysis.

The goal is not clinical emotion detection. These features give practical
public-speaking feedback:
- pace: words per minute from transcript timing
- tone variation: pitch and volume variation from the WAV signal
"""

import math
import wave
from pathlib import Path

import numpy as np


def parse_time(value):
    if isinstance(value, (int, float)):
        return float(value)

    minutes, seconds = value.split(":")
    return int(minutes) * 60 + float(seconds)


def segment_text(segment):
    return segment.get("text", "")


def segment_word_count(segment):
    return len(segment_text(segment).split())


def midpoint(start_s, end_s):
    return (start_s + end_s) / 2


def window_around(time_s, start_s, end_s, radius_s=1.0):
    return {
        "highlight_start_s": round(max(start_s, time_s - radius_s), 3),
        "highlight_end_s": round(min(end_s, time_s + radius_s), 3),
        "event_time_s": round(time_s, 3),
    }


def read_wav_mono(audio_path):
    audio_path = Path(audio_path)
    with wave.open(str(audio_path), "rb") as wav_file:
        channels = wav_file.getnchannels()
        sample_rate = wav_file.getframerate()
        sample_width = wav_file.getsampwidth()
        frames = wav_file.readframes(wav_file.getnframes())

    if sample_width != 2:
        raise ValueError("Only 16-bit PCM WAV files are supported for vocal analysis.")

    samples = np.frombuffer(frames, dtype=np.int16).astype(np.float32)
    if channels > 1:
        samples = samples.reshape(-1, channels).mean(axis=1)

    samples = samples / 32768.0
    return sample_rate, samples


def estimate_pitch_hz(frame, sample_rate):
    frame = frame - np.mean(frame)
    energy = np.sqrt(np.mean(frame * frame))
    if energy < 0.01:
        return None

    min_lag = int(sample_rate / 350)
    max_lag = int(sample_rate / 80)
    if len(frame) <= max_lag:
        return None

    corr = np.correlate(frame, frame, mode="full")[len(frame) - 1 :]
    if corr[0] <= 0:
        return None

    search = corr[min_lag:max_lag]
    if len(search) == 0:
        return None

    lag = int(np.argmax(search) + min_lag)
    confidence = corr[lag] / corr[0]
    if confidence < 0.28:
        return None

    return sample_rate / lag


def audio_stats_for_window(sample_rate, samples, start_s, end_s):
    start_index = max(0, int(start_s * sample_rate))
    end_index = min(len(samples), int(end_s * sample_rate))
    segment = samples[start_index:end_index]
    if len(segment) == 0:
        return {
            "pitch_mean_hz": 0.0,
            "pitch_std_hz": 0.0,
            "volume_std_db": 0.0,
            "voiced_frame_count": 0,
        }

    frame_size = max(1, int(sample_rate * 0.04))
    hop_size = max(1, int(sample_rate * 0.02))
    pitches = []
    volumes_db = []

    for start in range(0, max(1, len(segment) - frame_size + 1), hop_size):
        frame = segment[start : start + frame_size]
        if len(frame) < frame_size:
            break

        rms = float(np.sqrt(np.mean(frame * frame)))
        if rms < 0.005:
            continue

        volumes_db.append(20 * math.log10(rms + 1e-8))
        pitch = estimate_pitch_hz(frame, sample_rate)
        if pitch is not None:
            pitches.append(pitch)

    return {
        "pitch_mean_hz": round(float(np.mean(pitches)), 1) if pitches else 0.0,
        "pitch_std_hz": round(float(np.std(pitches)), 1) if len(pitches) >= 2 else 0.0,
        "volume_std_db": round(float(np.std(volumes_db)), 1) if len(volumes_db) >= 2 else 0.0,
        "voiced_frame_count": len(pitches),
    }


def pace_issue(segment, start_s, end_s, fast_wpm, slow_wpm):
    duration_s = max(0.1, end_s - start_s)
    words = segment_word_count(segment)
    wpm = (words / duration_s) * 60

    if words < 4:
        return None

    event = midpoint(start_s, end_s)
    if wpm > fast_wpm:
        return {
            **window_around(event, start_s, end_s, radius_s=1.2),
            "type": "voice",
            "title": "Speaking pace was fast",
            "label": "Vocal delivery",
            "evidence": f"This section was about {wpm:.0f} words per minute.",
            "meaning": "A fast pace can make details harder for the audience to absorb.",
            "suggestion": "Add a short pause after the key phrase and slow the next sentence slightly.",
        }

    if wpm < slow_wpm:
        return {
            **window_around(event, start_s, end_s, radius_s=1.2),
            "type": "voice",
            "title": "Speaking pace was slow",
            "label": "Vocal delivery",
            "evidence": f"This section was about {wpm:.0f} words per minute.",
            "meaning": "A very slow pace can reduce energy unless it is used intentionally for emphasis.",
            "suggestion": "Keep the pause, but connect the next few words with a little more momentum.",
        }

    return None


def tone_issue(segment, start_s, end_s, audio_stats, min_pitch_std_hz, min_volume_std_db):
    duration_s = end_s - start_s
    if duration_s < 5 or audio_stats["voiced_frame_count"] < 8:
        return None

    flat_pitch = audio_stats["pitch_std_hz"] and audio_stats["pitch_std_hz"] < min_pitch_std_hz
    flat_volume = audio_stats["volume_std_db"] < min_volume_std_db
    if not (flat_pitch and flat_volume):
        return None

    event = midpoint(start_s, end_s)
    return {
        **window_around(event, start_s, end_s, radius_s=1.4),
        "type": "voice",
        "title": "Tone sounded flat",
        "label": "Vocal delivery",
        "evidence": (
            f"Pitch variation was about {audio_stats['pitch_std_hz']:.1f} Hz and "
            f"volume variation was about {audio_stats['volume_std_db']:.1f} dB."
        ),
        "meaning": "Limited pitch and volume variation can make a section sound less expressive.",
        "suggestion": "Emphasize one important word with a slightly higher pitch or stronger volume.",
    }


def analyze_vocal_features(
    transcript_segments,
    audio_path,
    fast_wpm=175,
    slow_wpm=95,
    min_pitch_std_hz=18,
    min_volume_std_db=3.0,
):
    if not audio_path:
        return {}

    sample_rate, samples = read_wav_mono(audio_path)
    issues_by_segment = {}

    for segment in transcript_segments:
        start_s = parse_time(segment["start"])
        end_s = parse_time(segment["end"])
        issues = []

        pace = pace_issue(segment, start_s, end_s, fast_wpm, slow_wpm)
        if pace:
            issues.append(pace)

        stats = audio_stats_for_window(sample_rate, samples, start_s, end_s)
        tone = tone_issue(
            segment,
            start_s,
            end_s,
            stats,
            min_pitch_std_hz,
            min_volume_std_db,
        )
        if tone:
            issues.append(tone)

        if issues:
            issues_by_segment[segment.get("id", f"seg-{int(start_s):03d}")] = issues

    return issues_by_segment
