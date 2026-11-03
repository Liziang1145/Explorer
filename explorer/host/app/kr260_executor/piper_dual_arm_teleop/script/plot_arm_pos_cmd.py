import re
import sys
import matplotlib.pyplot as plt
from datetime import datetime

def parse_joint_positions(log_path):
    left_joint_data = []
    right_joint_data = []
    left_timestamps = []
    right_timestamps = []

    # Regex patterns
    timestamp_pattern = r"\[(.*?)\]"
    left_pattern = r"Set left arm joint position:([-\d., ]+)"
    right_pattern = r"Set right arm joint position:([-\d., ]+)"

    with open(log_path, 'r') as file:
        for line in file:
            ts_match = re.search(timestamp_pattern, line)
            timestamp = None
            if ts_match:
                try:
                    timestamp = datetime.strptime(ts_match.group(1), "%Y-%m-%d %H:%M:%S.%f")
                except ValueError:
                    continue

            if "Set left arm joint position:" in line:
                match = re.search(left_pattern, line)
                if match:
                    values = [float(v.strip()) for v in match.group(1).split(",")]
                    left_joint_data.append(values)
                    left_timestamps.append(timestamp)

            elif "Set right arm joint position:" in line:
                match = re.search(right_pattern, line)
                if match:
                    values = [float(v.strip()) for v in match.group(1).split(",")]
                    right_joint_data.append(values)
                    right_timestamps.append(timestamp)

    return left_timestamps, left_joint_data, right_timestamps, right_joint_data

def plot_dual_arm_joint_positions(left_timestamps, left_data, right_timestamps, right_data):
    fig, (ax_left, ax_right) = plt.subplots(1, 2, figsize=(14, 6), sharex=True)
    fig.suptitle("Arm Joint Position Commands")

    if left_data:
        left_data_T = list(zip(*left_data))
        dof_left = len(left_data_T)
        time_left = [(t - left_timestamps[0]).total_seconds() for t in left_timestamps]
        for i in range(dof_left):
            ax_left.plot(time_left, left_data_T[i], label=f'Joint {i+1}')
        ax_left.set_title("Left Arm")
        ax_left.set_ylabel("Joint Position (rad)")
        ax_left.set_xlabel("Time (s)")
        ax_left.grid(True)
        ax_left.legend()

    if right_data:
        right_data_T = list(zip(*right_data))
        dof_right = len(right_data_T)
        time_right = [(t - right_timestamps[0]).total_seconds() for t in right_timestamps]
        for i in range(dof_right):
            ax_right.plot(time_right, right_data_T[i], label=f'Joint {i+1}')
        ax_right.set_title("Right Arm")
        ax_right.set_ylabel("Joint Position (rad)")
        ax_right.set_xlabel("Time (s)")
        ax_right.grid(True)
        ax_right.legend()

    plt.tight_layout(rect=[0, 0.03, 1, 0.95])
    plt.show()

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python3 plot_arm_pos_cmd.py <log_file_path>")
        sys.exit(1)

    log_file_path = sys.argv[1]
    try:
        l_times, l_data, r_times, r_data = parse_joint_positions(log_file_path)
        plot_dual_arm_joint_positions(l_times, l_data, r_times, r_data)
    except FileNotFoundError:
        print(f"Error: File not found: {log_file_path}")
        sys.exit(1)
