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

import aria.sdk_gen2 as sdk_gen2
import aria.stream_receiver as receiver
import rclpy
from aria_data_types.msg import AriaRaw
from projectaria_tools.core import calibration
from rclpy.node import Node
from std_msgs.msg import String

# Set up the device client to initiate connection to the device
device_client = sdk_gen2.DeviceClient()
calibration_json = str()


def device_streaming():
    # Set up the device client config to specify the device to be connected to e.g. device serial number.
    # If nothing is specified, the first device in the list of connected devices will be connected to
    config = sdk_gen2.DeviceClientConfig()
    device_client.set_client_config(config)
    device = device_client.connect()

    # Set recording config with profile name
    streaming_config = sdk_gen2.HttpStreamingConfig()
    streaming_config.profile_name = "profile9"
    streaming_config.streaming_interface = sdk_gen2.StreamingInterface.USB_NCM
    device.set_streaming_config(streaming_config)

    # Start and stop recording
    device.start_streaming()
    return device


class MinimalPublisher(Node):
    def __init__(self):
        super().__init__("minimal_publisher")
        self.event_pub = self.create_publisher(AriaRaw, "aria_raw_message", 1000)
        self.timer_pub = self.create_publisher(String, "calibration", 100)
        self.timer_period = 0.1  # 10 Hz
        self.timer = self.create_timer(self.timer_period, self.calib_publisher_callback)
        self.calib_msg = None
        # setup streaming receiver to receive streaming data and publish
        self.setup_streaming_receiver()

    def calib_publisher_callback(self):
        # publish calibration periodically
        if self.calib_msg is not None:
            self.timer_pub.publish(self.calib_msg)
            self.get_logger().info(
                f"Published calibration on periodic_topic: /calibration"
            )

    def stream_receiver_device_calib_callback(self, device_calib):
        # set the calibration message
        self.calib_msg = String()
        self.calib_msg.data = calibration.device_calibration_to_json_string(
            device_calib
        )

    def stream_receiver_raw_message_callback(self, message, offset):
        ros2_msg = AriaRaw()
        ros2_msg.id = message.id
        ros2_msg.payload = message.payload.as_memoryview()
        self.event_pub.publish(ros2_msg)
        self.get_logger().info(
            f"Received and published message: ID={sdk_gen2.MessageType.to_string(ros2_msg.id)}, payload length={len(ros2_msg.payload)}"
        )

    def setup_streaming_receiver(self):
        # setup the server to receive streaming data from the device
        # IP address : 0.0.0.0 means that the server is listening on all available interfaces
        # Port : 6768 is the port number that the server is listening on
        config = sdk_gen2.HttpServerConfig()
        config.address = "0.0.0.0"
        config.port = 6768

        # setup the receiver
        stream_receiver = receiver.StreamReceiver(
            enable_image_decoding=True, enable_raw_stream=True
        )
        stream_receiver.set_server_config(config)

        # register callbacks for each type of data
        stream_receiver.register_device_calib_callback(
            self.stream_receiver_device_calib_callback
        )
        stream_receiver.register_raw_message_callback(
            self.stream_receiver_raw_message_callback
        )
        # start the server
        stream_receiver.start_server()


def main(args=None):
    rclpy.init(args=args)

    device = device_streaming()

    minimal_publisher = MinimalPublisher()

    rclpy.spin(minimal_publisher)

    # Destroy the node explicitly
    # (optional - otherwise it will be done automatically
    # when the garbage collector destroys the node object)
    minimal_publisher.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
