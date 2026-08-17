from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
import seaborn as sns


ZONE_COLORS = {
    "Left Audience": "#3498db",
    "Center Audience": "#2ecc71",
    "Right Audience": "#e67e22",
    "Notes/Floor": "#e74c3c",
}


def is_valid_gaze(value):
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"true", "1", "yes"}


def gaze_output_paths(output_image):
    output_path = Path(output_image)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    return {
        "heatmap": output_path.with_name(f"{output_path.stem}_heatmap{output_path.suffix}"),
        "timeline": output_path.with_name(f"{output_path.stem}_timeline{output_path.suffix}"),
    }


def assign_zone(row):
    if row["pitch_deg"] < -15.0 or (pd.notna(row["depth"]) and row["depth"] < 0.8):
        return "Notes/Floor"
    if row["yaw_deg"] < -12.0:
        return "Left Audience"
    if row["yaw_deg"] > 12.0:
        return "Right Audience"
    return "Center Audience"


def build_ribbon_values(df):
    zone_map_numeric = {
        "Notes/Floor": 0,
        "Left Audience": 1,
        "Center Audience": 2,
        "Right Audience": 3,
    }
    df["zone_code"] = df["zone"].map(zone_map_numeric)

    if df["time_sec"].max() == df["time_sec"].min():
        return df["zone_code"].to_numpy()

    time_bins = np.linspace(df["time_sec"].min(), df["time_sec"].max(), 500)
    df["time_bin"] = pd.cut(df["time_sec"], bins=time_bins, labels=False)
    ribbon_series = df.groupby("time_bin")["zone_code"].agg(
        lambda x: x.mode()[0] if not x.empty else 2
    )
    return ribbon_series.values


def save_heatmap(df, output_path):
    fig, ax_heat = plt.subplots(figsize=(9, 6))
    try:
        sns.kdeplot(
            x=df["yaw_deg"],
            y=df["pitch_deg"],
            cmap="mako",
            fill=True,
            thresh=0.05,
            levels=15,
            ax=ax_heat,
        )
    except Exception:
        ax_heat.scatter(df["yaw_deg"], df["pitch_deg"], s=10, alpha=0.35, color="#0f766e")

    ax_heat.axvline(-12, color="white", linestyle="--", alpha=0.6, label="Audience zone threshold")
    ax_heat.axvline(12, color="white", linestyle="--", alpha=0.6)
    ax_heat.axhline(-15, color="orange", linestyle=":", linewidth=2, label="Notes/floor line")
    ax_heat.set_xlim(-45, 45)
    ax_heat.set_ylim(-40, 20)
    ax_heat.set_title("Gaze Heatmap", fontsize=13, pad=10)
    ax_heat.set_xlabel("Horizontal gaze angle (Left <- Yaw -> Right) [deg]")
    ax_heat.set_ylabel("Vertical gaze angle (Down <- Pitch -> Up) [deg]")
    ax_heat.legend(loc="upper right", framealpha=0.85)
    ax_heat.grid(True, alpha=0.2)
    plt.tight_layout()
    fig.savefig(output_path, dpi=240, bbox_inches="tight")
    plt.close(fig)


def save_timeline(df, output_path):
    ribbon_values = build_ribbon_values(df)
    colors = [
        ZONE_COLORS["Notes/Floor"],
        ZONE_COLORS["Left Audience"],
        ZONE_COLORS["Center Audience"],
        ZONE_COLORS["Right Audience"],
    ]
    legend_items = [
        Patch(facecolor=ZONE_COLORS["Left Audience"], label="Left"),
        Patch(facecolor=ZONE_COLORS["Center Audience"], label="Center"),
        Patch(facecolor=ZONE_COLORS["Right Audience"], label="Right"),
        Patch(facecolor=ZONE_COLORS["Notes/Floor"], label="Floor/Notes"),
    ]

    fig, ax_ribbon = plt.subplots(figsize=(11, 2.6))
    ax_ribbon.imshow(
        [ribbon_values],
        aspect="auto",
        cmap=plt.matplotlib.colors.ListedColormap(colors),
        extent=[df["time_sec"].min(), df["time_sec"].max(), 0, 1],
    )
    ax_ribbon.set_yticks([])
    ax_ribbon.set_title("Attention Timeline", fontsize=13, pad=10)
    ax_ribbon.set_xlabel("Elapsed speech time (seconds)")
    ax_ribbon.legend(
        handles=legend_items,
        ncol=4,
        loc="upper center",
        bbox_to_anchor=(0.5, -0.45),
        frameon=False,
    )
    plt.tight_layout()
    fig.savefig(output_path, dpi=240, bbox_inches="tight")
    plt.close(fig)


def analyze_advanced_gaze(csv_file_path, output_image="advanced_gaze_report.png", show=False):
    df = pd.read_csv(csv_file_path)
    df = df[df["combined_gaze_valid"].map(is_valid_gaze)].copy()
    if df.empty:
        print("[!] No valid eye tracking rows found; gaze images were not generated.")
        return None

    df["yaw_deg"] = np.degrees(df["yaw"])
    df["pitch_deg"] = np.degrees(df["pitch"])

    t0 = df["timestamp_ns"].iloc[0]
    df["time_sec"] = (df["timestamp_ns"] - t0) / 1e9
    df["zone"] = df.apply(assign_zone, axis=1)

    dt = df["time_sec"].diff().fillna(0.033)
    d_yaw = df["yaw_deg"].diff().fillna(0)
    d_pitch = df["pitch_deg"].diff().fillna(0)
    angular_distance = np.sqrt(d_yaw**2 + d_pitch**2)
    angular_velocity = angular_distance / np.where(dt == 0, 0.033, dt)
    df["is_fixation"] = angular_velocity < 35.0

    fixation_groups = (~df["is_fixation"]).cumsum()[df["is_fixation"]]
    fixation_durations = df.groupby(fixation_groups)["time_sec"].apply(
        lambda x: x.iloc[-1] - x.iloc[0]
    )
    avg_fixation = (
        fixation_durations[fixation_durations > 0.1].mean()
        if len(fixation_durations) > 0
        else 0.0
    )

    zone_counts = df["zone"].value_counts(normalize=True) * 100
    zone_percentages = {
        zone_name: round(float(zone_counts.get(zone_name, 0.0)), 1)
        for zone_name in ("Left Audience", "Center Audience", "Right Audience", "Notes/Floor")
    }
    total_duration = float(df["time_sec"].max() - df["time_sec"].min())
    yaw_min = float(df["yaw_deg"].min())
    yaw_max = float(df["yaw_deg"].max())
    pitch_min = float(df["pitch_deg"].min())
    pitch_max = float(df["pitch_deg"].max())

    print("=== Advanced Gaze Diagnostic Summary ===")
    for zone_name, pct in zone_percentages.items():
        print(f"  * {zone_name:16}: {pct:5.1f}%")
    print(f"  * Horizontal range    : {yaw_min:.1f} deg to {yaw_max:.1f} deg")
    print(f"  * Vertical range      : {pitch_min:.1f} deg to {pitch_max:.1f} deg")
    print(f"  * Average Fixation Hold : {avg_fixation:.2f} seconds")
    print("=========================================")

    output_paths = gaze_output_paths(output_image)
    save_heatmap(df, output_paths["heatmap"])
    save_timeline(df, output_paths["timeline"])
    print(f"\n[+] Gaze heatmap saved to: {output_paths['heatmap']}")
    print(f"[+] Gaze timeline saved to: {output_paths['timeline']}")
    if show:
        print("[!] show=True is ignored because plots are saved as separate dashboard images.")

    return {
        "image_path": str(output_paths["heatmap"]),
        "images": {
            "heatmap": str(output_paths["heatmap"]),
            "timeline": str(output_paths["timeline"]),
        },
        "duration_s": round(total_duration, 2),
        "valid_sample_count": int(len(df)),
        "yaw_range_deg": {
            "min": round(yaw_min, 1),
            "max": round(yaw_max, 1),
            "span": round(yaw_max - yaw_min, 1),
        },
        "pitch_range_deg": {
            "min": round(pitch_min, 1),
            "max": round(pitch_max, 1),
            "span": round(pitch_max - pitch_min, 1),
        },
        "zone_percentages": zone_percentages,
        "average_fixation_s": round(float(avg_fixation or 0.0), 2),
    }


if __name__ == "__main__":
    CSV_FILE = "output/eye_tracking/eye_tracking1.csv"
    analyze_advanced_gaze(CSV_FILE)
