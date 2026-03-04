"""
Lock-in Cycle Optimization Script

Tests different integration cycle counts across various wavelengths to find
the optimal balance between measurement speed and precision.

The goal is to answer: Do we really need 100 cycles? Can we use fewer cycles
(faster measurements) while maintaining acceptable precision?

Test wavelengths are chosen to cover:
- Strong signal region (500-600nm) - where solar cells respond well
- Weak signal tails (350-400nm, 700-750nm) - where SNR is challenging

For each wavelength and cycle count, we take multiple measurements and
calculate statistics. We report:
- CV% (coefficient of variation) - intrinsic measurement variability
- SEM% projected for n=5 - what the app would show (SEM = CV/√n)

The app uses n=5 measurements per wavelength and displays SEM-based quality.
This script uses more measurements (default 10) to get reliable CV% estimates,
then projects what SEM% you'd see in the app.

Usage:
    python scripts/optimize_lockin_cycles.py
    python scripts/optimize_lockin_cycles.py --output results.csv
    python scripts/optimize_lockin_cycles.py --cycles 20,40,60,80,100,120
    python scripts/optimize_lockin_cycles.py --wavelengths 400,550,700
"""

import argparse
import csv
import sys
import time
from datetime import datetime
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import numpy as np


def parse_args():
    parser = argparse.ArgumentParser(
        description="Optimize lock-in integration cycles across wavelengths"
    )
    parser.add_argument(
        "--wavelengths",
        type=str,
        default="400,500,550,600,700,750",
        help="Comma-separated wavelengths to test (nm)"
    )
    parser.add_argument(
        "--cycles",
        type=str,
        default="20,40,60,80,100,120",
        help="Comma-separated cycle counts to test"
    )
    parser.add_argument(
        "--measurements",
        type=int,
        default=10,
        help="Number of measurements per (wavelength, cycles) combination"
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output CSV file path (default: auto-generated with timestamp)"
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Run in offline mode with simulated data (for testing script)"
    )
    return parser.parse_args()


class MockPicoScope:
    """Mock PicoScope for offline testing."""

    def __init__(self):
        self._connected = True
        self._num_cycles = 100

    def is_connected(self):
        return self._connected

    def set_num_cycles(self, n):
        self._num_cycles = n

    def get_num_cycles(self):
        return self._num_cycles

    def perform_lockin_measurement(self):
        # Simulate measurement with noise that decreases with more cycles
        # More cycles = better SNR = lower noise
        base_signal = 0.05  # 50mV base signal
        noise_factor = 1.0 / np.sqrt(self._num_cycles)  # SNR improves with sqrt(N)
        noise = np.random.normal(0, base_signal * 0.1 * noise_factor)

        R = base_signal + noise
        theta = np.random.uniform(-5, 5)  # Small phase variation

        return {
            'R': abs(R),
            'X': R * np.cos(np.radians(theta)),
            'Y': R * np.sin(np.radians(theta)),
            'theta': theta,
            'freq': 81.0 + np.random.normal(0, 0.5),
            'ref_amplitude': 2.0
        }


class MockMonochromator:
    """Mock monochromator for offline testing."""

    def __init__(self):
        self._connected = True
        self._wavelength = 550
        self._shutter_open = False

    def is_connected(self):
        return self._connected

    def set_wavelength(self, wl):
        self._wavelength = wl
        time.sleep(0.05)  # Simulate move time
        return wl

    def get_wavelength(self):
        return self._wavelength

    def open_shutter(self):
        self._shutter_open = True

    def close_shutter(self):
        self._shutter_open = False

    def set_filter_for_wavelength(self, wl):
        return False  # No filter change needed


def connect_hardware(offline=False):
    """Connect to hardware or return mocks for offline mode."""
    if offline:
        print("Running in OFFLINE mode with simulated data")
        return MockPicoScope(), MockMonochromator()

    # Import hardware controllers
    from eqe.controllers.picoscope_lockin import PicoScopeController, PicoScopeError
    from eqe.controllers.monochromator import MonochromatorController, MonochromatorError

    print("Connecting to hardware...")

    picoscope = PicoScopeController()
    try:
        picoscope.connect()
        print("  PicoScope connected")
    except PicoScopeError as e:
        print(f"ERROR: Failed to connect to PicoScope: {e}")
        print("\nTip: Run with --offline to test the script without hardware")
        sys.exit(1)

    monochromator = MonochromatorController()
    try:
        monochromator.connect()
        print("  Monochromator connected")
    except MonochromatorError as e:
        print(f"ERROR: Failed to connect to monochromator: {e}")
        picoscope.disconnect()
        print("\nTip: Run with --offline to test the script without hardware")
        sys.exit(1)

    return picoscope, monochromator


def measure_at_cycles(picoscope, num_cycles, num_measurements, transimpedance_gain=1e-6):
    """
    Take multiple measurements at a specific cycle count.

    Returns dict with statistics.
    """
    # Set the cycle count
    original_cycles = picoscope.get_num_cycles()
    picoscope.set_num_cycles(num_cycles)

    # Calculate expected measurement time
    chopper_freq = 81  # Hz
    expected_time_per_measurement = num_cycles / chopper_freq

    R_values = []
    times = []

    try:
        for i in range(num_measurements):
            start_time = time.time()

            result = picoscope.perform_lockin_measurement()

            elapsed = time.time() - start_time
            times.append(elapsed)

            if result is not None:
                R_values.append(result['R'])
            else:
                print(f"    Warning: measurement {i+1} failed")

        if not R_values:
            return None

        # Calculate statistics
        R_array = np.array(R_values)
        current_array = R_array * transimpedance_gain  # Convert to current

        mean_R = np.mean(R_array)
        std_R = np.std(R_array, ddof=1) if len(R_array) > 1 else 0.0
        cv_percent = 100 * std_R / mean_R if mean_R > 0 else 0

        mean_current = np.mean(current_array)
        std_current = np.std(current_array, ddof=1) if len(current_array) > 1 else 0.0

        avg_time = np.mean(times)

        return {
            'n': len(R_values),
            'mean_V': mean_R,
            'std_V': std_R,
            'mean_A': mean_current,
            'std_A': std_current,
            'cv_percent': cv_percent,
            'avg_time_s': avg_time,
            'expected_time_s': expected_time_per_measurement
        }

    finally:
        # Restore original cycles
        picoscope.set_num_cycles(original_cycles)


def run_optimization(picoscope, monochromator, wavelengths, cycle_counts,
                     num_measurements, output_file):
    """Run the full optimization sweep."""

    # Prepare results storage
    results = []

    # Open shutter
    print("\nOpening shutter...")
    monochromator.open_shutter()
    time.sleep(0.5)

    total_combinations = len(wavelengths) * len(cycle_counts)
    current_combo = 0

    print(f"\nTesting {len(wavelengths)} wavelengths × {len(cycle_counts)} cycle counts")
    print(f"= {total_combinations} combinations × {num_measurements} measurements each")
    print(f"Estimated time: {total_combinations * num_measurements * 1.5 / 60:.1f} minutes (rough)\n")

    try:
        for wavelength in wavelengths:
            print(f"\n{'='*60}")
            print(f"WAVELENGTH: {wavelength} nm")
            print(f"{'='*60}")

            # Move to wavelength
            monochromator.set_wavelength(wavelength)
            monochromator.set_filter_for_wavelength(wavelength)
            time.sleep(1.0)  # Stabilization

            for cycles in cycle_counts:
                current_combo += 1
                progress = 100 * current_combo / total_combinations

                print(f"\n  [{progress:5.1f}%] Testing {cycles} cycles...")

                stats = measure_at_cycles(
                    picoscope,
                    cycles,
                    num_measurements
                )

                if stats:
                    # Project SEM% for app's n=5 measurements
                    # SEM% = CV% / sqrt(n), so projected SEM% = CV% / sqrt(5)
                    app_n = 5
                    sem_percent_n5 = stats['cv_percent'] / np.sqrt(app_n)

                    result = {
                        'wavelength_nm': wavelength,
                        'cycles': cycles,
                        'n': stats['n'],
                        'mean_V': stats['mean_V'],
                        'std_V': stats['std_V'],
                        'mean_nA': stats['mean_A'] * 1e9,  # Convert to nA
                        'std_nA': stats['std_A'] * 1e9,
                        'cv_percent': stats['cv_percent'],
                        'sem_percent_n5': sem_percent_n5,  # Projected for app's n=5
                        'avg_time_s': stats['avg_time_s'],
                        'expected_time_s': stats['expected_time_s']
                    }
                    results.append(result)

                    print(f"           Mean: {stats['mean_A']*1e9:.3f} nA")
                    print(f"           Std:  {stats['std_A']*1e9:.3f} nA")
                    print(f"           CV:   {stats['cv_percent']:.2f}%  (SEM% @n=5: {sem_percent_n5:.2f}%)")
                    print(f"           Time: {stats['avg_time_s']:.3f}s (expected {stats['expected_time_s']:.3f}s)")
                else:
                    print(f"           FAILED - no valid measurements")

    finally:
        # Close shutter
        print("\nClosing shutter...")
        monochromator.close_shutter()

    return results


def save_results(results, output_file):
    """Save results to CSV file."""
    if not results:
        print("No results to save")
        return

    fieldnames = [
        'wavelength_nm', 'cycles', 'n',
        'mean_V', 'std_V', 'mean_nA', 'std_nA',
        'cv_percent', 'sem_percent_n5', 'avg_time_s', 'expected_time_s'
    ]

    with open(output_file, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

    print(f"\nResults saved to: {output_file}")


def print_summary(results):
    """Print a summary analysis of the results."""
    if not results:
        return

    # Organize by wavelength
    wavelengths = sorted(set(r['wavelength_nm'] for r in results))
    cycle_counts = sorted(set(r['cycles'] for r in results))

    # Table 1: CV% (intrinsic variability)
    print("\n" + "="*70)
    print("SUMMARY: CV% by Wavelength and Cycle Count (intrinsic variability)")
    print("="*70)

    header = f"{'Wavelength':>10} |"
    for c in cycle_counts:
        header += f" {c:>6} |"
    print(header)
    print("-" * len(header))

    for wl in wavelengths:
        row = f"{wl:>10} |"
        for c in cycle_counts:
            match = [r for r in results if r['wavelength_nm'] == wl and r['cycles'] == c]
            if match:
                cv = match[0]['cv_percent']
                row += f" {cv:>5.1f}% |"
            else:
                row += f"   N/A |"
        print(row)

    # Table 2: SEM% projected for n=5 (what the app shows)
    print("\n" + "="*70)
    print("SUMMARY: SEM% @n=5 by Wavelength and Cycle Count (app display)")
    print("="*70)
    print("(This is what students see in the app with num_measurements=5)")

    header = f"{'Wavelength':>10} |"
    for c in cycle_counts:
        header += f" {c:>6} |"
    print(header)
    print("-" * len(header))

    for wl in wavelengths:
        row = f"{wl:>10} |"
        for c in cycle_counts:
            match = [r for r in results if r['wavelength_nm'] == wl and r['cycles'] == c]
            if match:
                sem = match[0]['sem_percent_n5']
                row += f" {sem:>5.1f}% |"
            else:
                row += f"   N/A |"
        print(row)

    # Table 3: Timing
    print("\n" + "="*70)
    print("SUMMARY: Measurement Time (seconds) by Cycle Count")
    print("="*70)

    print(f"{'Cycles':>10} | {'Avg Time':>10} | {'Expected':>10} | {'Overhead':>10}")
    print("-" * 50)
    for c in cycle_counts:
        matches = [r for r in results if r['cycles'] == c]
        if matches:
            avg_time = np.mean([r['avg_time_s'] for r in matches])
            expected = matches[0]['expected_time_s']
            overhead = avg_time - expected
            print(f"{c:>10} | {avg_time:>9.3f}s | {expected:>9.3f}s | {overhead:>9.3f}s")

    # Recommendations using SEM% thresholds (matching app)
    # App thresholds: Excellent < 0.5%, Good < 2%, Fair < 15%
    print("\n" + "="*70)
    print("RECOMMENDATIONS (using app's SEM% thresholds)")
    print("="*70)
    print("App quality thresholds: Excellent < 0.5%, Good < 2%, Fair < 15%")

    # Find minimum cycles for "Good" quality (SEM% < 2%) at each wavelength
    print("\nMinimum cycles for 'Good' quality (SEM% < 2%) at each wavelength:")
    for wl in wavelengths:
        wl_results = [r for r in results if r['wavelength_nm'] == wl]
        wl_results.sort(key=lambda x: x['cycles'])

        min_cycles = None
        for r in wl_results:
            if r['sem_percent_n5'] < 2.0:
                min_cycles = r['cycles']
                break

        if min_cycles:
            match = [r for r in wl_results if r['cycles'] == min_cycles][0]
            print(f"  {wl} nm: {min_cycles} cycles (SEM% = {match['sem_percent_n5']:.2f}%)")
        else:
            best = min(wl_results, key=lambda x: x['sem_percent_n5'])
            print(f"  {wl} nm: >{cycle_counts[-1]} cycles needed (best SEM% = {best['sem_percent_n5']:.2f}% at {best['cycles']} cycles)")

    # Overall recommendation
    print("\n" + "-"*70)

    # Find the minimum cycles that achieves "Good" at ALL wavelengths
    min_universal = None
    for c in cycle_counts:
        all_good = True
        for wl in wavelengths:
            match = [r for r in results if r['wavelength_nm'] == wl and r['cycles'] == c]
            if match and match[0]['sem_percent_n5'] >= 2.0:
                all_good = False
                break
            elif not match:
                all_good = False
                break
        if all_good:
            min_universal = c
            break

    if min_universal:
        # Calculate time savings
        time_at_100 = 100 / 81  # seconds per measurement at 100 cycles
        time_at_new = min_universal / 81
        savings_per_measurement = time_at_100 - time_at_new
        # For a typical sweep: 41 wavelengths × 5 measurements
        total_savings = 41 * 5 * savings_per_measurement

        print(f"RECOMMENDATION: Use {min_universal} cycles (currently using 100)")
        print(f"  - Time per lock-in: {time_at_new:.2f}s vs {time_at_100:.2f}s")
        print(f"  - Savings per sweep: ~{total_savings:.0f}s ({total_savings/60:.1f} min)")
    else:
        print("RECOMMENDATION: Keep 100 cycles - no lower value achieves 'Good' at all wavelengths")
        print("  Consider testing higher cycle counts for weak-signal wavelengths")


def main():
    args = parse_args()

    # Parse wavelengths and cycles
    wavelengths = [int(w.strip()) for w in args.wavelengths.split(',')]
    cycle_counts = [int(c.strip()) for c in args.cycles.split(',')]

    print("Lock-in Cycle Optimization Test")
    print("="*40)
    print(f"Wavelengths: {wavelengths}")
    print(f"Cycle counts: {cycle_counts}")
    print(f"Measurements per combination: {args.measurements}")

    # Generate output filename if not specified
    if args.output:
        output_file = args.output
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f"cycle_optimization_{timestamp}.csv"

    print(f"Output file: {output_file}")

    # Connect to hardware
    picoscope, monochromator = connect_hardware(offline=args.offline)

    try:
        # Run optimization
        results = run_optimization(
            picoscope, monochromator,
            wavelengths, cycle_counts,
            args.measurements, output_file
        )

        # Save results
        save_results(results, output_file)

        # Print summary
        print_summary(results)

    finally:
        # Disconnect hardware
        if not args.offline:
            print("\nDisconnecting hardware...")
            picoscope.disconnect()
            monochromator.disconnect()

    print("\nDone!")


if __name__ == "__main__":
    main()
