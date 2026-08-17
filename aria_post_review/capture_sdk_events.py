"""
Capture Meta Aria Gen 2 hand tracking and PPG events for post-speech review.

This script matches the local SDK examples added to the repo:
- PPG is read from MessageType.PPG_EVENT.
- Hand tracking is read from MessageType.MP_HT_RESULT.

The output is a compact JSON event file that can be converted into the
gesture_review UI format by build_review_data.py.
"""

import argparse
import json
import time
from pathlib import Path

import aria.oss_data_converter as data_converter
import aria.sdk_gen2 as sdk_gen2
import aria.stream_receiver as receiver
from projectaria_tools.core import calibration


STREAMING_INTERFACE_MAP = {
    "usb": sdk_gen2.StreamingInterface.USB_NCM,
    "wifi_sta": sdk_gen2.StreamingInterface.WIFI_STA,
    "wifi_sap": sdk_gen2.StreamingInterface.WIFI_SAP,
}


class ReviewCapture:
    def __init__(self):
        self.converter = data_converter.OssDataConverter()
        self.session_start_ns = None
        self.hand_samples = []
        self.ppg_samples = []

    def set_calibration(self, device_calib):
        calib_json = calibration.device_calibration_to_json_string(device_calib)
        self.converter.set_calibration(calib_json)
        print("Calibration received. Hand tracking conversion is ready.")

    def relative_seconds(self, timestamp_ns):
        if self.session_start_ns is None:
            self.session_start_ns = timestamp_ns
        return max(0.0, (timestamp_ns - self.session_start_ns) / 1_000_000_000)

    def handle_raw_message(self, message, _offset):
        shared_message = sdk_gen2.SharedMessage(
            message.id,
            message.payload.as_memoryview(),
        )

        if shared_message.id == sdk_gen2.MessageType.PPG_EVENT:
            ppg_data = self.converter.to_ppg(shared_message)
            if ppg_data is None:
                return

            timestamp_s = self.relative_seconds(ppg_data.capture_timestamp_ns)
            self.ppg_samples.append(
                {
                    "time_s": round(timestamp_s, 3),
                    "value": float(ppg_data.value),
                }
            )
            return

        if shared_message.id != sdk_gen2.MessageType.MP_HT_RESULT:
            return

        hand_data = self.converter.to_hand_pose(shared_message)
        if hand_data is None:
            return

        timestamp_s = hand_data.tracking_timestamp.total_seconds()
        left = self.hand_to_dict(hand_data.left_hand)
        right = self.hand_to_dict(hand_data.right_hand)
        self.hand_samples.append(
            {
                "time_s": round(timestamp_s, 3),
                "left_visible": left is not None,
                "right_visible": right is not None,
                "left": left,
                "right": right,
            }
        )

    @staticmethod
    def hand_to_dict(hand):
        if hand is None:
            return None

        return {
            "confidence": float(hand.confidence),
            "wrist_position_device": vector_to_list(hand.get_wrist_position_device()),
            "palm_position_device": vector_to_list(hand.get_palm_position_device()),
        }

    def write(self, output_path, duration_s, profile_name, interface):
        payload = {
            "metadata": {
                "source": "meta_aria_gen2_sdk",
                "profile_name": profile_name,
                "interface": interface,
                "duration_s": duration_s,
                "created_at_unix": int(time.time()),
            },
            "hand_samples": self.hand_samples,
            "ppg_samples": self.ppg_samples,
        }

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def vector_to_list(value):
    if value is None:
        return None

    try:
        return [float(value[0]), float(value[1]), float(value[2])]
    except (TypeError, IndexError):
        return [float(component) for component in value]


def connect_device(profile_name, interface):
    device_client = sdk_gen2.DeviceClient()
    config = sdk_gen2.DeviceClientConfig()
    device_client.set_client_config(config)
    device = device_client.connect()

    streaming_config = sdk_gen2.HttpStreamingConfig()
    streaming_config.profile_name = profile_name
    streaming_config.streaming_interface = STREAMING_INTERFACE_MAP[interface]
    device.set_streaming_config(streaming_config)
    device.start_streaming()
    return device


def capture_events(duration_s, output_path, profile_name, interface):
    capture = ReviewCapture()
    device = connect_device(profile_name, interface)

    server_config = sdk_gen2.HttpServerConfig()
    server_config.address = "0.0.0.0"
    server_config.port = 6768

    stream_receiver = receiver.StreamReceiver(
        enable_image_decoding=False,
        enable_raw_stream=True,
    )
    stream_receiver.set_server_config(server_config)
    stream_receiver.register_device_calib_callback(capture.set_calibration)
    stream_receiver.register_raw_message_callback(capture.handle_raw_message)

    print(f"Capturing Aria hand tracking and PPG for {duration_s} seconds...")
    stream_receiver.start_server()
    time.sleep(duration_s)

    device.stop_streaming()
    time.sleep(2)
    stream_receiver.stop_server()

    capture.write(output_path, duration_s, profile_name, interface)
    print(f"Wrote SDK events to {output_path}")


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--duration", type=int, default=90)
    parser.add_argument("--output", type=Path, default=Path("data/processed/aria_events.json"))
    parser.add_argument("--profile-name", default="profile9")
    parser.add_argument(
        "--interface",
        choices=list(STREAMING_INTERFACE_MAP.keys()),
        default="usb",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    capture_events(args.duration, args.output, args.profile_name, args.interface)
