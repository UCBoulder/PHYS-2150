"""
Long-term stability test for PicoScope EQE measurement
Mimics GUI workflow: phase adjustment → repeated current measurements
Tests stability over several minutes at a single wavelength
"""

from picoscope_driver import PicoScopeDriver
import numpy as np
import time
import datetime
from scipy.optimize import curve_fit

# Configuration
TEST_WAVELENGTH = 550.0  # nm - good signal in visible range
CHOPPER_FREQ = 81  # Hz
NUM_MEASUREMENTS = 20  # Number of repeated measurements
DELAY_BETWEEN_MEASUREMENTS = 5  # seconds (mimics wavelength stepping delay)
CORRECTION_FACTOR = 1.0  # Adjust if you have a calibration factor
TRANSIMPEDANCE_GAIN = 1e6  # 1 MΩ

print("=" * 80)
print("LONG-TERM STABILITY TEST FOR EQE MEASUREMENT")
print("=" * 80)
print(f"Test wavelength: {TEST_WAVELENGTH} nm")
print(f"Chopper frequency: {CHOPPER_FREQ} Hz")
print(f"Number of measurements: {NUM_MEASUREMENTS}")
print(f"Delay between measurements: {DELAY_BETWEEN_MEASUREMENTS} seconds")
print(f"Total test duration: ~{NUM_MEASUREMENTS * DELAY_BETWEEN_MEASUREMENTS / 60:.1f} minutes")
print("=" * 80)
print()

# Connect to PicoScope
print("Connecting to PicoScope...")
pico = PicoScopeDriver()
if not pico.connect():
    print("❌ Failed to connect to PicoScope")
    exit(1)

pico.set_reference_frequency(CHOPPER_FREQ)
print("✓ PicoScope connected\n")

# ============================================================================
# PHASE 1: PHASE ADJUSTMENT (MAXIMIZE SIGNAL)
# ============================================================================
print("=" * 80)
print("PHASE 1: PHASE ADJUSTMENT")
print("=" * 80)
print("Scanning phase from 0° to 360° to maximize signal...")
print()

# Scan phases to find optimal
phase_scan_points = 37  # 0° to 360° in 10° steps
phases = np.linspace(0, 360, phase_scan_points)
signals = []
r_squared_values = []

print("Phase (°)  Signal (V)  Status")
print("-" * 40)

for phase in phases:
    # Simulate phase adjustment by measuring signal
    # In real hardware, this would adjust the phase of the reference
    result = pico.software_lockin(CHOPPER_FREQ, num_cycles=100)
    
    if result:
        # For now, we'll use R magnitude (phase-independent)
        # In a real phase adjustment, you'd calculate X*cos(phase) + Y*sin(phase)
        signal = result['R']
        signals.append(signal)
        
        status = ""
        if len(signals) > 1 and signal > max(signals[:-1]):
            status = "← NEW MAX"
        
        print(f"{phase:6.1f}    {signal:.6f}   {status}")
    else:
        print(f"{phase:6.1f}    FAILED")
        signals.append(0)
    
    time.sleep(0.2)  # Small delay between phase measurements

# Fit sine curve to find optimal phase
def sine_model(x, amplitude, phase_shift, offset):
    return amplitude * np.sin(np.radians(x - phase_shift)) + offset

try:
    signals_array = np.array(signals)
    # Initial guess: amplitude = half range, phase = where max occurs, offset = mean
    max_idx = np.argmax(signals_array)
    initial_amplitude = (np.max(signals_array) - np.min(signals_array)) / 2
    initial_phase = phases[max_idx]
    initial_offset = np.mean(signals_array)
    
    popt, pcov = curve_fit(
        sine_model,
        phases,
        signals_array,
        p0=[initial_amplitude, initial_phase, initial_offset],
        maxfev=5000
    )
    
    optimal_amplitude, optimal_phase, offset = popt
    
    # Calculate R-squared
    ss_res = np.sum((signals_array - sine_model(phases, *popt))**2)
    ss_tot = np.sum((signals_array - np.mean(signals_array))**2)
    r_squared = 1 - (ss_res / ss_tot)
    
    # Calculate signal at optimal phase
    optimal_signal = optimal_amplitude + offset  # Maximum of sine wave
    
    print()
    print("=" * 40)
    print("PHASE ADJUSTMENT RESULTS:")
    print(f"  Optimal Phase:  {optimal_phase:.2f}°")
    print(f"  Signal:         {optimal_signal:.6f} V")
    print(f"  Amplitude:      {optimal_amplitude:.6f} V")
    print(f"  Offset:         {offset:.6f} V")
    print(f"  R²:             {r_squared:.4f}")
    
    if r_squared < 0.90:
        print(f"  ⚠️  WARNING: Low R² ({r_squared:.4f}) - phase adjustment may be unreliable")
    else:
        print(f"  ✓ Good fit (R² ≥ 0.90)")
    
    print("=" * 40)
    print()
    
except Exception as e:
    print(f"❌ Phase fitting failed: {e}")
    optimal_phase = phases[np.argmax(signals)]
    optimal_signal = max(signals)
    print(f"Using maximum signal point: Phase = {optimal_phase:.2f}°, Signal = {optimal_signal:.6f} V")
    print()

# ============================================================================
# PHASE 2: LONG-TERM CURRENT MEASUREMENT
# ============================================================================
print("=" * 80)
print("PHASE 2: LONG-TERM CURRENT STABILITY TEST")
print("=" * 80)
print(f"Measuring current at {TEST_WAVELENGTH} nm with {DELAY_BETWEEN_MEASUREMENTS}s intervals...")
print()
print("Time     Measurement  Current (A)      Voltage (V)  CV (%)   Status")
print("-" * 80)

current_measurements = []
voltage_measurements = []
timestamps = []
start_time = time.time()

for i in range(NUM_MEASUREMENTS):
    measurement_start = time.time()
    
    # Perform lock-in measurement (same as GUI: 5 measurements × 100 cycles)
    R_values = []
    num_measurements = 5
    
    for j in range(num_measurements):
        result = pico.software_lockin(CHOPPER_FREQ, num_cycles=100)
        
        if result is not None:
            R_values.append(result['R'])
        else:
            print(f"Warning: Lock-in measurement {j+1}/{num_measurements} failed")
    
    if not R_values:
        print(f"❌ All measurements failed at iteration {i+1}")
        continue
    
    # Same processing as GUI: trimmed mean
    R_array = np.array(R_values)
    median_signal = np.median(R_array)
    deviations = np.abs(R_array - median_signal)
    threshold = 2 * np.std(deviations)
    mask = deviations <= threshold
    R_trimmed = R_array[mask]
    
    if len(R_trimmed) >= 3:
        average_signal = np.mean(R_trimmed)
        std_signal = np.std(R_trimmed)
    else:
        average_signal = median_signal
        std_signal = np.std(R_array)
    
    # Convert to current (same as GUI)
    adjusted_voltage = average_signal / CORRECTION_FACTOR
    current = adjusted_voltage / TRANSIMPEDANCE_GAIN  # I = V / R for transimpedance amp
    
    # Store results
    voltage_measurements.append(average_signal)
    current_measurements.append(current)
    elapsed_time = time.time() - start_time
    timestamps.append(elapsed_time)
    
    # Calculate statistics so far
    if len(current_measurements) > 1:
        current_array = np.array(current_measurements)
        mean_current = np.mean(current_array)
        std_current = np.std(current_array)
        cv_current = 100 * std_current / mean_current if mean_current > 0 else 0
        
        status = "✓" if cv_current < 5 else ("⚠️" if cv_current < 10 else "❌")
    else:
        cv_current = 0
        status = "-"
    
    # Format time as MM:SS
    time_str = f"{int(elapsed_time // 60):02d}:{int(elapsed_time % 60):02d}"
    
    print(f"{time_str}   {i+1:4d}/{NUM_MEASUREMENTS:4d}   {current:.6e}   {average_signal:.6f}   {cv_current:6.2f}  {status}")
    
    # Wait before next measurement (except on last iteration)
    if i < NUM_MEASUREMENTS - 1:
        time.sleep(DELAY_BETWEEN_MEASUREMENTS)

pico.close()

# ============================================================================
# FINAL STATISTICS
# ============================================================================
print()
print("=" * 80)
print("FINAL STABILITY ANALYSIS")
print("=" * 80)

if len(current_measurements) > 0:
    current_array = np.array(current_measurements)
    voltage_array = np.array(voltage_measurements)
    
    # Current statistics
    mean_current = np.mean(current_array)
    std_current = np.std(current_array)
    cv_current = 100 * std_current / mean_current if mean_current > 0 else 0
    min_current = np.min(current_array)
    max_current = np.max(current_array)
    range_current = max_current - min_current
    
    # Voltage statistics
    mean_voltage = np.mean(voltage_array)
    std_voltage = np.std(voltage_array)
    cv_voltage = 100 * std_voltage / mean_voltage if mean_voltage > 0 else 0
    
    print(f"Number of measurements:  {len(current_measurements)}")
    print(f"Test duration:           {timestamps[-1] / 60:.2f} minutes")
    print()
    print("CURRENT MEASUREMENTS:")
    print(f"  Mean:        {mean_current:.6e} A")
    print(f"  Std Dev:     {std_current:.6e} A")
    print(f"  CV:          {cv_current:.2f}%")
    print(f"  Min:         {min_current:.6e} A")
    print(f"  Max:         {max_current:.6e} A")
    print(f"  Range:       {range_current:.6e} A ({100*range_current/mean_current:.1f}% of mean)")
    print()
    print("VOLTAGE MEASUREMENTS (Lock-in output):")
    print(f"  Mean:        {mean_voltage:.6f} V")
    print(f"  Std Dev:     {std_voltage:.6f} V")
    print(f"  CV:          {cv_voltage:.2f}%")
    print()
    
    # Assessment
    print("STABILITY ASSESSMENT:")
    if cv_current < 5:
        print(f"  ✓ EXCELLENT stability (CV = {cv_current:.2f}% < 5%)")
        print("    → System is highly stable and suitable for precision measurements")
    elif cv_current < 10:
        print(f"  ✓ GOOD stability (CV = {cv_current:.2f}% < 10%)")
        print("    → System meets target stability for reliable EQE measurements")
    elif cv_current < 20:
        print(f"  ⚠️  MODERATE stability (CV = {cv_current:.2f}% < 20%)")
        print("    → System is usable but may benefit from improvement")
    else:
        print(f"  ❌ POOR stability (CV = {cv_current:.2f}% > 20%)")
        print("    → System needs troubleshooting")
    
    print()
    print("COMPARISON TO PREVIOUS MEASUREMENTS:")
    print(f"  Target CV:           < 10%")
    print(f"  Previous hardware:   ~6.5% CV")
    print(f"  PicoScope (short):   ~1.57% CV (20 measurements, <1 min)")
    print(f"  PicoScope (this):    {cv_current:.2f}% CV ({NUM_MEASUREMENTS} measurements, {timestamps[-1]/60:.1f} min)")
    
    # Drift analysis
    if len(timestamps) >= 10:
        print()
        print("DRIFT ANALYSIS:")
        # Split into first and second half
        mid_point = len(current_array) // 2
        first_half_mean = np.mean(current_array[:mid_point])
        second_half_mean = np.mean(current_array[mid_point:])
        drift = second_half_mean - first_half_mean
        drift_percent = 100 * drift / first_half_mean if first_half_mean > 0 else 0
        
        print(f"  First half mean:     {first_half_mean:.6e} A")
        print(f"  Second half mean:    {second_half_mean:.6e} A")
        print(f"  Drift:               {drift:.6e} A ({drift_percent:+.2f}%)")
        
        if abs(drift_percent) < 2:
            print(f"  ✓ Minimal drift (< 2%)")
        elif abs(drift_percent) < 5:
            print(f"  ⚠️  Slight drift detected ({abs(drift_percent):.1f}%)")
        else:
            print(f"  ❌ Significant drift detected ({abs(drift_percent):.1f}%)")
            print("     → Check lamp stability, temperature, or connection stability")
    
    # Save data to CSV
    timestamp_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"longterm_stability_{timestamp_str}.csv"
    
    print()
    print(f"Saving data to {filename}...")
    
    with open(filename, 'w') as f:
        f.write("# Long-term stability test for PicoScope EQE measurement\n")
        f.write(f"# Test wavelength: {TEST_WAVELENGTH} nm\n")
        f.write(f"# Chopper frequency: {CHOPPER_FREQ} Hz\n")
        f.write(f"# Test duration: {timestamps[-1] / 60:.2f} minutes\n")
        f.write(f"# Mean current: {mean_current:.6e} A\n")
        f.write(f"# CV: {cv_current:.2f}%\n")
        f.write("#\n")
        f.write("Time (s),Current (A),Voltage (V)\n")
        
        for t, curr, volt in zip(timestamps, current_measurements, voltage_measurements):
            f.write(f"{t:.2f},{curr:.6e},{volt:.6f}\n")
    
    print(f"✓ Data saved to {filename}")

else:
    print("❌ No successful measurements recorded")

print()
print("=" * 80)
print("TEST COMPLETE")
print("=" * 80)
