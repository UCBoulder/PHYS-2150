"""
Configuration constants and settings for the JV measurement application.

All configuration values are loaded from defaults.json via the centralized
config loader. This module re-exports values for backward compatibility.

To customize values:
1. Edit defaults.json in the repo root (for permanent changes)
2. Or set PHYS2150_DISABLE_REMOTE_CONFIG=1 and edit defaults.json locally
"""

from typing import Dict, Any
from common.config.loader import jv_config

# Application mode - this stays in Python (not configurable via JSON)
OFFLINE_MODE = False  # Set to True to run without hardware (for GUI testing)


# Re-export configuration values for backward compatibility
# All existing imports like `from jv.config.settings import DEFAULT_MEASUREMENT_PARAMS` still work

def _make_mutable_copy(value: Any) -> Any:
    """Create a mutable copy of config values (lists/dicts) to maintain backward compat."""
    if isinstance(value, dict):
        return {k: _make_mutable_copy(v) for k, v in value.items()}
    elif isinstance(value, list):
        return list(value)
    return value


# Default measurement parameters
DEFAULT_MEASUREMENT_PARAMS: Dict[str, Any] = _make_mutable_copy(jv_config.defaults)

# J-V measurement configuration
JV_MEASUREMENT_CONFIG: Dict[str, Any] = _make_mutable_copy(jv_config.measurement)

# J-V Stability Test configuration
JV_STABILITY_TEST_CONFIG: Dict[str, Any] = _make_mutable_copy(jv_config.stability_test)
# Convert list back to tuple for duration_range and interval_range (backward compat)
if "duration_range" in JV_STABILITY_TEST_CONFIG:
    JV_STABILITY_TEST_CONFIG["duration_range"] = tuple(JV_STABILITY_TEST_CONFIG["duration_range"])
if "interval_range" in JV_STABILITY_TEST_CONFIG:
    JV_STABILITY_TEST_CONFIG["interval_range"] = tuple(JV_STABILITY_TEST_CONFIG["interval_range"])

# Measurement quality thresholds
JV_QUALITY_THRESHOLDS: Dict[str, Any] = _make_mutable_copy(jv_config.quality_thresholds)

# Keithley 2450 device configuration
DEVICE_CONFIG: Dict[str, Any] = _make_mutable_copy(jv_config.device)

# GUI configuration
GUI_CONFIG: Dict[str, Any] = _make_mutable_copy(jv_config.gui)
# Convert lists to tuples where expected
if "window_size" in GUI_CONFIG:
    GUI_CONFIG["window_size"] = tuple(GUI_CONFIG["window_size"])
if "window_min_size" in GUI_CONFIG:
    GUI_CONFIG["window_min_size"] = tuple(GUI_CONFIG["window_min_size"])
if "plot_figsize" in GUI_CONFIG:
    GUI_CONFIG["plot_figsize"] = tuple(GUI_CONFIG["plot_figsize"])
if "plot_min_size" in GUI_CONFIG:
    GUI_CONFIG["plot_min_size"] = tuple(GUI_CONFIG["plot_min_size"])
if "plot_max_size" in GUI_CONFIG:
    GUI_CONFIG["plot_max_size"] = tuple(GUI_CONFIG["plot_max_size"])

# Data export configuration
DATA_EXPORT_CONFIG: Dict[str, Any] = _make_mutable_copy(jv_config.export)

# Validation patterns
VALIDATION_PATTERNS: Dict[str, Any] = _make_mutable_copy(jv_config.validation)
# Convert list to tuple for pixel_range
if "pixel_range" in VALIDATION_PATTERNS:
    VALIDATION_PATTERNS["pixel_range"] = tuple(VALIDATION_PATTERNS["pixel_range"])

# Error messages
ERROR_MESSAGES: Dict[str, str] = _make_mutable_copy(jv_config.error_messages)
