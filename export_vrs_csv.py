import os
import csv
import json
from projectaria_tools.core import data_provider
from projectaria_tools.core.sensor_data import TimeDomain

def ensure_dir(path):
    if not os.path.exists(path):
        os.makedirs(path)

def export_vrs_to_csv(vrs_path):
    if not os.path.exists(vrs_path):
        print(f"Error: Could not find {vrs_path}")
        return

    provider = data_provider.create_vrs_data_provider(vrs_path)
    if not provider:
        print("Failed to open VRS file. It might be corrupted or incomplete.")
        return

    print(f"Successfully opened {vrs_path}")
    print("-" * 40)

    # Directories for output
    base_out = "output"
    dirs = {
        "Eye Tracking": os.path.join(base_out, "eye_tracking"),
        "Hand Gesture": os.path.join(base_out, "hand_gesture"),
        "PPG": os.path.join(base_out, "ppg"),
        "Voice": os.path.join(base_out, "voice")
    }
    for d in dirs.values():
        ensure_dir(d)

    # Map stream labels to Stream IDs
    available_streams = {}
    streams = provider.get_all_streams()
    for stream_id in streams:
        label = provider.get_label_from_stream_id(stream_id)
        if label:
            available_streams[label.lower()] = stream_id

    # Target stream keywords
    target_sensors = {
        "Eye Tracking": ["eyegaze", "camera-et"],
        "Hand Gesture": ["handtracking", "hand"],
        "PPG": ["ppg"],
        "Voice": ["mic", "audio"]
    }

    # Extract data for each target
    for sensor_name, keywords in target_sensors.items():
        target_id = None
        for key in keywords:
            for stream_label, stream_id in available_streams.items():
                if key in stream_label:
                    target_id = stream_id
                    break
            if target_id:
                break

        if not target_id:
            print(f"[!] {sensor_name} data not found in this recording.")
            continue

        num_records = provider.get_num_data(target_id)
        print(f"\nExporting {sensor_name} to CSV (Total Records: {num_records})...")

        out_csv_path = os.path.join(dirs[sensor_name], f"{sensor_name.lower().replace(' ', '_')}1.csv")
        
        with open(out_csv_path, 'w', newline='') as f:
            writer = csv.writer(f)
            
            # Write appropriate headers
            if sensor_name == "Eye Tracking":
                writer.writerow(['timestamp_ns', 'yaw', 'pitch', 'depth', 'vergence', 'combined_gaze_valid'])
            elif sensor_name == "Hand Gesture":
                writer.writerow([
                    'timestamp_ns', 
                    'left_confidence', 'left_wrist_x', 'left_wrist_y', 'left_wrist_z', 'left_palm_x', 'left_palm_y', 'left_palm_z',
                    'right_confidence', 'right_wrist_x', 'right_wrist_y', 'right_wrist_z', 'right_palm_x', 'right_palm_y', 'right_palm_z'
                ])
            elif sensor_name == "PPG":
                writer.writerow(['timestamp_ns', 'integration_time_us', 'led_current_ma', 'value'])
            elif sensor_name == "Voice":
                writer.writerow(['timestamp_ns', 'num_samples', 'audio_samples'])

            # Loop through all records
            for i in range(num_records):
                sensor_data = provider.get_sensor_data_by_index(target_id, i)
                timestamp_ns = sensor_data.get_time_ns(TimeDomain.DEVICE_TIME)
                
                # Fetch raw payload gracefully
                raw_data = None
                for method in ['eye_gaze_data', 'hand_pose_data', 'ppg_data', 'image_data_and_record', 'audio_data_and_record', 'imu_data', 'barometer_data', 'magnetometer_data', 'gps_data', 'wps_data', 'bluetooth_data']:
                    if hasattr(sensor_data, method):
                        try:
                            raw_data = getattr(sensor_data, method)()
                            if raw_data is not None:
                                break
                        except RuntimeError:
                            continue

                if not raw_data:
                    continue

                # Write rows depending on data type
                if sensor_name == "Eye Tracking":
                    yaw = getattr(raw_data, 'yaw', '')
                    pitch = getattr(raw_data, 'pitch', '')
                    depth = getattr(raw_data, 'depth', '')
                    vergence = getattr(raw_data, 'vergence', '')
                    valid = getattr(raw_data, 'combined_gaze_valid', '')
                    writer.writerow([timestamp_ns, yaw, pitch, depth, vergence, valid])
                
                elif sensor_name == "Hand Gesture":
                    row = [timestamp_ns]
                    
                    left_hand = getattr(raw_data, 'left_hand', None)
                    if left_hand:
                        conf = getattr(left_hand, 'confidence', '')
                        try:
                            w = left_hand.get_wrist_position_device()
                            p = left_hand.get_palm_position_device()
                            row.extend([conf, w[0], w[1], w[2], p[0], p[1], p[2]])
                        except Exception:
                            row.extend([conf, '', '', '', '', '', ''])
                    else:
                        row.extend(['', '', '', '', '', '', ''])
                        
                    right_hand = getattr(raw_data, 'right_hand', None)
                    if right_hand:
                        conf = getattr(right_hand, 'confidence', '')
                        try:
                            w = right_hand.get_wrist_position_device()
                            p = right_hand.get_palm_position_device()
                            row.extend([conf, w[0], w[1], w[2], p[0], p[1], p[2]])
                        except Exception:
                            row.extend([conf, '', '', '', '', '', ''])
                    else:
                        row.extend(['', '', '', '', '', '', ''])
                    
                    writer.writerow(row)
                    
                elif sensor_name == "PPG":
                    t = getattr(raw_data, 'capture_timestamp_ns', timestamp_ns)
                    it = getattr(raw_data, 'integration_time_us', '')
                    led = getattr(raw_data, 'led_current_ma', '')
                    val = getattr(raw_data, 'value', '')
                    writer.writerow([t, it, led, val])
                    
                elif sensor_name == "Voice":
                    # Audio data is a tuple (AudioData, AudioDataRecord)
                    if isinstance(raw_data, tuple) and len(raw_data) > 0:
                        audio_data = raw_data[0]
                        if hasattr(audio_data, 'data'):
                            arr = audio_data.data  # 'data' is a property, not a method
                            num = len(arr)
                            # Convert array to JSON string format to keep row count manageable
                            arr_str = json.dumps(arr)
                            writer.writerow([timestamp_ns, num, arr_str])

    print("\n[+] Successfully exported all requested files to 'output/' folders.")

if __name__ == "__main__":
    VRS_FILE_PATH = "recordings/Aria-rec2-team5_20260816_151844.vrs"
    export_vrs_to_csv(VRS_FILE_PATH)
