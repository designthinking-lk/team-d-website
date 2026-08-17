"""
Run the full post-speech review pipeline from three CSV files.

Input:
- hand gesture CSV
- PPG CSV
- voice CSV

Output:
- reconstructed WAV
- OpenAI transcript JSON
- dashboard report JSON
- review_data.generated.js
"""

import argparse
import sys
from pathlib import Path

from build_review_from_split_csv import build_review_from_split_csv
from extract_voice_audio import convert_voice_csv_to_wav
from transcribe_openai_audio import TIMESTAMP_MODEL, transcribe_audio

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from export_vrs_csv import export_vrs_to_csv
from plot_eye_tracking import analyze_advanced_gaze


def windows_path_to_wsl(path_text):
    if len(path_text) >= 3 and path_text[1:3] == ":\\":
        drive = path_text[0].lower()
        rest = path_text[3:].replace("\\", "/")
        return Path(f"/mnt/{drive}/{rest}")
    return Path(path_text)


def resolve_input_path(path_text):
    path = windows_path_to_wsl(path_text)
    if not path.exists():
        raise FileNotFoundError(f"Could not find input file: {path}")
    return path


def require_export(exported_paths, sensor_name):
    path_text = exported_paths.get(sensor_name)
    if not path_text:
        raise FileNotFoundError(f"{sensor_name} CSV was not exported from the VRS file.")

    path = Path(path_text)
    if not path.exists():
        raise FileNotFoundError(f"{sensor_name} CSV export was expected but missing: {path}")
    return path


def export_vrs_inputs(vrs_file, export_output_dir):
    print("Step 0/3: Exporting VRS streams to CSV")
    exported_paths = export_vrs_to_csv(str(vrs_file), str(export_output_dir))
    return (
        require_export(exported_paths, "Hand Gesture"),
        require_export(exported_paths, "PPG"),
        require_export(exported_paths, "Voice"),
        Path(exported_paths["Eye Tracking"]) if exported_paths.get("Eye Tracking") else None,
    )


def run_pipeline(
    hand_csv,
    ppg_csv,
    voice_csv,
    eye_csv,
    audio_output,
    eye_image_output,
    transcript_output,
    report_output,
    web_output,
    env_file,
    sample_rate,
    channels,
    channel_index,
    model,
    language,
    prompt,
    chunk_seconds,
    baseline_seconds,
    confidence_threshold,
    ppg_spike_threshold,
    ppg_variability_threshold,
    fast_wpm,
    slow_wpm,
    min_pitch_std_hz,
    min_volume_std_db,
):
    print("Step 1/4: Converting voice CSV to WAV")
    convert_voice_csv_to_wav(
        voice_csv,
        audio_output,
        sample_rate,
        channels,
        channel_index,
    )

    generated_eye_image = None
    generated_eye_report = None
    if eye_csv:
        print("Step 2/4: Generating eye tracking dashboard image")
        eye_image_output.parent.mkdir(parents=True, exist_ok=True)
        generated_eye_report = analyze_advanced_gaze(
            str(eye_csv),
            str(eye_image_output),
            show=False,
        )
        if isinstance(generated_eye_report, dict):
            generated_eye_image = generated_eye_report.get("image_path")
        else:
            generated_eye_image = generated_eye_report
    else:
        print("Step 2/4: Eye tracking CSV not available; skipping gaze image")

    print("Step 3/4: Transcribing WAV with OpenAI")
    transcribe_audio(
        audio_output,
        transcript_output,
        model,
        language,
        prompt,
        env_file,
        chunk_seconds,
    )

    print("Step 4/4: Building highlighted dashboard report")
    build_review_from_split_csv(
        hand_csv,
        ppg_csv,
        voice_csv,
        eye_csv,
        transcript_output,
        report_output,
        web_output,
        baseline_seconds,
        window_seconds=10,
        confidence_threshold=confidence_threshold,
        ppg_spike_threshold=ppg_spike_threshold,
        ppg_variability_threshold=ppg_variability_threshold,
        audio_path=audio_output,
        fast_wpm=fast_wpm,
        slow_wpm=slow_wpm,
        min_pitch_std_hz=min_pitch_std_hz,
        min_volume_std_db=min_volume_std_db,
        eye_image=Path(generated_eye_image) if generated_eye_image else None,
        eye_report=generated_eye_report if isinstance(generated_eye_report, dict) else None,
    )

    print("Done.")
    print(f"Transcript: {transcript_output}")
    print(f"Report JSON: {report_output}")
    print(f"Dashboard data: {web_output}")


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--vrs-file", default=None)
    parser.add_argument("--vrs-output-dir", type=Path, default=Path("data/processed/vrs_csv"))
    parser.add_argument("--hand-csv", default=None)
    parser.add_argument("--ppg-csv", default=None)
    parser.add_argument("--voice-csv", default=None)
    parser.add_argument("--eye-csv", default=None)
    parser.add_argument("--audio-output", type=Path, default=Path("data/processed/voice_mono16k.wav"))
    parser.add_argument("--eye-image-output", type=Path, default=Path("data/processed/eye_tracking_report.png"))
    parser.add_argument("--transcript-output", type=Path, default=Path("data/processed/transcript_openai.json"))
    parser.add_argument("--report-output", type=Path, default=Path("data/processed/review_data.json"))
    parser.add_argument("--web-output", type=Path, default=Path("review_data.generated.js"))
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument("--sample-rate", type=int, default=16000)
    parser.add_argument("--channels", type=int, default=8)
    parser.add_argument("--channel-index", type=int, default=-1)
    parser.add_argument("--model", default=TIMESTAMP_MODEL)
    parser.add_argument("--language", default="en")
    parser.add_argument(
        "--prompt",
        default="This is a student public speaking practice recording. Preserve spoken wording clearly.",
    )
    parser.add_argument("--chunk-seconds", type=float, default=8.0)
    parser.add_argument("--baseline-seconds", type=int, default=10)
    parser.add_argument("--confidence-threshold", type=float, default=0.5)
    parser.add_argument("--ppg-spike-threshold", type=float, default=5000.0)
    parser.add_argument("--ppg-variability-threshold", type=float, default=None)
    parser.add_argument("--fast-wpm", type=float, default=175)
    parser.add_argument("--slow-wpm", type=float, default=95)
    parser.add_argument("--min-pitch-std-hz", type=float, default=18)
    parser.add_argument("--min-volume-std-db", type=float, default=3.0)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    try:
        if args.vrs_file:
            hand_csv, ppg_csv, voice_csv, eye_csv = export_vrs_inputs(
                resolve_input_path(args.vrs_file),
                args.vrs_output_dir,
            )
        else:
            missing = [
                name
                for name, value in (
                    ("--hand-csv", args.hand_csv),
                    ("--ppg-csv", args.ppg_csv),
                    ("--voice-csv", args.voice_csv),
                )
                if not value
            ]
            if missing:
                raise ValueError(
                    "Provide either --vrs-file or all three CSV inputs: "
                    + ", ".join(missing)
                )
            hand_csv = resolve_input_path(args.hand_csv)
            ppg_csv = resolve_input_path(args.ppg_csv)
            voice_csv = resolve_input_path(args.voice_csv)
            eye_csv = resolve_input_path(args.eye_csv) if args.eye_csv else None

        run_pipeline(
            hand_csv,
            ppg_csv,
            voice_csv,
            eye_csv,
            args.audio_output,
            args.eye_image_output,
            args.transcript_output,
            args.report_output,
            args.web_output,
            args.env_file,
            args.sample_rate,
            args.channels,
            args.channel_index,
            args.model,
            args.language,
            args.prompt,
            args.chunk_seconds,
            args.baseline_seconds,
            args.confidence_threshold,
            args.ppg_spike_threshold,
            args.ppg_variability_threshold,
            args.fast_wpm,
            args.slow_wpm,
            args.min_pitch_std_hz,
            args.min_volume_std_db,
        )
    except Exception as error:
        print(f"Pipeline failed: {error}", file=sys.stderr)
        sys.exit(1)
