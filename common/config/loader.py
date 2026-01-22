"""
Centralized configuration loader.

Loads ALL configuration from defaults.json with fallback chain:
1. Fresh fetch from GitHub (5 sec timeout)
2. Local cache (~/.phys2150/cache/)
3. Bundled copy (packaged with exe)

This module replaces the distributed settings.py approach with a single
JSON file as the source of truth.

To disable remote config during development, set environment variable:
    PHYS2150_DISABLE_REMOTE_CONFIG=1
"""

import json
import logging
import os
import ssl
import sys
import urllib.request
import urllib.error
from pathlib import Path
from typing import Any, Dict, Optional

_logger = logging.getLogger(__name__)

# Use certifi for SSL certificates (required for PyInstaller frozen builds)
try:
    import certifi
    _SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    _SSL_CONTEXT = None

# GitHub raw URL for remote config
REMOTE_CONFIG_URL = "https://raw.githubusercontent.com/UCBoulder/PHYS-2150/main/defaults.json"

# Singleton cache for loaded config
_config_cache: Optional[Dict[str, Any]] = None


def get_cache_path() -> Path:
    """
    Get path for cached remote config.

    Uses user's home directory for cache (works reliably on all systems).
    """
    cache_dir = Path.home() / ".phys2150" / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir / "defaults.json"


def get_bundled_path() -> Path:
    """
    Get path to bundled defaults.json.

    In development: repo root
    In frozen app: alongside the executable in the data directory
    """
    if getattr(sys, 'frozen', False):
        # Running as PyInstaller bundle
        # _MEIPASS is the temp directory where PyInstaller extracts files
        base = Path(sys._MEIPASS)
    else:
        # Running from source - find repo root
        base = Path(__file__).parent.parent.parent

    return base / "defaults.json"


def fetch_remote_config(timeout: float = 5.0) -> Optional[Dict[str, Any]]:
    """
    Fetch config from GitHub.

    Args:
        timeout: Network timeout in seconds

    Returns:
        Config dict if successful, None on failure
    """
    try:
        req = urllib.request.Request(
            REMOTE_CONFIG_URL,
            headers={'User-Agent': 'PHYS2150-Lab-App'}
        )
        with urllib.request.urlopen(req, timeout=timeout, context=_SSL_CONTEXT) as response:
            data = json.loads(response.read().decode('utf-8'))
            _logger.info(f"Fetched remote config version: {data.get('version', 'unknown')}")
            return data
    except urllib.error.URLError as e:
        _logger.warning(f"Failed to fetch remote config (network): {e}")
        return None
    except json.JSONDecodeError as e:
        _logger.warning(f"Failed to parse remote config (invalid JSON): {e}")
        return None
    except TimeoutError:
        _logger.warning("Failed to fetch remote config (timeout)")
        return None
    except Exception as e:
        _logger.warning(f"Failed to fetch remote config: {e}")
        return None


def load_cached_config() -> Optional[Dict[str, Any]]:
    """
    Load config from local cache.

    Returns:
        Cached config dict if available, None otherwise
    """
    cache_path = get_cache_path()
    if cache_path.exists():
        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                _logger.debug(f"Loaded cached config version: {data.get('version', 'unknown')}")
                return data
        except json.JSONDecodeError as e:
            _logger.warning(f"Failed to parse cached config: {e}")
        except IOError as e:
            _logger.warning(f"Failed to read cached config: {e}")
    return None


def load_bundled_config() -> Optional[Dict[str, Any]]:
    """
    Load config from bundled defaults.json.

    Returns:
        Bundled config dict if available, None otherwise
    """
    bundled_path = get_bundled_path()
    if bundled_path.exists():
        try:
            with open(bundled_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                _logger.debug(f"Loaded bundled config version: {data.get('version', 'unknown')}")
                return data
        except json.JSONDecodeError as e:
            _logger.warning(f"Failed to parse bundled config: {e}")
        except IOError as e:
            _logger.warning(f"Failed to read bundled config: {e}")
    return None


def save_to_cache(config: Dict[str, Any]) -> None:
    """
    Save config to local cache.

    Args:
        config: Config dict to cache
    """
    try:
        cache_path = get_cache_path()
        with open(cache_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2)
        _logger.debug(f"Cached config to {cache_path}")
    except IOError as e:
        _logger.warning(f"Failed to cache config: {e}")


def load_full_config(timeout: float = 5.0) -> Dict[str, Any]:
    """
    Load full config with fallback chain.

    Fallback order:
    1. Fresh fetch from GitHub
    2. Cached config from local file
    3. Bundled config (packaged with exe)
    4. Empty dict (use hardcoded defaults)

    Set PHYS2150_DISABLE_REMOTE_CONFIG=1 to skip remote config entirely.

    Args:
        timeout: Network timeout in seconds

    Returns:
        Full config dict
    """
    global _config_cache

    # Return cached if already loaded
    if _config_cache is not None:
        return _config_cache

    # Check if remote config is disabled
    if os.environ.get('PHYS2150_DISABLE_REMOTE_CONFIG'):
        _logger.info("Remote config disabled via PHYS2150_DISABLE_REMOTE_CONFIG")
        # Still try bundled for local defaults
        config = load_bundled_config() or {}
        _config_cache = config
        return config

    # Try fresh fetch first
    config = fetch_remote_config(timeout)

    if config:
        save_to_cache(config)
    else:
        # Fall back to cache
        config = load_cached_config()
        if config:
            _logger.info("Using cached remote config")
        else:
            # Fall back to bundled
            config = load_bundled_config()
            if config:
                _logger.info("Using bundled config")
            else:
                _logger.warning("No config available - using empty defaults")
                config = {}

    _config_cache = config
    return config


def get_config() -> Dict[str, Any]:
    """
    Get the full configuration dict.

    Loads config on first call, returns cached copy on subsequent calls.

    Returns:
        Full config dict
    """
    return load_full_config()


def reload_config() -> Dict[str, Any]:
    """
    Force reload config from source (useful for testing).

    Returns:
        Freshly loaded config dict
    """
    global _config_cache
    _config_cache = None
    return load_full_config()


class JVConfig:
    """
    Type-safe accessor for JV configuration values.

    All properties lazily load from the singleton config cache.
    Provides backward-compatible access to all JV settings.
    """

    @staticmethod
    def _get_jv() -> Dict[str, Any]:
        """Get the jv section of config."""
        return get_config().get("jv", {})

    # Default measurement parameters
    @property
    def defaults(self) -> Dict[str, Any]:
        """Default measurement parameters for GUI initialization."""
        return self._get_jv().get("defaults", {
            "start_voltage": -0.2,
            "stop_voltage": 1.5,
            "step_voltage": 0.02,
            "cell_number": "",
            "pixel_number": 1,
        })

    # Measurement configuration
    @property
    def measurement(self) -> Dict[str, Any]:
        """JV measurement timing and acquisition parameters."""
        return self._get_jv().get("measurement", {
            "num_measurements": 10,
            "source_delay_s": 0.05,
            "nplc": 1.0,
            "averaging_count": 1,
            "averaging_filter": "REPEAT",
            "initial_stabilization_s": 2.0,
            "inter_sweep_delay_s": 2.0,
            "plot_update_interval": 1,
            "current_range": 10,
            "voltage_range": 2,
            "current_compliance": 1,
            "remote_sensing": True,
            "voltage_decimals": 2,
            "current_quantize_precision": "0.00001",
        })

    # Stability test configuration
    @property
    def stability_test(self) -> Dict[str, Any]:
        """JV stability test parameters."""
        return self._get_jv().get("stability_test", {
            "default_target_voltage": 0.5,
            "default_duration_min": 5,
            "duration_range": [1, 60],
            "default_interval_sec": 2,
            "interval_range": [0.5, 60],
            "target_stabilization_s": 5.0,
            "num_measurements": 10,
            "nplc": 1.0,
            "averaging_count": 1,
            "averaging_filter": "REPEAT",
            "source_delay_s": 0.05,
            "current_range": 10,
            "voltage_range": 2,
            "current_compliance": 1,
            "remote_sensing": True,
        })

    # Quality thresholds
    @property
    def quality_thresholds(self) -> Dict[str, float]:
        """SEM% thresholds for measurement quality assessment."""
        return self._get_jv().get("quality_thresholds", {
            "excellent": 0.1,
            "good": 0.5,
            "fair": 2.0,
        })

    # Device configuration
    @property
    def device(self) -> Dict[str, Any]:
        """Keithley 2450 device configuration."""
        return self._get_jv().get("device", {
            "timeout_ms": 30000,
            "usb_id_pattern": "USB0::0x05E6::0x2450",
            "write_termination": "\n",
            "read_termination": "\n",
        })

    # GUI configuration
    @property
    def gui(self) -> Dict[str, Any]:
        """GUI appearance and behavior settings."""
        return self._get_jv().get("gui", {
            "window_title": "PHYS 2150 J-V Characterization",
            "window_size": [1200, 800],
            "window_min_size": [800, 600],
            "input_panel_width_fraction": 0.1,
            "plot_figsize": [14, 14],
            "plot_dpi": 100,
            "plot_min_size": [525, 525],
            "plot_max_size": [700, 700],
            "font_sizes": {
                "label": 14,
                "button": 14,
                "input": 14,
                "plot_title": 10,
                "plot_axis": 10,
                "plot_tick": 8,
                "plot_legend": 10,
            },
            "colors": {
                "forward_scan": "#0077BB",
                "reverse_scan": "#EE7733",
                "start_button": "#CCDDAA",
                "stop_button": "#FFCCCC",
            },
        })

    # Export configuration
    @property
    def export(self) -> Dict[str, Any]:
        """Data export settings."""
        return self._get_jv().get("export", {
            "default_format": "csv",
            "csv_delimiter": ",",
            "voltage_precision": 2,
            "current_precision": 5,
            "date_format": "%Y_%m_%d",
            "file_template": "{date}_IV_cell{cell_number}_pixel{pixel_number}.csv",
            "headers": {
                "voltage": "Voltage (V)",
                "forward_current": "Forward Scan (mA)",
                "forward_std": "Forward Std (mA)",
                "forward_n": "Forward n",
                "reverse_current": "Reverse Scan (mA)",
                "reverse_std": "Reverse Std (mA)",
                "reverse_n": "Reverse n",
            },
            "headers_raw": {
                "direction": "Direction",
                "voltage": "Voltage (V)",
                "current": "Current (mA)",
                "std": "Std (mA)",
                "n": "n",
            },
            "stability_file_template": "{date}_IV_stability_cell{cell_number}_pixel{pixel_number}.csv",
            "headers_stability": {
                "timestamp": "Timestamp (s)",
                "voltage": "Voltage (V)",
                "current": "Current (mA)",
            },
        })

    # Validation patterns
    @property
    def validation(self) -> Dict[str, Any]:
        """Input validation patterns."""
        return self._get_jv().get("validation", {
            "cell_number": r'^[A-Z]\d{2}$',
            "pixel_range": [1, 8],
            "voltage_bounds": {
                "min_start": -1.0,
                "max_stop": 2.0,
                "min_step": 0.001,
                "max_step": 0.5,
            },
        })

    # Error messages
    @property
    def error_messages(self) -> Dict[str, str]:
        """User-facing error messages."""
        return self._get_jv().get("error_messages", {
            "device_not_found": (
                "Keithley 2450 device not found. "
                "Please connect and power on the device and try again."
            ),
            "invalid_voltages": (
                "Please enter valid numerical values for voltages and step size."
            ),
            "invalid_cell_number": (
                "Cell number must be a letter + 2 digits (e.g., A03, R26)."
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
        })


class EQEConfig:
    """
    Type-safe accessor for EQE configuration values.

    All properties lazily load from the singleton config cache.
    Provides backward-compatible access to all EQE settings.
    """

    @staticmethod
    def _get_eqe() -> Dict[str, Any]:
        """Get the eqe section of config."""
        return get_config().get("eqe", {})

    # Default measurement parameters
    @property
    def defaults(self) -> Dict[str, Any]:
        """Default measurement parameters for GUI initialization."""
        return self._get_eqe().get("defaults", {
            "start_wavelength": 350.0,
            "end_wavelength": 720.0,
            "step_size": 10.0,
            "cell_number": "",
            "pixel_number": 1,
        })

    # Power measurement configuration
    @property
    def power_measurement(self) -> Dict[str, Any]:
        """Power measurement parameters."""
        return self._get_eqe().get("power_measurement", {
            "num_measurements": 200,
            "correction_factor": 2.0,
            "stabilization_time": 0.2,
        })

    # Current measurement configuration
    @property
    def current_measurement(self) -> Dict[str, Any]:
        """Current measurement parameters."""
        return self._get_eqe().get("current_measurement", {
            "num_measurements": 5,
            "transimpedance_gain": 1e-6,
            "stabilization_time": 0.2,
            "initial_stabilization_time": 1.0,
        })

    # Phase adjustment configuration
    @property
    def phase_adjustment(self) -> Dict[str, Any]:
        """Phase adjustment parameters."""
        return self._get_eqe().get("phase_adjustment", {
            "alignment_wavelength": 532,
            "min_r_squared": 0.90,
            "num_visualization_points": 37,
            "stabilization_time": 1.0,
        })

    # Stability test configuration
    @property
    def stability_test(self) -> Dict[str, Any]:
        """EQE stability test parameters."""
        return self._get_eqe().get("stability_test", {
            "initial_stabilization_time": 2.0,
            "outlier_rejection_std": 2.0,
            "default_wavelength": 550,
            "default_duration_min": 5,
            "duration_range": [1, 60],
            "default_interval_sec": 2,
            "interval_range": [1, 60],
        })

    # Quality thresholds
    @property
    def quality_thresholds(self) -> Dict[str, Any]:
        """SEM% thresholds for measurement quality assessment."""
        return self._get_eqe().get("quality_thresholds", {
            "power": {
                "excellent": 1.5,
                "good": 2.5,
                "fair": 4.0,
                "low_signal_threshold": None,
            },
            "current": {
                "excellent": 0.5,
                "good": 2.0,
                "fair": 15.0,
                "low_signal_threshold": 5e-9,
            }
        })

    # Device configurations (raw - for string key access)
    @property
    def devices_raw(self) -> Dict[str, Any]:
        """Device configurations with string keys."""
        return self._get_eqe().get("devices", {
            "thorlabs_power_meter": {"timeout": 5.0},
            "monochromator": {
                "interface": "usb",
                "timeout_msec": 29000,
                "grating_wavelength_threshold": 685,
                "wavelength_range": [200, 1200],
            },
            "picoscope_lockin": {
                "default_chopper_freq": 81,
                "chopper_freq_tolerance": 0.15,
                "min_reference_amplitude": 1.0,
                "default_num_cycles": 12,
                "fast_measurement_cycles": 5,
                "num_measurements": 5,
                "saturation_threshold_v": 0.95,
                "signal_quality_reference_v": 0.1,
                "correction_factor": 0.5,
            }
        })

    # Filter configuration
    @property
    def filter(self) -> Dict[str, Any]:
        """Filter wheel configuration."""
        return self._get_eqe().get("filter", {
            "threshold_lower": 420,
            "threshold_upper": 800,
            "positions": {
                "1": {"name": "400 nm filter"},
                "2": {"name": "780 nm filter"},
                "3": {"name": "no filter"},
            }
        })

    @property
    def filter_threshold_lower(self) -> int:
        """Lower filter threshold wavelength (nm)."""
        return self.filter.get("threshold_lower", 420)

    @property
    def filter_threshold_upper(self) -> int:
        """Upper filter threshold wavelength (nm)."""
        return self.filter.get("threshold_upper", 800)

    # Lock-in Lab configuration
    @property
    def lockinlab(self) -> Dict[str, Any]:
        """Lock-in Lab visualization settings."""
        return self._get_eqe().get("lockinlab", {
            "waveform_display_points": 10000,
            "fft_max_frequency": 200,
        })

    # GUI configuration
    @property
    def gui(self) -> Dict[str, Any]:
        """GUI appearance and behavior settings."""
        return self._get_eqe().get("gui", {
            "window_title": "PHYS 2150 EQE Measurement - MVC Architecture",
            "window_size": [1400, 750],
            "window_min_size": [1000, 600],
            "plot_size": [300, 300],
            "plot_max_size": [400, 400],
            "live_monitor_interval_ms": 500,
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
            },
            "prompt_phase_data_save": False,
        })

    # Export configuration
    @property
    def export(self) -> Dict[str, Any]:
        """Data export settings."""
        return self._get_eqe().get("export", {
            "default_format": "csv",
            "csv_delimiter": ",",
            "precision": 6,
            "include_measurement_stats": True,
            "date_format": "%Y_%m_%d",
            "power_file_template": "{date}_power_cell{cell_number}.csv",
            "current_file_template": "{date}_current_cell{cell_number}_pixel{pixel_number}.csv",
            "phase_file_template": "{date}_phase_cell{cell_number}.csv",
            "headers": {
                "power": ["Wavelength (nm)", "Power (uW)"],
                "power_with_stats": ["Wavelength (nm)", "Power_mean (uW)", "Power_std (uW)", "n"],
                "current": ["Wavelength (nm)", "Current (nA)"],
                "current_with_stats": ["Wavelength (nm)", "Current_mean (nA)", "Current_std (nA)", "n"],
                "phase": ["Pixel #", "Set Angle", "Signal", "R^2 Value"],
            }
        })

    # Validation patterns
    @property
    def validation(self) -> Dict[str, Any]:
        """Input validation patterns."""
        return self._get_eqe().get("validation", {
            "cell_number": r'^[A-Z]\d{2}$',
            "pixel_range": [1, 8],
        })

    # Error messages
    @property
    def error_messages(self) -> Dict[str, str]:
        """User-facing error messages."""
        return self._get_eqe().get("error_messages", {
            "device_not_found": "Device not found. Please check the connection.",
            "invalid_cell_number": "Cell number must be a letter + 2 digits (e.g., A03, R26).",
            "invalid_pixel_number": "Pixel number must be between {min} and {max}.",
            "measurement_failed": "Measurement failed. Please check device connections.",
            "file_save_failed": "Failed to save file. Please check permissions and disk space.",
            "low_r_squared": "Is the lamp on? If it is, pixel {pixel} might be dead. Check in with a TA.",
        })


# Singleton instances for convenience
jv_config = JVConfig()
eqe_config = EQEConfig()
