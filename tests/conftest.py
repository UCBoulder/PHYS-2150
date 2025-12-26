"""
Pytest configuration and shared fixtures for PHYS 2150 test suite.

This file provides:
- Common test fixtures (sample data, valid parameters)
- Mock controllers for hardware simulation (Phase 2+)
- Data generators for physics-based test data (Phase 2+)
"""

import pytest
import numpy as np


# ==================== Phase 1: Pure Function Test Fixtures ====================

@pytest.fixture
def sample_sine_data():
    """Generate sample sine wave data for phase fitting tests."""
    phases = np.linspace(0, 360, 37)  # 10-degree steps
    amplitude = 0.5
    phase_shift = np.radians(45)
    offset = 1.0
    signals = amplitude * np.sin(np.radians(phases) + phase_shift) + offset
    return phases, signals, (amplitude, phase_shift, offset)


@pytest.fixture
def sample_noisy_sine_data():
    """Generate noisy sine wave data for robustness tests."""
    np.random.seed(42)  # Reproducible
    phases = np.linspace(0, 360, 37)
    amplitude = 0.5
    phase_shift = np.radians(45)
    offset = 1.0
    noise = np.random.normal(0, 0.05, len(phases))
    signals = amplitude * np.sin(np.radians(phases) + phase_shift) + offset + noise
    return phases, signals


@pytest.fixture
def sample_measurement_data():
    """Generate sample measurement data for statistics tests."""
    np.random.seed(42)
    return np.random.normal(100, 10, 50)  # mean=100, std=10, n=50


@pytest.fixture
def valid_cell_params():
    """Standard valid measurement parameters."""
    return {
        'cell_number': '195',
        'pixel_number': 1,
        'start_voltage': -0.2,
        'stop_voltage': 1.5,
        'step_voltage': 0.02,
    }


@pytest.fixture
def sample_wavelength_range():
    """Standard EQE wavelength range."""
    return {'start': 350.0, 'end': 750.0, 'step': 10.0}


@pytest.fixture
def sample_wavelengths():
    """Array of wavelengths for EQE tests."""
    return np.array([400, 450, 500, 550, 600, 650, 700, 750, 800])


# ==================== Phase 2: Mock Controllers (To Be Implemented) ====================

# @pytest.fixture
# def mock_keithley_controller():
#     """Mock Keithley 2450 returning physics-based I-V data."""
#     pass

# @pytest.fixture
# def mock_picoscope_controller():
#     """Mock PicoScope lock-in with configurable signal level."""
#     pass

# @pytest.fixture
# def mock_monochromator_controller():
#     """Mock monochromator tracking wavelength, grating, filter, shutter."""
#     pass

# @pytest.fixture
# def mock_power_meter_controller():
#     """Mock Thorlabs power meter returning lamp spectrum power."""
#     pass
