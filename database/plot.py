# plot_anomaly_scores.py
"""
Visualize anomaly scores for the last 100 cycles
"""

import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
from datetime import datetime
from ml import ISBMDefectDetector

print("="*80)
print("ANOMALY SCORE VISUALIZATION")
print("="*80)
print()

# Configuration
MACHINE_ID = 60
MODEL_PATH = f"models/machine_{MACHINE_ID}_model.pkl"
N_CYCLES = 200  # Number of recent cycles to plot

# Load model
print("Loading model...")
detector = ISBMDefectDetector()

try:
    detector.load_model(MODEL_PATH)
    print(f"✓ Model loaded from {MODEL_PATH}")
except FileNotFoundError:
    print(f"✗ Model not found at {MODEL_PATH}")
    print("Run: python train_model.py first!")
    exit(1)

# Fetch data
print(f"Fetching last {N_CYCLES} cycles...")
df = detector.fetch_training_data(
    machine_id=MACHINE_ID,
    limit=N_CYCLES
)

if df.empty:
    print("✗ No data found")
    exit(1)

print(f"✓ Fetched {len(df)} cycles")

# Make predictions
print("Calculating anomaly scores...")
predictions, scores, alerts = detector.predict_batch(df)

df['prediction'] = predictions
df['anomaly_score'] = scores
df['alert_level'] = alerts

# Sort by timestamp (oldest to newest for better visualization)
df = df.sort_values('timestamp').reset_index(drop=True)

# Create figure with multiple subplots
fig, axes = plt.subplots(3, 1, figsize=(14, 10))
fig.suptitle(f'Anomaly Detection - Machine {MACHINE_ID} (Last {len(df)} Cycles)', 
             fontsize=16, fontweight='bold')

# Color coding
colors = []
for alert in df['alert_level']:
    if alert == 'HIGH':
        colors.append('red')
    elif alert == 'MEDIUM':
        colors.append('orange')
    else:
        colors.append('green')

# Plot 1: Anomaly Score over Time
ax1 = axes[0]
ax1.plot(df.index, df['anomaly_score'], 'b-', linewidth=1, alpha=0.5)
scatter = ax1.scatter(df.index, df['anomaly_score'], c=colors, s=50, alpha=0.7, edgecolors='black', linewidth=0.5)

# Add threshold line
threshold = -0.15  # Medium alert threshold
ax1.axhline(y=threshold, color='orange', linestyle='--', linewidth=2, label=f'Medium Alert Threshold ({threshold})')
ax1.axhline(y=0, color='gray', linestyle=':', linewidth=1, alpha=0.5)

# Highlight defects
defects = df[df['prediction'] == -1]
if len(defects) > 0:
    ax1.scatter(defects.index, defects['anomaly_score'], 
               color='red', s=200, marker='X', edgecolors='darkred', 
               linewidth=2, label=f'Defects ({len(defects)})', zorder=5)

ax1.set_xlabel('Cycle Number (Most Recent →)', fontsize=11)
ax1.set_ylabel('Anomaly Score', fontsize=11)
ax1.set_title('Anomaly Score Over Time', fontsize=12, fontweight='bold')
ax1.grid(True, alpha=0.3)
ax1.legend(loc='lower left')

# Add text annotation for defects
for idx, row in defects.iterrows():
    ax1.annotate(f"ID: {row['id']}", 
                xy=(idx, row['anomaly_score']), 
                xytext=(10, 10), 
                textcoords='offset points',
                fontsize=8,
                bbox=dict(boxstyle='round,pad=0.3', facecolor='yellow', alpha=0.7),
                arrowprops=dict(arrowstyle='->', connectionstyle='arc3,rad=0', color='red'))

# Plot 2: Distribution of Anomaly Scores (Histogram)
ax2 = axes[1]
n_bins = 30

# Separate normal and defects
normal_scores = df[df['prediction'] == 1]['anomaly_score']
defect_scores = df[df['prediction'] == -1]['anomaly_score']

ax2.hist(normal_scores, bins=n_bins, alpha=0.7, color='green', 
         edgecolor='black', label=f'Normal ({len(normal_scores)})')
if len(defect_scores) > 0:
    ax2.hist(defect_scores, bins=n_bins, alpha=0.7, color='red', 
            edgecolor='black', label=f'Defects ({len(defect_scores)})')

ax2.axvline(x=threshold, color='orange', linestyle='--', linewidth=2, 
           label=f'Medium Alert Threshold')
ax2.axvline(x=df['anomaly_score'].mean(), color='blue', linestyle=':', 
           linewidth=2, label=f"Mean ({df['anomaly_score'].mean():.3f})")

ax2.set_xlabel('Anomaly Score', fontsize=11)
ax2.set_ylabel('Frequency', fontsize=11)
ax2.set_title('Anomaly Score Distribution', fontsize=12, fontweight='bold')
ax2.legend()
ax2.grid(True, alpha=0.3, axis='y')

# Plot 3: Alert Level Summary (Bar Chart)
ax3 = axes[2]

alert_counts = df['alert_level'].value_counts()
alert_order = ['HIGH', 'MEDIUM', 'LOW']
alert_colors_bar = {'HIGH': 'red', 'MEDIUM': 'orange', 'LOW': 'green'}

counts = [alert_counts.get(level, 0) for level in alert_order]
bars = ax3.bar(alert_order, counts, color=[alert_colors_bar[level] for level in alert_order],
               edgecolor='black', linewidth=1.5, alpha=0.8)

# Add count labels on bars
for bar, count in zip(bars, counts):
    height = bar.get_height()
    ax3.text(bar.get_x() + bar.get_width()/2., height,
            f'{int(count)}\n({count/len(df)*100:.1f}%)',
            ha='center', va='bottom', fontsize=11, fontweight='bold')

ax3.set_ylabel('Number of Cycles', fontsize=11)
ax3.set_title('Alert Level Distribution', fontsize=12, fontweight='bold')
ax3.grid(True, alpha=0.3, axis='y')
ax3.set_ylim(0, max(counts) * 1.15)  # Extra space for labels

# Add statistics text box
stats_text = f"""
Statistics (Last {len(df)} Cycles):
━━━━━━━━━━━━━━━━━━━━━━━━━
- Total Cycles: {len(df)}
- Defects: {len(defects)} ({len(defects)/len(df)*100:.1f}%)
- Mean Score: {df['anomaly_score'].mean():.4f}
- Min Score: {df['anomaly_score'].min():.4f}
- Max Score: {df['anomaly_score'].max():.4f}
- Std Dev: {df['anomaly_score'].std():.4f}

Date Range:
- From: {df['timestamp'].min().strftime('%Y-%m-%d %H:%M')}
- To: {df['timestamp'].max().strftime('%Y-%m-%d %H:%M')}
"""

plt.figtext(0.02, 0.02, stats_text, fontsize=9, family='monospace',
            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

plt.tight_layout(rect=[0, 0.12, 1, 0.96])

# Save figure
timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
filename = f'anomaly_scores_machine{MACHINE_ID}_{timestamp}.png'
plt.savefig(filename, dpi=300, bbox_inches='tight')
print(f"\n✓ Plot saved to: {filename}")

# Display
plt.show()

# Print detailed defect information
if len(defects) > 0:
    print("\n" + "="*80)
    print("DETAILED DEFECT INFORMATION")
    print("="*80)
    print(defects[['id', 'timestamp', 'anomaly_score', 'alert_level']].to_string(index=False))
else:
    print("\n✓ No defects detected in the last {} cycles".format(len(df)))

print("\n" + "="*80)
print("VISUALIZATION COMPLETE")
print("="*80)