#!/usr/bin/env fbpython
# (c) Meta Platforms, Inc. and affiliates. Confidential and proprietary.

import argparse

import aria.sdk_gen2 as sdk_gen2


def device_connect(serial):
    # Set up the device client to initiate connection to the device
    device_client = sdk_gen2.DeviceClient()
    config = sdk_gen2.DeviceClientConfig()
    device_client.set_client_config(config)

    # try to connect to the device
    # If a serial is provided, connect to that specific device
    # Otherwise, connect to the first available device
    try:
        device = device_client.connect(sdk_gen2.DeviceTarget(serial=serial))
        print(f"Successfully connected to device {device.connection_id()}")
    except Exception:
        print("Failed to connect to device.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--serial",
        dest="serial",
        type=str,
        default="",
        required=False,
        help="Serial number of the device which will be connected. (e.g. 1M0YDB5H7B0020)",
    )

    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    device_connect(args.serial)
