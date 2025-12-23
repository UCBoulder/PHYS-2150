"""
Measurement Parameter Optimization Script

Tests different combinations of measurement parameters at various wavelengths
to find optimal settings for minimizing CV% (coefficient of variation).

Run with: python scripts/test_measurement_parameters.py

Author: PHYS 2150 Lab
"""

import sys
import time
import numpy as np
from pathlib import Path
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from eqe.controllers.picoscope_lockin import PicoScopeController
from eqe.controllers.monochromator import MonochromatorController


def measure_with_params(lockin: PicoScopeController,
                        num_cycles: int,
                        num_measurements: int,
                        remove_outliers: bool = False) -> dict:
    """
    Take measurements with specified parameters and return statistics.

    Args:
        lockin: PicoScope controller instance
        num_cycles: Number of lock-in integration cycles
        num_measurements: Number of readings to average
        remove_outliers: Whether to apply outlier rejection

    Returns:
        dict with mean, std, cv_percent, n_used, raw_values
    """
    # Set number of cycles
    original_cycles = lockin._num_cycles
    lockin._num_cycles = num_cycles

    try:
        R_values = []

        for i in range(num_measurements):
            result = lockin.perform_lockin_measurement()
            if result is not None:
                R_values.append(result['R'])

        if not R_values:
            return None

        R_array = np.array(R_values)

        if remove_outliers and len(R_array) >= 5:
            # Same algorithm as production code
            median_signal = np.median(R_array)
            deviations = np.abs(R_array - median_signal)
            threshold = 2 * np.std(deviations)
            mask = deviations <= threshold
            if np.sum(mask) >= 3:
                R_used = R_array[mask]
            else:
                R_used = R_array
        else:
            R_used = R_array

        mean_val = np.mean(R_used)
        std_val = np.std(R_used)
        cv = 100 * std_val / mean_val if mean_val > 0 else 0

        # Convert to current (nA) for readability
        tia_gain = 1e-6  # 1 MΩ
        correction = 0.5
        mean_nA = mean_val * tia_gain * correction * 1e9
        std_nA = std_val * tia_gain * correction * 1e9

        return {
            'mean_nA': mean_nA,
            'std_nA': std_nA,
            'cv_percent': cv,
            'n_used': len(R_used),
            'n_total': len(R_array),
            'raw_values_nA': R_array * tia_gain * correction * 1e9
        }

    finally:
        lockin._num_cycles = original_cycles


def test_stabilization_time(mono: MonochromatorController,
                           lockin: PicoScopeController,
                           wavelength: float,
                           stabilization_times: list,
                           num_cycles: int = 100,
                           num_measurements: int = 10):
    """Test different stabilization times after wavelength change."""

    print(f"\n{'='*60}")
    print(f"Testing stabilization times at {wavelength} nm")
    print(f"num_cycles={num_cycles}, num_measurements={num_measurements}")
    print(f"{'='*60}")

    results = []

    for stab_time in stabilization_times:
        # Move away then back to force a real wavelength change
        mono.set_wavelength(wavelength - 50)
        time.sleep(0.5)

        # Move to target and wait
        mono.set_wavelength(wavelength)
        time.sleep(stab_time)

        # Measure
        stats = measure_with_params(lockin, num_cycles, num_measurements, remove_outliers=False)

        if stats:
            print(f"  stab_time={stab_time:.1f}s: {stats['mean_nA']:.2f} ± {stats['std_nA']:.2f} nA, CV={stats['cv_percent']:.1f}%")
            results.append({
                'stabilization_time': stab_time,
                **stats
            })

    return results


def test_num_cycles(lockin: PicoScopeController,
                    cycle_values: list,
                    num_measurements: int = 10):
    """Test different numbers of lock-in integration cycles."""

    print(f"\n{'='*60}")
    print(f"Testing num_cycles (num_measurements={num_measurements})")
    print(f"{'='*60}")

    results = []

    for cycles in cycle_values:
        start = time.time()
        stats = measure_with_params(lockin, cycles, num_measurements, remove_outliers=False)
        elapsed = time.time() - start

        if stats:
            time_per_meas = elapsed / num_measurements
            print(f"  cycles={cycles:3d}: {stats['mean_nA']:.2f} ± {stats['std_nA']:.2f} nA, CV={stats['cv_percent']:.1f}%, time/meas={time_per_meas:.2f}s")
            results.append({
                'num_cycles': cycles,
                'time_per_measurement': time_per_meas,
                **stats
            })

    return results


def test_num_measurements(lockin: PicoScopeController,
                          measurement_counts: list,
                          num_cycles: int = 100):
    """Test different numbers of measurements to average."""

    print(f"\n{'='*60}")
    print(f"Testing num_measurements (num_cycles={num_cycles})")
    print(f"{'='*60}")

    results = []

    for n_meas in measurement_counts:
        start = time.time()
        stats = measure_with_params(lockin, num_cycles, n_meas, remove_outliers=False)
        elapsed = time.time() - start

        if stats:
            print(f"  n={n_meas:2d}: {stats['mean_nA']:.2f} ± {stats['std_nA']:.2f} nA, CV={stats['cv_percent']:.1f}%, total_time={elapsed:.1f}s")
            print(f"         raw values: {', '.join([f'{v:.1f}' for v in stats['raw_values_nA']])}")
            results.append({
                'num_measurements': n_meas,
                'total_time': elapsed,
                **stats
            })

    return results


def test_outlier_rejection(lockin: PicoScopeController,
                           num_cycles: int = 100,
                           num_measurements: int = 10):
    """Compare results with and without outlier rejection."""

    print(f"\n{'='*60}")
    print(f"Testing outlier rejection effect")
    print(f"{'='*60}")

    stats_no_reject = measure_with_params(lockin, num_cycles, num_measurements, remove_outliers=False)
    stats_with_reject = measure_with_params(lockin, num_cycles, num_measurements, remove_outliers=True)

    if stats_no_reject and stats_with_reject:
        print(f"  Without rejection: {stats_no_reject['mean_nA']:.2f} ± {stats_no_reject['std_nA']:.2f} nA, CV={stats_no_reject['cv_percent']:.1f}% (n={stats_no_reject['n_used']}/{stats_no_reject['n_total']})")
        print(f"  With rejection:    {stats_with_reject['mean_nA']:.2f} ± {stats_with_reject['std_nA']:.2f} nA, CV={stats_with_reject['cv_percent']:.1f}% (n={stats_with_reject['n_used']}/{stats_with_reject['n_total']})")

    return {'without': stats_no_reject, 'with': stats_with_reject}


def run_wavelength_sweep_test(mono: MonochromatorController,
                              lockin: PicoScopeController,
                              wavelengths: list,
                              num_cycles: int = 100,
                              num_measurements: int = 10,
                              stabilization_time: float = 0.5):
    """Test parameters across multiple wavelengths."""

    print(f"\n{'='*60}")
    print(f"Wavelength sweep test")
    print(f"cycles={num_cycles}, n={num_measurements}, stab={stabilization_time}s")
    print(f"{'='*60}")

    results = []

    mono.open_shutter()

    for wl in wavelengths:
        mono.set_wavelength(wl)
        mono.set_filter_for_wavelength(wl)
        time.sleep(stabilization_time)

        stats = measure_with_params(lockin, num_cycles, num_measurements, remove_outliers=False)

        if stats:
            print(f"  {wl:3.0f}nm: {stats['mean_nA']:7.2f} ± {stats['std_nA']:5.2f} nA, CV={stats['cv_percent']:5.1f}%")
            results.append({
                'wavelength': wl,
                **stats
            })

    return results


def main():
    print("="*60)
    print("Measurement Parameter Optimization Test")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)

    # Initialize devices
    print("\nInitializing devices...")

    try:
        mono = MonochromatorController()
        mono.connect()
        print("  Monochromator connected")

        lockin = PicoScopeController()
        lockin.connect()
        print("  PicoScope connected")

    except Exception as e:
        print(f"Failed to initialize devices: {e}")
        return

    try:
        # Open shutter and go to a good wavelength for testing
        mono.open_shutter()
        test_wavelength = 550  # Peak signal
        mono.set_wavelength(test_wavelength)
        mono.set_filter_for_wavelength(test_wavelength)
        print(f"\nSet to {test_wavelength} nm, waiting for stabilization...")
        time.sleep(2.0)

        # Test 1: Number of cycles at peak wavelength
        print("\n" + "="*60)
        print("TEST 1: Effect of num_cycles on measurement precision")
        print("="*60)
        test_num_cycles(lockin, [50, 75, 100, 150, 200], num_measurements=10)

        # Test 2: Number of measurements
        print("\n" + "="*60)
        print("TEST 2: Effect of num_measurements on statistics")
        print("="*60)
        test_num_measurements(lockin, [5, 10, 15, 20], num_cycles=100)

        # Test 3: Stabilization time
        print("\n" + "="*60)
        print("TEST 3: Effect of stabilization time after wavelength change")
        print("="*60)
        test_stabilization_time(mono, lockin, 550, [0.1, 0.2, 0.5, 1.0], num_cycles=100, num_measurements=10)

        # Test 4: Outlier rejection comparison
        print("\n" + "="*60)
        print("TEST 4: Outlier rejection effect")
        print("="*60)
        test_outlier_rejection(lockin, num_cycles=100, num_measurements=15)

        # Test 5: Sweep across wavelengths
        print("\n" + "="*60)
        print("TEST 5: Performance across wavelength range")
        print("="*60)
        test_wavelengths = [350, 400, 450, 500, 550, 600, 650, 700, 750]
        run_wavelength_sweep_test(mono, lockin, test_wavelengths,
                                  num_cycles=100, num_measurements=10, stabilization_time=0.5)

        # Test 6: Repeat wavelength sweep with more cycles
        print("\n" + "="*60)
        print("TEST 6: Wavelength sweep with increased cycles (150)")
        print("="*60)
        run_wavelength_sweep_test(mono, lockin, test_wavelengths,
                                  num_cycles=150, num_measurements=10, stabilization_time=0.5)

        print("\n" + "="*60)
        print("TESTS COMPLETE")
        print(f"Finished: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*60)

        # Return to safe position
        mono.set_wavelength(532)
        mono.close_shutter()

    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")

    except Exception as e:
        print(f"\nError during testing: {e}")
        import traceback
        traceback.print_exc()

    finally:
        # Cleanup
        print("\nCleaning up...")
        try:
            mono.close_shutter()
            mono.disconnect()
        except:
            pass
        try:
            lockin.disconnect()
        except:
            pass


if __name__ == "__main__":
    main()
