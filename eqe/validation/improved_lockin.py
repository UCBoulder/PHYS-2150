"""
Improved Lock-in Algorithm Experiments

Experimental implementations of improved lock-in algorithms as described
in the validation plan. These can be tested against the current algorithm
using the simulator and hardware tester.

Proposed improvements:
1. Synthesized sine reference (instead of Hilbert transform)
2. Proper low-pass filtering (instead of simple averaging)
3. Configurable time constant

Author: Physics 2150
Date: December 2025
"""

import numpy as np
from scipy.signal import hilbert, butter, filtfilt


def current_lockin(signal_data: np.ndarray, reference_data: np.ndarray,
                   fs: float, reference_freq: float) -> dict:
    """
    Current lock-in algorithm (exact copy from picoscope_driver.py).

    Uses Hilbert transform for quadrature generation.

    Args:
        signal_data: Signal channel data (volts)
        reference_data: Reference channel data (volts)
        fs: Sample rate in Hz
        reference_freq: Expected reference frequency in Hz

    Returns:
        dict: Lock-in results {X, Y, R, theta, freq}
    """
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
    ref_sin = np.imag(analytic_signal)  # Quadrature reference

    # Mix signal with reference
    mixed_cos = signal_normalized * ref_cos
    mixed_sin = signal_normalized * ref_sin

    # Low-pass filter by averaging
    X = 2 * np.mean(mixed_cos)
    Y = 2 * np.mean(mixed_sin)

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
        'freq': measured_freq
    }


def synthesized_reference_lockin(signal_data: np.ndarray, reference_data: np.ndarray,
                                  fs: float, reference_freq: float,
                                  filter_cutoff_ratio: float = 0.1) -> dict:
    """
    Improved lock-in using synthesized sine reference.

    Instead of using the actual (noisy, square) reference signal,
    we measure its frequency and synthesize clean sine/cosine references.

    Advantages:
    - No harmonics in reference (pure fundamental)
    - Predictable scaling (R = signal amplitude at fundamental)
    - No Hilbert transform edge effects

    Args:
        signal_data: Signal channel data (volts)
        reference_data: Reference channel data (volts)
        fs: Sample rate in Hz
        reference_freq: Expected reference frequency in Hz
        filter_cutoff_ratio: Low-pass cutoff as fraction of reference freq

    Returns:
        dict: Lock-in results {X, Y, R, theta, freq}
    """
    # Measure reference frequency from actual signal
    freq = measure_frequency(reference_data, fs, reference_freq)

    # Generate synthesized sine/cosine reference (clean, no harmonics)
    t = np.arange(len(signal_data)) / fs
    ref_cos = np.cos(2 * np.pi * freq * t)
    ref_sin = np.sin(2 * np.pi * freq * t)

    # Remove DC from signal
    signal_ac = signal_data - np.mean(signal_data)

    # Mix with synthesized references
    mixed_cos = signal_ac * ref_cos
    mixed_sin = signal_ac * ref_sin

    # Low-pass filter (proper Butterworth filter)
    cutoff = freq * filter_cutoff_ratio
    # Ensure cutoff is valid (< Nyquist)
    nyquist = fs / 2
    if cutoff >= nyquist:
        cutoff = nyquist * 0.9

    b, a = butter(2, cutoff / nyquist, btype='low')

    # Apply filter and average
    X = 2 * np.mean(filtfilt(b, a, mixed_cos))
    Y = 2 * np.mean(filtfilt(b, a, mixed_sin))

    # Magnitude and phase
    R = np.sqrt(X**2 + Y**2)
    theta = np.arctan2(Y, X)
    theta_deg = np.rad2deg(theta)

    return {
        'X': X,
        'Y': Y,
        'R': R,
        'theta': theta_deg,
        'freq': freq
    }


def filtered_lockin(signal_data: np.ndarray, reference_data: np.ndarray,
                    fs: float, reference_freq: float,
                    time_constant_ms: float = 100) -> dict:
    """
    Lock-in with proper low-pass filtering instead of simple averaging.

    Uses the current Hilbert transform approach but replaces simple
    averaging with a proper Butterworth low-pass filter with configurable
    time constant (like analog lock-ins: 100ms, 300ms, 1s).

    Args:
        signal_data: Signal channel data (volts)
        reference_data: Reference channel data (volts)
        fs: Sample rate in Hz
        reference_freq: Expected reference frequency in Hz
        time_constant_ms: Filter time constant in milliseconds

    Returns:
        dict: Lock-in results {X, Y, R, theta, freq}
    """
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
    ref_cos = ref_normalized
    ref_sin = np.imag(analytic_signal)

    # Mix signal with reference
    mixed_cos = signal_normalized * ref_cos
    mixed_sin = signal_normalized * ref_sin

    # Calculate filter cutoff from time constant
    # For a first-order filter, cutoff = 1/(2*pi*tau)
    # We use 2nd order Butterworth for better rolloff
    tau = time_constant_ms / 1000.0  # Convert to seconds
    cutoff = 1.0 / (2 * np.pi * tau)

    # Ensure cutoff is valid
    nyquist = fs / 2
    if cutoff >= nyquist:
        cutoff = nyquist * 0.9

    b, a = butter(2, cutoff / nyquist, btype='low')

    # Apply filter then average
    X = 2 * np.mean(filtfilt(b, a, mixed_cos))
    Y = 2 * np.mean(filtfilt(b, a, mixed_sin))

    # Calculate magnitude and phase
    R = np.sqrt(X**2 + Y**2)
    theta = np.arctan2(Y, X)
    theta_deg = np.rad2deg(theta)

    # Measure actual reference frequency
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
        'time_constant_ms': time_constant_ms
    }


def measure_frequency(reference_data: np.ndarray, fs: float,
                      expected_freq: float) -> float:
    """
    Measure the fundamental frequency of the reference signal.

    Uses FFT with peak finding near expected frequency.

    Args:
        reference_data: Reference signal data
        fs: Sample rate in Hz
        expected_freq: Expected frequency for search window

    Returns:
        float: Measured frequency in Hz
    """
    freqs = np.fft.rfftfreq(len(reference_data), 1/fs)
    fft_ref = np.fft.rfft(reference_data)

    # Search within ±50% of expected frequency
    freq_range = (expected_freq * 0.5, expected_freq * 1.5)
    mask = (freqs >= freq_range[0]) & (freqs <= freq_range[1])

    if np.any(mask):
        peak_idx = np.argmax(np.abs(fft_ref[mask]))
        return freqs[mask][peak_idx]
    else:
        # Fallback: find global peak (excluding DC)
        return freqs[np.argmax(np.abs(fft_ref[1:])) + 1]


def compare_algorithms(signal_data: np.ndarray, reference_data: np.ndarray,
                       fs: float, reference_freq: float) -> dict:
    """
    Run all lock-in algorithms on the same data and compare results.

    Args:
        signal_data: Signal channel data (volts)
        reference_data: Reference channel data (volts)
        fs: Sample rate in Hz
        reference_freq: Expected reference frequency in Hz

    Returns:
        dict: Comparison results for each algorithm
    """
    results = {}

    # Current algorithm (Hilbert transform)
    results['current'] = current_lockin(signal_data, reference_data, fs, reference_freq)

    # Synthesized reference
    results['synthesized'] = synthesized_reference_lockin(
        signal_data, reference_data, fs, reference_freq)

    # Filtered (various time constants)
    for tc in [50, 100, 300]:
        key = f'filtered_{tc}ms'
        results[key] = filtered_lockin(
            signal_data, reference_data, fs, reference_freq, tc)

    return results


def print_comparison(results: dict, input_amplitude: float = None):
    """
    Print comparison table of algorithm results.

    Args:
        results: Dictionary of results from compare_algorithms()
        input_amplitude: Known input amplitude for error calculation
    """
    print("\nAlgorithm Comparison")
    print("=" * 70)
    print(f"{'Algorithm':<20} {'R (V)':<12} {'X (V)':<12} {'Y (V)':<12} {'Phase':<10}")
    print("-" * 70)

    for name, result in results.items():
        if result:
            print(f"{name:<20} {result['R']:<12.6f} {result['X']:<12.6f} "
                  f"{result['Y']:<12.6f} {result['theta']:<10.1f}")

    if input_amplitude is not None:
        print("\nScaling factors (R / input_amplitude):")
        print("-" * 40)
        for name, result in results.items():
            if result:
                scaling = result['R'] / input_amplitude
                error = (scaling - 1.0) * 100
                print(f"  {name:<20}: {scaling:.4f} ({error:+.2f}%)")


if __name__ == "__main__":
    # Quick test with synthetic data
    from eqe.validation.lockin_simulator import LockinSimulator

    print("Testing improved lock-in algorithms with synthetic data")
    print("=" * 60)

    sim = LockinSimulator()

    # Generate test signals
    freq = 81.0
    amplitude = 1.0
    signal = sim.generate_square_wave(freq, amplitude)
    reference = sim.generate_square_wave(freq, amplitude)

    # Compare algorithms
    results = compare_algorithms(signal, reference, sim.sample_rate, freq)
    print_comparison(results, amplitude)
