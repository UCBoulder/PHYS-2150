"""
Plot long-term stability test results
"""

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.ticker import ScalarFormatter
import sys

# Check if filename provided
if len(sys.argv) > 1:
    filename = sys.argv[1]
else:
    filename = "longterm_stability_20251008_115736.csv"

print(f"Plotting data from: {filename}")

# Read metadata from file
metadata = {}
with open(filename, 'r') as f:
    for line in f:
        if line.startswith('#'):
            if ':' in line:
                key, value = line[1:].split(':', 1)
                metadata[key.strip()] = value.strip()
        elif line.startswith('Time'):
            break

# Load data
data = np.genfromtxt(filename, delimiter=',', skip_header=7, names=True)
time_seconds = data['Time_s']
current_A = data['Current_A']
voltage_V = data['Voltage_V']

# Convert time to minutes
time_minutes = time_seconds / 60

# Calculate statistics
mean_current = np.mean(current_A)
std_current = np.std(current_A)
cv_current = 100 * std_current / mean_current
min_current = np.min(current_A)
max_current = np.max(current_A)

mean_voltage = np.mean(voltage_V)
std_voltage = np.std(voltage_V)
cv_voltage = 100 * std_voltage / mean_voltage

# Create figure with 2 subplots
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10))
fig.suptitle('Long-Term Stability Test - PicoScope EQE Measurement', 
             fontsize=16, fontweight='bold')

# ============================================================================
# SUBPLOT 1: Current vs Time
# ============================================================================
ax1.plot(time_minutes, current_A * 1e9, 'o-', color='#2E86AB', 
         linewidth=2, markersize=8, markeredgecolor='white', markeredgewidth=1,
         label='Measured Current')

# Add mean line
ax1.axhline(mean_current * 1e9, color='green', linestyle='--', linewidth=2,
            label=f'Mean = {mean_current*1e9:.2f} nA')

# Add ±1σ band
ax1.fill_between(time_minutes, 
                 (mean_current - std_current) * 1e9,
                 (mean_current + std_current) * 1e9,
                 alpha=0.2, color='green', label=f'±1σ = {std_current*1e9:.2f} nA')

# Add ±2σ lines
ax1.axhline((mean_current + 2*std_current) * 1e9, color='orange', 
            linestyle=':', linewidth=1.5, alpha=0.7, label='±2σ')
ax1.axhline((mean_current - 2*std_current) * 1e9, color='orange', 
            linestyle=':', linewidth=1.5, alpha=0.7)

ax1.set_xlabel('Time (minutes)', fontsize=12, fontweight='bold')
ax1.set_ylabel('Current (nA)', fontsize=12, fontweight='bold')
ax1.set_title('Photocurrent Stability Over Time', fontsize=14, fontweight='bold')
ax1.grid(True, alpha=0.3, linestyle='--')
ax1.legend(loc='best', fontsize=10)

# Add statistics box
stats_text = f'CV = {cv_current:.2f}%\n'
stats_text += f'Range = {(max_current - min_current)*1e9:.2f} nA\n'
stats_text += f'n = {len(current_A)}'
ax1.text(0.02, 0.98, stats_text, transform=ax1.transAxes,
         fontsize=11, verticalalignment='top',
         bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))

# Add test info
info_text = f"Wavelength: {metadata.get('Test wavelength', 'N/A')}\n"
info_text += f"Duration: {metadata.get('Test duration', 'N/A')}"
ax1.text(0.98, 0.98, info_text, transform=ax1.transAxes,
         fontsize=10, verticalalignment='top', horizontalalignment='right',
         bbox=dict(boxstyle='round', facecolor='lightblue', alpha=0.8))

# ============================================================================
# SUBPLOT 2: Lock-in Voltage vs Time
# ============================================================================
ax2.plot(time_minutes, voltage_V, 's-', color='#A23B72', 
         linewidth=2, markersize=7, markeredgecolor='white', markeredgewidth=1,
         label='Lock-in Output')

# Add mean line
ax2.axhline(mean_voltage, color='green', linestyle='--', linewidth=2,
            label=f'Mean = {mean_voltage:.4f} V')

# Add ±1σ band
ax2.fill_between(time_minutes, 
                 mean_voltage - std_voltage,
                 mean_voltage + std_voltage,
                 alpha=0.2, color='green', label=f'±1σ = {std_voltage:.4f} V')

# Add ±2σ lines
ax2.axhline(mean_voltage + 2*std_voltage, color='orange', 
            linestyle=':', linewidth=1.5, alpha=0.7, label='±2σ')
ax2.axhline(mean_voltage - 2*std_voltage, color='orange', 
            linestyle=':', linewidth=1.5, alpha=0.7)

ax2.set_xlabel('Time (minutes)', fontsize=12, fontweight='bold')
ax2.set_ylabel('Lock-in Voltage (V)', fontsize=12, fontweight='bold')
ax2.set_title('Lock-in Amplifier Output Stability', fontsize=14, fontweight='bold')
ax2.grid(True, alpha=0.3, linestyle='--')
ax2.legend(loc='best', fontsize=10)

# Add statistics box
stats_text2 = f'CV = {cv_voltage:.2f}%\n'
stats_text2 += f'Range = {(np.max(voltage_V) - np.min(voltage_V)):.4f} V\n'
stats_text2 += f'n = {len(voltage_V)}'
ax2.text(0.02, 0.98, stats_text2, transform=ax2.transAxes,
         fontsize=11, verticalalignment='top',
         bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))

# Drift analysis
mid_point = len(current_A) // 2
first_half_mean = np.mean(current_A[:mid_point])
second_half_mean = np.mean(current_A[mid_point:])
drift_percent = 100 * (second_half_mean - first_half_mean) / first_half_mean

# Add drift analysis box
drift_color = 'lightgreen' if abs(drift_percent) < 2 else ('yellow' if abs(drift_percent) < 5 else 'lightcoral')
drift_text = f'Drift Analysis:\n'
drift_text += f'First half: {first_half_mean*1e9:.2f} nA\n'
drift_text += f'Second half: {second_half_mean*1e9:.2f} nA\n'
drift_text += f'Drift: {drift_percent:+.2f}%'
ax2.text(0.98, 0.98, drift_text, transform=ax2.transAxes,
         fontsize=10, verticalalignment='top', horizontalalignment='right',
         bbox=dict(boxstyle='round', facecolor=drift_color, alpha=0.8))

plt.tight_layout()

# Save plot
output_filename = filename.replace('.csv', '_plot.png')
plt.savefig(output_filename, dpi=300, bbox_inches='tight')
print(f"✓ Plot saved to: {output_filename}")

plt.show()

# ============================================================================
# Print summary statistics
# ============================================================================
print()
print("=" * 80)
print("STABILITY ANALYSIS SUMMARY")
print("=" * 80)
print(f"Test wavelength: {metadata.get('Test wavelength', 'N/A')}")
print(f"Test duration:   {metadata.get('Test duration', 'N/A')}")
print(f"Measurements:    {len(current_A)}")
print()
print("CURRENT MEASUREMENTS:")
print(f"  Mean:     {mean_current*1e9:.3f} nA ({mean_current:.6e} A)")
print(f"  Std Dev:  {std_current*1e9:.3f} nA ({std_current:.6e} A)")
print(f"  CV:       {cv_current:.2f}%")
print(f"  Min:      {min_current*1e9:.3f} nA")
print(f"  Max:      {max_current*1e9:.3f} nA")
print(f"  Range:    {(max_current-min_current)*1e9:.3f} nA ({100*(max_current-min_current)/mean_current:.1f}% of mean)")
print()
print("VOLTAGE MEASUREMENTS:")
print(f"  Mean:     {mean_voltage:.6f} V")
print(f"  Std Dev:  {std_voltage:.6f} V")
print(f"  CV:       {cv_voltage:.2f}%")
print()
print("DRIFT ANALYSIS:")
print(f"  First half mean:  {first_half_mean*1e9:.3f} nA")
print(f"  Second half mean: {second_half_mean*1e9:.3f} nA")
print(f"  Drift:            {drift_percent:+.2f}%")
print()
print("STABILITY ASSESSMENT:")
if cv_current < 5:
    print(f"  ✓ EXCELLENT stability (CV = {cv_current:.2f}% < 5%)")
elif cv_current < 10:
    print(f"  ✓ GOOD stability (CV = {cv_current:.2f}% < 10%)")
elif cv_current < 20:
    print(f"  ⚠️  MODERATE stability (CV = {cv_current:.2f}% < 20%)")
else:
    print(f"  ❌ POOR stability (CV = {cv_current:.2f}% > 20%)")

if abs(drift_percent) < 2:
    print(f"  ✓ Minimal drift (< 2%)")
elif abs(drift_percent) < 5:
    print(f"  ⚠️  Slight drift detected ({abs(drift_percent):.1f}%)")
else:
    print(f"  ❌ Significant drift detected ({abs(drift_percent):.1f}%)")

print("=" * 80)
