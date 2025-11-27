"""
Configuration constants and settings for the JV measurement application.

All measurement parameters are centralized here for easy tuning.
This follows the design principle that parameters should be configurable,
not hardcoded, to accommodate evolving measurement protocols.
"""

from typing import Dict, Any

# Application mode
OFFLINE_MODE = False  # Set to True to run without hardware (for GUI testing)


# Default measurement parameters
# These define the voltage sweep range and step size for J-V characterization
DEFAULT_MEASUREMENT_PARAMS: Dict[str, Any] = {
    "start_voltage": -0.2,      # V - reverse bias starting point
    "stop_voltage": 1.5,        # V - forward bias endpoint (beyond typical Voc)
    "step_voltage": 0.02,       # V - voltage step size
    "cell_number": "",          # Three-digit cell identifier (e.g., "195")
    "pixel_number": 1,          # Pixel being measured (1-8)
}


# J-V measurement configuration
# Timing and acquisition parameters for the voltage sweep
JV_MEASUREMENT_CONFIG: Dict[str, Any] = {
    # Dwell time after setting voltage before measuring current
    # Allows cell to stabilize - important for perovskite hysteresis
    "dwell_time_ms": 500,

    # Initial stabilization time at start voltage before sweep begins
    "initial_stabilization_s": 2.0,

    # Pause time between forward and reverse sweeps
    "inter_sweep_delay_s": 2.0,

    # Plot update frequency (update every N points)
    "plot_update_interval": 10,

    # Current measurement range (Amps)
    "current_range": 10,  # mA scale for typical solar cells

    # Voltage source range (Volts)
    "voltage_range": 2,

    # Current compliance limit (Amps)
    "current_compliance": 1,

    # Enable 4-wire (remote) sensing for accurate measurements
    "remote_sensing": True,
}


# Keithley 2450 device configuration
DEVICE_CONFIG: Dict[str, Any] = {
    # VISA timeout in milliseconds
    "timeout_ms": 30000,

    # USB device identification pattern
    "usb_id_pattern": "USB0::0x05E6::0x2450",

    # SCPI command termination
    "write_termination": "\n",
    "read_termination": "\n",
}


# GUI configuration
GUI_CONFIG: Dict[str, Any] = {
    "window_title": "PHYS 2150 J-V Characterization",
    "window_geometry": (100, 100, 800, 600),

    # Input panel width as fraction of screen
    "input_panel_width_fraction": 0.1,

    # Plot configuration
    "plot_figsize": (14, 14),
    "plot_dpi": 100,
    "plot_min_size": (525, 525),
    "plot_max_size": (700, 700),

    # Font sizes
    "font_sizes": {
        "label": 14,
        "button": 14,
        "input": 14,
        "plot_title": 10,
        "plot_axis": 10,
        "plot_tick": 8,
        "plot_legend": 10,
    },

    # Colors - colorblind-friendly palette
    "colors": {
        "forward_scan": "#0077BB",   # Blue
        "reverse_scan": "#EE7733",   # Orange
        "start_button": "#CCDDAA",   # Light green
        "stop_button": "#FFCCCC",    # Light red
    },
}


# Data export configuration
DATA_EXPORT_CONFIG: Dict[str, Any] = {
    "default_format": "csv",
    "csv_delimiter": ",",

    # Decimal precision for exported values
    "voltage_precision": 2,
    "current_precision": 5,

    # File naming template
    "date_format": "%Y_%m_%d",
    "file_template": "{date}_JV_cell{cell_number}_pixel{pixel_number}.csv",

    # CSV column headers
    "headers": {
        "voltage": "Voltage (V)",
        "forward_current": "Forward Scan (mA)",
        "reverse_current": "Reverse Scan (mA)",
    },
}


# Validation patterns
VALIDATION_PATTERNS: Dict[str, Any] = {
    # Cell number must be exactly 3 digits
    "cell_number": r'^\d{3}$',

    # Valid pixel range
    "pixel_range": (1, 8),

    # Voltage bounds (for physics-informed validation)
    "voltage_bounds": {
        "min_start": -1.0,    # V - extreme reverse bias limit
        "max_stop": 2.0,      # V - extreme forward bias limit
        "min_step": 0.001,    # V - minimum step size
        "max_step": 0.5,      # V - maximum step size
    },
}


# Error messages
ERROR_MESSAGES: Dict[str, str] = {
    "device_not_found": (
        "Keithley 2450 device not found. "
        "Please connect and power on the device and try again."
    ),
    "invalid_voltages": (
        "Please enter valid numerical values for voltages and step size."
    ),
    "invalid_cell_number": (
        "Cell number must be a 3-digit number (e.g., 195)."
    ),
    "invalid_pixel_number": (
        "Pixel number must be between 1 and 8."
    ),
    "measurement_failed": (
        "Measurement failed. Please check device connections."
    ),
    "file_save_failed": (
        "Failed to save file. Please check permissions and disk space."
    ),
}
