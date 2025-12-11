"""
Lock-in Amplifier Simulator

Phase 1 of validation: Test lock-in algorithm with synthetic signals.
No hardware required - runs the exact same algorithm as picoscope_driver.py
with known input signals to verify scaling and accuracy.

Author: Physics 2150
Date: December 2025
"""

import numpy as np
from scipy.signal import hilbert


class LockinSimulator:
    """
    Simulate and test the lock-in algorithm with synthetic signals.

    This class generates known test signals and runs them through the
    exact same lock-in algorithm used in picoscope_driver.py to verify
    correct scaling and operation.
    """

    def __init__(self, sample_rate: float = 24414.0, num_samples: int = 2000):
        """
        Initialize simulator.

        Args:
            sample_rate: Simulated sample rate in Hz (default matches ps2000 timebase 12)
            num_samples: Number of samples per acquisition (default 2000 for ps2000)
        """
        self.sample_rate = sample_rate
        self.num_samples = num_samples
        self.t = np.arange(num_samples) / sample_rate

    def generate_square_wave(self, frequency: float, amplitude: float,
                             phase_deg: float = 0, duty_cycle: float = 0.5,
                             dc_offset: float = 0) -> np.ndarray:
        """
        Generate a square wave signal.

        Args:
            frequency: Frequency in Hz
            amplitude: Peak amplitude in volts (signal swings ±amplitude)
            phase_deg: Phase offset in degrees
            duty_cycle: Duty cycle (0 to 1)
            dc_offset: DC offset in volts

        Returns:
            np.ndarray: Square wave signal
        """
        phase_rad = np.deg2rad(phase_deg)
        # Create square wave using sign of sine
        phase = 2 * np.pi * frequency * self.t + phase_rad
        # Duty cycle adjustment
        threshold = 2 * np.pi * (1 - duty_cycle)
        wave = np.where((phase % (2 * np.pi)) < (2 * np.pi * duty_cycle),
                        amplitude, -amplitude)
        return wave + dc_offset

    def generate_sine_wave(self, frequency: float, amplitude: float,
                           phase_deg: float = 0, dc_offset: float = 0) -> np.ndarray:
        """
        Generate a sine wave signal.

        Args:
            frequency: Frequency in Hz
            amplitude: Peak amplitude in volts
            phase_deg: Phase offset in degrees
            dc_offset: DC offset in volts

        Returns:
            np.ndarray: Sine wave signal
        """
        phase_rad = np.deg2rad(phase_deg)
        return amplitude * np.sin(2 * np.pi * frequency * self.t + phase_rad) + dc_offset

    def add_noise(self, signal: np.ndarray, noise_amplitude: float) -> np.ndarray:
        """
        Add Gaussian noise to a signal.

        Args:
            signal: Input signal
            noise_amplitude: RMS amplitude of noise

        Returns:
            np.ndarray: Signal with added noise
        """
        noise = np.random.normal(0, noise_amplitude, len(signal))
        return signal + noise

    def run_lockin(self, signal_data: np.ndarray, reference_data: np.ndarray,
                   reference_freq: float) -> dict:
        """
        Run the exact lock-in algorithm from picoscope_driver.py.

        This is a direct copy of the algorithm in software_lockin() to ensure
        we're testing exactly what the real system uses.

        Args:
            signal_data: Signal channel data (volts)
            reference_data: Reference channel data (volts)
            reference_freq: Expected reference frequency (for FFT analysis)

        Returns:
            dict: Lock-in results {X, Y, R, theta, freq}
        """
        fs = self.sample_rate

        # SOFTWARE LOCK-IN ALGORITHM (exact copy from picoscope_driver.py)

        # Remove DC offsets
        signal_normalized = signal_data - np.mean(signal_data)
        ref_normalized = reference_data - np.mean(reference_data)

        # Normalize reference signal
        ref_rms = np.sqrt(np.mean(ref_normalized**2))
        if ref_rms > 0:
            ref_normalized = ref_normalized / ref_rms
        else:
            return None

        # Create quadrature reference using Hilbert transform
        analytic_signal = hilbert(ref_normalized)
        ref_cos = ref_normalized  # In-phase reference
        ref_sin = np.imag(analytic_signal)  # Quadrature reference (90° shifted)

        # Mix signal with reference
        mixed_cos = signal_normalized * ref_cos
        mixed_sin = signal_normalized * ref_sin

        # Low-pass filter by averaging
        X = 2 * np.mean(mixed_cos)  # In-phase component (factor of 2 for RMS)
        Y = 2 * np.mean(mixed_sin)  # Quadrature component

        # Calculate magnitude and phase
        R = np.sqrt(X**2 + Y**2)
        theta = np.arctan2(Y, X)
        theta_deg = np.rad2deg(theta)

        # Measure actual reference frequency using FFT
        freqs = np.fft.rfftfreq(len(reference_data), 1/fs)
        fft_ref = np.fft.rfft(reference_data)
        freq_range = (reference_freq * 0.5, reference_freq * 1.5)
        mask = (freqs >= freq_range[0]) & (freqs <= freq_range[1])

        if np.any(mask):
            peak_idx = np.argmax(np.abs(fft_ref[mask]))
            measured_freq = freqs[mask][peak_idx]
        else:
            measured_freq = freqs[np.argmax(np.abs(fft_ref[1:]))+1]

        return {
            'X': X,
            'Y': Y,
            'R': R,
            'theta': theta_deg,
            'freq': measured_freq,
            'signal_data': signal_data,
            'reference_data': reference_data
        }

    def test_square_wave_response(self, frequency: float = 81.0,
                                   amplitude: float = 1.0) -> dict:
        """
        Test lock-in response to identical square waves on both channels.

        This simulates the AWG validation test where the same signal is
        fed to both channels via a BNC tee.

        Args:
            frequency: Test frequency in Hz
            amplitude: Peak amplitude in volts

        Returns:
            dict: Test results including expected vs measured R
        """
        # Generate identical square waves for both channels
        signal = self.generate_square_wave(frequency, amplitude)
        reference = self.generate_square_wave(frequency, amplitude)

        # Run lock-in
        result = self.run_lockin(signal, reference, frequency)

        if result is None:
            return {'error': 'Lock-in failed'}

        # Calculate expected R value
        # For square wave: after DC removal, signal swings ±amplitude
        # After RMS normalization of reference and mixing, the expected
        # value depends on the algorithm specifics
        expected_R = amplitude  # First approximation

        # Calculate scaling factor
        scaling_factor = result['R'] / amplitude if amplitude > 0 else 0

        return {
            'input_amplitude': amplitude,
            'measured_R': result['R'],
            'measured_X': result['X'],
            'measured_Y': result['Y'],
            'measured_theta': result['theta'],
            'measured_freq': result['freq'],
            'scaling_factor': scaling_factor,
            'percent_error': (scaling_factor - 1.0) * 100
        }

    def test_sine_wave_response(self, frequency: float = 81.0,
                                 amplitude: float = 1.0) -> dict:
        """
        Test lock-in response to sine wave signal with square wave reference.

        This is closer to real EQE operation where the photocurrent is
        roughly sinusoidal but the chopper reference is square.

        Args:
            frequency: Test frequency in Hz
            amplitude: Peak amplitude in volts

        Returns:
            dict: Test results
        """
        # Sine signal, square reference
        signal = self.generate_sine_wave(frequency, amplitude)
        reference = self.generate_square_wave(frequency, 1.0)  # Normalized reference

        result = self.run_lockin(signal, reference, frequency)

        if result is None:
            return {'error': 'Lock-in failed'}

        scaling_factor = result['R'] / amplitude if amplitude > 0 else 0

        return {
            'input_amplitude': amplitude,
            'measured_R': result['R'],
            'measured_X': result['X'],
            'measured_Y': result['Y'],
            'measured_theta': result['theta'],
            'measured_freq': result['freq'],
            'scaling_factor': scaling_factor,
            'percent_error': (scaling_factor - 1.0) * 100
        }

    def run_linearity_test(self, frequency: float = 81.0,
                           amplitudes: list = None) -> dict:
        """
        Test lock-in linearity across a range of amplitudes.

        Args:
            frequency: Test frequency in Hz
            amplitudes: List of amplitudes to test (default: 0.01 to 2V)

        Returns:
            dict: Linearity test results
        """
        if amplitudes is None:
            amplitudes = [0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1.0, 2.0]

        results = []
        for amp in amplitudes:
            test = self.test_square_wave_response(frequency, amp)
            results.append({
                'amplitude': amp,
                'R': test['measured_R'],
                'scaling': test['scaling_factor']
            })

        # Calculate linearity (R² of linear fit)
        amps = np.array([r['amplitude'] for r in results])
        Rs = np.array([r['R'] for r in results])

        # Linear regression
        slope, intercept = np.polyfit(amps, Rs, 1)
        fit_line = slope * amps + intercept
        ss_res = np.sum((Rs - fit_line) ** 2)
        ss_tot = np.sum((Rs - np.mean(Rs)) ** 2)
        r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0

        return {
            'results': results,
            'slope': slope,
            'intercept': intercept,
            'r_squared': r_squared,
            'mean_scaling': np.mean([r['scaling'] for r in results]),
            'scaling_std': np.std([r['scaling'] for r in results])
        }

    def run_noise_test(self, frequency: float = 81.0, amplitude: float = 0.1,
                       noise_levels: list = None, num_trials: int = 10) -> dict:
        """
        Test lock-in performance with varying noise levels.

        Args:
            frequency: Test frequency in Hz
            amplitude: Signal amplitude in volts
            noise_levels: List of noise RMS values to test
            num_trials: Number of trials per noise level

        Returns:
            dict: Noise test results
        """
        if noise_levels is None:
            noise_levels = [0, 0.01, 0.02, 0.05, 0.1, 0.2]

        results = []
        for noise in noise_levels:
            trial_Rs = []
            for _ in range(num_trials):
                signal = self.generate_square_wave(frequency, amplitude)
                reference = self.generate_square_wave(frequency, amplitude)

                if noise > 0:
                    signal = self.add_noise(signal, noise)
                    reference = self.add_noise(reference, noise)

                result = self.run_lockin(signal, reference, frequency)
                if result:
                    trial_Rs.append(result['R'])

            if trial_Rs:
                results.append({
                    'noise_level': noise,
                    'snr_db': 20 * np.log10(amplitude / noise) if noise > 0 else float('inf'),
                    'mean_R': np.mean(trial_Rs),
                    'std_R': np.std(trial_Rs),
                    'cv_percent': 100 * np.std(trial_Rs) / np.mean(trial_Rs) if np.mean(trial_Rs) > 0 else 0
                })

        return {'results': results}


def run_validation_suite():
    """
    Run complete validation suite and print results.
    """
    print("=" * 60)
    print("Lock-in Amplifier Simulation Validation")
    print("=" * 60)

    sim = LockinSimulator()

    # Test 1: Square wave response
    print("\n1. Square Wave Response Test (81 Hz, 1V amplitude)")
    print("-" * 40)
    result = sim.test_square_wave_response(81.0, 1.0)
    print(f"   Input amplitude:  {result['input_amplitude']:.4f} V")
    print(f"   Measured R:       {result['measured_R']:.4f} V")
    print(f"   Scaling factor:   {result['scaling_factor']:.4f}")
    print(f"   Percent error:    {result['percent_error']:+.2f}%")
    print(f"   Phase (theta):    {result['measured_theta']:.1f}°")

    # Test 2: Linearity
    print("\n2. Linearity Test")
    print("-" * 40)
    linearity = sim.run_linearity_test()
    print(f"   Slope:            {linearity['slope']:.4f}")
    print(f"   Intercept:        {linearity['intercept']:.6f}")
    print(f"   R² (linearity):   {linearity['r_squared']:.6f}")
    print(f"   Mean scaling:     {linearity['mean_scaling']:.4f}")
    print(f"   Scaling std:      {linearity['scaling_std']:.4f}")

    # Test 3: Noise performance
    print("\n3. Noise Performance Test")
    print("-" * 40)
    noise_test = sim.run_noise_test()
    print(f"   {'SNR (dB)':<12} {'Mean R':<12} {'CV (%)':<12}")
    for r in noise_test['results']:
        snr = f"{r['snr_db']:.1f}" if r['snr_db'] != float('inf') else "inf"
        print(f"   {snr:<12} {r['mean_R']:.4f}       {r['cv_percent']:.2f}")

    print("\n" + "=" * 60)
    print("Validation complete")
    print("=" * 60)

    return sim


if __name__ == "__main__":
    run_validation_suite()
