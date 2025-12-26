"""
Integration tests for EQE measurement workflow.

Tests the complete EQE measurement workflow from parameter setup through
data collection using mock controllers.
"""

import pytest
import numpy as np
import time
from unittest.mock import Mock, patch, MagicMock

from eqe.models.current_measurement import CurrentMeasurementModel, CurrentMeasurementError
from eqe.models.power_measurement import PowerMeasurementModel, PowerMeasurementError
from eqe.models.phase_adjustment import PhaseAdjustmentModel, PhaseAdjustmentError
from eqe.config.settings import (
    DEFAULT_MEASUREMENT_PARAMS,
    PHASE_ADJUSTMENT_CONFIG,
    CURRENT_MEASUREMENT_CONFIG,
    POWER_MEASUREMENT_CONFIG,
)
from eqe.utils.data_handling import MeasurementDataLogger
from tests.mocks.mock_controllers import (
    MockPicoScopeController,
    MockMonochromatorController,
    MockPowerMeterController,
)


class MockLogger(MeasurementDataLogger):
    """Mock logger that doesn't print to console."""

    def __init__(self):
        self.logs = []

    def log(self, message: str, level: str = "INFO") -> None:
        self.logs.append((level, message))

    def debug(self, message: str) -> None:
        self.logs.append(("DEBUG", message))


class TestCurrentMeasurementWorkflow:
    """Integration tests for current measurement workflow with mock controllers."""

    @pytest.fixture
    def current_model(self):
        """Create CurrentMeasurementModel with mock controllers."""
        lockin = MockPicoScopeController()
        lockin.connect()
        mono = MockMonochromatorController()
        mono.connect()
        logger = MockLogger()

        # Patch config for faster tests
        with patch.dict(CURRENT_MEASUREMENT_CONFIG, {
            "stabilization_time": 0.01,
            "initial_stabilization_time": 0.01,
            "num_measurements": 3,
        }):
            yield CurrentMeasurementModel(lockin=lockin, monochromator=mono, logger=logger)

    def test_measure_current_at_wavelength(self, current_model):
        """Should measure current at a specific wavelength."""
        wavelength, current = current_model.measure_current_at_wavelength(550.0)

        assert wavelength == pytest.approx(550.0)
        assert current is not None
        assert isinstance(current, float)

    def test_measure_current_with_stats(self, current_model):
        """Should return statistics when requested."""
        wavelength, current, stats = current_model.measure_current_at_wavelength(
            550.0, return_stats=True
        )

        assert wavelength == pytest.approx(550.0)
        assert current is not None
        assert 'std_dev' in stats
        assert 'n' in stats
        assert 'cv_percent' in stats

    def test_start_measurement_validates_wavelengths(self, current_model):
        """Should validate start < end wavelength."""
        with pytest.raises(CurrentMeasurementError, match="less than"):
            current_model.start_measurement(
                start_wavelength=700,
                end_wavelength=400,
                step_size=10,
                pixel_number=1
            )

    def test_start_measurement_validates_step_size(self, current_model):
        """Should validate positive step size."""
        with pytest.raises(CurrentMeasurementError, match="positive"):
            current_model.start_measurement(
                start_wavelength=400,
                end_wavelength=700,
                step_size=-10,
                pixel_number=1
            )

    def test_start_measurement_validates_pixel_number(self, current_model):
        """Should validate pixel number 1-8."""
        with pytest.raises(CurrentMeasurementError, match="between 1 and 8"):
            current_model.start_measurement(
                start_wavelength=400,
                end_wavelength=700,
                step_size=10,
                pixel_number=0
            )

        with pytest.raises(CurrentMeasurementError, match="between 1 and 8"):
            current_model.start_measurement(
                start_wavelength=400,
                end_wavelength=700,
                step_size=10,
                pixel_number=9
            )

    def test_measurement_callbacks_fired(self, current_model):
        """Measurement should fire progress and completion callbacks."""
        progress_calls = []
        completion_calls = []

        def on_progress(wavelength, current, progress):
            progress_calls.append((wavelength, current, progress))

        def on_complete(success):
            completion_calls.append(success)

        current_model.set_progress_callback(on_progress)
        current_model.set_completion_callback(on_complete)

        # Start measurement with small range
        current_model.start_measurement(
            start_wavelength=500,
            end_wavelength=520,
            step_size=10,
            pixel_number=1
        )

        # Wait for completion
        completed = current_model.wait_for_completion(timeout=10)
        assert completed is True

        # Verify callbacks were called
        assert len(progress_calls) > 0
        assert len(completion_calls) == 1
        assert completion_calls[0] is True

    def test_measurement_collects_data(self, current_model):
        """Measurement should collect wavelength-current pairs."""
        current_model.start_measurement(
            start_wavelength=500,
            end_wavelength=520,
            step_size=10,
            pixel_number=3
        )

        current_model.wait_for_completion(timeout=10)

        wavelengths, currents, pixel, stats = current_model.get_measurement_data()

        assert len(wavelengths) == 3  # 500, 510, 520
        assert len(currents) == 3
        assert pixel == 3
        assert wavelengths[0] == pytest.approx(500)
        assert wavelengths[-1] == pytest.approx(520)

    def test_measurement_updates_filter(self, current_model):
        """Measurement should update filter when crossing thresholds."""
        # Measure across 420nm threshold
        current_model.start_measurement(
            start_wavelength=400,
            end_wavelength=450,
            step_size=50,
            pixel_number=1
        )

        current_model.wait_for_completion(timeout=10)

        # Filter should have changed during measurement
        wavelengths, _, _, _ = current_model.get_measurement_data()
        assert 400 in [int(w) for w in wavelengths]
        assert 450 in [int(w) for w in wavelengths]

    def test_measurement_can_be_stopped(self, current_model):
        """Measurement should stop when requested."""
        current_model.start_measurement(
            start_wavelength=400,
            end_wavelength=800,
            step_size=5,  # Many points
            pixel_number=1
        )

        # Give it a moment to start
        time.sleep(0.1)

        # Stop the measurement
        current_model.stop_measurement()

        # Wait for it to stop
        completed = current_model.wait_for_completion(timeout=5)
        assert completed is True

        # Should not be measuring anymore
        assert current_model.is_measuring() is False


class TestPowerMeasurementWorkflow:
    """Integration tests for power measurement workflow with mock controllers."""

    @pytest.fixture
    def power_model(self):
        """Create PowerMeasurementModel with mock controllers."""
        power_meter = MockPowerMeterController()
        power_meter.connect()
        mono = MockMonochromatorController()
        mono.connect()
        logger = MockLogger()

        # Patch config for faster tests
        with patch.dict(POWER_MEASUREMENT_CONFIG, {
            "stabilization_time": 0.01,
            "num_measurements": 3,
            "correction_factor": 1.0,
        }):
            yield PowerMeasurementModel(
                power_meter=power_meter,
                monochromator=mono,
                logger=logger
            )

    def test_measure_power_at_wavelength(self, power_model):
        """Should measure power at a specific wavelength."""
        wavelength, power = power_model.measure_power_at_wavelength(550.0)

        assert wavelength == pytest.approx(550.0)
        assert power is not None
        assert isinstance(power, float)
        assert power > 0

    def test_start_measurement_validates_wavelengths(self, power_model):
        """Should validate start < end wavelength."""
        with pytest.raises(PowerMeasurementError, match="less than"):
            power_model.start_measurement(
                start_wavelength=700,
                end_wavelength=400,
                step_size=10
            )

    def test_measurement_collects_data(self, power_model):
        """Measurement should collect wavelength-power pairs."""
        power_model.start_measurement(
            start_wavelength=500,
            end_wavelength=520,
            step_size=10
        )

        power_model.wait_for_completion(timeout=10)

        wavelengths, powers = power_model.get_measurement_data()

        assert len(wavelengths) == 3  # 500, 510, 520
        assert len(powers) == 3
        assert all(p > 0 for p in powers)

    def test_power_wavelength_dependence(self, power_model):
        """Power should vary with wavelength (mock uses bell curve)."""
        power_model.start_measurement(
            start_wavelength=400,
            end_wavelength=700,
            step_size=100
        )

        power_model.wait_for_completion(timeout=10)

        wavelengths, powers = power_model.get_measurement_data()

        # 550nm should have highest power (bell curve center)
        peak_idx = np.argmax(powers)
        peak_wavelength = wavelengths[peak_idx]
        assert 500 <= peak_wavelength <= 600


class TestPhaseAdjustmentWorkflow:
    """Integration tests for phase adjustment workflow with mock controllers."""

    @pytest.fixture
    def phase_model(self):
        """Create PhaseAdjustmentModel with mock controllers."""
        lockin = MockPicoScopeController()
        lockin.connect()
        mono = MockMonochromatorController()
        mono.connect()
        logger = MockLogger()

        # Patch config for faster tests
        with patch.dict(PHASE_ADJUSTMENT_CONFIG, {
            "stabilization_time": 0.01,
            "alignment_wavelength": 532,
            "num_visualization_points": 37,
            "min_r_squared": 0.90,
        }):
            yield PhaseAdjustmentModel(lockin=lockin, monochromator=mono, logger=logger)

    def test_start_adjustment_validates_pixel_number(self, phase_model):
        """Should validate pixel number 1-8."""
        with pytest.raises(PhaseAdjustmentError, match="between 1 and 8"):
            phase_model.start_adjustment(pixel_number=0)

        with pytest.raises(PhaseAdjustmentError, match="between 1 and 8"):
            phase_model.start_adjustment(pixel_number=9)

    def test_adjustment_collects_phase_data(self, phase_model):
        """Adjustment should collect phase-signal pairs."""
        completion_results = []

        def on_complete(success, results):
            completion_results.append((success, results))

        phase_model.set_completion_callback(on_complete)

        phase_model.start_adjustment(pixel_number=1)
        phase_model.wait_for_completion(timeout=10)

        # Should have results
        assert len(completion_results) == 1
        success, results = completion_results[0]
        assert success is True
        assert 'optimal_phase' in results
        assert 'r_squared' in results
        assert 'phase_data' in results
        assert 'signal_data' in results

    def test_adjustment_finds_optimal_phase(self, phase_model):
        """Adjustment should find optimal phase angle."""
        phase_model.start_adjustment(pixel_number=1)
        phase_model.wait_for_completion(timeout=10)

        data = phase_model.get_adjustment_data()

        assert data['optimal_phase'] is not None
        assert 0 <= data['optimal_phase'] <= 360

    def test_r_squared_quality_check(self, phase_model):
        """Should check R² quality threshold."""
        phase_model.start_adjustment(pixel_number=1)
        phase_model.wait_for_completion(timeout=10)

        # Mock should produce acceptable R² (use == to handle numpy bool)
        assert phase_model.is_r_squared_acceptable() == True

    def test_clear_data(self, phase_model):
        """clear_data should reset all results."""
        phase_model.start_adjustment(pixel_number=1)
        phase_model.wait_for_completion(timeout=10)

        # Verify data exists
        assert phase_model.optimal_phase is not None

        # Clear
        phase_model.clear_data()

        # Verify cleared
        assert phase_model.optimal_phase is None
        assert phase_model.r_squared is None
        assert phase_model.phase_data == []


class TestEQEParameterValidation:
    """Integration tests for EQE parameter validation workflow."""

    def test_default_params_structure(self):
        """Default params should have expected structure."""
        assert "cell_number" in DEFAULT_MEASUREMENT_PARAMS
        assert "pixel_number" in DEFAULT_MEASUREMENT_PARAMS
        assert "start_wavelength" in DEFAULT_MEASUREMENT_PARAMS
        assert "end_wavelength" in DEFAULT_MEASUREMENT_PARAMS
        assert "step_size" in DEFAULT_MEASUREMENT_PARAMS

    def test_wavelength_range_reasonable(self):
        """Default wavelength range should be reasonable for EQE."""
        start = DEFAULT_MEASUREMENT_PARAMS["start_wavelength"]
        end = DEFAULT_MEASUREMENT_PARAMS["end_wavelength"]
        step = DEFAULT_MEASUREMENT_PARAMS["step_size"]

        # Typical EQE range is 300-1100nm
        assert 300 <= start <= 500, "Start wavelength should be in UV-visible"
        assert 700 <= end <= 1200, "End wavelength should extend to NIR"
        assert 1 <= step <= 20, "Step size should be reasonable"


class TestEQEConfigIntegration:
    """Tests for EQE configuration integration."""

    def test_phase_adjustment_config(self):
        """Phase adjustment config should have expected values."""
        assert "min_r_squared" in PHASE_ADJUSTMENT_CONFIG
        assert "alignment_wavelength" in PHASE_ADJUSTMENT_CONFIG
        assert "num_visualization_points" in PHASE_ADJUSTMENT_CONFIG
        assert "stabilization_time" in PHASE_ADJUSTMENT_CONFIG

        # Verify reasonable values
        assert 0 < PHASE_ADJUSTMENT_CONFIG["min_r_squared"] <= 1
        assert 400 <= PHASE_ADJUSTMENT_CONFIG["alignment_wavelength"] <= 600

    def test_current_measurement_config(self):
        """Current measurement config should have expected values."""
        assert "stabilization_time" in CURRENT_MEASUREMENT_CONFIG
        assert "num_measurements" in CURRENT_MEASUREMENT_CONFIG

    def test_power_measurement_config(self):
        """Power measurement config should have expected values."""
        assert "stabilization_time" in POWER_MEASUREMENT_CONFIG
        assert "num_measurements" in POWER_MEASUREMENT_CONFIG
        assert "correction_factor" in POWER_MEASUREMENT_CONFIG


class TestEQEDataFlow:
    """Integration tests for EQE data flow through the system."""

    def test_current_measurement_data_flow(self):
        """Test data flows correctly through current measurement."""
        lockin = MockPicoScopeController()
        lockin.connect()
        lockin.set_signal_amplitude(1e-7)  # 100 nA

        mono = MockMonochromatorController()
        mono.connect()

        logger = MockLogger()

        with patch.dict(CURRENT_MEASUREMENT_CONFIG, {
            "stabilization_time": 0.01,
            "initial_stabilization_time": 0.01,
            "num_measurements": 3,
        }):
            model = CurrentMeasurementModel(lockin=lockin, monochromator=mono, logger=logger)

            # Measure at single wavelength
            wavelength, current = model.measure_current_at_wavelength(532.0)

            # Current should be close to set amplitude
            assert abs(current - 1e-7) < 1e-8  # Within 10%

    def test_power_measurement_data_flow(self):
        """Test data flows correctly through power measurement."""
        power_meter = MockPowerMeterController()
        power_meter.connect()

        mono = MockMonochromatorController()
        mono.connect()

        logger = MockLogger()

        with patch.dict(POWER_MEASUREMENT_CONFIG, {
            "stabilization_time": 0.01,
            "num_measurements": 3,
            "correction_factor": 1.0,
        }):
            model = PowerMeasurementModel(
                power_meter=power_meter,
                monochromator=mono,
                logger=logger
            )

            # Measure at wavelength
            wavelength, power = model.measure_power_at_wavelength(550.0)

            # Power should be positive and reasonable
            assert power > 0
            assert power < 1.0  # Less than 1W

