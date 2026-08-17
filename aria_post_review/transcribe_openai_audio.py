"""
Transcribe a WAV file with the OpenAI API into dashboard transcript JSON.

Security:
- Do not paste your API key into this file.
- Set OPENAI_API_KEY in your shell, or create a local .env file that is ignored
  by Git.

Timestamp modes:
- whisper-1: uses OpenAI's verbose_json segment and word timestamps.
- gpt-4o-transcribe / gpt-4o-mini-transcribe: transcribes fixed WAV chunks and
  uses chunk start/end times for dashboard alignment.
"""

import argparse
import json
import os
import tempfile
import wave
from pathlib import Path

from openai import OpenAI

from build_review_data import format_time


TIMESTAMP_MODEL = "whisper-1"
ACCURATE_MODEL = "gpt-4o-transcribe"
PLACEHOLDER_API_KEY = "sk-proj-paste_your_real_key_here"


def load_env_file(env_path):
    if not env_path.exists():
        return

    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def require_api_key(env_path):
    load_env_file(env_path)
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is not set. Create a local .env file from .env.example "
            "or set it in your shell before running this script."
        )
    if api_key == PLACEHOLDER_API_KEY:
        raise RuntimeError(
            "OPENAI_API_KEY is still the placeholder. Open .env and replace it "
            "with your real OpenAI API key."
        )


def object_to_dict(value):
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if isinstance(value, dict):
        return value
    return json.loads(value.model_dump_json())


def normalize_text(text):
    return " ".join((text or "").strip().split())


def transcribe_with_timestamps(client, audio_path, language, prompt):
    with audio_path.open("rb") as audio_file:
        response = client.audio.transcriptions.create(
            model=TIMESTAMP_MODEL,
            file=audio_file,
            language=language,
            prompt=prompt,
            response_format="verbose_json",
            timestamp_granularities=["segment", "word"],
        )

    data = object_to_dict(response)
    words = [
        {
            "start": round(float(word["start"]), 3),
            "end": round(float(word["end"]), 3),
            "text": normalize_text(word.get("word")),
        }
        for word in data.get("words", [])
        if normalize_text(word.get("word"))
    ]

    transcript_segments = []
    for index, segment in enumerate(data.get("segments", []), start=1):
        text = normalize_text(segment.get("text"))
        if not text:
            continue

        segment_start = float(segment["start"])
        segment_end = float(segment["end"])
        segment_words = [
            word
            for word in words
            if segment_start <= ((word["start"] + word["end"]) / 2) <= segment_end
        ]

        transcript_segments.append(
            {
                "id": f"speech-{index:03d}",
                "start": round(segment_start, 3),
                "end": round(segment_end, 3),
                "text": text,
                "words": segment_words,
            }
        )

    return {
        "source": "openai_audio_transcriptions",
        "model": TIMESTAMP_MODEL,
        "timestamp_mode": "segment_word",
        "segments": transcript_segments,
    }


def wav_duration(audio_path):
    with wave.open(str(audio_path), "rb") as wav_file:
        return wav_file.getnframes() / wav_file.getframerate()


def write_wav_chunk(source, output_path, start_s, end_s):
    with wave.open(str(source), "rb") as wav_file:
        params = wav_file.getparams()
        frame_rate = wav_file.getframerate()
        start_frame = int(start_s * frame_rate)
        frame_count = int((end_s - start_s) * frame_rate)
        wav_file.setpos(start_frame)
        frames = wav_file.readframes(frame_count)

    with wave.open(str(output_path), "wb") as chunk_file:
        chunk_file.setparams(params)
        chunk_file.writeframes(frames)


def transcribe_chunk(client, chunk_path, model, language, prompt):
    with chunk_path.open("rb") as audio_file:
        response = client.audio.transcriptions.create(
            model=model,
            file=audio_file,
            language=language,
            prompt=prompt,
        )

    data = object_to_dict(response)
    return normalize_text(data.get("text"))


def transcribe_in_chunks(client, audio_path, model, language, prompt, chunk_seconds):
    duration_s = wav_duration(audio_path)
    transcript_segments = []

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        start_s = 0.0
        index = 1
        while start_s < duration_s:
            end_s = min(duration_s, start_s + chunk_seconds)
            if end_s - start_s < 1.0 and transcript_segments:
                break

            chunk_path = temp_path / f"chunk-{index:03d}.wav"
            write_wav_chunk(audio_path, chunk_path, start_s, end_s)
            text = transcribe_chunk(client, chunk_path, model, language, prompt)
            if text:
                transcript_segments.append(
                    {
                        "id": f"speech-{index:03d}",
                        "start": format_time(start_s),
                        "end": format_time(end_s),
                        "text": text,
                    }
                )

            start_s = end_s
            index += 1

    return {
        "source": "openai_audio_transcriptions",
        "model": model,
        "timestamp_mode": f"{chunk_seconds:g}s_chunks",
        "segments": transcript_segments,
    }


def transcribe_audio(
    audio_path,
    output_path,
    model,
    language,
    prompt,
    env_path,
    chunk_seconds,
):
    require_api_key(env_path)
    client = OpenAI()

    if model == TIMESTAMP_MODEL:
        result = transcribe_with_timestamps(client, audio_path, language, prompt)
    else:
        result = transcribe_in_chunks(
            client,
            audio_path,
            model,
            language,
            prompt,
            chunk_seconds,
        )

    transcript = {
        "metadata": {
            "source": result["source"],
            "audio_file": str(audio_path),
            "model": result["model"],
            "language": language,
            "timestamp_mode": result["timestamp_mode"],
        },
        "segments": result["segments"],
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(transcript, indent=2), encoding="utf-8")
    print(f"Wrote transcript to {output_path}")
    print(f"Segments: {len(result['segments'])}")
    print(f"Model: {model}")


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--audio", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("data/processed/transcript_openai.json"))
    parser.add_argument(
        "--model",
        default=TIMESTAMP_MODEL,
        help="Use whisper-1 for real segment timestamps, or gpt-4o-transcribe for chunked timestamps.",
    )
    parser.add_argument("--language", default="en")
    parser.add_argument(
        "--prompt",
        default="This is a student public speaking practice recording. Preserve spoken wording clearly.",
    )
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument("--chunk-seconds", type=float, default=8.0)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    transcribe_audio(
        args.audio,
        args.output,
        args.model,
        args.language,
        args.prompt,
        args.env_file,
        args.chunk_seconds,
    )
