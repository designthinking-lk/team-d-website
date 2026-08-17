"""
Local EloQ dashboard server for Aria Gen 2 recording workflows.

The normal dashboard still works as static HTML with the last generated report.
Run this server when the glasses are connected and the UI should start/stop a
recording, download the VRS, and generate a fresh report.
"""

import argparse
import json
import sys
import time
from datetime import datetime
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

REPO_ROOT = Path(__file__).resolve().parents[1]
ARIA_REVIEW_DIR = REPO_ROOT / "aria_post_review"
sys.path.insert(0, str(ARIA_REVIEW_DIR))
sys.path.insert(0, str(REPO_ROOT))

from run_full_review_pipeline import TIMESTAMP_MODEL, export_vrs_inputs, run_pipeline


class AriaRecordingController:
    def __init__(self, profile_name, recording_root):
        self.profile_name = profile_name
        self.recording_root = recording_root
        self.device_client = None
        self.device = None
        self.sdk_gen2 = None
        self.connected = False
        self.connection_id = None
        self.recording_uuid = None
        self.recording_name = None
        self.recording_started_at = None
        self.last_vrs_path = None
        self.last_download_dir = None
        self.last_error = None

    def _load_sdk(self):
        if self.sdk_gen2 is None:
            import aria.sdk_gen2 as sdk_gen2

            self.sdk_gen2 = sdk_gen2
        return self.sdk_gen2

    def connect(self):
        sdk_gen2 = self._load_sdk()
        self.device_client = sdk_gen2.DeviceClient()
        config = sdk_gen2.DeviceClientConfig()
        self.device_client.set_client_config(config)
        self.device = self.device_client.connect()
        self.connected = True
        self.connection_id = str(self.device.connection_id())
        self.last_error = None
        return self.status()

    def check_status(self):
        if self.connected and self.device:
            return self.status()

        try:
            return self.connect()
        except Exception as error:
            self.connected = False
            self.device = None
            self.connection_id = None
            self.last_error = str(error) or "Could not connect to the glasses."
            return self.status()

    def start(self):
        if not self.connected or not self.device:
            self.connect()

        if self.recording_uuid:
            return self.status()

        sdk_gen2 = self._load_sdk()
        self.recording_name = f"eloq_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        recording_config = sdk_gen2.RecordingConfig()
        recording_config.recording_name = self.recording_name
        recording_config.profile_name = self.profile_name
        self.device.set_recording_config(recording_config)

        self.recording_uuid = str(self.device.start_recording())
        self.recording_started_at = time.time()
        self.last_error = None
        return self.status()

    def stop(self):
        if not self.recording_uuid or not self.device:
            raise RuntimeError("No active recording to stop.")

        recording_uuid = self.recording_uuid
        download_dir = self.recording_root / self.recording_name
        download_dir.mkdir(parents=True, exist_ok=True)

        self.device.stop_recording()
        self.device.download_recording(uuid=recording_uuid, output_path=str(download_dir))

        try:
            self.device.download_all_thumbnails(uuid=recording_uuid, output_dir=str(download_dir))
        except Exception:
            # Thumbnails are useful but not required for the report pipeline.
            pass

        self.last_download_dir = download_dir
        self.last_vrs_path = self._find_latest_vrs(download_dir)
        self.recording_uuid = None
        self.recording_started_at = None
        self.last_error = None
        return self.status(extra={"downloaded": bool(self.last_vrs_path)})

    def _find_latest_vrs(self, folder):
        candidates = sorted(
            folder.rglob("*.vrs"),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        return candidates[0] if candidates else None

    def status(self, extra=None):
        payload = {
            "connected": self.connected,
            "connection_id": self.connection_id,
            "recording": bool(self.recording_uuid),
            "recording_uuid": self.recording_uuid,
            "recording_name": self.recording_name,
            "recording_seconds": round(time.time() - self.recording_started_at, 1)
            if self.recording_started_at
            else 0,
            "last_vrs_path": str(self.last_vrs_path) if self.last_vrs_path else None,
            "last_download_dir": str(self.last_download_dir) if self.last_download_dir else None,
            "last_error": self.last_error,
        }
        if extra:
            payload.update(extra)
        return payload


class EloQServer(ThreadingHTTPServer):
    def __init__(self, server_address, handler_class, controller):
        super().__init__(server_address, handler_class)
        self.controller = controller


class DashboardRequestHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(REPO_ROOT), **kwargs)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/device/status":
            return self.write_json(self.server.controller.check_status())

        if parsed.path == "/":
            self.path = "/index.html"
            return super().do_GET()

        if not self.is_allowed_static_path(parsed.path):
            return self.write_json(
                {"error": "This local server only exposes the EloQ dashboard assets."},
                status=HTTPStatus.FORBIDDEN,
            )

        return super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        try:
            if parsed.path == "/api/recording/start":
                return self.write_json(self.server.controller.start())
            if parsed.path == "/api/recording/stop":
                return self.write_json(self.server.controller.stop())
            if parsed.path == "/api/report/generate":
                return self.write_json(self.generate_report())
        except Exception as error:
            return self.write_json({"error": str(error)}, status=HTTPStatus.INTERNAL_SERVER_ERROR)

        return self.write_json({"error": "Unknown API endpoint."}, status=HTTPStatus.NOT_FOUND)

    def is_allowed_static_path(self, path):
        decoded = unquote(path).lstrip("/")
        requested_path = (REPO_ROOT / decoded).resolve()
        allowed_root_files = {
            REPO_ROOT / "index.html",
            REPO_ROOT / "app.js",
            REPO_ROOT / "styles.css",
            REPO_ROOT / "review_data.generated.js",
        }
        if requested_path in {path.resolve() for path in allowed_root_files}:
            return True
        return self.is_relative_to(requested_path, REPO_ROOT / "data/processed")

    @staticmethod
    def is_relative_to(path, parent):
        try:
            path.relative_to(parent.resolve())
            return True
        except ValueError:
            return False

    def generate_report(self):
        vrs_path = self.server.controller.last_vrs_path
        if not vrs_path or not Path(vrs_path).exists():
            raise RuntimeError("No downloaded VRS file is ready. Record and stop first.")

        hand_csv, ppg_csv, voice_csv, eye_csv = export_vrs_inputs(
            Path(vrs_path),
            REPO_ROOT / "data/processed/vrs_csv",
        )

        run_pipeline(
            hand_csv=hand_csv,
            ppg_csv=ppg_csv,
            voice_csv=voice_csv,
            eye_csv=eye_csv,
            audio_output=REPO_ROOT / "data/processed/voice_mono16k.wav",
            eye_image_output=REPO_ROOT / "data/processed/eye_tracking_report.png",
            transcript_output=REPO_ROOT / "data/processed/transcript_openai.json",
            report_output=REPO_ROOT / "data/processed/review_data.json",
            web_output=REPO_ROOT / "review_data.generated.js",
            env_file=REPO_ROOT / ".env",
            sample_rate=16000,
            channels=8,
            channel_index=-1,
            model=TIMESTAMP_MODEL,
            language="en",
            prompt="This is a student public speaking practice recording. Preserve spoken wording clearly.",
            chunk_seconds=8.0,
            baseline_seconds=10,
            confidence_threshold=0.5,
            ppg_spike_threshold=5000.0,
            ppg_variability_threshold=None,
            fast_wpm=175,
            slow_wpm=95,
            min_pitch_std_hz=18,
            min_volume_std_db=3.0,
        )

        review_path = REPO_ROOT / "data/processed/review_data.json"
        review_data = json.loads(review_path.read_text(encoding="utf-8"))
        return {
            "message": "Report generated.",
            "vrs_file": str(vrs_path),
            "review_json": str(review_path),
            "web_output": str(REPO_ROOT / "review_data.generated.js"),
            "review_data": review_data,
            "device": self.server.controller.status(),
        }

    def write_json(self, payload, status=HTTPStatus.OK):
        body = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--profile-name", default="profile9")
    parser.add_argument("--recording-root", type=Path, default=REPO_ROOT / "data/raw/aria_recordings")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    controller = AriaRecordingController(args.profile_name, args.recording_root)
    server = EloQServer((args.host, args.port), DashboardRequestHandler, controller)
    print(f"EloQ dashboard server: http://{args.host}:{args.port}/")
    print("Open that URL when the Aria Gen 2 glasses are connected over USB-C.")
    server.serve_forever()

