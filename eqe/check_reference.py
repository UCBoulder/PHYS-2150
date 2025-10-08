"""
Diagnostic: Check reference waveform characteristics

PURPOSE:
  This tool analyzes the reference signal (Channel B) to determine
  the correct trigger threshold for stable lock-in measurements.

WHEN TO USE:
  - Initial setup of new PicoScope hardware
  - Troubleshooting stability issues (high CV)
  - After changing chopper or reference signal source
  - Validating trigger configuration

HISTORY:
  Created during PicoScope migration (Oct 2025) to diagnose stability
  issues. Identified that trigger threshold needed to be 2.5V (not 0V)
  for 0-5V square wave reference, improving CV from 24-60% to 0.66%.

USAGE:
  python check_reference.py
  
  Look for "Midpoint (for trigger)" value - this should match the
  trigger threshold in picoscope_driver.py (currently 2500 mV).
"""
from picoscope_driver import PicoScopeDriver
import numpy as np

pico = PicoScopeDriver()
if not pico.connect():
    print("Failed to connect")
    exit(1)

pico.set_reference_frequency(81)

# Capture one measurement
result = pico.software_lockin(81, num_cycles=100)

if result:
    ref_data = result['reference_data']
    
    print(f"Reference signal statistics:")
    print(f"  Min:    {np.min(ref_data):.4f} V")
    print(f"  Max:    {np.max(ref_data):.4f} V")
    print(f"  Mean:   {np.mean(ref_data):.4f} V")
    print(f"  Median: {np.median(ref_data):.4f} V")
    print(f"  Std:    {np.std(ref_data):.4f} V")
    print(f"  Range:  {np.max(ref_data) - np.min(ref_data):.4f} V")
    print(f"\n  Midpoint (for trigger): {(np.min(ref_data) + np.max(ref_data))/2:.4f} V")
    
    # Check if it looks like a square wave
    hist, bins = np.histogram(ref_data, bins=20)
    print(f"\n  Histogram shows signal distribution:")
    print(f"    Most samples near min/max? {hist[0] + hist[-1] > 0.5 * len(ref_data)}")
    
    # Estimate frequency
    from scipy.signal import find_peaks
    peaks, _ = find_peaks(ref_data, distance=len(ref_data)//200)
    if len(peaks) > 1:
        avg_period_samples = np.mean(np.diff(peaks))
        fs = 100e6 / 1024  # sampling rate
        freq_estimate = fs / avg_period_samples
        print(f"\n  Estimated frequency: {freq_estimate:.2f} Hz")
    
    print(f"\n  Signal: R = {result['R']:.4f} V")

pico.close()
