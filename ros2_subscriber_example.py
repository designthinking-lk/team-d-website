# Copyright 2016 Open Source Robotics Foundation, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import aria.oss_data_converter as data_converter
import aria.sdk_gen2 as sdk_gen2
import rclpy
from aria_data_types.msg import AriaRaw
from rclpy.node import Node
from std_msgs.msg import String

converter = data_converter.OssDataConverter()

# Global flag to track if calibration has been received
calibration_received = False


def raw_message_callback(raw_message: AriaRaw):
    """
    Universal raw message callback that handles all sensor types.

    Converts raw flatbuffer messages to typed data and prints basic information.

    Args:
        message: SharedMessage containing the raw flatbuffer data
        offset: Payload offset (not used in this example)
    """
    if raw_message.payload is None:
        print("No payload received, cannot decode this message")
        return

    message = sdk_gen2.SharedMessage(raw_message.id, raw_message.payload)
    message_id = raw_message.id

    try:
        # Image data (SLAM, ET, RGB cameras)
        if message_id == sdk_gen2.MessageType.SLAM_CAMERA_FRAME:
            image_data, image_record = converter.to_image_data_and_record(message)
            if image_data is not None:
                print(
                    f"[SLAM Camera] Size: {image_data.get_width()}x{image_data.get_height()}, "
                    f"Timestamp: {image_record.capture_timestamp_ns} ns, "
                    f"Camera ID: {image_record.camera_id}"
                )

        elif message_id == sdk_gen2.MessageType.ET_CAMERA_FRAME:
            image_data, image_record = converter.to_image_data_and_record(message)
            if image_data is not None:
                print(
                    f"[ET Camera] Size: {image_data.get_width()}x{image_data.get_height()}, "
                    f"Timestamp: {image_record.capture_timestamp_ns} ns, "
                    f"Camera ID: {image_record.camera_id}"
                )

        elif message_id == sdk_gen2.MessageType.POV_CAMERA_FRAME:
            image_data, image_record = converter.to_image_data_and_record(message)
            if image_data is not None:
                print(
                    f"[RGB Camera] Size: {image_data.get_width()}x{image_data.get_height()}, "
                    f"Timestamp: {image_record.capture_timestamp_ns} ns, "
                    f"Camera ID: {image_record.camera_id}"
                )

        # Audio data
        elif message_id == sdk_gen2.MessageType.AUDIO_REC_DATA:
            audio_data, audio_record = converter.to_audio(message)
            if audio_data is not None:
                print(
                    f"[Audio] Samples: {len(audio_data.data)}, "
                    f"Timestamps: {len(audio_record.capture_timestamps_ns)}, "
                    f"Capture timestamp: {audio_record.capture_timestamps_ns[0] if audio_record.capture_timestamps_ns else 0} ns"
                )

        # IMU data
        elif message_id == sdk_gen2.MessageType.IMU_EVENT:
            imu_data_list = converter.to_imu(message)
            if imu_data_list is not None and len(imu_data_list) > 0:
                imu_data = imu_data_list[0]
                print(
                    f"[IMU] Accel: [{imu_data.accel_msec2[0]:.3f}, {imu_data.accel_msec2[1]:.3f}, {imu_data.accel_msec2[2]:.3f}] m/s², "
                    f"Gyro: [{imu_data.gyro_radsec[0]:.3f}, {imu_data.gyro_radsec[1]:.3f}, {imu_data.gyro_radsec[2]:.3f}] rad/s, "
                    f"Timestamp: {imu_data.capture_timestamp_ns} ns, "
                    f"Count: {len(imu_data_list)} samples"
                )

        # Magnetometer data
        elif message_id == sdk_gen2.MessageType.MAG_EVENT:
            mag_data_list = converter.to_magnetometer(message)
            if mag_data_list is not None and len(mag_data_list) > 0:
                mag_data = mag_data_list[0]
                print(
                    f"[Magnetometer] Mag: [{mag_data.mag_tesla[0]:.6f}, {mag_data.mag_tesla[1]:.6f}, {mag_data.mag_tesla[2]:.6f}] T, "
                    f"Timestamp: {mag_data.capture_timestamp_ns} ns, "
                    f"Count: {len(mag_data_list)} samples"
                )

        # Barometer data
        elif message_id == sdk_gen2.MessageType.BARO_EVENT:
            baro_data = converter.to_barometer(message)
            if baro_data is not None:
                print(
                    f"[Barometer] Pressure: {baro_data.pressure:.2f} Pa, "
                    f"Temperature: {baro_data.temperature:.2f} °C, "
                    f"Timestamp: {baro_data.capture_timestamp_ns} ns"
                )

        # GPS/GNSS data
        elif message_id == sdk_gen2.MessageType.GNSS_EVENT:
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

        # Phone location data
        elif message_id == sdk_gen2.MessageType.PHONE_LOCATION_DATA:
            phone_location = converter.to_phone_location(message)
            if phone_location is not None:
                print(
                    f"[Phone Location] Latitude: {phone_location.latitude:.6f}°, "
                    f"Longitude: {phone_location.longitude:.6f}°, "
                    f"Altitude: {phone_location.altitude:.2f} m, "
                    f"Accuracy: {phone_location.accuracy:.2f} m, "
                    f"Provider: {phone_location.provider}, "
                    f"Timestamp: {phone_location.capture_timestamp_ns} ns"
                )

        # PPG data
        elif message_id == sdk_gen2.MessageType.PPG_EVENT:
            ppg_data = converter.to_ppg(message)
            if ppg_data is not None:
                print(
                    f"[PPG] Value: {ppg_data.value:.2f}, "
                    f"Timestamp: {ppg_data.capture_timestamp_ns} ns"
                )

        # Bluetooth beacon data
        elif message_id == sdk_gen2.MessageType.BLE_BEACONS:
            ble_beacons = converter.to_bluetooth_beacon(message)
            if ble_beacons is not None and len(ble_beacons) > 0:
                print(
                    f"[Bluetooth Beacons] Count: {len(ble_beacons)}, "
                    f"First beacon - ID: {ble_beacons[0].unique_id}, "
                    f"RSSI: {ble_beacons[0].rssi} dBm, "
                    f"Frequency: {ble_beacons[0].freq_mhz} MHz, "
                    f"Timestamp: {ble_beacons[0].board_timestamp_ns} ns"
                )

        # WiFi beacon data
        elif message_id == sdk_gen2.MessageType.WIFI_BEACONS:
            wifi_beacons = converter.to_wifi_beacon(message)
            if wifi_beacons is not None and len(wifi_beacons) > 0:
                print(
                    f"[WiFi Beacons] Count: {len(wifi_beacons)}, "
                    f"First beacon - SSID: {wifi_beacons[0].ssid}, "
                    f"BSSID: {wifi_beacons[0].bssid_mac}, "
                    f"RSSI: {wifi_beacons[0].rssi} dBm, "
                    f"Frequency: {wifi_beacons[0].freq_mhz} MHz, "
                    f"Timestamp: {wifi_beacons[0].board_timestamp_ns} ns"
                )

        # Eye gaze data
        elif message_id == sdk_gen2.MessageType.MP_ET_RESULT:
            eyegaze_data = converter.to_eye_gaze(message)
            if eyegaze_data is not None:
                print(
                    f"[Eye Gaze] Yaw: {eyegaze_data.yaw:.3f} rad, "
                    f"Pitch: {eyegaze_data.pitch:.3f} rad, "
                    f"Depth: {eyegaze_data.depth:.3f} m, "
                    f"Timestamp: {eyegaze_data.tracking_timestamp.total_seconds():.3f} s"
                )

        # Hand tracking data
        elif message_id == sdk_gen2.MessageType.MP_HT_RESULT:
            handtracking_data = converter.to_hand_pose(message)
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

        # VIO (Visual Inertial Odometry) result
        elif message_id == sdk_gen2.MessageType.MP_VIO_RESULT:
            vio_data = converter.to_vio_result(message)
            if vio_data is not None:
                print(
                    f"[VIO] timestamp {vio_data.capture_timestamp_ns} with transform_odometry_bodyimu: {vio_data.transform_odometry_bodyimu.rotation().log()} and {vio_data.transform_odometry_bodyimu.translation()} ns"
                )

        # VIO high frequency pose
        elif message_id == sdk_gen2.MessageType.MP_VIO_HIGH_FREQUENCY_POSE:
            vio_high_freq_list = converter.to_vio_high_freq_pose(message)
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

    except Exception as e:
        print(f"[Error] Failed to process message ID {hex(message_id)}: {e}")


class MinimalSubscriber(Node):
    def __init__(self):
        super().__init__("minimal_subscriber")
        self.subscription = self.create_subscription(
            AriaRaw, "aria_raw_message", self.listener_callback, 10
        )
        self.subscription  # prevent unused variable warning

        self.calib_sub = self.create_subscription(
            String, "calibration", self.calib_callback, 10
        )
        self.calib_sub  # prevent unused variable warning

    def listener_callback(self, msg):
        if calibration_received:
            raw_message_callback(msg)

    def calib_callback(self, msg):
        global calibration_received

        print("[Calibration] Received device calibration")

        if calibration_received is False:
            converter.set_calibration(msg.data)
            calibration_received = True

            print(
                "[Calibration] Calibration set in converter - VIO, eye gaze, and hand pose decoding enabled"
            )


def main(args=None):
    rclpy.init(args=args)

    minimal_subscriber = MinimalSubscriber()

    rclpy.spin(minimal_subscriber)

    # Destroy the node explicitly
    # (optional - otherwise it will be done automatically
    # when the garbage collector destroys the node object)
    minimal_subscriber.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
