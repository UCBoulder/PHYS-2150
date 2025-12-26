"""
Unit tests for StabilityTestModel.

Tests power and current stability tests including callbacks,
statistics calculation, and state management.
"""

import pytest
import time
from unittest.mock import Mock, patch, MagicMock

from eqe.models.stability_test import StabilityTestModel
from eqe.config.settings import STABILITY_TEST_CONFIG
from tests.mocks.mock_controllers import (
    MockPicoScopeController,
    MockMonochromatorController,
    MockPowerMeterController,
)


class TestStabilityTestModelInitialization:
    """Tests for StabilityTestModel initialization and state."""

    def test_initial_state(self):
        """Model should start with empty state."""
        model = StabilityTestModel()

        assert model.is_running() is False
        assert model.timestamps == []
        assert model.values == []
        assert model.test_type is None

    def test_initialization_with_controllers(self):
        """Model should accept controllers."""
        lockin = MockPicoScopeController()
        mono = MockMonochromatorController()
        power_meter = MockPowerMeterController()

        model = StabilityTestModel(
            power_meter=power_meter,
            monochromator=mono,
            lockin=lockin
        )

        assert model.power_meter is power_meter
        assert model.monochromator is mono
        assert model.lockin is lockin


class TestStabilityTestCallbacks:
    """Tests for callback setting and invocation."""

    def test_set_measurement_callback(self):
        """Should set measurement callback."""
        model = StabilityTestModel()
        callback = Mock()

        model.set_measurement_callback(callback)

        assert model.measurement_callback is callback

    def test_set_completion_callback(self):
        """Should set completion callback."""
        model = StabilityTestModel()
        callback = Mock()

        model.set_completion_callback(callback)

        assert model.completion_callback is callback

    def test_set_error_callback(self):
        """Should set error callback."""
        model = StabilityTestModel()
        callback = Mock()

        model.set_error_callback(callback)

        assert model.error_callback is callback

    def test_set_status_callback(self):
        """Should set status callback."""
        model = StabilityTestModel()
        callback = Mock()

        model.set_status_callback(callback)

        assert model.status_callback is callback

    def test_set_monochromator_callback(self):
        """Should set monochromator callback."""
        model = StabilityTestModel()
        callback = Mock()

        model.set_monochromator_callback(callback)

        assert model.monochromator_callback is callback


class TestPowerStabilityTest:
    """Tests for power stability test functionality."""

    @pytest.fixture
    def power_test_model(self):
        """Create model configured for power tests."""
        power_meter = MockPowerMeterController()
        power_meter.connect()
        mono = MockMonochromatorController()
        mono.connect()

        model = StabilityTestModel(
            power_meter=power_meter,
            monochromator=mono
        )
        return model

    def test_start_power_test_without_devices_fails(self):
        """Starting power test without devices should error."""
        model = StabilityTestModel()
        error_callback = Mock()
        model.set_error_callback(error_callback)

        model.start_power_test(wavelength=550, duration_min=0.01, interval_sec=0.1)

        error_callback.assert_called_once()
        assert "not available" in error_callback.call_args[0][0]

    def test_start_power_test_while_running_fails(self, power_test_model):
        """Starting test while one is running should error."""
        error_callback = Mock()
        power_test_model.set_error_callback(error_callback)

        # Manually set running state
        power_test_model._is_running = True

        power_test_model.start_power_test(wavelength=550, duration_min=0.01, interval_sec=0.1)

        error_callback.assert_called_once()
        assert "already running" in error_callback.call_args[0][0]

    @patch.dict('eqe.models.stability_test.STABILITY_TEST_CONFIG', {'initial_stabilization_time': 0.01})
    @patch.dict('eqe.models.stability_test.POWER_MEASUREMENT_CONFIG', {
        'num_measurements': 3,
        'correction_factor': 1.0
    })
    def test_power_test_runs_and_completes(self, power_test_model):
        """Power test should run and call completion callback."""
        completion_callback = Mock()
        measurement_callback = Mock()
        status_callback = Mock()

        power_test_model.set_completion_callback(completion_callback)
        power_test_model.set_measurement_callback(measurement_callback)
        power_test_model.set_status_callback(status_callback)

        # Run very short test
        power_test_model.start_power_test(
            wavelength=550,
            duration_min=0.02,  # ~1.2 seconds
            interval_sec=0.1
        )

        # Wait for completion
        time.sleep(2)

        # Should have completed
        assert power_test_model.is_running() is False
        completion_callback.assert_called_once()

        # Should have some measurements
        timestamps, values = completion_callback.call_args[0]
        assert len(timestamps) > 0
        assert len(values) > 0
        assert len(timestamps) == len(values)

    @patch.dict('eqe.models.stability_test.STABILITY_TEST_CONFIG', {'initial_stabilization_time': 0.01})
    @patch.dict('eqe.models.stability_test.POWER_MEASUREMENT_CONFIG', {
        'num_measurements': 3,
        'correction_factor': 1.0
    })
    def test_power_test_stores_data(self, power_test_model):
        """Power test should store timestamps and values."""
        power_test_model.start_power_test(
            wavelength=550,
            duration_min=0.02,
            interval_sec=0.1
        )

        time.sleep(2)

        assert len(power_test_model.timestamps) > 0
        assert len(power_test_model.values) > 0
        assert power_test_model.test_type == "power"


class TestCurrentStabilityTest:
    """Tests for current stability test functionality."""

    @pytest.fixture
    def current_test_model(self):
        """Create model configured for current tests."""
        lockin = MockPicoScopeController()
        lockin.connect()
        mono = MockMonochromatorController()
        mono.connect()

        model = StabilityTestModel(
            lockin=lockin,
            monochromator=mono
        )
        return model

    def test_start_current_test_without_devices_fails(self):
        """Starting current test without devices should error."""
        model = StabilityTestModel()
        error_callback = Mock()
        model.set_error_callback(error_callback)

        model.start_current_test(wavelength=550, duration_min=0.01, interval_sec=0.1)

        error_callback.assert_called_once()
        assert "not available" in error_callback.call_args[0][0]

    def test_start_current_test_without_connection_fails(self):
        """Starting current test with disconnected lock-in should error."""
        lockin = MockPicoScopeController()  # Not connected
        mono = MockMonochromatorController()
        mono.connect()

        model = StabilityTestModel(lockin=lockin, monochromator=mono)
        error_callback = Mock()
        model.set_error_callback(error_callback)

        model.start_current_test(wavelength=550, duration_min=0.01, interval_sec=0.1)

        error_callback.assert_called_once()
        assert "not connected" in error_callback.call_args[0][0]

    @patch.dict('eqe.models.stability_test.CURRENT_MEASUREMENT_CONFIG', {
        'stabilization_time': 0.01,
        'num_measurements': 3
    })
    def test_current_test_runs_and_completes(self, current_test_model):
        """Current test should run and call completion callback."""
        completion_callback = Mock()
        measurement_callback = Mock()

        current_test_model.set_completion_callback(completion_callback)
        current_test_model.set_measurement_callback(measurement_callback)

        current_test_model.start_current_test(
            wavelength=550,
            duration_min=0.02,
            interval_sec=0.1,
            pixel_number=1
        )

        time.sleep(2)

        assert current_test_model.is_running() is False
        completion_callback.assert_called_once()

        timestamps, values = completion_callback.call_args[0]
        assert len(timestamps) > 0
        assert len(values) > 0

    @patch.dict('eqe.models.stability_test.CURRENT_MEASUREMENT_CONFIG', {
        'stabilization_time': 0.01,
        'num_measurements': 3
    })
    def test_current_test_stores_data(self, current_test_model):
        """Current test should store timestamps and values."""
        current_test_model.start_current_test(
            wavelength=550,
            duration_min=0.02,
            interval_sec=0.1,
            pixel_number=3
        )

        time.sleep(2)

        assert len(current_test_model.timestamps) > 0
        assert len(current_test_model.values) > 0
        assert current_test_model.test_type == "current"


class TestStabilityTestStop:
    """Tests for stopping stability tests."""

    @pytest.fixture
    def running_model(self):
        """Create model with test running."""
        lockin = MockPicoScopeController()
        lockin.connect()
        mono = MockMonochromatorController()
        mono.connect()

        model = StabilityTestModel(lockin=lockin, monochromator=mono)
        return model

    @patch.dict('eqe.models.stability_test.CURRENT_MEASUREMENT_CONFIG', {
        'stabilization_time': 0.01,
        'num_measurements': 3
    })
    def test_stop_test_stops_running_test(self, running_model):
        """stop_test should stop a running test."""
        status_callback = Mock()
        running_model.set_status_callback(status_callback)

        # Start a long test
        running_model.start_current_test(
            wavelength=550,
            duration_min=1,  # Would run for 60 seconds
            interval_sec=0.1,
            pixel_number=1
        )

        # Wait for it to start
        time.sleep(0.2)
        assert running_model.is_running() is True

        # Stop it
        running_model.stop_test()

        # Wait for stop
        time.sleep(0.5)
        assert running_model.is_running() is False

        # Should have called status callback with stopping message
        assert any("Stop" in str(call) for call in status_callback.call_args_list)


class TestCalculateStatistics:
    """Tests for statistics calculation."""

    def test_empty_list_returns_zeros(self):
        """Empty list should return zero statistics."""
        result = StabilityTestModel.calculate_statistics([])

        assert result['mean'] == 0.0
        assert result['std'] == 0.0
        assert result['cv_percent'] == 0.0
        assert result['min'] == 0.0
        assert result['max'] == 0.0
        assert result['range'] == 0.0
        assert result['count'] == 0

    def test_single_value_statistics(self):
        """Single value should have zero std."""
        result = StabilityTestModel.calculate_statistics([5.0])

        assert result['mean'] == 5.0
        assert result['std'] == 0.0
        assert result['cv_percent'] == 0.0
        assert result['min'] == 5.0
        assert result['max'] == 5.0
        assert result['range'] == 0.0
        assert result['count'] == 1

    def test_basic_statistics(self):
        """Should calculate correct basic statistics."""
        values = [10.0, 20.0, 30.0, 40.0, 50.0]
        result = StabilityTestModel.calculate_statistics(values)

        assert result['mean'] == 30.0
        assert result['min'] == 10.0
        assert result['max'] == 50.0
        assert result['range'] == 40.0
        assert result['count'] == 5

    def test_cv_percent_calculation(self):
        """Should calculate correct CV%."""
        # Values with known CV
        values = [100.0, 100.0, 100.0]  # CV = 0%
        result = StabilityTestModel.calculate_statistics(values)
        assert result['cv_percent'] == pytest.approx(0.0)

        # Values with non-zero CV
        values = [90.0, 100.0, 110.0]  # mean=100, std~8.16
        result = StabilityTestModel.calculate_statistics(values)
        assert result['cv_percent'] > 0

    def test_cv_with_zero_mean(self):
        """CV should be 0 if mean is 0."""
        values = [-5.0, 0.0, 5.0]  # mean = 0
        result = StabilityTestModel.calculate_statistics(values)
        assert result['cv_percent'] == 0.0

    def test_realistic_power_data(self):
        """Should handle realistic power measurement data."""
        # Simulate power in Watts with small variations
        import numpy as np
        np.random.seed(42)
        values = list(np.random.normal(1e-3, 1e-5, 100))  # 1mW +/- 10uW

        result = StabilityTestModel.calculate_statistics(values)

        assert result['count'] == 100
        assert result['mean'] == pytest.approx(1e-3, rel=0.1)
        assert result['cv_percent'] < 5  # Should be ~1%

    def test_realistic_current_data(self):
        """Should handle realistic current measurement data."""
        import numpy as np
        np.random.seed(42)
        values = list(np.random.normal(1e-7, 1e-9, 50))  # 100nA +/- 1nA

        result = StabilityTestModel.calculate_statistics(values)

        assert result['count'] == 50
        assert result['mean'] == pytest.approx(1e-7, rel=0.1)

    def test_returns_python_floats(self):
        """Statistics should return Python floats, not numpy types."""
        values = [1.0, 2.0, 3.0]
        result = StabilityTestModel.calculate_statistics(values)

        assert type(result['mean']) is float
        assert type(result['std']) is float
        assert type(result['cv_percent']) is float
        assert type(result['min']) is float
        assert type(result['max']) is float
        assert type(result['range']) is float


class TestMonochromatorCallbacks:
    """Tests for monochromator state callbacks during tests."""

    @pytest.fixture
    def model_with_callbacks(self):
        """Create model with all callbacks set."""
        lockin = MockPicoScopeController()
        lockin.connect()
        mono = MockMonochromatorController()
        mono.connect()

        model = StabilityTestModel(lockin=lockin, monochromator=mono)
        return model

    @patch.dict('eqe.models.stability_test.CURRENT_MEASUREMENT_CONFIG', {
        'stabilization_time': 0.01,
        'num_measurements': 3
    })
    def test_monochromator_callback_called_with_wavelength(self, model_with_callbacks):
        """Monochromator callback should be called with wavelength."""
        mono_callback = Mock()
        model_with_callbacks.set_monochromator_callback(mono_callback)

        model_with_callbacks.start_current_test(
            wavelength=532,
            duration_min=0.02,
            interval_sec=0.1,
            pixel_number=1
        )

        time.sleep(2)

        # Should have been called at least once
        assert mono_callback.call_count >= 1

        # First call should have wavelength
        first_call = mono_callback.call_args_list[0]
        wavelength, shutter_open = first_call[0]
        assert wavelength == pytest.approx(532)

