"""
TIA (Transimpedance Amplifier) Gain Verification Test

This script verifies the TIA gain by:
1. Sourcing known DC currents from the Keithley 2450 SMU
2. Measuring the TIA output voltage with the PicoScope
3. Calculating actual gain: V_out / I_in

Setup:
    Keithley 2450 HI → TIA input (photodiode side)
    Keithley 2450 LO → TIA ground
    TIA output → PicoScope Ch A

Expected gain: 1 MΩ (1e6 V/A)
    - 1 µA input → 1 V output
    - 100 nA input → 100 mV output
    - 10 µA input → 10 V output

Author: Physics 2150
Date: December 2025
"""

import sys
import time
import numpy as np
import pyvisa as visa
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from eqe.drivers.picoscope_driver import PicoScopeDriver


class Keithley2450CurrentSource:
    """
    Simplified Keithley 2450 controller for current sourcing.

    This is a minimal controller specifically for TIA testing.
    """

    def __init__(self):
        self._rm = None
        self._device = None
        self._connected = False

    def connect(self, address=None):
        """Connect to Keithley 2450."""
        try:
            self._rm = visa.ResourceManager()

            if address is None:
                # Search for Keithley
                for resource in self._rm.list_resources():
                    if "USB0::0x05E6::0x2450" in resource:
                        address = resource
                        break

            if address is None:
                print("ERROR: Keithley 2450 not found")
                return False

            self._device = self._rm.open_resource(address)
            self._device.timeout = 5000
            self._connected = True

            # Get ID
            idn = self._device.query("*IDN?").strip()
            print(f"Connected to: {idn}")

            return True

        except Exception as e:
            print(f"ERROR connecting to Keithley: {e}")
            return False

    def configure_current_source(self, current_range=1e-6, voltage_limit=10):
        """
        Configure as DC current source.

        Args:
            current_range: Current source range in Amps (e.g., 1e-6 for 1 µA range)
            voltage_limit: Voltage compliance limit in Volts
        """
        if not self._connected:
            raise RuntimeError("Not connected")

        # Reset to known state
        self._device.write("*RST")
        time.sleep(0.5)

        # Configure as current source
        self._device.write("SOUR:FUNC CURR")  # Current source mode
        self._device.write(f"SOUR:CURR:RANG {current_range}")  # Set range
        self._device.write(f"SOUR:CURR:VLIM {voltage_limit}")  # Voltage compliance
        self._device.write("SOUR:CURR 0")  # Start at 0

        # Configure voltage measurement (to verify compliance)
        self._device.write('SENS:FUNC "VOLT"')
        self._device.write("SENS:VOLT:RANG 10")  # 10V range

        print(f"Configured: Current source, {current_range*1e6:.1f} µA range, {voltage_limit}V compliance")

    def set_current(self, current_amps):
        """Set output current in Amps."""
        if not self._connected:
            raise RuntimeError("Not connected")
        self._device.write(f"SOUR:CURR {current_amps}")

    def measure_voltage(self):
        """Measure voltage at output (to check compliance)."""
        if not self._connected:
            raise RuntimeError("Not connected")
        response = self._device.query("MEAS:VOLT?")
        return float(response)

    def output_on(self):
        """Enable output."""
        self._device.write("OUTP ON")

    def output_off(self):
        """Disable output."""
        self._device.write("OUTP OFF")

    def disconnect(self):
        """Disconnect from device."""
        if self._connected:
            try:
                self.output_off()
                self._device.close()
            except:
                pass
            self._connected = False


def measure_dc_voltage(scope, num_samples=1000, settle_time=0.5):
    """
    Measure DC voltage using PicoScope.

    Takes a block capture and returns the mean voltage on Channel A.

    Args:
        scope: Connected PicoScopeDriver instance
        num_samples: Number of samples to average
        settle_time: Time to wait before measuring (seconds)

    Returns:
        tuple: (mean_voltage, std_dev) in Volts
    """
    time.sleep(settle_time)  # Let signal settle

    # Acquire data - use minimal decimation for fast capture
    signal_data, _ = scope._acquire_block(num_samples, decimation=1)

    if signal_data is None:
        return None, None

    mean_v = np.mean(signal_data)
    std_v = np.std(signal_data, ddof=1) if len(signal_data) > 1 else 0.0

    return mean_v, std_v


def run_tia_gain_test():
    """
    Run the TIA gain verification test.
    """
    print("=" * 60)
    print("TIA GAIN VERIFICATION TEST")
    print("=" * 60)
    print()
    print("Setup required:")
    print("  - Keithley 2450 HI → TIA input")
    print("  - Keithley 2450 LO → TIA ground")
    print("  - TIA output → PicoScope Ch A")
    print()

    # Test currents to source (in Amps)
    # Keep within PicoScope ±2V range (for 1 MΩ TIA, max ~1.8 µA)
    test_currents = [
        50e-9,    # 50 nA → expect 50 mV
        100e-9,   # 100 nA → expect 100 mV
        200e-9,   # 200 nA → expect 200 mV
        500e-9,   # 500 nA → expect 500 mV
        1e-6,     # 1 µA → expect 1 V
        1.5e-6,   # 1.5 µA → expect 1.5 V
        1.8e-6,   # 1.8 µA → expect 1.8 V (near scope limit)
    ]

    expected_gain = 1e6  # 1 MΩ (magnitude - TIA may be inverting)

    # Initialize devices
    keithley = Keithley2450CurrentSource()
    scope = PicoScopeDriver()

    try:
        # Connect to Keithley
        print("Connecting to Keithley 2450...")
        if not keithley.connect():
            print("FAILED: Could not connect to Keithley 2450")
            return

        # Connect to PicoScope
        print("\nConnecting to PicoScope...")
        if not scope.connect():
            print("FAILED: Could not connect to PicoScope")
            return

        # Configure Keithley as current source
        print("\nConfiguring Keithley as current source...")
        keithley.configure_current_source(
            current_range=10e-6,  # 10 µA range (covers all test currents)
            voltage_limit=15      # 15V compliance (TIA may output up to 10V)
        )

        # Measure offset with 0 current
        print("\nMeasuring zero-current offset...")
        keithley.set_current(0)
        keithley.output_on()
        time.sleep(1.0)  # Let it settle

        offset_v, offset_std = measure_dc_voltage(scope, settle_time=0.5)
        print(f"  Offset voltage: {offset_v*1000:.2f} mV (σ = {offset_std*1000:.2f} mV)")

        # Run gain tests
        print("\n" + "-" * 60)
        print("GAIN MEASUREMENTS")
        print("-" * 60)
        print(f"{'Current':>12}  {'V_out':>10}  {'Gain':>12}  {'Error':>8}  {'Status'}")
        print("-" * 60)

        results = []

        for i_source in test_currents:
            # Set current
            keithley.set_current(i_source)
            time.sleep(0.3)  # Settling time

            # Measure output voltage
            v_out, v_std = measure_dc_voltage(scope, settle_time=0.3)

            if v_out is None:
                print(f"{i_source*1e6:>10.2f} µA  {'ERROR':>10}  {'---':>12}  {'---':>8}")
                continue

            # Subtract offset
            v_corrected = v_out - offset_v

            # Check for saturation (PicoScope 2204A at ±2V range)
            saturation_threshold = 1.95  # V (leave margin)
            is_saturated = abs(v_corrected) > saturation_threshold

            # Calculate gain (use magnitude - TIA may be inverting)
            if i_source > 0:
                measured_gain = abs(v_corrected) / i_source
                error_pct = (measured_gain - expected_gain) / expected_gain * 100

                # Check if within tolerance (±5%) and not saturated
                if is_saturated:
                    status = "CLIPPED"
                elif abs(error_pct) < 5:
                    status = "OK"
                else:
                    status = "CHECK"

                # Only include non-saturated results in analysis
                if not is_saturated:
                    results.append({
                        'current': i_source,
                        'voltage': abs(v_corrected),
                        'gain': measured_gain,
                        'error': error_pct,
                        'is_inverting': v_corrected < 0
                    })

                # Show sign to indicate inverting/non-inverting
                sign = "-" if v_corrected < 0 else "+"
                print(f"{i_source*1e6:>10.2f} µA  {v_corrected:>+10.4f} V  {sign}{measured_gain/1e6:>9.4f} MΩ  {error_pct:>+7.2f}%  {status}")

        # Summary
        print("\n" + "=" * 60)
        print("SUMMARY")
        print("=" * 60)

        if results:
            gains = [r['gain'] for r in results]
            mean_gain = np.mean(gains)
            std_gain = np.std(gains, ddof=1) if len(gains) > 1 else 0.0

            print(f"  Mean gain:      {mean_gain/1e6:.4f} MΩ")
            print(f"  Std deviation:  {std_gain/1e6:.4f} MΩ ({std_gain/mean_gain*100:.2f}%)")
            print(f"  Expected:       {expected_gain/1e6:.4f} MΩ")
            print(f"  Overall error:  {(mean_gain - expected_gain)/expected_gain*100:+.2f}%")

            # Linearity check
            currents = np.array([r['current'] for r in results])
            voltages = np.array([r['voltage'] for r in results])

            # Linear fit
            coeffs = np.polyfit(currents, voltages, 1)
            fitted_gain = coeffs[0]

            # R² calculation
            fitted = np.polyval(coeffs, currents)
            ss_res = np.sum((voltages - fitted) ** 2)
            ss_tot = np.sum((voltages - np.mean(voltages)) ** 2)
            r_squared = 1 - (ss_res / ss_tot)

            print(f"\n  Linear fit gain: {fitted_gain/1e6:.4f} MΩ")
            print(f"  Linearity (R²):  {r_squared:.6f}")

            # Check if TIA is inverting (majority of readings negative)
            is_inverting = sum(1 for r in results if r['is_inverting']) > len(results) / 2

            if abs((mean_gain - expected_gain)/expected_gain) < 0.05:
                print(f"\n  ✓ TIA gain is within 5% of expected 1 MΩ")
                if is_inverting:
                    print("  ✓ TIA is inverting (negative output) - this is normal")
                print("\n  No changes needed to settings.py")
            else:
                print(f"\n  ⚠ TIA gain differs from expected!")
                print(f"    Update eqe/config/settings.py transimpedance_gain to: {1/mean_gain:.2e}")

        # Turn off
        keithley.set_current(0)
        keithley.output_off()

    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")

    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()

    finally:
        # Clean up
        print("\nCleaning up...")
        keithley.disconnect()
        scope.close()
        print("Done.")


if __name__ == "__main__":
    run_tia_gain_test()
