"""
Configuration constants and settings for the EQE measurement application.

All configuration values are loaded from defaults.json via the centralized
config loader. This module re-exports values for backward compatibility.

Enums (MeasurementType, DeviceType) remain in Python since they're used for
type-safe lookups in the codebase.

To customize values:
1. Edit defaults.json in the repo root (for permanent changes)
2. Or set PHYS2150_DISABLE_REMOTE_CONFIG=1 and edit defaults.json locally
"""

from enum import Enum
from typing import Dict, Any
from common.config.loader import eqe_config

# Application mode - this stays in Python (not configurable via JSON)
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


def _make_mutable_copy(value: Any) -> Any:
    """Create a mutable copy of config values (lists/dicts) to maintain backward compat."""
    if isinstance(value, dict):
        return {k: _make_mutable_copy(v) for k, v in value.items()}
    elif isinstance(value, list):
        return list(value)
    return value


# Default measurement parameters
DEFAULT_MEASUREMENT_PARAMS = _make_mutable_copy(eqe_config.defaults)

# Power measurement configuration
POWER_MEASUREMENT_CONFIG = _make_mutable_copy(eqe_config.power_measurement)

# Current measurement configuration
CURRENT_MEASUREMENT_CONFIG = _make_mutable_copy(eqe_config.current_measurement)

# Phase adjustment configuration
PHASE_ADJUSTMENT_CONFIG = _make_mutable_copy(eqe_config.phase_adjustment)

# Stability test configuration
STABILITY_TEST_CONFIG = _make_mutable_copy(eqe_config.stability_test)
# Convert list back to tuple for duration_range and interval_range (backward compat)
if "duration_range" in STABILITY_TEST_CONFIG:
    STABILITY_TEST_CONFIG["duration_range"] = tuple(STABILITY_TEST_CONFIG["duration_range"])
if "interval_range" in STABILITY_TEST_CONFIG:
    STABILITY_TEST_CONFIG["interval_range"] = tuple(STABILITY_TEST_CONFIG["interval_range"])

# Measurement quality thresholds
MEASUREMENT_QUALITY_THRESHOLDS = _make_mutable_copy(eqe_config.quality_thresholds)


def _build_device_configs() -> Dict[DeviceType, Dict[str, Any]]:
    """
    Build DEVICE_CONFIGS dict with DeviceType enum keys from JSON string keys.

    JSON uses string keys like "monochromator", but Python code expects
    DeviceType enum keys for type-safe lookups.
    """
    raw = eqe_config.devices_raw
    key_map = {
        "thorlabs_power_meter": DeviceType.THORLABS_POWER_METER,
        "monochromator": DeviceType.MONOCHROMATOR,
        "picoscope_lockin": DeviceType.PICOSCOPE_LOCKIN,
    }
    result = {}
    for str_key, config in raw.items():
        if str_key in key_map:
            # Make mutable copy and convert wavelength_range list to tuple if present
            config_copy = _make_mutable_copy(config)
            if "wavelength_range" in config_copy:
                config_copy["wavelength_range"] = tuple(config_copy["wavelength_range"])
            result[key_map[str_key]] = config_copy
    return result


# Device-specific configurations with DeviceType enum keys
DEVICE_CONFIGS = _build_device_configs()

# Filter wavelength thresholds
_filter_config = eqe_config.filter
FILTER_THRESHOLD_LOWER = _filter_config.get("threshold_lower", 420)
FILTER_THRESHOLD_UPPER = _filter_config.get("threshold_upper", 800)


def _build_filter_config() -> Dict[int, Dict[str, Any]]:
    """
    Build FILTER_CONFIG from JSON with computed wavelength ranges.

    The wavelength ranges are computed from thresholds rather than stored,
    maintaining the original logic that uses FILTER_THRESHOLD_LOWER/UPPER.
    """
    return {
        1: {"name": "400 nm filter", "wavelength_range": (FILTER_THRESHOLD_LOWER, FILTER_THRESHOLD_UPPER)},
        2: {"name": "780 nm filter", "wavelength_range": (FILTER_THRESHOLD_UPPER, float('inf'))},
        3: {"name": "no filter", "wavelength_range": (0, FILTER_THRESHOLD_LOWER)},
    }


# Filter wheel configuration
FILTER_CONFIG = _build_filter_config()

# Lock-in Lab visualization settings
LOCKINLAB_CONFIG = _make_mutable_copy(eqe_config.lockinlab)

# GUI configuration
GUI_CONFIG = _make_mutable_copy(eqe_config.gui)
# Convert lists to tuples where expected
if "window_size" in GUI_CONFIG:
    GUI_CONFIG["window_size"] = tuple(GUI_CONFIG["window_size"])
if "window_min_size" in GUI_CONFIG:
    GUI_CONFIG["window_min_size"] = tuple(GUI_CONFIG["window_min_size"])
if "plot_size" in GUI_CONFIG:
    GUI_CONFIG["plot_size"] = tuple(GUI_CONFIG["plot_size"])
if "plot_max_size" in GUI_CONFIG:
    GUI_CONFIG["plot_max_size"] = tuple(GUI_CONFIG["plot_max_size"])

# Data export configuration
DATA_EXPORT_CONFIG = _make_mutable_copy(eqe_config.export)

# Validation patterns
VALIDATION_PATTERNS = _make_mutable_copy(eqe_config.validation)
# Convert list to tuple for pixel_range
if "pixel_range" in VALIDATION_PATTERNS:
    VALIDATION_PATTERNS["pixel_range"] = tuple(VALIDATION_PATTERNS["pixel_range"])

# Error messages
ERROR_MESSAGES = _make_mutable_copy(eqe_config.error_messages)
