# (c) Meta Platforms, Inc. and affiliates. Confidential and proprietary.

"""
Example script demonstrating device streaming with raw message callbacks.

This script shows how to:
1. Stream data from an Aria device via USB-NCM, Wi-Fi STA, or Wi-Fi SAP interface
2. Use raw message callbacks with manual conversion
3. Handle all sensor types including cameras, IMU, audio, GPS, WiFi/BLE beacons, and ML outputs
4. Optionally record streaming data to VRS format

Usage:
    # Stream with raw callbacks (USB-NCM, default)
    python device_raw_streaming.py

    # Stream over Wi-Fi (when USB-NCM is not available)
    python device_raw_streaming.py --interface wifi_sta

    # Decode images from compressed format
    python device_raw_streaming.py --decode-images
"""

import argparse
import time

import aria.oss_data_converter as data_converter
import aria.sdk_gen2 as sdk_gen2
import aria.stream_receiver as receiver
from projectaria_tools.core import calibration

# Set up the device client to initiate connection to the device
device_client = sdk_gen2.DeviceClient()
converter = data_converter.OssDataConverter()

# Global flag to track if calibration has been received
calibration_received = False


STREAMING_INTERFACE_MAP = {
    "usb": sdk_gen2.StreamingInterface.USB_NCM,
    "wifi_sta": sdk_gen2.StreamingInterface.WIFI_STA,
    "wifi_sap": sdk_gen2.StreamingInterface.WIFI_SAP,
}


def device_streaming(
    profile_name: str = "profile9",
    interface: str = "usb",
):
    # Set up the device client config to specify the device to be connected to e.g. device serial number.
    # If nothing is specified, the first device in the list of connected devices will be connected to
    config = sdk_gen2.DeviceClientConfig()
    device_client.set_client_config(config)
    try:
        device = device_client.connect()
    except Exception as e:
        print(f"Failed to connect to device: {e}")
        return None

    # Set streaming config with profile name
    streaming_config = sdk_gen2.HttpStreamingConfig()
    streaming_config.profile_name = profile_name
    streaming_config.streaming_interface = STREAMING_INTERFACE_MAP[interface]
    device.set_streaming_config(streaming_config)

    # Start and stop recording
    device.start_streaming()
    return device


class AriaRawMessage:
    def __init__(self, shared_message: sdk_gen2.SharedMessage):
        self.id = shared_message.id
        self.payload = shared_message.payload.as_memoryview()

    def to_shared_message(self):
        if self.payload is None:
            return None
        return sdk_gen2.SharedMessage(self.id, self.payload)


def raw_message_callback(message, offset):
    """
    Universal raw message callback that handles all sensor types.

    Converts raw flatbuffer messages to typed data and prints basic information.

    Args:
        message: SharedMessage containing the raw flatbuffer data
        offset: Payload offset (not used in this example)
    """
    custom_message = AriaRawMessage(message)
    shared_message = custom_message.to_shared_message()

    if shared_message is None:
        return

    try:
        # Image data (SLAM, ET, RGB cameras)
        if shared_message.id == sdk_gen2.MessageType.SLAM_CAMERA_FRAME:
            image_data, image_record = converter.to_image_data_and_record(
                shared_message
            )
            if image_data is not None:
                print(
                    f"[SLAM Camera] Size: {image_data.get_width()}x{image_data.get_height()}, "
                    f"Timestamp: {image_record.capture_timestamp_ns} ns, "
                    f"Camera ID: {image_record.camera_id}"
                )
            else:
                raise Exception(
                    f"Cannot convert {sdk_gen2.MessageType.to_string(shared_message.id)}"
                )

        elif shared_message.id == sdk_gen2.MessageType.ET_CAMERA_FRAME:
            image_data, image_record = converter.to_image_data_and_record(
                shared_message
            )
            if image_data is not None:
                print(
                    f"[ET Camera] Size: {image_data.get_width()}x{image_data.get_height()}, "
                    f"Timestamp: {image_record.capture_timestamp_ns} ns, "
                    f"Camera ID: {image_record.camera_id}"
                )
            else:
                raise Exception(
                    f"Cannot convert {sdk_gen2.MessageType.to_string(shared_message.id)}"
                )

        elif shared_message.id == sdk_gen2.MessageType.POV_CAMERA_FRAME:
            image_data, image_record = converter.to_image_data_and_record(
                shared_message
            )
            if image_data is not None:
                print(
                    f"[RGB Camera] Size: {image_data.get_width()}x{image_data.get_height()}, "
                    f"Timestamp: {image_record.capture_timestamp_ns} ns, "
                    f"Camera ID: {image_record.camera_id}"
                )
            else:
                raise Exception(
                    f"Cannot convert {sdk_gen2.MessageType.to_string(shared_message.id)}"
                )

        # Audio data
        elif shared_message.id == sdk_gen2.MessageType.AUDIO_REC_DATA:
            audio_data, audio_record = converter.to_audio(shared_message)
            if audio_data is not None:
                print(
                    f"[Audio] Samples: {len(audio_data.data)}, "
                    f"Timestamps: {len(audio_record.capture_timestamps_ns)}, "
                    f"Capture timestamp: {audio_record.capture_timestamps_ns[0] if audio_record.capture_timestamps_ns else 0} ns"
                )
            else:
                raise Exception(
                    f"Cannot convert {sdk_gen2.MessageType.to_string(shared_message.id)}"
                )

        # IMU data
        elif shared_message.id == sdk_gen2.MessageType.IMU_EVENT:
            imu_data_list = converter.to_imu(shared_message)
            if imu_data_list is not None and len(imu_data_list) > 0:
                imu_data = imu_data_list[0]
                print(
                    f"[IMU] Accel: [{imu_data.accel_msec2[0]:.3f}, {imu_data.accel_msec2[1]:.3f}, {imu_data.accel_msec2[2]:.3f}] m/s², "
                    f"Gyro: [{imu_data.gyro_radsec[0]:.3f}, {imu_data.gyro_radsec[1]:.3f}, {imu_data.gyro_radsec[2]:.3f}] rad/s, "
                    f"Timestamp: {imu_data.capture_timestamp_ns} ns, "
                    f"Count: {len(imu_data_list)} samples"
                )
            else:
                raise Exception(
                    f"Cannot convert {sdk_gen2.MessageType.to_string(shared_message.id)}"
                )

        # Magnetometer data
        elif shared_message.id == sdk_gen2.MessageType.MAG_EVENT:
            mag_data_list = converter.to_magnetometer(shared_message)
            if mag_data_list is not None and len(mag_data_list) > 0:
                mag_data = mag_data_list[0]
                print(
                    f"[Magnetometer] Mag: [{mag_data.mag_tesla[0]:.6f}, {mag_data.mag_tesla[1]:.6f}, {mag_data.mag_tesla[2]:.6f}] T, "
                    f"Timestamp: {mag_data.capture_timestamp_ns} ns, "
                    f"Count: {len(mag_data_list)} samples"
                )
            else:
                raise Exception(
                    f"Cannot convert {sdk_gen2.MessageType.to_string(shared_message.id)}"
                )

        # Barometer data
        elif shared_message.id == sdk_gen2.MessageType.BARO_EVENT:
            baro_data = converter.to_barometer(shared_message)
            if baro_data is not None:
                print(
                    f"[Barometer] Pressure: {baro_data.pressure:.2f} Pa, "
                    f"Temperature: {baro_data.temperature:.2f} °C, "
                    f"Timestamp: {baro_data.capture_timestamp_ns} ns"
                )
            else:
                raise Exception(
                    f"Cannot convert {sdk_gen2.MessageType.to_string(shared_message.id)}"
                )

        # GPS/GNSS data
        elif shared_message.id == sdk_gen2.MessageType.GNSS_EVENT:
            gnss_data = converter.to_gnss(message)
            if gnss_data is not None:
                print(
                    f"[GNSS] Latitude: {gnss_data.latitude:.6f}°, "
                    f"Longitude: {gnss_data.longitude:.6f}°, "
                    f"Altitude: {gnss_data.altitude:.2f} m, "
                    f"Accuracy: {gnss_data.accuracy:.2f} m, "
                    f"Provider: {gnss_data.provider}, "
                    f"Timestamp: {gnss_data.capture_timestamp_ns} ns"
                )
            else:
                raise Exception(
                    f"Cannot convert {sdk_gen2.MessageType.to_string(shared_message.id)}"
                )

        # Phone location data
        elif shared_message.id == sdk_gen2.MessageType.PHONE_LOCATION_DATA:
            phone_location = converter.to_phone_location(shared_message)
            if phone_location is not None:
                print(
                    f"[Phone Location] Latitude: {phone_location.latitude:.6f}°, "
                    f"Longitude: {phone_location.longitude:.6f}°, "
                    f"Altitude: {phone_location.altitude:.2f} m, "
                    f"Accuracy: {phone_location.accuracy:.2f} m, "
                    f"Provider: {phone_location.provider}, "
                    f"Timestamp: {phone_location.capture_timestamp_ns} ns"
                )
            else:
                raise Exception(
                    f"Cannot convert {sdk_gen2.MessageType.to_string(shared_message.id)}"
                )

        # PPG data
        elif shared_message.id == sdk_gen2.MessageType.PPG_EVENT:
            ppg_data = converter.to_ppg(shared_message)
            if ppg_data is not None:
                print(
                    f"[PPG] Value: {ppg_data.value:.2f}, "
                    f"Timestamp: {ppg_data.capture_timestamp_ns} ns"
                )

        # Bluetooth beacon data
        elif shared_message.id == sdk_gen2.MessageType.BLE_BEACONS:
            ble_beacons = converter.to_bluetooth_beacon(shared_message)
            if ble_beacons is not None and len(ble_beacons) > 0:
                print(
                    f"[Bluetooth Beacons] Count: {len(ble_beacons)}, "
                    f"First beacon - ID: {ble_beacons[0].unique_id}, "
                    f"RSSI: {ble_beacons[0].rssi} dBm, "
                    f"Frequency: {ble_beacons[0].freq_mhz} MHz, "
                    f"Timestamp: {ble_beacons[0].board_timestamp_ns} ns"
                )
            else:
                raise Exception(
                    f"Cannot convert {sdk_gen2.MessageType.to_string(shared_message.id)}"
                )

        # WiFi beacon data
        elif shared_message.id == sdk_gen2.MessageType.WIFI_BEACONS:
            wifi_beacons = converter.to_wifi_beacon(shared_message)
            if wifi_beacons is not None and len(wifi_beacons) > 0:
                print(
                    f"[WiFi Beacons] Count: {len(wifi_beacons)}, "
                    f"First beacon - SSID: {wifi_beacons[0].ssid}, "
                    f"BSSID: {wifi_beacons[0].bssid_mac}, "
                    f"RSSI: {wifi_beacons[0].rssi} dBm, "
                    f"Frequency: {wifi_beacons[0].freq_mhz} MHz, "
                    f"Timestamp: {wifi_beacons[0].board_timestamp_ns} ns"
                )
            else:
                raise Exception(
                    f"Cannot convert {sdk_gen2.MessageType.to_string(shared_message.id)}"
                )

        # Eye gaze data
        elif shared_message.id == sdk_gen2.MessageType.MP_ET_RESULT:
            eyegaze_data = converter.to_eye_gaze(shared_message)
            if eyegaze_data is not None:
                print(
                    f"[Eye Gaze] Yaw: {eyegaze_data.yaw:.3f} rad, "
                    f"Pitch: {eyegaze_data.pitch:.3f} rad, "
                    f"Depth: {eyegaze_data.depth:.3f} m, "
                    f"Timestamp: {eyegaze_data.tracking_timestamp.total_seconds():.3f} s"
                )
            else:
                raise Exception(
                    f"Cannot convert {sdk_gen2.MessageType.to_string(shared_message.id)}"
                )

        # Hand tracking data
        elif shared_message.id == sdk_gen2.MessageType.MP_HT_RESULT:
            handtracking_data = converter.to_hand_pose(shared_message)
            if handtracking_data is not None:
                left_status = (
                    "detected"
                    if handtracking_data.left_hand is not None
                    else "not detected"
                )
                right_status = (
                    "detected"
                    if handtracking_data.right_hand is not None
                    else "not detected"
                )
                print(
                    f"[Hand Tracking] Left hand: {left_status}, "
                    f"Right hand: {right_status}, "
                    f"Timestamp: {handtracking_data.tracking_timestamp.total_seconds():.3f} s"
                )
            else:
                raise Exception(
                    f"Cannot convert {sdk_gen2.MessageType.to_string(shared_message.id)}"
                )

        # VIO (Visual Inertial Odometry) result
        elif shared_message.id == sdk_gen2.MessageType.MP_VIO_RESULT:
            vio_data = converter.to_vio_result(shared_message)
            if vio_data is not None:
                print(
                    f"[VIO] timestamp {vio_data.capture_timestamp_ns} with transform_odometry_bodyimu: {vio_data.transform_odometry_bodyimu.rotation().log()} and {vio_data.transform_odometry_bodyimu.translation()} ns"
                )
            else:
                raise Exception(
                    f"Cannot convert {sdk_gen2.MessageType.to_string(shared_message.id)}"
                )

        # VIO high frequency pose
        elif shared_message.id == sdk_gen2.MessageType.MP_VIO_HIGH_FREQUENCY_POSE:
            vio_high_freq_list = converter.to_vio_high_freq_pose(shared_message)
            if vio_high_freq_list is not None and len(vio_high_freq_list) > 0:
                open_loop_traj_pose = vio_high_freq_list[0]
                translation = (
                    open_loop_traj_pose.transform_odometry_device.translation()
                )
                print(
                    f"[VIO High Freq] Translation: [{translation[0][0]:.3f}, {translation[0][1]:.3f}, {translation[0][2]:.3f}] m, "
                    f"Timestamp: {open_loop_traj_pose.tracking_timestamp.total_seconds():.3f} s, "
                    f"Count: {len(vio_high_freq_list)} poses"
                )
            else:
                raise Exception(
                    f"Cannot convert {sdk_gen2.MessageType.to_string(shared_message.id)}"
                )

    except Exception as e:
        print(f"[Error] Failed to process message ID {hex(shared_message.id)}: {e}")


def device_calib_callback(device_calib):
    """
    Calibration callback that receives device calibration data.

    This callback is triggered when calibration data is received from the device.
    The calibration is required for proper conversion of VIO, eye gaze, and hand pose data.

    Args:
        calib_json_str: Device calibration in JSON string format
    """
    global calibration_received

    print("[Calibration] Received device calibration")
    calib_json_str = calibration.device_calibration_to_json_string(device_calib)
    converter.set_calibration(calib_json_str)
    calibration_received = True

    print(
        "[Calibration] Calibration set in converter - VIO, eye gaze, and hand pose decoding enabled"
    )


def setup_streaming_receiver(device, enable_image_decoding):
    # setup the server to receive streaming data from the device
    # IP address : 0.0.0.0 means that the server is listening on all available interfaces
    # Port : 6768 is the port number that the server is listening on
    config = sdk_gen2.HttpServerConfig()
    config.address = "0.0.0.0"
    config.port = 6768

    # setup the receiver with raw stream enabled
    stream_receiver = receiver.StreamReceiver(
        enable_image_decoding=enable_image_decoding, enable_raw_stream=True
    )

    stream_receiver.set_server_config(config)

    # Register the calibration callback first (critical for VIO, eye gaze, and hand pose conversion)
    print("Registering calibration callback...")
    stream_receiver.register_device_calib_callback(device_calib_callback)

    # Register raw message callback
    print("Registering raw message callback...")
    stream_receiver.register_raw_message_callback(raw_message_callback)

    # start the server
    print("Starting streaming server...")
    stream_receiver.start_server()

    # Stream for 10 seconds
    print(f"Streaming for 10 seconds...")
    time.sleep(10)

    # stop streaming and terminate the server
    device.stop_streaming()
    time.sleep(2)

    # Stop server with proper callback cleanup
    stream_receiver.stop_server()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--decode-images",
        action="store_true",
        default=False,
        required=False,
    )
    parser.add_argument(
        "--profile-name",
        dest="profile_name",
        type=str,
        default="profile9",
        required=False,
        help="Name of the streaming profile to use (default: profile9)",
    )
    parser.add_argument(
        "--interface",
        dest="interface",
        type=str,
        choices=list(STREAMING_INTERFACE_MAP.keys()),
        default="usb",
        required=False,
        help="Streaming interface (default: usb). Use wifi_sta or wifi_sap when USB-NCM is not available.",
    )

    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    # update data converter decoder setting
    converter.set_python_image_decoding(args.decode_images)

    # setup device to start streaming
    device = device_streaming(
        profile_name=args.profile_name,
        interface=args.interface,
    )
    if device is None:
        exit(0)

    # setup streaming receiver to receive streaming data with raw callbacks
    setup_streaming_receiver(device, args.decode_images)
