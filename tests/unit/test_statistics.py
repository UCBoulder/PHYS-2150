"""
Unit tests for StabilityTestModel.calculate_statistics()

Tests statistics calculation for measurement stability analysis.
"""

import pytest
import numpy as np
from numpy.testing import assert_almost_equal

from eqe.models.stability_test import StabilityTestModel


class TestCalculateStatistics:
    """Tests for StabilityTestModel.calculate_statistics()"""

    def test_basic_statistics(self):
        """Calculate statistics for simple dataset."""
        values = [10.0, 20.0, 30.0, 40.0, 50.0]
        stats = StabilityTestModel.calculate_statistics(values)

        assert stats['count'] == 5
        assert_almost_equal(stats['mean'], 30.0)
        assert_almost_equal(stats['min'], 10.0)
        assert_almost_equal(stats['max'], 50.0)
        assert_almost_equal(stats['range'], 40.0)

    def test_standard_deviation(self):
        """Verify standard deviation calculation."""
        # Use values with known std dev
        values = [2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0]
        stats = StabilityTestModel.calculate_statistics(values)

        # numpy std (population std dev)
        expected_std = np.std(values)
        assert_almost_equal(stats['std'], expected_std, decimal=5)

    def test_cv_percent(self):
        """Verify coefficient of variation calculation."""
        # CV% = (std / mean) * 100
        values = [100.0, 100.0, 100.0, 100.0]  # No variation
        stats = StabilityTestModel.calculate_statistics(values)
        assert_almost_equal(stats['cv_percent'], 0.0)

        # With variation
        values = [90.0, 100.0, 110.0]  # mean=100, some variation
        stats = StabilityTestModel.calculate_statistics(values)
        expected_cv = (np.std(values) / np.mean(values)) * 100
        assert_almost_equal(stats['cv_percent'], expected_cv, decimal=5)

    def test_empty_list_returns_zeros(self):
        """Empty list should return all zeros."""
        stats = StabilityTestModel.calculate_statistics([])

        assert stats['count'] == 0
        assert stats['mean'] == 0.0
        assert stats['std'] == 0.0
        assert stats['cv_percent'] == 0.0
        assert stats['min'] == 0.0
        assert stats['max'] == 0.0
        assert stats['range'] == 0.0

    def test_single_value(self):
        """Single value should have zero std and cv."""
        stats = StabilityTestModel.calculate_statistics([42.0])

        assert stats['count'] == 1
        assert stats['mean'] == 42.0
        assert stats['std'] == 0.0
        assert stats['cv_percent'] == 0.0
        assert stats['min'] == 42.0
        assert stats['max'] == 42.0
        assert stats['range'] == 0.0

    def test_negative_values(self):
        """Handle negative values correctly."""
        values = [-10.0, -5.0, 0.0, 5.0, 10.0]
        stats = StabilityTestModel.calculate_statistics(values)

        assert_almost_equal(stats['mean'], 0.0)
        assert stats['min'] == -10.0
        assert stats['max'] == 10.0
        assert stats['range'] == 20.0

    def test_cv_with_zero_mean(self):
        """CV should be 0 when mean is 0 (avoid division by zero)."""
        values = [-1.0, 0.0, 1.0]  # mean = 0
        stats = StabilityTestModel.calculate_statistics(values)

        assert_almost_equal(stats['mean'], 0.0)
        assert stats['cv_percent'] == 0.0  # Not NaN or Inf

    def test_realistic_measurement_data(self):
        """Test with realistic photocurrent measurement data."""
        # Simulating nanoamp-level currents with ~1% noise
        np.random.seed(42)
        mean_current = 5e-9  # 5 nA
        values = list(np.random.normal(mean_current, mean_current * 0.01, 100))

        stats = StabilityTestModel.calculate_statistics(values)

        assert stats['count'] == 100
        # Mean should be close to 5e-9
        assert abs(stats['mean'] - mean_current) < mean_current * 0.1
        # CV should be around 1%
        assert 0.5 < stats['cv_percent'] < 2.0

    def test_large_dataset(self):
        """Handle large datasets efficiently."""
        np.random.seed(42)
        values = list(np.random.normal(100, 10, 10000))

        stats = StabilityTestModel.calculate_statistics(values)

        assert stats['count'] == 10000
        # Mean should be close to 100
        assert 98 < stats['mean'] < 102
        # Std should be close to 10
        assert 9 < stats['std'] < 11

    def test_returns_python_floats(self):
        """Values should be Python floats, not numpy types."""
        values = [1.0, 2.0, 3.0]
        stats = StabilityTestModel.calculate_statistics(values)

        assert isinstance(stats['mean'], float)
        assert isinstance(stats['std'], float)
        assert isinstance(stats['cv_percent'], float)
        assert isinstance(stats['min'], float)
        assert isinstance(stats['max'], float)
        assert isinstance(stats['range'], float)
        assert isinstance(stats['count'], int)

    def test_all_same_values(self):
        """All identical values should have zero std."""
        values = [42.0, 42.0, 42.0, 42.0, 42.0]
        stats = StabilityTestModel.calculate_statistics(values)

        assert stats['mean'] == 42.0
        assert stats['std'] == 0.0
        assert stats['cv_percent'] == 0.0
        assert stats['range'] == 0.0
