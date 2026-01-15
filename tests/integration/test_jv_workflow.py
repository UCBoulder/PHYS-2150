"""
Integration tests for J-V measurement workflow.

Tests the complete J-V measurement workflow from parameter setup through
data collection using mock controllers.
"""

import pytest
import numpy as np
import time
from unittest.mock import Mock, patch, MagicMock

from jv.models.jv_measurement import JVMeasurementModel, JVMeasurementResult, SweepData
from jv.models.jv_experiment import JVExperimentError
from jv.config.settings import JV_MEASUREMENT_CONFIG, DEFAULT_MEASUREMENT_PARAMS
from tests.mocks.mock_controllers import MockKeithley2450Controller


class TestJVMeasurementWorkflow:
    """Integration tests for J-V measurement workflow with mock controller."""

    @pytest.fixture
    def measurement_model(self):
        """Create JVMeasurementModel with mock controller."""
        controller = MockKeithley2450Controller()
        controller.connect()
        config = JV_MEASUREMENT_CONFIG.copy()
        # Speed up tests
        config["dwell_time_ms"] = 10
        config["initial_stabilization_s"] = 0.01
        config["inter_sweep_delay_s"] = 0.01
        return JVMeasurementModel(controller, config)

    def test_voltage_array_generation_inclusive(self, measurement_model):
        """Voltage array should include both start and stop values."""
        voltages = measurement_model.generate_voltage_array(-0.2, 1.2, 0.1)

        assert voltages[0] == pytest.approx(-0.2)
        assert voltages[-1] == pytest.approx(1.2)
        assert len(voltages) == 15  # -0.2 to 1.2 in 0.1 steps = 15 points

    def test_voltage_array_reverse_direction(self, measurement_model):
        """Voltage array should work for reverse sweeps."""
        voltages = measurement_model.generate_voltage_array(1.2, -0.2, -0.1)

        assert voltages[0] == pytest.approx(1.2)
        assert voltages[-1] == pytest.approx(-0.2)

    def test_measurement_callbacks_fired(self, measurement_model):
        """Measurement should fire progress and completion callbacks."""
        progress_calls = []
        completion_calls = []

        def on_progress(direction, current, total, voltage, current_val):
            progress_calls.append((direction, current, total, voltage, current_val))

        def on_complete(success, result):
            completion_calls.append((success, result))

        measurement_model.set_progress_callback(on_progress)
        measurement_model.set_completion_callback(on_complete)

        # Start measurement with small sweep
        measurement_model.start_measurement(
            start_voltage=0.0,
            stop_voltage=0.2,
            step_voltage=0.1,
            pixel_number=1
        )

        # Wait for completion
        completed = measurement_model.wait_for_completion(timeout=10)
        assert completed is True

        # Verify callbacks were called
        assert len(progress_calls) > 0
        assert len(completion_calls) == 1
        assert completion_calls[0][0] is True  # success

    def test_measurement_collects_forward_reverse_data(self, measurement_model):
        """Measurement should collect both forward and reverse sweep data."""
        measurement_model.start_measurement(
            start_voltage=0.0,
            stop_voltage=0.2,
            step_voltage=0.1,
            pixel_number=1
        )

        completed = measurement_model.wait_for_completion(timeout=10)
        assert completed is True

        result = measurement_model.get_measurement_data()

        # Should have forward data
        assert len(result.forward.voltages) > 0
        assert len(result.forward.currents) > 0

        # Should have reverse data
        assert len(result.reverse.voltages) > 0
        assert len(result.reverse.currents) > 0

        # Forward should go 0 -> 0.2
        assert result.forward.voltages[0] == pytest.approx(0.0)
        assert result.forward.voltages[-1] == pytest.approx(0.2)

        # Reverse should go 0.2 -> 0
        assert result.reverse.voltages[0] == pytest.approx(0.2)
        assert result.reverse.voltages[-1] == pytest.approx(0.0)

    def test_measurement_stores_pixel_number(self, measurement_model):
        """Measurement should store the pixel number."""
        measurement_model.start_measurement(
            start_voltage=0.0,
            stop_voltage=0.1,
            step_voltage=0.1,
            pixel_number=5
        )

        measurement_model.wait_for_completion(timeout=10)
        result = measurement_model.get_measurement_data()

        assert result.pixel_number == 5

    def test_measurement_can_be_stopped(self, measurement_model):
        """Measurement should stop when requested."""
        # Use a larger sweep so we have time to stop it
        measurement_model.start_measurement(
            start_voltage=0.0,
            stop_voltage=1.0,
            step_voltage=0.01,
            pixel_number=1
        )

        # Give it a moment to start
        time.sleep(0.1)

        # Stop the measurement
        measurement_model.stop_measurement()

        # Wait for it to stop
        completed = measurement_model.wait_for_completion(timeout=5)
        assert completed is True

        # Should not be measuring anymore
        assert measurement_model.is_measuring() is False

        # Should have partial data (not complete)
        result = measurement_model.get_measurement_data()
        assert result.measurement_complete is False

    def test_measurement_physics_realistic_currents(self, measurement_model):
        """Mock controller should return physics-realistic I-V data."""
        measurement_model.start_measurement(
            start_voltage=-0.1,
            stop_voltage=1.0,
            step_voltage=0.1,
            pixel_number=1
        )

        measurement_model.wait_for_completion(timeout=10)
        result = measurement_model.get_measurement_data()

        # Current should be positive at 0V (short-circuit condition)
        forward = result.forward
        zero_idx = np.argmin(np.abs(np.array(forward.voltages)))
        jsc = forward.currents[zero_idx]
        assert jsc > 0, "Short-circuit current should be positive"

        # Current should decrease as voltage increases (solar cell behavior)
        # Near Voc, current should be close to zero or negative
        high_v_idx = np.argmax(forward.voltages)
        high_v_current = forward.currents[high_v_idx]
        assert high_v_current < jsc, "Current should decrease with voltage"


class TestJVParameterValidation:
    """Integration tests for J-V parameter validation workflow."""

    def test_valid_parameters_pass(self):
        """Valid parameters should pass validation."""
        from jv.models.jv_experiment import VALIDATION_PATTERNS
        import re

        params = {
            'cell_number': '195',
            'pixel_number': 1,
            'start_voltage': -0.2,
            'stop_voltage': 1.5,
            'step_voltage': 0.02,
        }

        # Validate cell number
        cell_pattern = VALIDATION_PATTERNS["cell_number"]
        assert re.match(cell_pattern, params['cell_number']) is not None

        # Validate pixel number
        pixel_min, pixel_max = VALIDATION_PATTERNS["pixel_range"]
        assert pixel_min <= params['pixel_number'] <= pixel_max

        # Validate voltage parameters
        assert params['step_voltage'] > 0

    def test_cell_number_validation_patterns(self):
        """Cell number validation should match expected patterns."""
        from jv.config.settings import VALIDATION_PATTERNS
        import re

        pattern = VALIDATION_PATTERNS["cell_number"]

        # Valid patterns
        assert re.match(pattern, "195") is not None
        assert re.match(pattern, "001") is not None
        assert re.match(pattern, "999") is not None

        # Invalid patterns
        assert re.match(pattern, "12") is None  # Too short
        assert re.match(pattern, "1234") is None  # Too long
        assert re.match(pattern, "abc") is None  # Non-numeric

    def test_pixel_range_from_config(self):
        """Pixel range should match config values."""
        from jv.config.settings import VALIDATION_PATTERNS

        pixel_min, pixel_max = VALIDATION_PATTERNS["pixel_range"]
        assert pixel_min == 1
        assert pixel_max == 8


class TestJVDataResult:
    """Tests for JVMeasurementResult data structure."""

    def test_sweep_data_add_point(self):
        """SweepData should store voltage-current pairs."""
        sweep = SweepData(direction="forward")

        sweep.add_point(0.0, 35.0)
        sweep.add_point(0.5, 30.0)
        sweep.add_point(1.0, 10.0)

        assert len(sweep) == 3
        assert sweep.voltages == [0.0, 0.5, 1.0]
        assert sweep.currents == [35.0, 30.0, 10.0]

    def test_sweep_data_clear(self):
        """SweepData.clear() should reset data."""
        sweep = SweepData()
        sweep.add_point(0.0, 35.0)
        sweep.add_point(0.5, 30.0)

        sweep.clear()

        assert len(sweep) == 0
        assert sweep.voltages == []
        assert sweep.currents == []

    def test_result_clear(self):
        """JVMeasurementResult.clear() should reset all data."""
        result = JVMeasurementResult()
        result.forward.add_point(0.0, 35.0)
        result.reverse.add_point(1.0, -5.0)
        result.pixel_number = 3
        result.measurement_complete = True

        result.clear()

        assert len(result.forward) == 0
        assert len(result.reverse) == 0
        assert result.pixel_number == 0
        assert result.measurement_complete is False


class TestJVConfigIntegration:
    """Tests for J-V configuration integration."""

    def test_measurement_config_defaults(self):
        """Measurement config should have expected defaults."""
        assert "voltage_range" in JV_MEASUREMENT_CONFIG
        assert "current_range" in JV_MEASUREMENT_CONFIG
        assert "current_compliance" in JV_MEASUREMENT_CONFIG
        assert "source_delay_s" in JV_MEASUREMENT_CONFIG

    def test_default_params_structure(self):
        """Default params should have expected structure."""
        assert "cell_number" in DEFAULT_MEASUREMENT_PARAMS
        assert "pixel_number" in DEFAULT_MEASUREMENT_PARAMS
        assert "start_voltage" in DEFAULT_MEASUREMENT_PARAMS
        assert "stop_voltage" in DEFAULT_MEASUREMENT_PARAMS
        assert "step_voltage" in DEFAULT_MEASUREMENT_PARAMS

    def test_default_voltage_range(self):
        """Default voltage range should be reasonable for solar cells."""
        start = DEFAULT_MEASUREMENT_PARAMS["start_voltage"]
        stop = DEFAULT_MEASUREMENT_PARAMS["stop_voltage"]
        step = DEFAULT_MEASUREMENT_PARAMS["step_voltage"]

        # Typical range is -0.2 to 1.5 V
        assert start < 0, "Start voltage should be negative for reverse bias"
        assert stop > 0, "Stop voltage should be positive for forward bias"
        assert step > 0, "Step voltage should be positive"
        assert step < 1.0, "Step voltage should be small for good resolution"

