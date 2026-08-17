"""
Convert an Aria voice CSV export into a WAV file.

The current voice.csv export contains:
- timestamp_ns
- num_samples
- audio_samples, a Python/JSON-like list of signed audio sample values

This script does not transcribe speech. It reconstructs the audio so a
speech-to-text tool can create the timestamped transcript JSON used by the
dashboard.
"""

import argparse
import ast
import csv
import wave
from array import array
from pathlib import Path


def parse_int(value, default=None):
    if value in (None, ""):
        return default
    try:
        return int(float(value))
    except ValueError:
        return default


def clamp_int16(value):
    return max(-32768, min(32767, int(value)))


def select_channel(samples, channels, channel_index):
    if channels <= 1:
        return samples

    if channel_index == -1:
        mixed = []
        usable_length = len(samples) - (len(samples) % channels)
        for index in range(0, usable_length, channels):
            frame = samples[index : index + channels]
            mixed.append(round(sum(frame) / channels))
        return mixed

    return samples[channel_index::channels]


def infer_sample_rate(first_timestamp_ns, last_timestamp_ns, sample_count, fallback):
    if first_timestamp_ns is None or last_timestamp_ns is None:
        return fallback

    duration_s = (last_timestamp_ns - first_timestamp_ns) / 1_000_000_000
    if duration_s <= 0 or sample_count <= 0:
        return fallback

    return round(sample_count / duration_s)


def convert_voice_csv_to_wav(
    voice_csv,
    output_wav,
    sample_rate,
    channels,
    channel_index,
):
    output_wav.parent.mkdir(parents=True, exist_ok=True)

    first_timestamp_ns = None
    last_timestamp_ns = None
    sample_count = 0
    chunks = []

    with voice_csv.open(newline="", encoding="utf-8-sig") as csv_file:
        reader = csv.DictReader(csv_file)
        for row in reader:
            timestamp_ns = parse_int(row.get("timestamp_ns"))
            if timestamp_ns is not None:
                first_timestamp_ns = timestamp_ns if first_timestamp_ns is None else first_timestamp_ns
                last_timestamp_ns = timestamp_ns

            raw_samples = row.get("audio_samples")
            if not raw_samples:
                continue

            samples = ast.literal_eval(raw_samples)
            samples = select_channel(samples, channels, channel_index)
            sample_count += len(samples)

            chunk = array("h", (clamp_int16(sample) for sample in samples))
            chunks.append(chunk)

    resolved_sample_rate = sample_rate or infer_sample_rate(
        first_timestamp_ns,
        last_timestamp_ns,
        sample_count,
        fallback=48000,
    )

    with wave.open(str(output_wav), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(resolved_sample_rate)
        for chunk in chunks:
            wav_file.writeframes(chunk.tobytes())

    duration_s = sample_count / resolved_sample_rate if resolved_sample_rate else 0.0
    print(f"Wrote WAV to {output_wav}")
    print(f"Sample rate: {resolved_sample_rate} Hz")
    print(f"Samples: {sample_count}")
    print(f"Duration: {duration_s:.2f}s")


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--voice-csv", type=Path, required=True)
    parser.add_argument("--output-wav", type=Path, default=Path("data/processed/voice.wav"))
    parser.add_argument(
        "--sample-rate",
        type=int,
        default=None,
        help="Override sample rate. If omitted, the script infers it from timestamps.",
    )
    parser.add_argument(
        "--channels",
        type=int,
        default=1,
        help="Number of interleaved channels in audio_samples.",
    )
    parser.add_argument(
        "--channel-index",
        type=int,
        default=0,
        help="Channel to keep. Use -1 to average all channels.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    convert_voice_csv_to_wav(
        args.voice_csv,
        args.output_wav,
        args.sample_rate,
        args.channels,
        args.channel_index,
    )
