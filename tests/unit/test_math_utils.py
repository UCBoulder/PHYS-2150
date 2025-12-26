"""
Unit tests for eqe/utils/math_utils.py

Tests MathUtils, SignalProcessing, and CalibrationUtils pure functions.
"""

import pytest
import numpy as np
from numpy.testing import assert_array_almost_equal, assert_almost_equal

from eqe.utils.math_utils import MathUtils, SignalProcessing, CalibrationUtils


class TestMathUtilsFitSineWave:
    """Tests for MathUtils.fit_sine_wave()"""

    def test_fit_perfect_sine(self, sample_sine_data):
        """Fit should recover exact parameters for perfect sine wave."""
        phases, signals, expected = sample_sine_data
        result = MathUtils.fit_sine_wave(phases, signals)

        assert result is not None
        amplitude, phase_shift, offset = result
        assert_almost_equal(amplitude, expected[0], decimal=2)
        assert_almost_equal(offset, expected[2], decimal=2)

    def test_fit_noisy_sine(self, sample_noisy_sine_data):
        """Fit should handle noisy data gracefully."""
        phases, signals = sample_noisy_sine_data
        result = MathUtils.fit_sine_wave(phases, signals)

        assert result is not None
        amplitude, phase_shift, offset = result
        # With noise, we expect approximate results
        assert 0.3 < amplitude < 0.7  # Should be near 0.5
        assert 0.8 < offset < 1.2  # Should be near 1.0

    def test_fit_flat_signal_returns_none(self):
        """Fit should handle flat (no signal) data."""
        phases = np.linspace(0, 360, 37)
        signals = np.ones_like(phases) * 5.0  # Flat signal
        result = MathUtils.fit_sine_wave(phases, signals)
        # May return None or very small amplitude - both acceptable
        if result is not None:
            amplitude, _, _ = result
            assert amplitude < 0.1  # Essentially flat

    def test_fit_empty_array_returns_none(self):
        """Fit should return None for empty arrays."""
        result = MathUtils.fit_sine_wave(np.array([]), np.array([]))
        assert result is None


class TestMathUtilsCalculateRSquared:
    """Tests for MathUtils.calculate_r_squared()"""

    def test_r_squared_perfect_fit(self, sample_sine_data):
        """Perfect fit should give R² = 1.0"""
        phases, signals, fit_params = sample_sine_data
        r_squared = MathUtils.calculate_r_squared(phases, signals, fit_params)

        assert r_squared is not None
        assert_almost_equal(r_squared, 1.0, decimal=5)

    def test_r_squared_poor_fit(self, sample_sine_data):
        """Wrong parameters should give low R²."""
        phases, signals, _ = sample_sine_data
        wrong_params = (0.1, 0, 0)  # Wrong amplitude, phase, offset
        r_squared = MathUtils.calculate_r_squared(phases, signals, wrong_params)

        assert r_squared is not None
        assert r_squared < 0.5  # Poor fit

    def test_r_squared_constant_signal(self):
        """R² should be None for constant signal (ss_tot = 0)."""
        phases = np.linspace(0, 360, 10)
        signals = np.ones(10) * 5.0
        r_squared = MathUtils.calculate_r_squared(phases, signals, (0, 0, 5.0))
        assert r_squared is None


class TestMathUtilsFindOptimalPhase:
    """Tests for MathUtils.find_optimal_phase()"""

    def test_find_optimal_phase_positive(self):
        """Find phase for maximum positive signal."""
        # Sine peaks at 90 degrees when phase_shift = 0
        fit_params = (1.0, 0.0, 0.0)  # amplitude, phase_shift, offset
        optimal = MathUtils.find_optimal_phase(fit_params, prefer_positive=True)
        assert_almost_equal(optimal, 90.0, decimal=1)

    def test_find_optimal_phase_negative(self):
        """Find phase for minimum (negative) signal."""
        fit_params = (1.0, 0.0, 0.0)
        optimal = MathUtils.find_optimal_phase(fit_params, prefer_positive=False)
        assert_almost_equal(optimal, 270.0, decimal=1)

    def test_find_optimal_phase_with_shift(self):
        """Handle non-zero phase shift."""
        # With 45 degree shift, peak moves
        fit_params = (1.0, np.radians(45), 0.0)
        optimal = MathUtils.find_optimal_phase(fit_params, prefer_positive=True)
        # Should be 90 - 45 = 45 degrees
        assert_almost_equal(optimal, 45.0, decimal=1)


class TestMathUtilsCalculateStatistics:
    """Tests for MathUtils.calculate_statistics()"""

    def test_statistics_basic(self, sample_measurement_data):
        """Calculate basic statistics."""
        stats = MathUtils.calculate_statistics(sample_measurement_data)

        assert 'mean' in stats
        assert 'std' in stats
        assert 'min' in stats
        assert 'max' in stats
        assert 'median' in stats
        assert 'count' in stats

        assert stats['count'] == 50
        assert 90 < stats['mean'] < 110  # Should be near 100
        assert 5 < stats['std'] < 15  # Should be near 10

    def test_statistics_single_value(self):
        """Handle single value array."""
        data = np.array([42.0])
        stats = MathUtils.calculate_statistics(data)

        assert stats['mean'] == 42.0
        assert stats['std'] == 0.0
        assert stats['count'] == 1


class TestMathUtilsMovingAverage:
    """Tests for MathUtils.moving_average()"""

    def test_moving_average_smooths_noise(self):
        """Moving average should smooth noisy data."""
        np.random.seed(42)
        data = np.sin(np.linspace(0, 4*np.pi, 100)) + np.random.normal(0, 0.3, 100)
        smoothed = MathUtils.moving_average(data, window_size=5)

        # Smoothed data should have lower variance
        assert np.std(smoothed) < np.std(data)

    def test_moving_average_preserves_length(self):
        """Output length should match input."""
        data = np.array([1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
        smoothed = MathUtils.moving_average(data, window_size=3)
        assert len(smoothed) == len(data)

    def test_moving_average_large_window(self):
        """Window larger than data should return mean."""
        data = np.array([1, 2, 3, 4, 5])
        smoothed = MathUtils.moving_average(data, window_size=10)
        assert_array_almost_equal(smoothed, np.full_like(data, 3.0, dtype=float))


class TestMathUtilsNormalizeData:
    """Tests for MathUtils.normalize_data()"""

    def test_normalize_minmax(self):
        """Min-max normalization should scale to [0, 1]."""
        data = np.array([10, 20, 30, 40, 50])
        normalized = MathUtils.normalize_data(data, method='minmax')

        assert_almost_equal(normalized.min(), 0.0)
        assert_almost_equal(normalized.max(), 1.0)
        assert_array_almost_equal(normalized, [0, 0.25, 0.5, 0.75, 1.0])

    def test_normalize_zscore(self):
        """Z-score normalization should give mean=0, std=1."""
        data = np.array([10, 20, 30, 40, 50], dtype=float)
        normalized = MathUtils.normalize_data(data, method='zscore')

        assert_almost_equal(np.mean(normalized), 0.0, decimal=10)
        assert_almost_equal(np.std(normalized), 1.0, decimal=10)

    def test_normalize_constant_returns_zeros(self):
        """Constant data should return zeros."""
        data = np.array([5, 5, 5, 5, 5])
        normalized = MathUtils.normalize_data(data, method='minmax')
        assert_array_almost_equal(normalized, np.zeros(5))

    def test_normalize_invalid_method_raises(self):
        """Invalid method should raise ValueError."""
        data = np.array([1, 2, 3])
        with pytest.raises(ValueError, match="Unknown normalization method"):
            MathUtils.normalize_data(data, method='invalid')


class TestSignalProcessingRemoveOutliers:
    """Tests for SignalProcessing.remove_outliers()"""

    def test_remove_outliers_iqr(self):
        """IQR method should remove extreme values."""
        data = np.array([1, 2, 3, 4, 5, 100])  # 100 is outlier
        cleaned, mask = SignalProcessing.remove_outliers(data, method='iqr')

        assert 100 not in cleaned
        assert mask[-1] == True  # Last element is outlier

    def test_remove_outliers_zscore(self):
        """Z-score method should remove extreme values."""
        np.random.seed(42)
        data = np.concatenate([np.random.normal(0, 1, 100), [10, -10]])  # Add outliers
        cleaned, mask = SignalProcessing.remove_outliers(data, method='zscore', factor=3)

        assert len(cleaned) < len(data)
        assert mask[-1] == True or mask[-2] == True  # At least one outlier detected

    def test_remove_outliers_no_outliers(self):
        """Clean data should not be modified."""
        data = np.array([1.0, 1.1, 0.9, 1.05, 0.95])
        cleaned, mask = SignalProcessing.remove_outliers(data, method='iqr')

        assert len(cleaned) == len(data)
        assert not any(mask)


class TestCalibrationUtils:
    """Tests for CalibrationUtils conversion functions."""

    def test_wavelength_to_energy(self, sample_wavelengths):
        """Convert wavelengths to energy (E = 1239.84/λ)."""
        energies = CalibrationUtils.wavelength_to_energy(sample_wavelengths)

        # 500nm should be ~2.48 eV
        idx_500 = np.where(sample_wavelengths == 500)[0][0]
        assert_almost_equal(energies[idx_500], 1239.84/500, decimal=2)

        # Energy should decrease as wavelength increases
        assert energies[0] > energies[-1]

    def test_energy_to_wavelength(self):
        """Convert energy to wavelength (λ = 1239.84/E)."""
        energies = np.array([1.0, 1.5, 2.0, 2.5, 3.0])
        wavelengths = CalibrationUtils.energy_to_wavelength(energies)

        # 2.0 eV should be ~620nm
        assert_almost_equal(wavelengths[2], 1239.84/2.0, decimal=2)

    def test_wavelength_energy_roundtrip(self, sample_wavelengths):
        """Converting wavelength→energy→wavelength should be identity."""
        energies = CalibrationUtils.wavelength_to_energy(sample_wavelengths)
        recovered = CalibrationUtils.energy_to_wavelength(energies)
        assert_array_almost_equal(recovered, sample_wavelengths)

    def test_apply_correction_factor(self):
        """Apply correction factor to data."""
        data = np.array([1.0, 2.0, 3.0])
        corrected = CalibrationUtils.apply_correction_factor(data, 0.5)
        assert_array_almost_equal(corrected, [0.5, 1.0, 1.5])
