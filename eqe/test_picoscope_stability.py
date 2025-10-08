"""
Test stability of PicoScope lock-in measurements
Performs repeated measurements at same wavelength to check CV
"""

from picoscope_driver import PicoScopeDriver
import numpy as np
import time

print("PicoScope Lock-in Stability Test")
print("=" * 70)

# Connect to PicoScope
pico = PicoScopeDriver()
if not pico.connect():
    print("Failed to connect to PicoScope")
    exit(1)

pico.set_reference_frequency(81)

# Perform 20 consecutive measurements
print("\nPerforming 20 consecutive measurements...")
print("(Simulating real EQE scan conditions)")
print()

measurements = []
for i in range(20):
    result = pico.software_lockin(81, num_cycles=100)
    
    if result:
        R = result['R']
        measurements.append(R)
        print(f"  {i+1:2d}. R = {R:.6f} V")
        
        # Small delay to simulate wavelength stepping
        time.sleep(0.1)
    else:
        print(f"  {i+1:2d}. FAILED")

pico.close()

# Calculate statistics
if len(measurements) > 0:
    measurements = np.array(measurements)
    mean = np.mean(measurements)
    std = np.std(measurements)
    cv = 100 * std / mean if mean > 0 else 0
    min_val = np.min(measurements)
    max_val = np.max(measurements)
    
    print()
    print("=" * 70)
    print("STABILITY ANALYSIS")
    print("=" * 70)
    print(f"  Number of measurements: {len(measurements)}")
    print(f"  Mean:        {mean:.6f} V")
    print(f"  Std Dev:     {std:.6f} V")
    print(f"  CV:          {cv:.2f}%")
    print(f"  Min:         {min_val:.6f} V")
    print(f"  Max:         {max_val:.6f} V")
    print(f"  Range:       {max_val - min_val:.6f} V ({100*(max_val-min_val)/mean:.1f}% of mean)")
    print()
    
    if cv < 5:
        print("  ✓ EXCELLENT stability (CV < 5%)")
    elif cv < 10:
        print("  ✓ GOOD stability (CV < 10%)")
    elif cv < 20:
        print("  ⚠ MODERATE stability (CV < 20%) - may need improvement")
    else:
        print("  ✗ POOR stability (CV > 20%) - needs debugging")
    
    print()
    print("Target: CV < 10% for reliable EQE measurements")
    print("Previous hardware performance: CV ≈ 6.5%")
    print()
else:
    print("\n✗ No successful measurements!")
