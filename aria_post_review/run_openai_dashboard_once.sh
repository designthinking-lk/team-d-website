#!/usr/bin/env bash
set -euo pipefail

python_bin="${PYTHON_BIN:-$HOME/.venvs/speak_sync/bin/python}"

if [[ "$#" -eq 1 ]]; then
  "$python_bin" aria_post_review/run_full_review_pipeline.py \
    --vrs-file "$1"
  exit 0
fi

hand_csv="${1:-/mnt/c/Users/thusi/Downloads/hand_gesture.csv}"
ppg_csv="${2:-/mnt/c/Users/thusi/Downloads/ppg.csv}"
voice_csv="${3:-/mnt/c/Users/thusi/Downloads/voice.csv}"
eye_csv="${4:-}"

extra_args=()
if [[ -n "$eye_csv" ]]; then
  extra_args+=(--eye-csv "$eye_csv")
fi

"$python_bin" aria_post_review/run_full_review_pipeline.py \
  --hand-csv "$hand_csv" \
  --ppg-csv "$ppg_csv" \
  --voice-csv "$voice_csv" \
  "${extra_args[@]}"
