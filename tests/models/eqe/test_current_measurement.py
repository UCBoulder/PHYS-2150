"""
Unit tests for CurrentMeasurementModel and monochromator filter switching.

Tests the filter switching logic at 420nm and 800nm thresholds.
"""

import pytest
from numpy.testing import assert_almost_equal

from tests.mocks.mock_controllers import MockMonochromatorController
from eqe.config.settings import FILTER_THRESHOLD_LOWER, FILTER_THRESHOLD_UPPER


class TestMonochromatorFilterSelection:
    """Tests for filter selection based on wavelength thresholds."""

    def test_filter_thresholds_match_config(self):
        """Verify test uses correct threshold values from config."""
        assert FILTER_THRESHOLD_LOWER == 420
        assert FILTER_THRESHOLD_UPPER == 800

    def test_no_filter_below_420nm(self, mock_monochromator_controller):
        """Wavelengths <= 420nm should use no filter (position 3)."""
        controller = mock_monochromator_controller

        # Test boundary and below
        for wavelength in [350, 400, 410, 420]:
            filter_pos = controller.get_filter_for_wavelength(wavelength)
            assert filter_pos == 3, f"Expected no filter (3) for {wavelength}nm, got {filter_pos}"

    def test_400nm_filter_between_420_and_800nm(self, mock_monochromator_controller):
        """Wavelengths 421-800nm should use 400nm filter (position 1)."""
        controller = mock_monochromator_controller

        # Test various points in range
        for wavelength in [421, 500, 550, 600, 700, 800]:
            filter_pos = controller.get_filter_for_wavelength(wavelength)
            assert filter_pos == 1, f"Expected 400nm filter (1) for {wavelength}nm, got {filter_pos}"

    def test_780nm_filter_above_800nm(self, mock_monochromator_controller):
        """Wavelengths > 800nm should use 780nm filter (position 2)."""
        controller = mock_monochromator_controller

        for wavelength in [801, 850, 900, 1000, 1100]:
            filter_pos = controller.get_filter_for_wavelength(wavelength)
            assert filter_pos == 2, f"Expected 780nm filter (2) for {wavelength}nm, got {filter_pos}"

    def test_boundary_at_420nm(self, mock_monochromator_controller):
        """Test exact boundary at 420nm."""
        controller = mock_monochromator_controller

        # At 420nm: no filter
        assert controller.get_filter_for_wavelength(420) == 3

        # Just above 420nm: 400nm filter
        assert controller.get_filter_for_wavelength(421) == 1

    def test_boundary_at_800nm(self, mock_monochromator_controller):
        """Test exact boundary at 800nm."""
        controller = mock_monochromator_controller

        # At 800nm: 400nm filter
        assert controller.get_filter_for_wavelength(800) == 1

        # Just above 800nm: 780nm filter
        assert controller.get_filter_for_wavelength(801) == 2


class TestMonochromatorFilterSwitching:
    """Tests for set_filter_for_wavelength() state changes."""

    def test_filter_changes_reported(self, mock_monochromator_controller):
        """set_filter_for_wavelength should report when filter changes."""
        controller = mock_monochromator_controller

        # Start in middle range (filter 1)
        controller.set_filter(1)
        controller.configure_for_wavelength(500)

        # Move to UV (filter 3) - should report change
        changed = controller.set_filter_for_wavelength(400)
        assert changed is True
        assert controller.get_filter() == 3

    def test_no_change_when_filter_same(self, mock_monochromator_controller):
        """set_filter_for_wavelength should not report change if filter same."""
        controller = mock_monochromator_controller

        # Set to filter 1 range
        controller.configure_for_wavelength(500)

        # Move within same filter range - should not report change
        changed = controller.set_filter_for_wavelength(600)
        assert changed is False
        assert controller.get_filter() == 1

    def test_filter_switching_sequence(self, mock_monochromator_controller):
        """Test filter switching through a typical wavelength scan."""
        controller = mock_monochromator_controller

        # UV region (no filter)
        controller.configure_for_wavelength(350)
        assert controller.get_filter() == 3

        # Visible region (400nm filter)
        controller.configure_for_wavelength(550)
        assert controller.get_filter() == 1

        # NIR region (780nm filter)
        controller.configure_for_wavelength(900)
        assert controller.get_filter() == 2

        # Back to visible
        controller.configure_for_wavelength(600)
        assert controller.get_filter() == 1


class TestMonochromatorConfigureForWavelength:
    """Tests for configure_for_wavelength() comprehensive setup."""

    def test_configure_sets_wavelength(self, mock_monochromator_controller):
        """configure_for_wavelength should set the wavelength."""
        controller = mock_monochromator_controller

        result = controller.configure_for_wavelength(550.0)
        assert result == 550.0
        assert controller.get_wavelength() == 550.0

    def test_configure_sets_filter(self, mock_monochromator_controller):
        """configure_for_wavelength should set appropriate filter."""
        controller = mock_monochromator_controller

        controller.configure_for_wavelength(900)
        assert controller.get_filter() == 2  # 780nm filter for NIR

    def test_configure_returns_wavelength(self, mock_monochromator_controller):
        """configure_for_wavelength should return confirmed wavelength."""
        controller = mock_monochromator_controller

        result = controller.configure_for_wavelength(632.8)
        assert_almost_equal(result, 632.8)


class TestCurrentMeasurementWithMockControllers:
    """Tests for current measurement using mock controllers."""

    def test_mock_lockin_returns_current(self, mock_picoscope_controller):
        """Mock PicoScope should return current values."""
        controller = mock_picoscope_controller

        current = controller.read_current(num_measurements=5)
        assert current is not None
        assert isinstance(current, float)
        assert current != 0

    def test_mock_lockin_returns_stats(self, mock_picoscope_controller):
        """Mock PicoScope should return statistics when requested."""
        controller = mock_picoscope_controller

        result = controller.read_current(num_measurements=10, return_stats=True)
        assert 'current' in result
        assert 'std_dev' in result
        assert 'n' in result
        assert 'cv_percent' in result
        assert result['n'] == 10

    def test_mock_lockin_configurable_amplitude(self, mock_picoscope_controller):
        """Mock PicoScope amplitude should be configurable."""
        controller = mock_picoscope_controller

        # Set low signal
        controller.set_signal_amplitude(1e-9)  # 1 nA
        low_current = controller.read_current()

        # Set high signal
        controller.set_signal_amplitude(1e-6)  # 1 uA
        high_current = controller.read_current()

        # High signal should be ~1000x larger
        assert high_current > low_current * 100

    def test_wavelength_scan_with_mocks(self, mock_monochromator_controller, mock_picoscope_controller):
        """Simulate a wavelength scan with mock controllers."""
        mono = mock_monochromator_controller
        lockin = mock_picoscope_controller

        wavelengths = [400, 500, 600, 700, 800, 900]
        currents = []

        for wl in wavelengths:
            mono.configure_for_wavelength(wl)
            current = lockin.read_current()
            currents.append(current)

        assert len(currents) == len(wavelengths)
        assert all(c is not None for c in currents)
