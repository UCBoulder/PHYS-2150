"""
Configuration constants and settings for the EQE measurement application.
"""

from enum import Enum
from typing import Dict, Any

# Application mode
OFFLINE_MODE = False  # Set to True to run without hardware (for GUI testing)


class MeasurementType(Enum):
    """Types of measurements supported."""
    POWER = "power"
    CURRENT = "current"
    PHASE = "phase"


class DeviceType(Enum):
    """Types of devices in the system."""
    THORLABS_POWER_METER = "thorlabs_power_meter"
    MONOCHROMATOR = "monochromator"
    PICOSCOPE_LOCKIN = "picoscope_lockin"


# Default measurement parameters
DEFAULT_MEASUREMENT_PARAMS = {
    "start_wavelength": 350.0,  # nm
    "end_wavelength": 850.0,    # nm
    "step_size": 10.0,          # nm
    "cell_number": "167",       # Three-digit cell number
    "pixel_number": 1,
}

# Power measurement configuration
POWER_MEASUREMENT_CONFIG = {
    "num_measurements": 200,
    "correction_factor": 2.0,
    "stabilization_time": 0.2,  # seconds
}

# Current measurement configuration
CURRENT_MEASUREMENT_CONFIG = {
    "num_measurements": 5,         # Number of lock-in measurements to average
    "transimpedance_gain": 1e-6,  # Accounts for transimpedance amplifier (1 MΩ)
}

# Phase adjustment configuration
PHASE_ADJUSTMENT_CONFIG = {
    "alignment_wavelength": 532,   # nm - wavelength for phase adjustment
    "min_r_squared": 0.90,        # Minimum acceptable R² for phase fit visualization
    "num_visualization_points": 37,  # Number of points for phase response visualization
}

# Device-specific configurations
DEVICE_CONFIGS = {
    DeviceType.THORLABS_POWER_METER: {
        "timeout": 5.0,
    },
    DeviceType.MONOCHROMATOR: {
        "interface": "usb",
        "timeout_msec": 29000,
        "grating_wavelength_threshold": 685,  # nm - switch to grating 2 above this
    },
    DeviceType.PICOSCOPE_LOCKIN: {
        "default_chopper_freq": 81,    # Hz - default chopper frequency
        "default_num_cycles": 100,     # Number of cycles for lock-in integration
        "num_measurements": 5,         # Number of measurements to average for stability
        # Note: No correction factor needed for software lock-in!
        # Digital lock-in uses actual square wave reference, preserving all harmonics
        # SR510's 0.45 factor was needed due to sine wave reference losing harmonic content
    }
}

# Monochromator correction factors by serial number
# NOTE: The previous 0.45 factors were for SR510 analog lock-in harmonic loss,
# not for monochromator optical efficiency. With PicoScope software lock-in,
# no correction is needed (uses actual square wave reference, preserving harmonics).
# If optical corrections are needed in the future, they should be measured separately.
MONOCHROMATOR_CORRECTION_FACTORS = {
    "130B5203": 1.0,  # EQE2 - no correction needed with software lock-in
    "130B5201": 1.0,  # EQE3 - no correction needed with software lock-in
    "130B5202": 1.0,  # EQE1 - no correction needed with software lock-in
}

# Filter configuration for monochromator
FILTER_CONFIG = {
    1: {"name": "400 nm filter", "wavelength_range": (420, 800)},
    2: {"name": "780 nm filter", "wavelength_range": (800, float('inf'))},
    3: {"name": "no filter", "wavelength_range": (0, 420)},
}

# File naming conventions
FILE_NAMING = {
    "date_format": "%Y_%m_%d",
    "power_file_template": "{date}_power_cell{cell_number}.csv",
    "current_file_template": "{date}_current_cell{cell_number}_pixel{pixel_number}.csv",
    "phase_file_template": "{date}_phase_cell{cell_number}.csv",
}

# GUI configuration
GUI_CONFIG = {
    "window_title": "PHYS 2150 EQE Measurement - MVC Architecture",
    "window_size": (1200, 800),
    "plot_size": (300, 300),
    "plot_max_size": (400, 400),
    "font_sizes": {
        "label": 14,
        "button": 14,
        "plot_title": 10,
        "plot_axis": 10,
        "plot_tick": 8,
    },
    "colors": {
        "start_button": "#CCDDAA",
        "stop_button": "#FFCCCC",
        "plot_line": "#0077BB",
    }
}

# Data export configuration
DATA_EXPORT_CONFIG = {
    "default_format": "csv",
    "csv_delimiter": ",",
    "precision": 6,  # Number of decimal places for measurements
    "headers": {
        "power": ["Wavelength (nm)", "Power (W)"],
        "current": ["Wavelength (nm)", "Current (A)"],
        "phase": ["Pixel #", "Set Angle", "Signal", "R^2 Value"],
    }
}

# Validation patterns
VALIDATION_PATTERNS = {
    "cell_number": r'^\d{3}$',  # Three-digit cell number (e.g., 167, 001, 999)
    "pixel_range": (1, 8),  # Valid pixel numbers (now 8 pixels per cell)
}

# Error messages
ERROR_MESSAGES = {
    "device_not_found": "Device not found. Please check the connection.",
    "invalid_cell_number": "Cell number must be a three-digit number (e.g., 167, 001, 999).",
    "invalid_pixel_number": "Pixel number must be between 1 and 8.",
    "measurement_failed": "Measurement failed. Please check device connections.",
    "file_save_failed": "Failed to save file. Please check permissions and disk space.",
    "low_r_squared": "Is the lamp on? If it is, pixel {pixel} might be dead. Check in with a TA.",
}