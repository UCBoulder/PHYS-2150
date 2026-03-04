"""
Unit tests for PhaseAdjustmentModel R² threshold validation.

Tests is_r_squared_acceptable() and related phase adjustment logic.
"""

import pytest
import numpy as np
from unittest.mock import Mock, patch

from eqe.models.phase_adjustment import PhaseAdjustmentModel
from eqe.config.settings import PHASE_ADJUSTMENT_CONFIG
from tests.mocks.mock_controllers import MockPicoScopeController, MockMonochromatorController


@pytest.fixture
def phase_model():
    """Create PhaseAdjustmentModel with mock controllers."""
    lockin = MockPicoScopeController()
    lockin.connect()
    mono = MockMonochromatorController()
    mono.connect()
    return PhaseAdjustmentModel(lockin=lockin, monochromator=mono)


class TestRSquaredThreshold:
    """Tests for R² threshold validation."""

    def test_min_r_squared_from_config(self):
        """Verify we're using the correct threshold from config."""
        assert PHASE_ADJUSTMENT_CONFIG["min_r_squared"] == 0.90

    def test_r_squared_none_is_not_acceptable(self, phase_model):
        """R² = None should not be acceptable."""
        phase_model.r_squared = None
        assert phase_model.is_r_squared_acceptable() is False

    def test_r_squared_below_threshold_not_acceptable(self, phase_model):
        """R² below 0.90 should not be acceptable."""
        phase_model.r_squared = 0.85
        assert phase_model.is_r_squared_acceptable() is False

        phase_model.r_squared = 0.50
        assert phase_model.is_r_squared_acceptable() is False

        phase_model.r_squared = 0.0
        assert phase_model.is_r_squared_acceptable() is False

    def test_r_squared_at_threshold_is_acceptable(self, phase_model):
        """R² = 0.90 (exactly at threshold) should be acceptable."""
        phase_model.r_squared = 0.90
        assert phase_model.is_r_squared_acceptable() is True

    def test_r_squared_above_threshold_is_acceptable(self, phase_model):
        """R² above 0.90 should be acceptable."""
        phase_model.r_squared = 0.91
        assert phase_model.is_r_squared_acceptable() is True

        phase_model.r_squared = 0.95
        assert phase_model.is_r_squared_acceptable() is True

        phase_model.r_squared = 0.99
        assert phase_model.is_r_squared_acceptable() is True

        phase_model.r_squared = 1.0
        assert phase_model.is_r_squared_acceptable() is True

    def test_r_squared_just_below_threshold(self, phase_model):
        """R² just below 0.90 should not be acceptable."""
        phase_model.r_squared = 0.899
        assert phase_model.is_r_squared_acceptable() is False

        phase_model.r_squared = 0.8999
        assert phase_model.is_r_squared_acceptable() is False


class TestPhaseAdjustmentModelState:
    """Tests for PhaseAdjustmentModel state management."""

    def test_initial_state(self, phase_model):
        """Model should start with empty state."""
        assert phase_model.phase_data == []
        assert phase_model.signal_data == []
        assert phase_model.optimal_phase is None
        assert phase_model.optimal_signal is None
        assert phase_model.r_squared is None
        assert phase_model.is_adjusting() is False

    def test_clear_data(self, phase_model):
        """clear_data should reset all data."""
        # Set some data
        phase_model.phase_data = [0, 10, 20]
        phase_model.signal_data = [1.0, 1.2, 1.1]
        phase_model.optimal_phase = 45.0
        phase_model.optimal_signal = 1.5
        phase_model.r_squared = 0.95

        # Clear
        phase_model.clear_data()

        # Verify cleared
        assert phase_model.phase_data == []
        assert phase_model.signal_data == []
        assert phase_model.optimal_phase is None
        assert phase_model.optimal_signal is None
        assert phase_model.r_squared is None

    def test_get_adjustment_data(self, phase_model):
        """get_adjustment_data should return current state."""
        phase_model.optimal_phase = 45.0
        phase_model.optimal_signal = 1.5e-7
        phase_model.r_squared = 0.98

        results = phase_model.get_adjustment_data()

        assert results['optimal_phase'] == 45.0
        assert results['optimal_signal'] == 1.5e-7
        assert results['r_squared'] == 0.98


class TestPhaseAdjustmentConfig:
    """Tests for phase adjustment configuration values."""

    def test_alignment_wavelength(self):
        """Verify alignment wavelength from config."""
        assert PHASE_ADJUSTMENT_CONFIG["alignment_wavelength"] == 532

    def test_num_visualization_points(self):
        """Verify number of visualization points from config."""
        assert PHASE_ADJUSTMENT_CONFIG["num_visualization_points"] == 37

    def test_stabilization_time(self):
        """Verify stabilization time from config."""
        assert PHASE_ADJUSTMENT_CONFIG["stabilization_time"] == 1.0


class TestPhaseAdjustmentWithMocks:
    """Integration tests using mock controllers."""

    def test_model_creation_with_mocks(self):
        """PhaseAdjustmentModel should work with mock controllers."""
        lockin = MockPicoScopeController()
        mono = MockMonochromatorController()

        model = PhaseAdjustmentModel(lockin=lockin, monochromator=mono)

        assert model.lockin is lockin
        assert model.monochromator is mono

    def test_callbacks_can_be_set(self, phase_model):
        """Callbacks should be settable."""
        def progress_cb(phase, signal):
            pass

        def completion_cb(success, results):
            pass

        phase_model.set_progress_callback(progress_cb)
        phase_model.set_completion_callback(completion_cb)

        assert phase_model.progress_callback is progress_cb
        assert phase_model.completion_callback is completion_cb

    def test_mock_lockin_phase_response(self):
        """Mock lockin should return phase response data."""
        lockin = MockPicoScopeController()
        lockin.connect()

        phase, magnitude, quality = lockin.measure_phase_response()

        assert isinstance(phase, float)
        assert isinstance(magnitude, float)
        assert isinstance(quality, float)
        assert 0 <= quality <= 1

    def test_mock_lockin_measurement(self):
        """Mock lockin should return lock-in measurement."""
        lockin = MockPicoScopeController()
        lockin.connect()

        result = lockin.perform_lockin_measurement()

        assert 'X' in result
        assert 'Y' in result
        assert 'R' in result
        assert 'theta' in result
        assert 'freq' in result
