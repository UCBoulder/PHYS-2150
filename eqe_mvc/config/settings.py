"""
Configuration constants and settings for the EQE measurement application.
"""

from enum import Enum
from typing import Dict, Any


class MeasurementType(Enum):
    """Types of measurements supported."""
    POWER = "power"
    CURRENT = "current"
    PHASE = "phase"


class DeviceType(Enum):
    """Types of devices in the system."""
    THORLABS_POWER_METER = "thorlabs_power_meter"
    KEITHLEY_2110 = "keithley_2110"
    MONOCHROMATOR = "monochromator"
    SR510_LOCKIN = "sr510_lockin"


# Default measurement parameters
DEFAULT_MEASUREMENT_PARAMS = {
    "start_wavelength": 350.0,  # nm
    "end_wavelength": 850.0,    # nm
    "step_size": 10.0,          # nm
    "cell_number": "C60_01",
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
    "num_voltage_readings": 100,
    "transimpedance_gain": 1e-6,  # Accounts for transimpedance amplifier
    "voltage_threshold": 10.0,    # Voltage threshold for sensitivity adjustment
}

# Phase adjustment configuration
PHASE_ADJUSTMENT_CONFIG = {
    "num_phase_points": 7,        # Number of phase points to sample
    "phase_range": (0, 360),      # Phase range in degrees
    "alignment_wavelength": 532,   # nm
    "min_r_squared": 0.90,        # Minimum acceptable R² for phase fit
}

# Device-specific configurations
DEVICE_CONFIGS = {
    DeviceType.THORLABS_POWER_METER: {
        "timeout": 5.0,
    },
    DeviceType.KEITHLEY_2110: {
        "timeout": 5.0,
    },
    DeviceType.MONOCHROMATOR: {
        "interface": "usb",
        "timeout_msec": 29000,
        "grating_wavelength_threshold": 685,  # nm - switch to grating 2 above this
    },
    DeviceType.SR510_LOCKIN: {
        "baudrate": 19200,
        "timeout": 2.0,
        "com_port_description": "Prolific PL2303GT USB Serial COM Port",
    }
}

# Monochromator correction factors by serial number
MONOCHROMATOR_CORRECTION_FACTORS = {
    "130B5203": 0.45,  # EQE2
    "130B5201": 0.45,  # EQE3
    "130B5202": 0.45,  # EQE1
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
    "cell_number": r'^(C60_\d+|\d+-\d+)$',  # e.g., C60_01 or 2501-04
    "pixel_range": (1, 6),  # Valid pixel numbers
}

# Error messages
ERROR_MESSAGES = {
    "device_not_found": "Device not found. Please check the connection.",
    "invalid_cell_number": "Cell number must be in format C60_XX or XXXX-XX (e.g., C60_01, 2501-04).",
    "invalid_pixel_number": "Pixel number must be between 1 and 6.",
    "measurement_failed": "Measurement failed. Please check device connections.",
    "file_save_failed": "Failed to save file. Please check permissions and disk space.",
    "low_r_squared": "Is the lamp on? If it is, pixel {pixel} might be dead. Check in with a TA.",
}