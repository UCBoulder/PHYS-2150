"""
Lock-In Amplifier Live Test

Tests the lock-in amplifier with real signals:
- Channel A: TIA output (photocurrent)
- Channel B: Chopper reference

Reports:
- Real-time R (magnitude) readings
- Statistics (mean, std, CV%)
- Phase stability

Setup:
    TIA output → PicoScope Ch A
    Chopper reference → PicoScope Ch B

Author: Physics 2150
Date: December 2025
"""

import sys
import time
import numpy as np
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from eqe.drivers.picoscope_driver import PicoScopeDriver
from eqe.config.settings import DEVICE_CONFIGS, DeviceType

# Load lock-in configuration from settings
LOCKIN_CONFIG = DEVICE_CONFIGS[DeviceType.PICOSCOPE_LOCKIN]


def run_lockin_live_test():
    """
    Run live lock-in measurements and report statistics.
    """
    print("=" * 60)
    print("LOCK-IN AMPLIFIER LIVE TEST")
    print("=" * 60)
    print()
    print("Setup:")
    print("  - Ch A: TIA output (photocurrent signal)")
    print("  - Ch B: Chopper reference")
    print()

    # Configuration - load from settings
    CHOPPER_FREQ = LOCKIN_CONFIG.get("default_chopper_freq", 81.0)
    NUM_CYCLES = LOCKIN_CONFIG.get("default_num_cycles", 100)
    CORRECTION_FACTOR = LOCKIN_CONFIG.get("correction_factor", 0.5)
    NUM_MEASUREMENTS = 20  # How many measurements to take
    DELAY_BETWEEN = 0.5  # Seconds between measurements

    # Ask user for chopper frequency
    user_input = input(f"Chopper frequency in Hz [{CHOPPER_FREQ}]: ").strip()
    if user_input:
        try:
            CHOPPER_FREQ = float(user_input)
        except ValueError:
            pass
    print()

    # Connect to PicoScope
    scope = PicoScopeDriver()

    try:
        print("Connecting to PicoScope...")
        if not scope.connect():
            print("FAILED: Could not connect to PicoScope")
            return

        print()
        print(f"Taking {NUM_MEASUREMENTS} measurements at {CHOPPER_FREQ} Hz...")
        print()
        print("=" * 60)
        print("LOCK-IN MEASUREMENTS (Hilbert algorithm)")
        print("=" * 60)
        print()
        print(f"{'#':>3}  {'R (V)':>12}  {'Phase (°)':>10}  {'Freq (Hz)':>10}  {'Signal':>12}")
        print("-" * 60)

        results = []

        for i in range(NUM_MEASUREMENTS):
            result = scope.software_lockin(
                CHOPPER_FREQ,
                num_cycles=NUM_CYCLES,
                correction_factor=CORRECTION_FACTOR
            )

            if result is None:
                print(f"{i+1:>3}  {'ERROR':>12}")
                continue

            R = result['R']
            phase = result['theta']
            freq = result['freq']

            # Get signal amplitude info
            sig_pp = np.max(result['signal_data']) - np.min(result['signal_data'])

            results.append({
                'R': R,
                'phase': phase,
                'freq': freq,
                'signal_pp': sig_pp
            })

            print(f"{i+1:>3}  {R:>12.6f}  {phase:>+10.1f}  {freq:>10.2f}  {sig_pp:>10.4f} Vpp")

            if i < NUM_MEASUREMENTS - 1:
                time.sleep(DELAY_BETWEEN)

        # Statistics
        if results:
            R_vals = [r['R'] for r in results]
            phase_vals = [r['phase'] for r in results]
            freq_vals = [r['freq'] for r in results]

            R_mean = np.mean(R_vals)
            R_std = np.std(R_vals)
            R_cv = (R_std / R_mean * 100) if R_mean > 0 else 0

            phase_mean = np.mean(phase_vals)
            phase_std = np.std(phase_vals)

            freq_mean = np.mean(freq_vals)
            freq_std = np.std(freq_vals)

            print()
            print("=" * 60)
            print("STATISTICS")
            print("=" * 60)
            print(f"  R magnitude:")
            print(f"    Mean:   {R_mean:.6f} V")
            print(f"    Std:    {R_std:.6f} V")
            print(f"    CV:     {R_cv:.2f}%")
            print(f"  Phase:")
            print(f"    Mean:   {phase_mean:+.1f}°")
            print(f"    Std:    {phase_std:.1f}°")
            print(f"  Frequency:")
            print(f"    Mean:   {freq_mean:.2f} Hz")
            print(f"    Std:    {freq_std:.2f} Hz")

            # Quality assessment
            print()
            if R_cv < 1:
                print(f"  ✓ Excellent stability (CV < 1%)")
            elif R_cv < 5:
                print(f"  ✓ Good stability (CV < 5%)")
            elif R_cv < 10:
                print(f"  ⚠ Moderate stability (CV < 10%)")
            else:
                print(f"  ✗ Poor stability (CV > 10%) - check signal/reference")

            # Convert R to current (assuming 1 MΩ TIA)
            TIA_GAIN = 1e6  # 1 MΩ
            current_nA = R_mean / TIA_GAIN * 1e9
            print(f"\n  Estimated photocurrent: {current_nA:.2f} nA (assuming 1 MΩ TIA)")

    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")

    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()

    finally:
        print("\nCleaning up...")
        scope.close()
        print("Done.")


def run_continuous_monitor():
    """
    Continuously monitor lock-in output until user stops.
    Useful for alignment and debugging.
    """
    print("=" * 60)
    print("LOCK-IN CONTINUOUS MONITOR")
    print("=" * 60)
    print()
    print("Press Ctrl+C to stop")
    print()

    # Load from settings
    CHOPPER_FREQ = LOCKIN_CONFIG.get("default_chopper_freq", 81.0)
    CORRECTION_FACTOR = LOCKIN_CONFIG.get("correction_factor", 0.5)

    user_input = input(f"Chopper frequency in Hz [{CHOPPER_FREQ}]: ").strip()
    if user_input:
        try:
            CHOPPER_FREQ = float(user_input)
        except ValueError:
            pass

    scope = PicoScopeDriver()

    try:
        print("\nConnecting to PicoScope...")
        if not scope.connect():
            print("FAILED: Could not connect to PicoScope")
            return

        print()
        print(f"{'Time':>10}  {'R (V)':>12}  {'Current':>12}  {'Phase':>10}  {'Ref Freq':>10}")
        print("-" * 60)

        TIA_GAIN = 1e6
        start_time = time.time()

        while True:
            result = scope.software_lockin(
                CHOPPER_FREQ,
                num_cycles=50,  # Fewer cycles for faster updates
                correction_factor=CORRECTION_FACTOR
            )

            if result:
                elapsed = time.time() - start_time
                R = result['R']
                current = R / TIA_GAIN
                phase = result['theta']
                freq = result['freq']

                # Format current with appropriate units
                if current >= 1e-6:
                    current_str = f"{current*1e6:.3f} µA"
                else:
                    current_str = f"{current*1e9:.2f} nA"

                print(f"{elapsed:>8.1f}s  {R:>12.6f}  {current_str:>12}  {phase:>+9.1f}°  {freq:>9.2f} Hz")

            time.sleep(0.3)

    except KeyboardInterrupt:
        print("\n\nMonitoring stopped.")

    finally:
        scope.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Lock-in amplifier live test")
    parser.add_argument('--monitor', '-m', action='store_true',
                        help='Continuous monitoring mode')
    args = parser.parse_args()

    if args.monitor:
        run_continuous_monitor()
    else:
        run_lockin_live_test()
