"""
Remote configuration loader.

Fetches config from GitHub, caches locally, merges with built-in defaults.
This allows updating default parameters (scan settings, cell naming conventions)
by editing a file in the GitHub repo without rebuilding the application.
"""
import json
import logging
import os
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional, Dict, Any

_logger = logging.getLogger(__name__)

# GitHub raw URL for remote config
REMOTE_CONFIG_URL = "https://raw.githubusercontent.com/UCBoulder/PHYS-2150/main/remote-defaults.json"


def get_cache_path() -> Path:
    """
    Get path for cached remote config.

    Tries app directory first (works for installed exe),
    falls back to user's home if app dir not writable.
    """
    # Try app directory first (works for installed exe)
    app_dir = Path(__file__).parent.parent.parent
    cache_dir = app_dir / ".config-cache"

    # Fall back to user's home if app dir not writable
    if not os.access(app_dir, os.W_OK):
        cache_dir = Path.home() / ".phys2150" / "cache"

    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir / "remote-defaults.json"


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
        with urllib.request.urlopen(req, timeout=timeout) as response:
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
        _logger.debug(f"Cached remote config to {cache_path}")
    except IOError as e:
        _logger.warning(f"Failed to cache config: {e}")


def deep_merge(base: Dict, override: Dict) -> Dict:
    """
    Deep merge override dict into base dict.

    Args:
        base: Base dictionary
        override: Dictionary with values to override

    Returns:
        New merged dictionary (base is not modified)
    """
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def get_remote_config(app: str, timeout: float = 5.0) -> Dict[str, Any]:
    """
    Get remote config for an app, with fallback chain.

    Fallback order:
    1. Fresh fetch from GitHub
    2. Cached config from local file
    3. Empty dict (use built-in defaults only)

    Args:
        app: 'jv' or 'eqe'
        timeout: Network timeout in seconds

    Returns:
        Config dict for the app (empty dict if no remote config available)
    """
    # Try to fetch fresh config
    remote = fetch_remote_config(timeout)

    if remote:
        save_to_cache(remote)
    else:
        # Fall back to cached config
        remote = load_cached_config()
        if remote:
            _logger.info("Using cached remote config")

    if remote and app in remote:
        return remote[app]

    return {}
