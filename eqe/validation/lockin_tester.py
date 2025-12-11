"""
Lock-in Amplifier Hardware Tester

Phase 3 of validation: Test lock-in with PicoScope's AWG generating
known signals fed back into the input channels.

Requires:
- PicoScope 2204A connected
- BNC tee connecting AWG output to both Ch A and Ch B

Author: Physics 2150
Date: December 2025
"""

import numpy as np
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from eqe.drivers.picoscope_driver import PicoScopeDriver


class LockinTester:
    """
    Hardware validation of lock-in amplifier using PicoScope AWG.

    Test Setup:
    - AWG Out -> BNC Tee -> Ch A (signal) + Ch B (reference)
    - AWG generates known amplitude/frequency square wave
    - Lock-in processes and we compare measured R to expected
    """

    def __init__(self):
        """Initialize tester with PicoScope driver."""
        self.scope = None
        self.connected = False

    def connect(self) -> bool:
        """
        Connect to PicoScope.

        Returns:
            bool: True if connected successfully
        """
        self.scope = PicoScopeDriver()
        self.connected = self.scope.connect()
        return self.connected

    def disconnect(self):
        """Disconnect from PicoScope."""
        if self.scope:
            self.scope.close()
            self.connected = False

    def set_awg(self, frequency: float, amplitude_vpp: float,
                waveform: str = 'square', offset_v: float = 0) -> bool:
        """
        Configure the AWG to output a test signal.

        Args:
            frequency: Output frequency in Hz
            amplitude_vpp: Peak-to-peak amplitude in volts
            waveform: 'sine', 'square', or 'triangle'
            offset_v: DC offset in volts

        Returns:
            bool: True if AWG configured successfully
        """
        if not self.connected:
            print("ERROR: Not connected to PicoScope")
            return False

        return self.scope.set_awg(frequency, amplitude_vpp, waveform, offset_v)

    def stop_awg(self) -> bool:
        """
        Stop the AWG output.

        Returns:
            bool: True if stopped successfully
        """
        if not self.connected:
            return False
        return self.scope.stop_awg()

    def run_awg_test(self, frequency: float = 81.0, amplitude_vpp: float = 2.0,
                     num_cycles: int = 50) -> dict:
        """
        Run a single AWG validation test.

        1. Configure AWG to output known signal
        2. Run lock-in measurement
        3. Compare measured R to expected value

        Args:
            frequency: Test frequency in Hz
            amplitude_vpp: Peak-to-peak amplitude in volts
            num_cycles: Number of cycles for lock-in integration

        Returns:
            dict: Test results
        """
        if not self.connected:
            return {'error': 'Not connected'}

        # Configure AWG
        print(f"Setting AWG: {frequency} Hz, {amplitude_vpp} Vpp square wave")
        if not self.set_awg(frequency, amplitude_vpp, 'square'):
            return {'error': 'Failed to configure AWG'}

        # Wait for AWG to stabilize
        import time
        time.sleep(0.5)

        # Run lock-in measurement
        print(f"Running lock-in measurement ({num_cycles} cycles)...")
        result = self.scope.software_lockin(frequency, num_cycles)

        if result is None:
            return {'error': 'Lock-in measurement failed'}

        # Calculate expected R value
        # For square wave: peak amplitude = Vpp/2
        expected_amplitude = amplitude_vpp / 2.0

        # Calculate scaling factor
        scaling_factor = result['R'] / expected_amplitude if expected_amplitude > 0 else 0

        return {
            'frequency': frequency,
            'amplitude_vpp': amplitude_vpp,
            'expected_amplitude': expected_amplitude,
            'measured_R': result['R'],
            'measured_X': result['X'],
            'measured_Y': result['Y'],
            'measured_theta': result['theta'],
            'measured_freq': result['freq'],
            'scaling_factor': scaling_factor,
            'percent_error': (scaling_factor - 1.0) * 100,
            'signal_data': result['signal_data'],
            'reference_data': result['reference_data']
        }

    def run_linearity_test(self, frequency: float = 81.0,
                           amplitudes_vpp: list = None) -> dict:
        """
        Test lock-in linearity with varying AWG amplitudes.

        Args:
            frequency: Test frequency in Hz
            amplitudes_vpp: List of Vpp values to test

        Returns:
            dict: Linearity test results
        """
        if amplitudes_vpp is None:
            # Test from 100mVpp to 4Vpp (2204A AWG max is 4Vpp)
            amplitudes_vpp = [0.1, 0.2, 0.5, 1.0, 2.0, 4.0]

        results = []
        for vpp in amplitudes_vpp:
            print(f"\nTesting {vpp} Vpp...")
            test = self.run_awg_test(frequency, vpp)
            if 'error' not in test:
                results.append({
                    'amplitude_vpp': vpp,
                    'expected': vpp / 2.0,
                    'measured_R': test['measured_R'],
                    'scaling': test['scaling_factor'],
                    'error_percent': test['percent_error']
                })

        if not results:
            return {'error': 'All tests failed'}

        # Calculate linearity
        expected = np.array([r['expected'] for r in results])
        measured = np.array([r['measured_R'] for r in results])

        slope, intercept = np.polyfit(expected, measured, 1)
        fit_line = slope * expected + intercept
        ss_res = np.sum((measured - fit_line) ** 2)
        ss_tot = np.sum((measured - np.mean(measured)) ** 2)
        r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0

        return {
            'results': results,
            'slope': slope,
            'intercept': intercept,
            'r_squared': r_squared,
            'mean_scaling': np.mean([r['scaling'] for r in results]),
            'scaling_std': np.std([r['scaling'] for r in results])
        }

    def run_frequency_test(self, amplitude_vpp: float = 2.0,
                           frequencies: list = None) -> dict:
        """
        Test lock-in response across frequency range.

        Args:
            amplitude_vpp: Test amplitude in Vpp
            frequencies: List of frequencies to test

        Returns:
            dict: Frequency test results
        """
        if frequencies is None:
            frequencies = [50, 60, 70, 81, 90, 100, 120, 150, 200]

        results = []
        for freq in frequencies:
            print(f"\nTesting {freq} Hz...")
            test = self.run_awg_test(freq, amplitude_vpp)
            if 'error' not in test:
                results.append({
                    'frequency': freq,
                    'measured_R': test['measured_R'],
                    'measured_freq': test['measured_freq'],
                    'scaling': test['scaling_factor'],
                    'theta': test['measured_theta']
                })

        if not results:
            return {'error': 'All tests failed'}

        return {
            'results': results,
            'mean_scaling': np.mean([r['scaling'] for r in results]),
            'scaling_std': np.std([r['scaling'] for r in results])
        }

    def run_noise_floor_test(self, frequency: float = 81.0,
                             num_trials: int = 10) -> dict:
        """
        Measure lock-in noise floor with AWG off.

        Args:
            frequency: Reference frequency for lock-in
            num_trials: Number of measurements to average

        Returns:
            dict: Noise floor results
        """
        # Stop AWG to measure baseline noise
        self.stop_awg()

        import time
        time.sleep(0.5)

        Rs = []
        for i in range(num_trials):
            print(f"Noise measurement {i+1}/{num_trials}...")
            result = self.scope.software_lockin(frequency, num_cycles=50)
            if result:
                Rs.append(result['R'])

        if not Rs:
            return {'error': 'All measurements failed'}

        return {
            'mean_R': np.mean(Rs),
            'std_R': np.std(Rs),
            'min_R': np.min(Rs),
            'max_R': np.max(Rs),
            'measurements': Rs
        }


def run_hardware_validation():
    """
    Run complete hardware validation suite.
    """
    print("=" * 60)
    print("Lock-in Amplifier Hardware Validation")
    print("=" * 60)
    print("\nREQUIRED SETUP:")
    print("  AWG Out -> BNC Tee -> Ch A + Ch B")
    print("=" * 60)

    tester = LockinTester()

    # Connect
    print("\nConnecting to PicoScope...")
    if not tester.connect():
        print("ERROR: Failed to connect to PicoScope")
        return None

    try:
        # Test 1: Basic AWG test
        print("\n" + "=" * 40)
        print("1. Basic AWG Test (81 Hz, 2 Vpp)")
        print("=" * 40)
        result = tester.run_awg_test(81.0, 2.0)
        if 'error' not in result:
            print(f"   Expected amplitude: {result['expected_amplitude']:.4f} V")
            print(f"   Measured R:         {result['measured_R']:.4f} V")
            print(f"   Scaling factor:     {result['scaling_factor']:.4f}")
            print(f"   Percent error:      {result['percent_error']:+.2f}%")
            print(f"   Measured frequency: {result['measured_freq']:.2f} Hz")
            print(f"   Phase:              {result['measured_theta']:.1f}°")
        else:
            print(f"   ERROR: {result['error']}")

        # Test 2: Linearity
        print("\n" + "=" * 40)
        print("2. Linearity Test")
        print("=" * 40)
        linearity = tester.run_linearity_test()
        if 'error' not in linearity:
            print(f"   R² (linearity):  {linearity['r_squared']:.6f}")
            print(f"   Mean scaling:    {linearity['mean_scaling']:.4f}")
            print(f"   Scaling std:     {linearity['scaling_std']:.4f}")
            print(f"\n   {'Vpp':<8} {'Expected':<10} {'Measured':<10} {'Error %':<10}")
            for r in linearity['results']:
                print(f"   {r['amplitude_vpp']:<8.2f} {r['expected']:<10.4f} {r['measured_R']:<10.4f} {r['error_percent']:+.2f}")
        else:
            print(f"   ERROR: {linearity['error']}")

        # Test 3: Noise floor
        print("\n" + "=" * 40)
        print("3. Noise Floor Test (AWG off)")
        print("=" * 40)
        noise = tester.run_noise_floor_test(num_trials=5)
        if 'error' not in noise:
            print(f"   Mean R:  {noise['mean_R']:.6f} V")
            print(f"   Std R:   {noise['std_R']:.6f} V")
            print(f"   Range:   {noise['min_R']:.6f} to {noise['max_R']:.6f} V")
        else:
            print(f"   ERROR: {noise['error']}")

    finally:
        # Clean up
        tester.stop_awg()
        tester.disconnect()

    print("\n" + "=" * 60)
    print("Hardware validation complete")
    print("=" * 60)

    return tester


if __name__ == "__main__":
    run_hardware_validation()
