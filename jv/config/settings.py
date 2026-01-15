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
    # Number of current measurements per voltage point
    # Multiple measurements allow calculation of statistics (mean, std_dev, SEM%)
    # Using trace buffer for efficient multi-reading acquisition (minimum 10 per Keithley spec)
    "num_measurements": 10,

    # Device-native source delay after setting voltage (seconds)
    # This replaces Python time.sleep() for more precise timing
    # Set to 0 for auto-delay (device determines optimal settling time)
    # Typical values: 0.01-0.05s for fast scans, 0.1-0.5s for precision
    "source_delay_s": 0.05,

    # Integration time as Number of Power Line Cycles (NPLC)
    # Higher NPLC = longer integration = lower noise but slower
    # At 60 Hz: NPLC 1 = 16.7ms, NPLC 0.1 = 1.67ms, NPLC 10 = 167ms
    # Recommended: 1.0 for balance, 0.1 for speed, 10 for precision
    "nplc": 1.0,

    # Device averaging is disabled (set to 1) when using trace buffer
    # We take multiple individual readings instead to get statistics
    "averaging_count": 1,

    # Averaging filter type (unused when averaging_count=1)
    "averaging_filter": "REPEAT",

    # Initial stabilization time at start voltage before sweep begins
    "initial_stabilization_s": 2.0,

    # Pause time between forward and reverse sweeps
    "inter_sweep_delay_s": 2.0,

    # Plot update frequency (update every N points)
    "plot_update_interval": 1,

    # Current measurement range (Amps)
    "current_range": 10,  # mA scale for typical solar cells

    # Voltage source range (Volts)
    "voltage_range": 2,

    # Current compliance limit (Amps)
    "current_compliance": 1,

    # Enable 4-wire (remote) sensing for accurate measurements
    "remote_sensing": True,

    # Precision settings for data rounding
    "voltage_decimals": 2,              # Decimal places for voltage array rounding
    "current_quantize_precision": "0.00001",  # Decimal precision string for Decimal quantization (mA)
}


# J-V Stability Test configuration
# Voltage stability testing at a fixed voltage over time
JV_STABILITY_TEST_CONFIG: Dict[str, Any] = {
    # UI defaults
    "default_target_voltage": 0.5,     # V - typical operating voltage
    "default_duration_min": 5,          # minutes - default test duration
    "duration_range": (1, 60),          # minutes - valid range (min, max)
    "default_interval_sec": 2,          # seconds - default measurement interval
    "interval_range": (0.5, 60),        # seconds - valid range (min, max)

    # Sweep parameters (start → target)
    "sweep_start_voltage": -0.2,        # V - starting voltage before sweeping to target
    "sweep_step_voltage": 0.05,         # V - step size during sweep to target
    "sweep_delay_s": 0.1,               # seconds - delay between sweep steps

    # Stabilization times
    "initial_stabilization_s": 2.0,     # seconds - wait at start voltage before sweep
    "target_stabilization_s": 2.0,      # seconds - wait at target voltage before measurements

    # Measurement configuration (reuse from JV_MEASUREMENT_CONFIG)
    "num_measurements": 10,             # Number of current measurements per point (min 10 per Keithley spec)
    "nplc": 1.0,                        # Integration time (NPLC)
    "averaging_count": 1,               # Device averaging (1 = use trace buffer instead)
    "averaging_filter": "REPEAT",       # Filter type (unused when averaging_count=1)
    "source_delay_s": 0.05,             # Device-native source delay

    # Device configuration (same as regular measurement)
    "current_range": 10,                # mA scale
    "voltage_range": 2,                 # V range
    "current_compliance": 1,            # A compliance limit
    "remote_sensing": True,             # 4-wire sensing
}

# Measurement quality thresholds based on SEM% (standard error of mean as % of mean)
# J-V measurements have different characteristics than EQE:
# - Continuous DC measurement (no chopping/lock-in)
# - Very low noise floor with Keithley 2450
# - Current varies over orders of magnitude across voltage sweep
JV_QUALITY_THRESHOLDS: Dict[str, Any] = {
    "excellent": 0.1,    # SEM% < 0.1% - excellent precision
    "good": 0.5,         # SEM% < 0.5% - good for most measurements
    "fair": 2.0,         # SEM% < 2% - acceptable for low-current regions
    # SEM% >= 2% = "Check measurement"
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
    "window_size": (1200, 800),        # pixels (width, height) - initial window dimensions
    "window_min_size": (800, 600),     # pixels - minimum window dimensions

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
    "file_template": "{date}_IV_cell{cell_number}_pixel{pixel_number}.csv",

    # CSV column headers for grouped format (voltage, forward, reverse columns)
    "headers": {
        "voltage": "Voltage (V)",
        "forward_current": "Forward Scan (mA)",
        "reverse_current": "Reverse Scan (mA)",
    },
    # CSV column headers for raw/sequential format (direction column)
    "headers_raw": {
        "direction": "Direction",
        "voltage": "Voltage (V)",
        "current": "Current (mA)",
    },

    # Stability test file naming and headers
    "stability_file_template": "{date}_stability_cell{cell_number}_pixel{pixel_number}_{voltage}V.csv",
    "headers_stability": {
        "timestamp": "Timestamp (s)",
        "voltage": "Voltage (V)",
        "current": "Current (mA)",
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
        "Pixel number must be between {min} and {max}."
    ),
    "measurement_failed": (
        "Measurement failed. Please check device connections."
    ),
    "file_save_failed": (
        "Failed to save file. Please check permissions and disk space."
    ),
}
