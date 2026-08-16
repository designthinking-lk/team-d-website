import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import seaborn as sns

def analyze_advanced_gaze(csv_file_path, output_image="advanced_gaze_report1.png"):
    # 1. Load and clean
    df = pd.read_csv(csv_file_path)
    df = df[df['combined_gaze_valid'] == True].copy()
    
    # 2. Coordinate Transformations
    df['yaw_deg'] = np.degrees(df['yaw'])
    df['pitch_deg'] = np.degrees(df['pitch'])
    
    # Convert timestamps from nanoseconds to relative seconds
    t0 = df['timestamp_ns'].iloc[0]
    df['time_sec'] = (df['timestamp_ns'] - t0) / 1e9
    
    # 3. Categorize Gaze Zones
    # Yaw: Left (< -12°), Center (-12° to 12°), Right (> 12°)
    # Pitch: Looking Down/Notes (< -15°)
    def assign_zone(row):
        if row['pitch_deg'] < -15.0 or (pd.notna(row['depth']) and row['depth'] < 0.8):
            return 'Notes/Floor'
        elif row['yaw_deg'] < -12.0:
            return 'Left Audience'
        elif row['yaw_deg'] > 12.0:
            return 'Right Audience'
        else:
            return 'Center Audience'

    df['zone'] = df.apply(assign_zone, axis=1)

    # 4. Compute Fixation vs. Saccade Metrics
    dt = df['time_sec'].diff().fillna(0.033)
    d_yaw = df['yaw_deg'].diff().fillna(0)
    d_pitch = df['pitch_deg'].diff().fillna(0)
    angular_distance = np.sqrt(d_yaw**2 + d_pitch**2)
    angular_velocity = angular_distance / np.where(dt == 0, 0.033, dt) # degrees/second

    # Standard threshold: velocities < 35 deg/s count as fixation (holding gaze)
    df['is_fixation'] = angular_velocity < 35.0
    
    # Estimate average fixation duration
    fixation_groups = (~df['is_fixation']).cumsum()[df['is_fixation']]
    fixation_durations = df.groupby(fixation_groups)['time_sec'].apply(lambda x: x.iloc[-1] - x.iloc[0])
    avg_fixation = fixation_durations[fixation_durations > 0.1].mean() if len(fixation_durations) > 0 else 0.0

    # 5. Zone Percentages
    zone_counts = df['zone'].value_counts(normalize=True) * 100
    
    print("=== Advanced Gaze Diagnostic Summary ===")
    for zone_name, pct in zone_counts.items():
        print(f"  * {zone_name:16}: {pct:5.1f}%")
    print(f"  * Average Fixation Hold : {avg_fixation:.2f} seconds")
    print("=========================================")

    # 6. Multi-Panel Visual Dashboard
    fig = plt.figure(figsize=(14, 8))
    gs = gridspec.GridSpec(2, 2, height_ratios=[3, 1], width_ratios=[2, 1])

    # Panel 1: 2D Stage Field-of-View Heatmap (Yaw vs Pitch)
    ax_heat = fig.add_subplot(gs[0, 0])
    sns.kdeplot(
        x=df['yaw_deg'], 
        y=df['pitch_deg'], 
        cmap='mako', 
        fill=True, 
        thresh=0.05, 
        levels=15, 
        ax=ax_heat
    )
    
    # Define stage zones on the plot
    ax_heat.axvline(-12, color='white', linestyle='--', alpha=0.6, label='Zone Thresholds')
    ax_heat.axvline(12, color='white', linestyle='--', alpha=0.6)
    ax_heat.axhline(-15, color='orange', linestyle=':', linewidth=2, label='Notes/Podium Line')

    ax_heat.set_xlim(-45, 45)
    ax_heat.set_ylim(-40, 20)
    ax_heat.set_title("2D Audience Field-of-View Coverage (Stage Heatmap)", fontsize=12, pad=10)
    ax_heat.set_xlabel("Horizontal Gaze Angle (Left ← Yaw → Right) [deg]")
    ax_heat.set_ylabel("Vertical Gaze Angle (Down ← Pitch → Up) [deg]")
    ax_heat.legend(loc='upper right', framealpha=0.8)
    ax_heat.grid(True, alpha=0.2)

    # Panel 2: Audience Zone Distribution (Donut Chart)
    ax_donut = fig.add_subplot(gs[0, 1])
    colors = {'Left Audience': '#3498db', 'Center Audience': '#2ecc71', 'Right Audience': '#e67e22', 'Notes/Floor': '#e74c3c'}
    available_zones = df['zone'].unique()
    plot_colors = [colors.get(z, '#95a5a6') for z in zone_counts.index]
    
    wedges, texts, autotexts = ax_donut.pie(
        zone_counts.values, 
        labels=zone_counts.index, 
        autopct='%1.1f%%', 
        startangle=90, 
        colors=plot_colors, 
        wedgeprops=dict(width=0.4, edgecolor='w')
    )
    ax_donut.set_title("Room Engagement Share", fontsize=12)

    # Panel 3: Attention Timeline Ribbon (Chronological Coverage)
    ax_ribbon = fig.add_subplot(gs[1, :])
    zone_map_numeric = {'Left Audience': 1, 'Center Audience': 2, 'Right Audience': 3, 'Notes/Floor': 0}
    df['zone_code'] = df['zone'].map(zone_map_numeric)

    # Create a continuous time ribbon
    time_bins = np.linspace(df['time_sec'].min(), df['time_sec'].max(), 500)
    df['time_bin'] = pd.cut(df['time_sec'], bins=time_bins, labels=False)
    ribbon_series = df.groupby('time_bin')['zone_code'].agg(lambda x: x.mode()[0] if not x.empty else 2)

    ax_ribbon.imshow(
        [ribbon_series.values], 
        aspect='auto', 
        cmap=plt.matplotlib.colors.ListedColormap(['#e74c3c', '#3498db', '#2ecc71', '#e67e22']),
        extent=[df['time_sec'].min(), df['time_sec'].max(), 0, 1]
    )
    ax_ribbon.set_yticks([])
    ax_ribbon.set_title("Chronological Attention Flow Across Speech (Timeline Ribbon)", fontsize=11)
    ax_ribbon.set_xlabel("Elapsed Speech Time (Seconds)")

    plt.tight_layout()
    plt.savefig(output_image, dpi=300, bbox_inches='tight')
    print(f"\n[+] Advanced gaze dashboard saved to: {output_image}")
    plt.show()

if __name__ == "__main__":
    CSV_FILE = "output/eye_tracking/eye_tracking1.csv"
    analyze_advanced_gaze(CSV_FILE)