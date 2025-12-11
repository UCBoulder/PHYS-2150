"""
Keysight AWG Validation Test

Uses the EDU33212A arbitrary waveform generator to validate the lock-in
amplifier with more accurate signals than the PicoScope's built-in AWG.

Test Setup:
  EDU33212A Ch1 --> PicoScope Ch A (signal)
  EDU33212A Ch2 --> PicoScope Ch B (reference)

Author: Physics 2150
Date: December 2025
"""

import pyvisa
import time
import numpy as np
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from eqe.drivers.picoscope_driver import PicoScopeDriver


class KeysightAWG:
    """Driver for Keysight EDU33212A Arbitrary Waveform Generator."""

    def __init__(self, resource_string=None):
        """
        Initialize connection to AWG.

        Args:
            resource_string: VISA resource string (auto-detected if None)
        """
        self.rm = pyvisa.ResourceManager()
        self.inst = None
        self.resource_string = resource_string

    def connect(self) -> bool:
        """Connect to the AWG."""
        try:
            if self.resource_string is None:
                # Auto-detect EDU33212A
                for r in self.rm.list_resources():
                    try:
                        inst = self.rm.open_resource(r, timeout=2000)
                        idn = inst.query('*IDN?')
                        if 'EDU33212A' in idn:
                            self.inst = inst
                            self.resource_string = r
                            print(f"Connected to: {idn.strip()}")
                            return True
                        inst.close()
                    except:
                        pass
                print("ERROR: EDU33212A not found")
                return False
            else:
                self.inst = self.rm.open_resource(self.resource_string, timeout=5000)
                idn = self.inst.query('*IDN?')
                print(f"Connected to: {idn.strip()}")
                return True
        except Exception as e:
            print(f"ERROR connecting to AWG: {e}")
            return False

    def disconnect(self):
        """Disconnect from AWG."""
        if self.inst:
            self.output_off(1)
            self.output_off(2)
            self.inst.close()

    def setup_square_wave(self, channel: int, frequency: float, amplitude_vpp: float,
                          offset: float = 0, phase_deg: float = 0, duty_cycle: float = 50):
        """
        Configure a channel to output a square wave.

        Args:
            channel: 1 or 2
            frequency: Frequency in Hz
            amplitude_vpp: Peak-to-peak amplitude in volts
            offset: DC offset in volts
            phase_deg: Phase offset in degrees
            duty_cycle: Duty cycle in percent (default 50%)
        """
        ch = f"SOURce{channel}"
        self.inst.write(f"{ch}:FUNCtion SQUare")
        self.inst.write(f"{ch}:FREQuency {frequency}")
        self.inst.write(f"{ch}:VOLTage {amplitude_vpp}")
        self.inst.write(f"{ch}:VOLTage:OFFSet {offset}")
        self.inst.write(f"{ch}:PHASe {phase_deg}")
        self.inst.write(f"{ch}:FUNCtion:SQUare:DCYCle {duty_cycle}")

    def setup_sine_wave(self, channel: int, frequency: float, amplitude_vpp: float,
                        offset: float = 0, phase_deg: float = 0):
        """
        Configure a channel to output a sine wave.

        Args:
            channel: 1 or 2
            frequency: Frequency in Hz
            amplitude_vpp: Peak-to-peak amplitude in volts
            offset: DC offset in volts
            phase_deg: Phase offset in degrees
        """
        ch = f"SOURce{channel}"
        self.inst.write(f"{ch}:FUNCtion SINusoid")
        self.inst.write(f"{ch}:FREQuency {frequency}")
        self.inst.write(f"{ch}:VOLTage {amplitude_vpp}")
        self.inst.write(f"{ch}:VOLTage:OFFSet {offset}")
        self.inst.write(f"{ch}:PHASe {phase_deg}")

    def sync_phases(self):
        """Synchronize phases of both channels."""
        self.inst.write("PHASe:SYNChronize")

    def output_on(self, channel: int):
        """Enable output on a channel."""
        self.inst.write(f"OUTPut{channel} ON")

    def output_off(self, channel: int):
        """Disable output on a channel."""
        self.inst.write(f"OUTPut{channel} OFF")

    def set_high_z(self, channel: int):
        """Set output to high-Z load (for accurate voltage into high-impedance input)."""
        self.inst.write(f"OUTPut{channel}:LOAD INFinity")


def run_keysight_validation():
    """
    Run comprehensive validation using Keysight AWG.
    """
    print("=" * 60)
    print("Lock-in Validation with Keysight EDU33212A")
    print("=" * 60)
    print("\nSetup:")
    print("  AWG Ch1 --> PicoScope Ch A (signal)")
    print("  AWG Ch2 --> PicoScope Ch B (reference)")
    print("=" * 60)

    # Connect to instruments
    awg = KeysightAWG()
    if not awg.connect():
        return None

    scope = PicoScopeDriver()
    if not scope.connect():
        awg.disconnect()
        return None

    results = {}

    try:
        # Configure AWG for high-Z load (PicoScope input is 1 MΩ)
        awg.set_high_z(1)
        awg.set_high_z(2)

        # ============================================================
        # Test 1: Amplitude Accuracy
        # ============================================================
        print("\n" + "=" * 50)
        print("Test 1: Amplitude Accuracy (81 Hz square wave)")
        print("=" * 50)

        amplitudes = [0.1, 0.2, 0.5, 1.0, 2.0]
        amp_results = []

        for vpp in amplitudes:
            # Setup both channels with identical square waves
            awg.setup_square_wave(1, 81.0, vpp)
            awg.setup_square_wave(2, 81.0, vpp)
            awg.sync_phases()
            awg.output_on(1)
            awg.output_on(2)
            time.sleep(0.5)

            # Measure with both algorithms
            r_hilbert = scope.software_lockin(81.0, 50, 'hilbert', 0.5)
            r_synth = scope.software_lockin(81.0, 50, 'synthesized')

            expected = vpp / 2.0
            h_err = (r_hilbert['R'] / expected - 1) * 100 if r_hilbert else float('nan')
            s_err = (r_synth['R'] / expected - 1) * 100 if r_synth else float('nan')

            amp_results.append({
                'vpp': vpp,
                'expected': expected,
                'hilbert': r_hilbert['R'] if r_hilbert else 0,
                'synthesized': r_synth['R'] if r_synth else 0,
                'hilbert_err': h_err,
                'synth_err': s_err
            })

            print(f"  {vpp:.1f} Vpp: Hilbert={r_hilbert['R']:.4f}V ({h_err:+.1f}%), "
                  f"Synth={r_synth['R']:.4f}V ({s_err:+.1f}%)")

        results['amplitude'] = amp_results

        # ============================================================
        # Test 2: Frequency Response
        # ============================================================
        print("\n" + "=" * 50)
        print("Test 2: Frequency Response (1 Vpp)")
        print("=" * 50)

        frequencies = [50, 60, 70, 81, 90, 100, 120, 150, 200]
        freq_results = []

        for freq in frequencies:
            awg.setup_square_wave(1, freq, 1.0)
            awg.setup_square_wave(2, freq, 1.0)
            awg.sync_phases()
            time.sleep(0.5)

            r_hilbert = scope.software_lockin(freq, 50, 'hilbert', 0.5)
            r_synth = scope.software_lockin(freq, 50, 'synthesized')

            expected = 0.5  # 1 Vpp / 2
            h_err = (r_hilbert['R'] / expected - 1) * 100 if r_hilbert else float('nan')
            s_err = (r_synth['R'] / expected - 1) * 100 if r_synth else float('nan')

            freq_results.append({
                'frequency': freq,
                'hilbert': r_hilbert['R'] if r_hilbert else 0,
                'synthesized': r_synth['R'] if r_synth else 0,
                'measured_freq': r_hilbert['freq'] if r_hilbert else 0,
                'hilbert_err': h_err,
                'synth_err': s_err
            })

            print(f"  {freq:3d} Hz: Hilbert={r_hilbert['R']:.4f}V ({h_err:+.1f}%), "
                  f"Synth={r_synth['R']:.4f}V ({s_err:+.1f}%), "
                  f"Measured={r_hilbert['freq']:.1f} Hz")

        results['frequency'] = freq_results

        # ============================================================
        # Test 3: Phase Offset Response
        # ============================================================
        print("\n" + "=" * 50)
        print("Test 3: Phase Offset Response (81 Hz, 1 Vpp)")
        print("=" * 50)

        phases = [0, 30, 45, 60, 90, 120, 150, 180]
        phase_results = []

        awg.setup_square_wave(1, 81.0, 1.0, phase_deg=0)
        awg.output_on(1)

        for phase in phases:
            awg.setup_square_wave(2, 81.0, 1.0, phase_deg=phase)
            awg.sync_phases()
            time.sleep(0.5)

            r_hilbert = scope.software_lockin(81.0, 50, 'hilbert', 0.5)
            r_synth = scope.software_lockin(81.0, 50, 'synthesized')

            phase_results.append({
                'phase_set': phase,
                'hilbert_R': r_hilbert['R'] if r_hilbert else 0,
                'hilbert_theta': r_hilbert['theta'] if r_hilbert else 0,
                'synth_R': r_synth['R'] if r_synth else 0,
                'synth_theta': r_synth['theta'] if r_synth else 0
            })

            print(f"  Phase {phase:3d} deg: Hilbert R={r_hilbert['R']:.4f}V, theta={r_hilbert['theta']:+.1f} deg | "
                  f"Synth R={r_synth['R']:.4f}V, theta={r_synth['theta']:+.1f} deg")

        results['phase'] = phase_results

        # ============================================================
        # Test 4: Sine Wave Signal (closer to real photocurrent)
        # ============================================================
        print("\n" + "=" * 50)
        print("Test 4: Sine Wave Signal with Square Reference")
        print("=" * 50)

        print("  (Simulates filtered/smoothed photocurrent)")

        sine_results = []
        for vpp in [0.5, 1.0, 2.0]:
            awg.setup_sine_wave(1, 81.0, vpp)  # Sine signal
            awg.setup_square_wave(2, 81.0, 1.0)  # Square reference
            awg.sync_phases()
            time.sleep(0.5)

            r_hilbert = scope.software_lockin(81.0, 50, 'hilbert', 0.5)
            r_synth = scope.software_lockin(81.0, 50, 'synthesized')

            expected = vpp / 2.0
            h_err = (r_hilbert['R'] / expected - 1) * 100 if r_hilbert else float('nan')
            s_err = (r_synth['R'] / expected - 1) * 100 if r_synth else float('nan')

            sine_results.append({
                'vpp': vpp,
                'expected': expected,
                'hilbert': r_hilbert['R'] if r_hilbert else 0,
                'synthesized': r_synth['R'] if r_synth else 0
            })

            print(f"  {vpp:.1f} Vpp sine: Hilbert={r_hilbert['R']:.4f}V ({h_err:+.1f}%), "
                  f"Synth={r_synth['R']:.4f}V ({s_err:+.1f}%)")

        results['sine'] = sine_results

        # ============================================================
        # Test 5: Duty Cycle Variation
        # ============================================================
        print("\n" + "=" * 50)
        print("Test 5: Duty Cycle Variation (81 Hz, 1 Vpp)")
        print("=" * 50)

        duty_cycles = [30, 40, 50, 60, 70]
        duty_results = []

        for duty in duty_cycles:
            awg.setup_square_wave(1, 81.0, 1.0, duty_cycle=duty)
            awg.setup_square_wave(2, 81.0, 1.0, duty_cycle=50)  # Reference stays 50%
            awg.sync_phases()
            time.sleep(0.5)

            r_hilbert = scope.software_lockin(81.0, 50, 'hilbert', 0.5)
            r_synth = scope.software_lockin(81.0, 50, 'synthesized')

            duty_results.append({
                'duty_cycle': duty,
                'hilbert': r_hilbert['R'] if r_hilbert else 0,
                'synthesized': r_synth['R'] if r_synth else 0
            })

            print(f"  Duty {duty:2d}%: Hilbert={r_hilbert['R']:.4f}V, Synth={r_synth['R']:.4f}V")

        results['duty_cycle'] = duty_results

    finally:
        awg.output_off(1)
        awg.output_off(2)
        awg.disconnect()
        scope.close()

    # ============================================================
    # Summary
    # ============================================================
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    # Calculate overall statistics
    amp_h_errors = [r['hilbert_err'] for r in results['amplitude']]
    amp_s_errors = [r['synth_err'] for r in results['amplitude']]
    freq_h_errors = [r['hilbert_err'] for r in results['frequency']]
    freq_s_errors = [r['synth_err'] for r in results['frequency']]

    print(f"\nAmplitude Test (mean error):")
    print(f"  Hilbert:     {np.mean(amp_h_errors):+.2f}% (std: {np.std(amp_h_errors):.2f}%)")
    print(f"  Synthesized: {np.mean(amp_s_errors):+.2f}% (std: {np.std(amp_s_errors):.2f}%)")

    print(f"\nFrequency Test (mean error):")
    print(f"  Hilbert:     {np.mean(freq_h_errors):+.2f}% (std: {np.std(freq_h_errors):.2f}%)")
    print(f"  Synthesized: {np.mean(freq_s_errors):+.2f}% (std: {np.std(freq_s_errors):.2f}%)")

    print(f"\nPhase tracking (R should be constant ~0.5V):")
    phase_h_R = [r['hilbert_R'] for r in results['phase']]
    phase_s_R = [r['synth_R'] for r in results['phase']]
    print(f"  Hilbert:     mean={np.mean(phase_h_R):.4f}V, std={np.std(phase_h_R):.4f}V")
    print(f"  Synthesized: mean={np.mean(phase_s_R):.4f}V, std={np.std(phase_s_R):.4f}V")

    print("\n" + "=" * 60)

    return results


if __name__ == "__main__":
    run_keysight_validation()
