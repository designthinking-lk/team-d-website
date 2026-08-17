"""
Transcribe a WAV file into dashboard transcript JSON.

This uses faster-whisper locally and writes:
{
  "segments": [
    {"id": "speech-001", "start": "00:00", "end": "00:08", "text": "..."}
  ]
}
"""

import argparse
import json
from pathlib import Path

from faster_whisper import WhisperModel

from build_review_data import format_time


def transcribe_audio(
    audio_path,
    output_path,
    model_size,
    language,
    compute_type,
):
    model = WhisperModel(model_size, device="cpu", compute_type=compute_type)
    segments, info = model.transcribe(
        str(audio_path),
        language=language,
        vad_filter=True,
        beam_size=5,
    )

    transcript_segments = []
    for index, segment in enumerate(segments, start=1):
        text = " ".join(segment.text.strip().split())
        if not text:
            continue

        transcript_segments.append(
            {
                "id": f"speech-{index:03d}",
                "start": format_time(segment.start),
                "end": format_time(segment.end),
                "text": text,
            }
        )

    transcript = {
        "metadata": {
            "source": "faster_whisper",
            "audio_file": str(audio_path),
            "model_size": model_size,
            "language": info.language,
            "language_probability": round(info.language_probability, 3),
        },
        "segments": transcript_segments,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(transcript, indent=2), encoding="utf-8")
    print(f"Wrote transcript to {output_path}")
    print(f"Segments: {len(transcript_segments)}")
    print(f"Detected language: {info.language} ({info.language_probability:.2f})")


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--audio", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("data/processed/transcript.json"))
    parser.add_argument("--model-size", default="base.en")
    parser.add_argument("--language", default="en")
    parser.add_argument("--compute-type", default="int8")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    transcribe_audio(
        args.audio,
        args.output,
        args.model_size,
        args.language,
        args.compute_type,
    )
