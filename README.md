# Speak_Sync (team-d-website - EduPlay)
An innovative solution using Meta Aria Gen 2 glasses to help people to feel confident in public speaking by developing an accsesible, realistic and judgement free platform.

## Setup
1. Create a virtual environment: `python3 -m venv venv`
2. Activate it: `source venv/bin/activate` (Mac/Linux) or `venv\Scripts\activate` (Windows)
3. Install dependencies: `pip install -r requirements.txt`
4. Pair your glasses: Run `aria auth pair` while your phone app is open.

## Gesture Recognition Review Prototype

Open `index.html` in a browser to view the post-speech feedback prototype.

The prototype shows:

- A transcript with color-coded clickable highlights.
- Red highlights for possible stress signals.
- Orange highlights for gesture or posture improvement areas.
- Green highlights for strong delivery moments.
- A details panel with evidence, meaning, and a practical suggestion.

Later, the sample data in `app.js` can be replaced with real transcript, hand tracking, and PPG outputs from the Meta Aria pipeline.

## Aria Post Review Flow

The Aria SDK is installed inside WSL at:

```bash
~/.venvs/speak_sync
```

From Ubuntu/WSL, run project commands from:

```bash
cd "/mnt/c/Users/thusi/Downloads/ICE - Speak_Sync/Speak_Sync"
```

Capture hand tracking and PPG SDK events:

```powershell
~/.venvs/speak_sync/bin/python aria_post_review/capture_sdk_events.py --duration 90 --output data/processed/aria_events.json
```

Build the color-coded transcript review JSON:

```powershell
~/.venvs/speak_sync/bin/python aria_post_review/build_review_data.py --events data/processed/aria_events.json --transcript review_sample.json --output data/processed/review_data.json
```

Open `index.html`, click `Load SDK JSON`, and select `data/processed/review_data.json`.

To test the same conversion flow without glasses:

```powershell
~/.venvs/speak_sync/bin/python aria_post_review/build_review_data.py --events aria_post_review/sample_events.json --transcript review_sample.json --output data/processed/review_data.json
```

## CSV Post Review Flow

If another pipeline extracts gesture and PPG data from VRS files into CSV, build the same report JSON from that CSV:

```bash
~/.venvs/speak_sync/bin/python aria_post_review/build_review_from_csv.py --csv path/to/features.csv --transcript review_sample.json --output data/processed/review_data.json
```

The CSV converter accepts common columns such as:

- `time_s`, `timestamp_s`, `seconds`, `time`
- `ppg`, `ppg_value`, `heart_rate`, `hr`, `bpm`
- `left_visible`, `right_visible`, `hands_visible`, `hand_count`
- `left_palm_x`, `left_palm_y`, `left_palm_z`
- `right_palm_x`, `right_palm_y`, `right_palm_z`

The gesture rules currently flag:

- hands mostly outside the field of view
- hands visible but held in the same region for a considerable section
- very low gesture movement
- good visible gesture support

To test with the included sample CSV:

```bash
~/.venvs/speak_sync/bin/python aria_post_review/build_review_from_csv.py --csv aria_post_review/sample_features.csv --transcript review_sample.json --output data/processed/review_data.json
```

## Split Hand/PPG CSV Flow

If hand gesture and PPG data are exported as separate CSV files, build the dashboard JSON with:

```bash
~/.venvs/speak_sync/bin/python aria_post_review/build_review_from_split_csv.py --hand-csv "/mnt/c/Users/thusi/Downloads/hand_gesture.csv" --ppg-csv "/mnt/c/Users/thusi/Downloads/ppg.csv" --output data/processed/review_data.json
```

This also writes `review_data.generated.js`, so `index.html` opens with the latest generated CSV report automatically.

If you do not pass `--transcript`, the dashboard automatically creates 10-second speech sections. If you have a transcript JSON later, add:

```bash
--transcript review_sample.json
```

## Voice CSV And Transcript Flow

The `voice.csv` file from the VRS export is raw audio samples, not transcript text. First convert it to a WAV file:

```bash
~/.venvs/speak_sync/bin/python aria_post_review/extract_voice_audio.py --voice-csv "/mnt/c/Users/thusi/Downloads/voice.csv" --output-wav data/processed/voice_mono16k.wav --channels 8 --channel-index -1 --sample-rate 16000
```

Then transcribe `data/processed/voice_mono16k.wav` to create a timestamped transcript JSON:

```bash
~/.venvs/speak_sync/bin/python aria_post_review/transcribe_audio.py --audio data/processed/voice_mono16k.wav --output data/processed/transcript.json --model-size tiny.en
```

For a more accurate cloud transcription with the OpenAI API, keep your key out of code and Git:

```bash
cp .env.example .env
nano .env
```

Put your real key only in `.env`:

```bash
OPENAI_API_KEY=your_real_key_here
```

Then run OpenAI transcription:

```bash
~/.venvs/speak_sync/bin/python aria_post_review/transcribe_openai_audio.py --audio data/processed/voice_mono16k.wav --output data/processed/transcript_openai.json --model whisper-1
```

Use `whisper-1` when you need word/segment timestamps for the highlighted dashboard. You can also try `--model gpt-4o-transcribe`, but that script uses fixed audio chunks for timestamps.

Or run the complete OpenAI transcript + dashboard rebuild flow once:

```bash
bash aria_post_review/run_openai_dashboard_once.sh
```

For any new recording, pass the three CSV files in this order:

```bash
bash aria_post_review/run_openai_dashboard_once.sh "/mnt/c/Users/thusi/Downloads/new_hand_gesture.csv" "/mnt/c/Users/thusi/Downloads/new_ppg.csv" "/mnt/c/Users/thusi/Downloads/new_voice.csv"
```

If you also have an eye tracking CSV, pass it as the fourth file:

```bash
bash aria_post_review/run_openai_dashboard_once.sh "/mnt/c/Users/thusi/Downloads/new_hand_gesture.csv" "/mnt/c/Users/thusi/Downloads/new_ppg.csv" "/mnt/c/Users/thusi/Downloads/new_voice.csv" "/mnt/c/Users/thusi/Downloads/new_eye_tracking.csv"
```

If you have the original VRS file instead, pass only the VRS file:

```bash
bash aria_post_review/run_openai_dashboard_once.sh "/mnt/c/Users/thusi/Downloads/new_recording.vrs"
```

This automatically:

- exports hand gesture, PPG, and voice CSVs from the VRS file when a VRS path is provided
- exports and analyzes eye tracking when it is available in the VRS file
- converts the voice CSV into `data/processed/voice_mono16k.wav`
- transcribes it with OpenAI using the key in `.env`
- creates `data/processed/transcript_openai.json`
- analyzes hand gestures, increased heart-rate moments, speaking pace, tone variation, and eye contact
- creates separate eye tracking visuals:
  `data/processed/eye_tracking_report_heatmap.png` and
  `data/processed/eye_tracking_report_timeline.png`
- writes `data/processed/review_data.json`
- refreshes `review_data.generated.js` for the dashboard

```json
{
  "segments": [
    { "start": "00:00", "end": "00:08", "text": "Hello everyone..." }
  ]
}
```

After you have that transcript, rebuild the dashboard with all three CSV files:

```bash
~/.venvs/speak_sync/bin/python aria_post_review/build_review_from_split_csv.py --hand-csv "/mnt/c/Users/thusi/Downloads/hand_gesture.csv" --ppg-csv "/mnt/c/Users/thusi/Downloads/ppg.csv" --voice-csv "/mnt/c/Users/thusi/Downloads/voice.csv" --transcript data/processed/transcript.json --output data/processed/review_data.json --audio data/processed/voice_mono16k.wav --ppg-spike-threshold 5000
```

If you used the OpenAI transcript, replace the transcript path:

```bash
~/.venvs/speak_sync/bin/python aria_post_review/build_review_from_split_csv.py --hand-csv "/mnt/c/Users/thusi/Downloads/hand_gesture.csv" --ppg-csv "/mnt/c/Users/thusi/Downloads/ppg.csv" --voice-csv "/mnt/c/Users/thusi/Downloads/voice.csv" --transcript data/processed/transcript_openai.json --output data/processed/review_data.json --audio data/processed/voice_mono16k.wav --ppg-spike-threshold 5000
```

The heart-rate signal rule now uses a hard threshold. A section is flagged only when its peak PPG-derived signal is at least `--ppg-spike-threshold` above the baseline. Increase this value if too many sections are red; decrease it if real stress moments are being missed.

When the transcript has word timestamps, feedback highlights attach to the nearest words around the sensor event. If the transcript only has segment timestamps, the builder estimates word positions inside that segment and still highlights a short phrase instead of the whole sentence.

Vocal delivery notes are added when `--audio data/processed/voice_mono16k.wav` is passed. Pace is flagged below `--slow-wpm 95` or above `--fast-wpm 175`. Tone is flagged when pitch and volume variation stay low for a section; tune this with `--min-pitch-std-hz` and `--min-volume-std-db`.

Eye tracking is shown as its own dashboard section when an eye tracking CSV is available. The transcript is not highlighted for gaze anymore; instead, the dashboard shows horizontal and vertical gaze range, fixation timing, a custom Left/Center/Right/Floor-Notes audience component, and separate heatmap/timeline images generated by `plot_eye_tracking.py`.

## Live USB-C Dashboard Controls

The EloQ dashboard can also be opened through a small local server when the Meta Aria Gen 2 glasses are connected over USB-C. This enables the top dashboard buttons:

- `Check Glasses` verifies SDK connectivity.
- `START` starts a new Aria recording.
- `STOP` stops the recording and downloads the VRS file into `data/raw/aria_recordings/`.
- `GENERATE` runs the full VRS-to-report pipeline and refreshes `review_data.generated.js`.

Run the local dashboard server from WSL:

```bash
cd "/mnt/c/Users/thusi/Downloads/team-d-website"
~/.venvs/speak_sync/bin/python aria_post_review/dashboard_server.py
```

Then open:

```text
http://127.0.0.1:8765/
```

If the dashboard is opened directly as `index.html`, or if the glasses are not connected, the recording buttons stay disabled and the dashboard simply shows the last generated report.
If you do not have a transcript yet, you can still include the voice CSV and the dashboard will show timed speech sections:

```bash
~/.venvs/speak_sync/bin/python aria_post_review/build_review_from_split_csv.py --hand-csv "/mnt/c/Users/thusi/Downloads/hand_gesture.csv" --ppg-csv "/mnt/c/Users/thusi/Downloads/ppg.csv" --voice-csv "/mnt/c/Users/thusi/Downloads/voice.csv" --output data/processed/review_data.json --ppg-spike-threshold 5000
```
