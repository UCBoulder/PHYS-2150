"""
Reference Signal Diagnostic

Captures the reference signal (Ch B) and analyzes it to determine
the actual chopper frequency with better resolution.

Uses zero-crossing detection and interpolated FFT for more accurate
frequency measurement than the standard FFT bin method.

Author: Physics 2150
Date: December 2025
"""

import sys
import time
import numpy as np
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from eqe.drivers.picoscope_driver import PicoScopeDriver


def analyze_reference_signal():
    """
    Capture and analyze the reference signal to determine actual frequency.
    """
    print("=" * 60)
    print("REFERENCE SIGNAL DIAGNOSTIC")
    print("=" * 60)
    print()

    scope = PicoScopeDriver()

    try:
        print("Connecting to PicoScope...")
        if not scope.connect():
            print("FAILED: Could not connect to PicoScope")
            return

        print()
        print("Capturing reference signal...")

        # Capture data - use maximum samples for best frequency resolution
        num_samples = 2000  # PS2204A limit with 2 channels
        signal_data, reference_data = scope._acquire_block(num_samples, decimation=1)

        if reference_data is None:
            print("ERROR: Failed to capture data")
            return

        # Calculate sample rate (timebase 12 = 40960 ns)
        fs = 1e9 / 40960  # ~24.4 kHz

        print(f"\nCapture info:")
        print(f"  Samples: {len(reference_data)}")
        print(f"  Sample rate: {fs:.1f} Hz")
        print(f"  Duration: {len(reference_data)/fs*1000:.1f} ms")

        # Reference signal stats
        ref_min = np.min(reference_data)
        ref_max = np.max(reference_data)
        ref_pp = ref_max - ref_min
        ref_mean = np.mean(reference_data)

        print(f"\nReference signal (Ch B):")
        print(f"  Min: {ref_min:.3f} V")
        print(f"  Max: {ref_max:.3f} V")
        print(f"  Peak-to-peak: {ref_pp:.3f} V")
        print(f"  Mean: {ref_mean:.3f} V")

        # Method 1: Standard FFT (what the driver uses)
        print(f"\n--- Method 1: Standard FFT ---")
        freqs = np.fft.rfftfreq(len(reference_data), 1/fs)
        fft_ref = np.abs(np.fft.rfft(reference_data - ref_mean))

        # Find peak in 50-150 Hz range
        mask = (freqs >= 50) & (freqs <= 150)
        peak_idx = np.argmax(fft_ref[mask])
        fft_freq = freqs[mask][peak_idx]

        bin_spacing = fs / len(reference_data)
        print(f"  FFT bin spacing: {bin_spacing:.2f} Hz")
        print(f"  Detected frequency: {fft_freq:.2f} Hz")

        # Method 2: Zero-crossing detection (more accurate for square waves)
        print(f"\n--- Method 2: Zero-crossing detection ---")
        ref_centered = reference_data - ref_mean

        # Find zero crossings (rising edges)
        crossings = []
        for i in range(1, len(ref_centered)):
            if ref_centered[i-1] < 0 and ref_centered[i] >= 0:
                # Linear interpolation for sub-sample accuracy
                t_cross = (i-1) + (-ref_centered[i-1]) / (ref_centered[i] - ref_centered[i-1])
                crossings.append(t_cross)

        if len(crossings) >= 2:
            # Calculate periods between crossings
            periods = np.diff(crossings) / fs  # Convert to seconds
            freq_from_crossings = 1.0 / np.mean(periods)
            freq_std = np.std(1.0 / periods, ddof=1) if len(periods) > 1 else 0.0

            print(f"  Rising edges detected: {len(crossings)}")
            print(f"  Complete cycles: {len(crossings) - 1}")
            print(f"  Detected frequency: {freq_from_crossings:.2f} Hz")
            print(f"  Frequency std: {freq_std:.2f} Hz")
        else:
            print(f"  Not enough zero crossings detected ({len(crossings)})")
            freq_from_crossings = None

        # Method 3: Interpolated FFT peak (parabolic interpolation)
        print(f"\n--- Method 3: Interpolated FFT ---")
        # Find the bin with max magnitude in our range
        peak_bin = np.argmax(fft_ref[mask]) + np.where(mask)[0][0]

        if peak_bin > 0 and peak_bin < len(fft_ref) - 1:
            # Parabolic interpolation using neighbors
            alpha = fft_ref[peak_bin - 1]
            beta = fft_ref[peak_bin]
            gamma = fft_ref[peak_bin + 1]

            # Peak offset from center bin
            p = 0.5 * (alpha - gamma) / (alpha - 2*beta + gamma)

            # Interpolated frequency
            interp_freq = freqs[peak_bin] + p * bin_spacing
            print(f"  Interpolated frequency: {interp_freq:.2f} Hz")
        else:
            interp_freq = fft_freq
            print(f"  Could not interpolate (peak at edge)")

        # Summary
        print(f"\n" + "=" * 60)
        print("SUMMARY")
        print("=" * 60)
        print(f"\n  Standard FFT:      {fft_freq:.2f} Hz (resolution limited)")
        if freq_from_crossings:
            print(f"  Zero-crossing:     {freq_from_crossings:.2f} Hz (most accurate)")
        print(f"  Interpolated FFT:  {interp_freq:.2f} Hz")

        if freq_from_crossings:
            best_freq = freq_from_crossings
        else:
            best_freq = interp_freq

        print(f"\n  Best estimate: {best_freq:.1f} Hz")

        if abs(best_freq - 81) < 3:
            print(f"\n  ✓ Reference frequency is close to expected 81 Hz")
            print(f"    The 85 Hz reading was due to FFT bin resolution")
        else:
            print(f"\n  ⚠ Reference frequency differs from expected 81 Hz")
            print(f"    Check chopper controller settings")

        # Show signal waveform info
        print(f"\n--- Signal shape analysis ---")

        # Check if it looks like a square wave
        # Square waves spend most time at extremes
        above_mean = np.sum(reference_data > ref_mean + ref_pp*0.3)
        below_mean = np.sum(reference_data < ref_mean - ref_pp*0.3)
        in_middle = len(reference_data) - above_mean - below_mean

        pct_extreme = (above_mean + below_mean) / len(reference_data) * 100
        print(f"  Time at extremes: {pct_extreme:.0f}%")

        if pct_extreme > 70:
            print(f"  Shape: Square wave (good for lock-in)")
        elif pct_extreme > 40:
            print(f"  Shape: Trapezoidal or clipped sine")
        else:
            print(f"  Shape: Sinusoidal")

    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()

    finally:
        scope.close()
        print("\nDone.")


if __name__ == "__main__":
    analyze_reference_signal()
