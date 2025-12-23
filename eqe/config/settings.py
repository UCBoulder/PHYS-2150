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
# These are the initial values shown in the GUI when the application starts
DEFAULT_MEASUREMENT_PARAMS = {
    "start_wavelength": 350.0,  # nm - beginning of wavelength sweep
    "end_wavelength": 750.0,    # nm - end of wavelength sweep
    "step_size": 10.0,          # nm - wavelength increment between measurements
    "cell_number": "",          # Three-digit cell identifier for file naming (user must enter)
    "pixel_number": 1,          # Which pixel (1-8) on the solar cell to measure
}

# Power measurement configuration
# Used when measuring incident light power with the Thorlabs power meter
POWER_MEASUREMENT_CONFIG = {
    "num_measurements": 200,    # Number of readings to average across chopper cycles
    "correction_factor": 2.0,   # Compensates for 50% duty cycle chopper blocking half the light
    "stabilization_time": 0.2,  # seconds - wait after wavelength change before measuring
}

# Current measurement configuration
CURRENT_MEASUREMENT_CONFIG = {
    "num_measurements": 5,         # Number of lock-in measurements to average
    "transimpedance_gain": 1e-6,  # Accounts for transimpedance amplifier (1 MΩ)
    "stabilization_time": 0.2,    # seconds - wait time after wavelength change for photocell stabilization
    "initial_stabilization_time": 1.0,  # seconds - wait time after setting initial wavelength
}

# Phase adjustment configuration
PHASE_ADJUSTMENT_CONFIG = {
    "alignment_wavelength": 532,   # nm - wavelength for phase adjustment
    "min_r_squared": 0.90,        # Minimum acceptable R² for phase fit visualization
    "num_visualization_points": 37,  # Number of points for phase response visualization
    "stabilization_time": 1.0,    # seconds - wait time for light stabilization before phase measurement
}

# Stability test configuration
STABILITY_TEST_CONFIG = {
    "initial_stabilization_time": 2.0,  # seconds - initial wait before starting measurements
    "outlier_rejection_std": 2.0,       # Number of standard deviations for outlier rejection
}

# Device-specific configurations
DEVICE_CONFIGS = {
    # Thorlabs PM100D power meter settings
    DeviceType.THORLABS_POWER_METER: {
        "timeout": 5.0,  # seconds - USB communication timeout
    },
    # Newport Cornerstone 130 monochromator settings
    DeviceType.MONOCHROMATOR: {
        "interface": "usb",         # Communication interface (USB via VISA)
        "timeout_msec": 29000,      # ms - command timeout (long for grating changes)
        "grating_wavelength_threshold": 685,  # nm - use grating 1 below, grating 2 above
    },
    # PicoScope 5000 series oscilloscope configured as software lock-in amplifier
    DeviceType.PICOSCOPE_LOCKIN: {
        # Chopper frequency - should match physical chopper wheel speed
        "default_chopper_freq": 81,        # Hz - reference frequency for lock-in detection
        # Integration cycles - more cycles = better noise rejection but slower
        "default_num_cycles": 100,         # cycles for accurate measurements (~1.2s at 81Hz)
        "fast_measurement_cycles": 20,     # cycles for live monitoring (~0.25s at 81Hz)
        # Averaging and quality control
        "num_measurements": 5,             # readings to average per data point
        "saturation_threshold_v": 0.95,    # V - warn if signal approaches ADC limit
        "signal_quality_reference_v": 0.1, # V - reference for SNR quality metric (0-1 scale)
        # Amplitude correction for Hilbert transform algorithm
        # The 0.5 factor compensates for RMS normalization of square wave reference
        # Validated via AWG testing - see docs/software-lockin.md
        "correction_factor": 0.5,
    }
}

# Filter wavelength thresholds (nm)
# Order-sorting filters block higher-order diffraction from the grating.
# Without filters, 400nm light could appear at 800nm (2nd order), etc.
FILTER_THRESHOLD_LOWER = 420   # nm - below this: no filter needed (no 2nd order overlap)
FILTER_THRESHOLD_UPPER = 800   # nm - above this: use 780nm longpass filter

# Filter wheel configuration for monochromator
# Maps filter position number to filter properties
FILTER_CONFIG = {
    1: {"name": "400 nm filter", "wavelength_range": (FILTER_THRESHOLD_LOWER, FILTER_THRESHOLD_UPPER)},
    2: {"name": "780 nm filter", "wavelength_range": (FILTER_THRESHOLD_UPPER, float('inf'))},
    3: {"name": "no filter", "wavelength_range": (0, FILTER_THRESHOLD_LOWER)},
}

# File naming conventions
# Templates use Python string formatting: {variable} is replaced with actual value
FILE_NAMING = {
    "date_format": "%Y_%m_%d",  # strftime format for date portion of filename
    "power_file_template": "{date}_power_cell{cell_number}.csv",           # Incident power vs wavelength
    "current_file_template": "{date}_current_cell{cell_number}_pixel{pixel_number}.csv",  # Photocurrent vs wavelength
    "phase_file_template": "{date}_phase_cell{cell_number}.csv",           # Phase adjustment results
}

# GUI configuration
# Controls appearance and behavior of the PySide6 application window
GUI_CONFIG = {
    "window_title": "PHYS 2150 EQE Measurement - MVC Architecture",
    "window_size": (1400, 950),       # pixels (width, height) - initial window dimensions
    "plot_size": (300, 300),          # pixels - minimum size for plot widgets
    "plot_max_size": (400, 400),      # pixels - maximum size for plot widgets
    "live_monitor_interval_ms": 500,  # ms - how often to update live signal display
    # Font sizes in points for various UI elements
    "font_sizes": {
        "label": 14,       # Input field labels
        "button": 14,      # Button text
        "plot_title": 10,  # Plot title text
        "plot_axis": 10,   # Axis labels (e.g., "Wavelength (nm)")
        "plot_tick": 8,    # Tick mark labels (numbers on axes)
    },
    # Colors as hex RGB strings
    "colors": {
        "start_button": "#CCDDAA",  # Light green - indicates safe/go action
        "stop_button": "#FFCCCC",   # Light red - indicates stop/caution
        "plot_line": "#0077BB",     # Blue - data trace color
    },
    # Set True to prompt user to save phase adjustment data after each current measurement
    "prompt_phase_data_save": False,
}

# Data export configuration
# Controls how measurement data is written to CSV files
DATA_EXPORT_CONFIG = {
    "default_format": "csv",   # File format for saved data
    "csv_delimiter": ",",      # Column separator character
    "precision": 6,            # Decimal places for floating-point values
    # Include measurement statistics (std dev, n, CV%) in exported CSV files
    # When True: exports mean, std_dev, n, CV% - teaches that uncertainty is part of measurement
    # When False: exports only mean value (legacy format, backwards compatible)
    "include_measurement_stats": True,
    # Column headers for each measurement type's CSV output
    "headers": {
        "power": ["Wavelength (nm)", "Power (W)"],
        "current": ["Wavelength (nm)", "Current (A)"],
        "current_with_stats": ["Wavelength (nm)", "Current_mean (nA)", "Current_std (nA)", "n", "CV_percent"],
        "phase": ["Pixel #", "Set Angle", "Signal", "R^2 Value"],
    }
}

# Validation patterns
# Used to validate user input in the GUI
VALIDATION_PATTERNS = {
    "cell_number": r'^\d{3}$',  # Regex: exactly three digits (e.g., 167, 001, 999)
    "pixel_range": (1, 8),      # Inclusive range of valid pixel numbers
}

# Error messages
# User-facing messages displayed when errors occur
ERROR_MESSAGES = {
    "device_not_found": "Device not found. Please check the connection.",
    "invalid_cell_number": "Cell number must be a three-digit number (e.g., 167, 001, 999).",
    "invalid_pixel_number": "Pixel number must be between 1 and 8.",
    "measurement_failed": "Measurement failed. Please check device connections.",
    "file_save_failed": "Failed to save file. Please check permissions and disk space.",
    "low_r_squared": "Is the lamp on? If it is, pixel {pixel} might be dead. Check in with a TA.",
}