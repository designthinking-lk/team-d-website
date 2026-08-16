# (c) Meta Platforms, Inc. and affiliates. Confidential and proprietary.

import argparse
import time

import aria.sdk_gen2 as sdk_gen2


def device_record(duration, output_path):
    device_client = sdk_gen2.DeviceClient()
    config = sdk_gen2.DeviceClientConfig()
    device_client.set_client_config(config)

    # try to connect to the device
    try:
        device = device_client.connect()
        print(f"Successfully connected to device {device.connection_id()}")

        # Set recording config with profile name
        print("Setup recording config")
        recording_config = sdk_gen2.RecordingConfig()
        recording_config.recording_name = "example_recording"
        recording_config.profile_name = "profile9"
        device.set_recording_config(recording_config)

        # Start and stop recording
        uuid = device.start_recording()
        print(f"Start recording for {duration} seconds with uuid: {uuid}")
        time.sleep(duration)
        device.stop_recording()

        # list existing recordings on device
        print("List recordings")
        recordings = device.list_recordings()
        print(f"Found {len(recordings)} recording(s):")
        for recording in recordings:
            print(f"  - Name: {recording.name}, Size: {recording.size} bytes")

        # download all recordings
        print(f"Download recordings {uuid}")
        device.download_recording(uuid=uuid, output_path=output_path)

        # Download all thumbnails of a recording
        print(f'Download thumbnails for recording "{uuid}"')
        device.download_all_thumbnails(uuid=uuid, output_dir=output_path)
    except Exception:
        print("Failed to connect to device and record")
        return


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        dest="output_path",
        type=str,
        default="",
        required=False,
        help="Output directory to save the recording",
    )
    parser.add_argument(
        "--duration",
        dest="duration",
        type=int,
        default=10,
        required=False,
        help="Recording duration in seconds (default: 10)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    device_record(args.duration, args.output_path)
