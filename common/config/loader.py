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


class ConfigurationError(Exception):
    """Raised when configuration cannot be loaded."""
    pass

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

    Raises ConfigurationError if no config source is available.

    Set PHYS2150_DISABLE_REMOTE_CONFIG=1 to skip remote config entirely.

    Args:
        timeout: Network timeout in seconds

    Returns:
        Full config dict

    Raises:
        ConfigurationError: If no configuration source is available
    """
    global _config_cache

    # Return cached if already loaded
    if _config_cache is not None:
        return _config_cache

    # Check if remote config is disabled
    if os.environ.get('PHYS2150_DISABLE_REMOTE_CONFIG'):
        _logger.info("Remote config disabled via PHYS2150_DISABLE_REMOTE_CONFIG")
        config = load_bundled_config()
        if not config:
            raise ConfigurationError(
                "No configuration available. Bundled defaults.json not found."
            )
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
                raise ConfigurationError(
                    "No configuration available. Check that defaults.json exists."
                )

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
    Requires defaults.json to be available (no hardcoded fallbacks).
    """

    @staticmethod
    def _get_jv() -> Dict[str, Any]:
        """Get the jv section of config."""
        return get_config()["jv"]

    @property
    def defaults(self) -> Dict[str, Any]:
        """Default measurement parameters for GUI initialization."""
        return self._get_jv()["defaults"]

    @property
    def measurement(self) -> Dict[str, Any]:
        """JV measurement timing and acquisition parameters."""
        return self._get_jv()["measurement"]

    @property
    def stability_test(self) -> Dict[str, Any]:
        """JV stability test parameters."""
        return self._get_jv()["stability_test"]

    @property
    def quality_thresholds(self) -> Dict[str, float]:
        """SEM% thresholds for measurement quality assessment."""
        return self._get_jv()["quality_thresholds"]

    @property
    def device(self) -> Dict[str, Any]:
        """Keithley 2450 device configuration."""
        return self._get_jv()["device"]

    @property
    def gui(self) -> Dict[str, Any]:
        """GUI appearance and behavior settings."""
        return self._get_jv()["gui"]

    @property
    def export(self) -> Dict[str, Any]:
        """Data export settings."""
        return self._get_jv()["export"]

    @property
    def validation(self) -> Dict[str, Any]:
        """Input validation patterns."""
        return self._get_jv()["validation"]

    @property
    def error_messages(self) -> Dict[str, str]:
        """User-facing error messages."""
        return self._get_jv()["error_messages"]


class EQEConfig:
    """
    Type-safe accessor for EQE configuration values.

    All properties lazily load from the singleton config cache.
    Requires defaults.json to be available (no hardcoded fallbacks).
    """

    @staticmethod
    def _get_eqe() -> Dict[str, Any]:
        """Get the eqe section of config."""
        return get_config()["eqe"]

    @property
    def defaults(self) -> Dict[str, Any]:
        """Default measurement parameters for GUI initialization."""
        return self._get_eqe()["defaults"]

    @property
    def power_measurement(self) -> Dict[str, Any]:
        """Power measurement parameters."""
        return self._get_eqe()["power_measurement"]

    @property
    def current_measurement(self) -> Dict[str, Any]:
        """Current measurement parameters."""
        return self._get_eqe()["current_measurement"]

    @property
    def phase_adjustment(self) -> Dict[str, Any]:
        """Phase adjustment parameters."""
        return self._get_eqe()["phase_adjustment"]

    @property
    def stability_test(self) -> Dict[str, Any]:
        """EQE stability test parameters."""
        return self._get_eqe()["stability_test"]

    @property
    def quality_thresholds(self) -> Dict[str, Any]:
        """SEM% thresholds for measurement quality assessment."""
        return self._get_eqe()["quality_thresholds"]

    @property
    def devices_raw(self) -> Dict[str, Any]:
        """Device configurations with string keys."""
        return self._get_eqe()["devices"]

    @property
    def filter(self) -> Dict[str, Any]:
        """Filter wheel configuration."""
        return self._get_eqe()["filter"]

    @property
    def filter_threshold_lower(self) -> int:
        """Lower filter threshold wavelength (nm)."""
        return self.filter["threshold_lower"]

    @property
    def filter_threshold_upper(self) -> int:
        """Upper filter threshold wavelength (nm)."""
        return self.filter["threshold_upper"]

    @property
    def lockinlab(self) -> Dict[str, Any]:
        """Lock-in Lab visualization settings."""
        return self._get_eqe()["lockinlab"]

    @property
    def gui(self) -> Dict[str, Any]:
        """GUI appearance and behavior settings."""
        return self._get_eqe()["gui"]

    @property
    def export(self) -> Dict[str, Any]:
        """Data export settings."""
        return self._get_eqe()["export"]

    @property
    def validation(self) -> Dict[str, Any]:
        """Input validation patterns."""
        return self._get_eqe()["validation"]

    @property
    def error_messages(self) -> Dict[str, str]:
        """User-facing error messages."""
        return self._get_eqe()["error_messages"]


# Singleton instances for convenience
jv_config = JVConfig()
eqe_config = EQEConfig()
