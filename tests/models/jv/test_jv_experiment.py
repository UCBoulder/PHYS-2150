"""
Unit tests for JVExperimentModel parameter validation.

Tests validate_parameters() for cell number, pixel, and voltage validation.
"""

import pytest
import re
from unittest.mock import Mock

from jv.models.jv_experiment import JVExperimentError
from jv.config.settings import VALIDATION_PATTERNS


class MockJVExperimentModel:
    """
    Mock JVExperimentModel that implements validate_parameters().

    This avoids Qt dependencies while testing the pure validation logic.
    """

    def __init__(self):
        self.params = {}
        self.controller = None
        self.measurement_model = None
        self._device_initialized = False

    def validate_parameters(self) -> bool:
        """
        Validate current measurement parameters.
        (Copied from JVExperimentModel to test without Qt)
        """
        # Validate cell number
        cell_number = self.params.get("cell_number", "")
        cell_pattern = VALIDATION_PATTERNS["cell_number"]
        if not cell_number or not re.match(cell_pattern, str(cell_number)):
            raise JVExperimentError(
                "Cell number must be a letter + 2 digits (e.g., A03, R26)."
            )

        # Validate pixel number
        pixel_number = self.params.get("pixel_number", 0)
        pixel_min, pixel_max = VALIDATION_PATTERNS["pixel_range"]
        if not (pixel_min <= pixel_number <= pixel_max):
            raise JVExperimentError(
                f"Pixel number must be between {pixel_min} and {pixel_max}."
            )

        # Validate voltage parameters
        start_v = self.params.get("start_voltage", 0)
        stop_v = self.params.get("stop_voltage", 0)
        step_v = self.params.get("step_voltage", 0)

        try:
            start_v = float(start_v)
            stop_v = float(stop_v)
            step_v = float(step_v)
        except (TypeError, ValueError):
            raise JVExperimentError(
                "Please enter valid numerical values for voltages."
            )

        if step_v <= 0:
            raise JVExperimentError("Step voltage must be positive.")

        return True


@pytest.fixture
def jv_experiment():
    """Create MockJVExperimentModel for testing."""
    return MockJVExperimentModel()


class TestValidateCellNumber:
    """Tests for cell number validation in validate_parameters()."""

    def test_valid_cell_number(self, jv_experiment):
        """Valid cell number (letter + 2 digits) should pass."""
        jv_experiment.params = {
            'cell_number': 'A03',
            'pixel_number': 1,
            'start_voltage': -0.2,
            'stop_voltage': 1.2,
            'step_voltage': 0.02,
        }
        assert jv_experiment.validate_parameters() is True

    def test_cell_number_with_different_letters(self, jv_experiment):
        """Cell numbers with different letters should pass."""
        jv_experiment.params = {
            'cell_number': 'R26',
            'pixel_number': 1,
            'start_voltage': -0.2,
            'stop_voltage': 1.2,
            'step_voltage': 0.02,
        }
        assert jv_experiment.validate_parameters() is True

    def test_empty_cell_number_raises(self, jv_experiment):
        """Empty cell number should raise error."""
        jv_experiment.params = {
            'cell_number': '',
            'pixel_number': 1,
            'start_voltage': -0.2,
            'stop_voltage': 1.2,
            'step_voltage': 0.02,
        }
        with pytest.raises(JVExperimentError, match="letter"):
            jv_experiment.validate_parameters()

    def test_single_digit_cell_number_raises(self, jv_experiment):
        """Cell number with single digit should raise error."""
        jv_experiment.params = {
            'cell_number': 'A1',
            'pixel_number': 1,
            'start_voltage': -0.2,
            'stop_voltage': 1.2,
            'step_voltage': 0.02,
        }
        with pytest.raises(JVExperimentError, match="letter"):
            jv_experiment.validate_parameters()

    def test_old_format_cell_number_raises(self, jv_experiment):
        """Old 3-digit format should raise error."""
        jv_experiment.params = {
            'cell_number': '195',
            'pixel_number': 1,
            'start_voltage': -0.2,
            'stop_voltage': 1.2,
            'step_voltage': 0.02,
        }
        with pytest.raises(JVExperimentError, match="letter"):
            jv_experiment.validate_parameters()

    def test_lowercase_cell_number_raises(self, jv_experiment):
        """Lowercase letter should raise error."""
        jv_experiment.params = {
            'cell_number': 'a03',
            'pixel_number': 1,
            'start_voltage': -0.2,
            'stop_voltage': 1.2,
            'step_voltage': 0.02,
        }
        with pytest.raises(JVExperimentError, match="letter"):
            jv_experiment.validate_parameters()


class TestValidatePixelNumber:
    """Tests for pixel number validation in validate_parameters()."""

    def test_valid_pixel_numbers(self, jv_experiment):
        """Pixel numbers 1-8 should pass."""
        for pixel in range(1, 9):
            jv_experiment.params = {
                'cell_number': 'A03',
                'pixel_number': pixel,
                'start_voltage': -0.2,
                'stop_voltage': 1.2,
                'step_voltage': 0.02,
            }
            assert jv_experiment.validate_parameters() is True

    def test_pixel_zero_raises(self, jv_experiment):
        """Pixel 0 should raise error."""
        jv_experiment.params = {
            'cell_number': 'A03',
            'pixel_number': 0,
            'start_voltage': -0.2,
            'stop_voltage': 1.2,
            'step_voltage': 0.02,
        }
        with pytest.raises(JVExperimentError, match="between"):
            jv_experiment.validate_parameters()

    def test_pixel_nine_raises(self, jv_experiment):
        """Pixel 9 should raise error."""
        jv_experiment.params = {
            'cell_number': 'A03',
            'pixel_number': 9,
            'start_voltage': -0.2,
            'stop_voltage': 1.2,
            'step_voltage': 0.02,
        }
        with pytest.raises(JVExperimentError, match="between"):
            jv_experiment.validate_parameters()

    def test_negative_pixel_raises(self, jv_experiment):
        """Negative pixel should raise error."""
        jv_experiment.params = {
            'cell_number': 'A03',
            'pixel_number': -1,
            'start_voltage': -0.2,
            'stop_voltage': 1.2,
            'step_voltage': 0.02,
        }
        with pytest.raises(JVExperimentError, match="between"):
            jv_experiment.validate_parameters()


class TestValidateVoltageParameters:
    """Tests for voltage parameter validation in validate_parameters()."""

    def test_valid_voltage_params(self, jv_experiment):
        """Valid voltage parameters should pass."""
        jv_experiment.params = {
            'cell_number': 'A03',
            'pixel_number': 1,
            'start_voltage': -0.2,
            'stop_voltage': 1.5,
            'step_voltage': 0.02,
        }
        assert jv_experiment.validate_parameters() is True

    def test_zero_step_voltage_raises(self, jv_experiment):
        """Zero step voltage should raise error."""
        jv_experiment.params = {
            'cell_number': 'A03',
            'pixel_number': 1,
            'start_voltage': -0.2,
            'stop_voltage': 1.2,
            'step_voltage': 0,
        }
        with pytest.raises(JVExperimentError, match="positive"):
            jv_experiment.validate_parameters()

    def test_negative_step_voltage_raises(self, jv_experiment):
        """Negative step voltage should raise error."""
        jv_experiment.params = {
            'cell_number': 'A03',
            'pixel_number': 1,
            'start_voltage': -0.2,
            'stop_voltage': 1.2,
            'step_voltage': -0.02,
        }
        with pytest.raises(JVExperimentError, match="positive"):
            jv_experiment.validate_parameters()

    def test_non_numeric_voltage_raises(self, jv_experiment):
        """Non-numeric voltage should raise error."""
        jv_experiment.params = {
            'cell_number': 'A03',
            'pixel_number': 1,
            'start_voltage': 'abc',
            'stop_voltage': 1.2,
            'step_voltage': 0.02,
        }
        with pytest.raises(JVExperimentError, match="valid numerical"):
            jv_experiment.validate_parameters()

    def test_none_voltage_raises(self, jv_experiment):
        """None voltage should raise error."""
        jv_experiment.params = {
            'cell_number': 'A03',
            'pixel_number': 1,
            'start_voltage': None,
            'stop_voltage': 1.2,
            'step_voltage': 0.02,
        }
        with pytest.raises(JVExperimentError, match="valid numerical"):
            jv_experiment.validate_parameters()

    def test_typical_perovskite_sweep(self, jv_experiment):
        """Typical perovskite parameters should pass."""
        jv_experiment.params = {
            'cell_number': 'A03',
            'pixel_number': 1,
            'start_voltage': -0.1,
            'stop_voltage': 1.3,
            'step_voltage': 0.02,
        }
        assert jv_experiment.validate_parameters() is True

    def test_typical_silicon_sweep(self, jv_experiment):
        """Typical silicon cell parameters should pass."""
        jv_experiment.params = {
            'cell_number': 'A03',
            'pixel_number': 1,
            'start_voltage': -0.2,
            'stop_voltage': 0.7,
            'step_voltage': 0.01,
        }
        assert jv_experiment.validate_parameters() is True
