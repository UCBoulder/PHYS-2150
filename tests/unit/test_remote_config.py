"""
Tests for remote configuration loading and caching.

These tests verify that:
1. Fresh fetch takes precedence over cache
2. Cache is updated after successful fetch
3. Fetch failure falls back to cache
4. Version tracking helps diagnose config source
"""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
import urllib.error

import pytest

from common.utils.remote_config import (
    fetch_remote_config,
    load_cached_config,
    save_to_cache,
    get_remote_config,
    get_cache_path,
    deep_merge,
    diagnose_config,
)


class TestDeepMerge:
    """Tests for the deep_merge function."""

    def test_shallow_merge(self):
        """Test merging flat dictionaries."""
        base = {"a": 1, "b": 2}
        override = {"b": 3, "c": 4}
        result = deep_merge(base, override)
        assert result == {"a": 1, "b": 3, "c": 4}

    def test_deep_merge_nested(self):
        """Test merging nested dictionaries."""
        base = {"defaults": {"start": 350, "end": 750}, "validation": {"pattern": "old"}}
        override = {"defaults": {"end": 720}}
        result = deep_merge(base, override)
        assert result["defaults"]["start"] == 350  # preserved
        assert result["defaults"]["end"] == 720   # overridden
        assert result["validation"]["pattern"] == "old"  # preserved

    def test_base_not_modified(self):
        """Test that base dict is not modified."""
        base = {"a": 1}
        override = {"a": 2}
        deep_merge(base, override)
        assert base["a"] == 1


class TestCacheOperations:
    """Tests for cache read/write operations."""

    def test_save_and_load_cache(self, tmp_path, monkeypatch):
        """Test that saved config can be loaded back."""
        cache_file = tmp_path / "cache" / "remote-defaults.json"
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr(
            "common.utils.remote_config.get_cache_path",
            lambda: cache_file
        )

        test_config = {"version": "test", "eqe": {"defaults": {"end_wavelength": 720}}}
        save_to_cache(test_config)

        loaded = load_cached_config()
        assert loaded == test_config

    def test_load_nonexistent_cache_returns_none(self, tmp_path, monkeypatch):
        """Test that loading from nonexistent cache returns None."""
        cache_file = tmp_path / "nonexistent" / "remote-defaults.json"
        monkeypatch.setattr(
            "common.utils.remote_config.get_cache_path",
            lambda: cache_file
        )

        result = load_cached_config()
        assert result is None

    def test_load_invalid_json_cache_returns_none(self, tmp_path, monkeypatch):
        """Test that invalid JSON in cache returns None."""
        cache_file = tmp_path / "cache" / "remote-defaults.json"
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        cache_file.write_text("not valid json {{{")

        monkeypatch.setattr(
            "common.utils.remote_config.get_cache_path",
            lambda: cache_file
        )

        result = load_cached_config()
        assert result is None


class TestFetchRemoteConfig:
    """Tests for fetching config from GitHub."""

    def test_fetch_success_returns_dict(self):
        """Test successful fetch returns parsed JSON."""
        mock_response = MagicMock()
        mock_response.read.return_value = b'{"version": "test", "eqe": {}}'
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_response):
            result = fetch_remote_config(timeout=1.0)

        assert result == {"version": "test", "eqe": {}}

    def test_fetch_network_error_returns_none(self):
        """Test network error returns None."""
        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("Network error")):
            result = fetch_remote_config(timeout=1.0)

        assert result is None

    def test_fetch_timeout_returns_none(self):
        """Test timeout returns None."""
        with patch("urllib.request.urlopen", side_effect=TimeoutError()):
            result = fetch_remote_config(timeout=1.0)

        assert result is None

    def test_fetch_invalid_json_returns_none(self):
        """Test invalid JSON response returns None."""
        mock_response = MagicMock()
        mock_response.read.return_value = b'not valid json'
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_response):
            result = fetch_remote_config(timeout=1.0)

        assert result is None


class TestGetRemoteConfig:
    """Tests for the main get_remote_config function."""

    def test_fresh_fetch_overrides_stale_cache(self, tmp_path, monkeypatch):
        """
        CRITICAL TEST: Fresh fetch must override stale cache.

        This tests the bug where the app was using cached 750nm instead of
        fetched 720nm.
        """
        cache_file = tmp_path / "cache" / "remote-defaults.json"
        cache_file.parent.mkdir(parents=True, exist_ok=True)

        # Set up stale cache with old value
        stale_cache = {
            "version": "old",
            "eqe": {"defaults": {"end_wavelength": 750.0}}
        }
        cache_file.write_text(json.dumps(stale_cache))

        monkeypatch.setattr(
            "common.utils.remote_config.get_cache_path",
            lambda: cache_file
        )

        # Mock fetch to return new value
        fresh_config = {
            "version": "new",
            "eqe": {"defaults": {"end_wavelength": 720.0}}
        }
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(fresh_config).encode()
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_response):
            result = get_remote_config("eqe", timeout=1.0)

        # Must return NEW value, not stale cache
        assert result["defaults"]["end_wavelength"] == 720.0

        # Cache must be updated with new value
        updated_cache = json.loads(cache_file.read_text())
        assert updated_cache["version"] == "new"
        assert updated_cache["eqe"]["defaults"]["end_wavelength"] == 720.0

    def test_fetch_failure_falls_back_to_cache(self, tmp_path, monkeypatch):
        """Test that fetch failure uses cached config."""
        cache_file = tmp_path / "cache" / "remote-defaults.json"
        cache_file.parent.mkdir(parents=True, exist_ok=True)

        # Set up cache
        cached_config = {
            "version": "cached",
            "eqe": {"defaults": {"end_wavelength": 750.0}}
        }
        cache_file.write_text(json.dumps(cached_config))

        monkeypatch.setattr(
            "common.utils.remote_config.get_cache_path",
            lambda: cache_file
        )

        # Mock fetch to fail
        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("Network error")):
            result = get_remote_config("eqe", timeout=1.0)

        # Should fall back to cached value
        assert result["defaults"]["end_wavelength"] == 750.0

    def test_no_fetch_no_cache_returns_empty(self, tmp_path, monkeypatch):
        """Test that no fetch and no cache returns empty dict."""
        cache_file = tmp_path / "nonexistent" / "remote-defaults.json"
        monkeypatch.setattr(
            "common.utils.remote_config.get_cache_path",
            lambda: cache_file
        )

        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("Network error")):
            result = get_remote_config("eqe", timeout=1.0)

        assert result == {}

    def test_disabled_via_env_var(self, monkeypatch):
        """Test that env var disables remote config."""
        monkeypatch.setenv("PHYS2150_DISABLE_REMOTE_CONFIG", "1")

        # Should not even try to fetch
        with patch("urllib.request.urlopen") as mock_fetch:
            result = get_remote_config("eqe", timeout=1.0)

        mock_fetch.assert_not_called()
        assert result == {}

    def test_unknown_app_returns_empty(self, tmp_path, monkeypatch):
        """Test that unknown app name returns empty dict."""
        cache_file = tmp_path / "cache" / "remote-defaults.json"
        monkeypatch.setattr(
            "common.utils.remote_config.get_cache_path",
            lambda: cache_file
        )

        fresh_config = {"version": "test", "eqe": {"defaults": {}}}
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(fresh_config).encode()
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_response):
            result = get_remote_config("unknown_app", timeout=1.0)

        assert result == {}


class TestVersionTracking:
    """Tests for version tracking to diagnose config source."""

    def test_fetch_logs_version(self, caplog):
        """Test that successful fetch logs the version."""
        import logging
        caplog.set_level(logging.INFO)

        mock_response = MagicMock()
        mock_response.read.return_value = b'{"version": "2026-spring", "eqe": {}}'
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_response):
            fetch_remote_config(timeout=1.0)

        assert "2026-spring" in caplog.text

    def test_cache_fallback_logs_message(self, tmp_path, monkeypatch, caplog):
        """Test that cache fallback is logged."""
        import logging
        caplog.set_level(logging.INFO)

        cache_file = tmp_path / "cache" / "remote-defaults.json"
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        cache_file.write_text('{"version": "cached", "eqe": {}}')

        monkeypatch.setattr(
            "common.utils.remote_config.get_cache_path",
            lambda: cache_file
        )

        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("fail")):
            get_remote_config("eqe", timeout=1.0)

        assert "Using cached remote config" in caplog.text


class TestDiagnoseConfig:
    """Tests for the diagnose_config diagnostic function."""

    def test_diagnose_returns_expected_keys(self, tmp_path, monkeypatch):
        """Test that diagnose_config returns all expected keys."""
        cache_file = tmp_path / "cache" / "remote-defaults.json"
        monkeypatch.setattr(
            "common.utils.remote_config.get_cache_path",
            lambda: cache_file
        )

        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("fail")):
            result = diagnose_config()

        expected_keys = [
            "cache_path", "cache_exists", "cache_version", "cache_eqe_end",
            "fetch_success", "fetch_version", "fetch_eqe_end", "match"
        ]
        for key in expected_keys:
            assert key in result

    def test_diagnose_detects_mismatch(self, tmp_path, monkeypatch):
        """Test that diagnose_config detects version mismatch."""
        cache_file = tmp_path / "cache" / "remote-defaults.json"
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        cache_file.write_text('{"version": "old", "eqe": {"defaults": {"end_wavelength": 750.0}}}')

        monkeypatch.setattr(
            "common.utils.remote_config.get_cache_path",
            lambda: cache_file
        )

        fresh_config = {"version": "new", "eqe": {"defaults": {"end_wavelength": 720.0}}}
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(fresh_config).encode()
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_response):
            result = diagnose_config()

        assert result["cache_version"] == "old"
        assert result["fetch_version"] == "new"
        assert result["cache_eqe_end"] == 750.0
        assert result["fetch_eqe_end"] == 720.0
        assert result["match"] is False
