"""
Unit tests for JVMeasurementModel.generate_voltage_array()

Tests voltage sweep array generation with inclusive endpoints and proper rounding.
"""

import pytest
import numpy as np
from unittest.mock import Mock
from numpy.testing import assert_array_almost_equal

from jv.models.jv_measurement import JVMeasurementModel


@pytest.fixture
def jv_model():
    """Create JVMeasurementModel with mock controller."""
    mock_controller = Mock()
    return JVMeasurementModel(controller=mock_controller)


class TestGenerateVoltageArray:
    """Tests for JVMeasurementModel.generate_voltage_array()"""

    def test_basic_sweep(self, jv_model):
        """Basic sweep from 0 to 1V with 0.1V steps."""
        voltages = jv_model.generate_voltage_array(0.0, 1.0, 0.1)

        expected = np.array([0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0])
        assert_array_almost_equal(voltages, expected, decimal=2)

    def test_stop_is_inclusive(self, jv_model):
        """Stop voltage should always be included."""
        voltages = jv_model.generate_voltage_array(-0.2, 1.5, 0.02)

        assert voltages[0] == -0.2
        assert voltages[-1] == 1.5
        assert 1.5 in voltages

    def test_negative_to_positive_sweep(self, jv_model):
        """Sweep from negative to positive voltage."""
        voltages = jv_model.generate_voltage_array(-0.5, 0.5, 0.1)

        assert voltages[0] == -0.5
        assert voltages[-1] == 0.5
        assert 0.0 in voltages

    def test_small_step_size(self, jv_model):
        """Small step size (0.01V) should work correctly."""
        voltages = jv_model.generate_voltage_array(0.0, 0.1, 0.01)

        expected = np.array([0.0, 0.01, 0.02, 0.03, 0.04, 0.05, 0.06, 0.07, 0.08, 0.09, 0.10])
        assert_array_almost_equal(voltages, expected, decimal=2)

    def test_typical_solar_cell_sweep(self, jv_model):
        """Typical solar cell sweep: -0.2V to 1.2V, 0.02V steps."""
        voltages = jv_model.generate_voltage_array(-0.2, 1.2, 0.02)

        assert voltages[0] == -0.2
        assert voltages[-1] == 1.2
        # Should have (1.2 - (-0.2)) / 0.02 + 1 = 71 points
        assert len(voltages) == 71

    def test_non_divisible_range_includes_stop(self, jv_model):
        """When range isn't perfectly divisible, stop should still be included."""
        # 0 to 1.05 with 0.1 step - not perfectly divisible
        voltages = jv_model.generate_voltage_array(0.0, 1.05, 0.1)

        # Stop should be included (possibly with adjustment)
        assert voltages[-1] >= 1.05 or np.isclose(voltages[-1], 1.05, atol=0.01)

    def test_rounding_to_two_decimals(self, jv_model):
        """Voltages should be rounded to 2 decimal places."""
        voltages = jv_model.generate_voltage_array(0.0, 1.0, 0.02)

        # Check all values are rounded to 2 decimals
        for v in voltages:
            rounded = round(v, 2)
            assert v == rounded, f"Voltage {v} not rounded to 2 decimals"

    def test_single_step(self, jv_model):
        """Single step sweep (start to stop in one step)."""
        voltages = jv_model.generate_voltage_array(0.0, 0.1, 0.1)

        assert len(voltages) == 2
        assert voltages[0] == 0.0
        assert voltages[-1] == 0.1

    def test_zero_range(self, jv_model):
        """Start equals stop should give single point."""
        voltages = jv_model.generate_voltage_array(0.5, 0.5, 0.1)

        assert len(voltages) == 1
        assert voltages[0] == 0.5

    def test_typical_perovskite_sweep(self, jv_model):
        """Typical perovskite sweep: -0.1V to 1.3V."""
        voltages = jv_model.generate_voltage_array(-0.1, 1.3, 0.02)

        assert voltages[0] == -0.1
        assert voltages[-1] == 1.3

    def test_voltages_are_monotonic(self, jv_model):
        """Voltage array should be strictly increasing."""
        voltages = jv_model.generate_voltage_array(-0.2, 1.5, 0.02)

        # Check monotonically increasing
        diffs = np.diff(voltages)
        assert all(diffs > 0), "Voltages should be strictly increasing"

    def test_step_size_consistency(self, jv_model):
        """Step sizes should be consistent (within floating point tolerance)."""
        voltages = jv_model.generate_voltage_array(0.0, 1.0, 0.02)

        diffs = np.diff(voltages)
        # All steps should be approximately 0.02V
        assert_array_almost_equal(diffs, np.full_like(diffs, 0.02), decimal=2)
