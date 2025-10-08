"""Quick 10-measurement stability test"""
from picoscope_driver import PicoScopeDriver
import numpy as np

pico = PicoScopeDriver()
if not pico.connect():
    print("Failed to connect")
    exit(1)

pico.set_reference_frequency(81)

measurements = []
for i in range(10):
    result = pico.software_lockin(81, num_cycles=100)
    if result:
        measurements.append(result['R'])
        print(f"{i+1}. R = {result['R']:.6f} V")

pico.close()

if measurements:
    measurements = np.array(measurements)
    mean = np.mean(measurements)
    std = np.std(measurements)
    cv = 100 * std / mean
    
    print(f"\nMean: {mean:.4f} V")
    print(f"Std:  {std:.4f} V")
    print(f"CV:   {cv:.2f}%")
    print(f"Range: {np.min(measurements):.4f} - {np.max(measurements):.4f} V")
    
    if cv < 10:
        print("✓ GOOD (CV < 10%)")
    else:
        print(f"✗ POOR (CV = {cv:.1f}% >> 10%)")
