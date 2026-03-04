# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This repository hosts resources for CU Boulder PHYS 2150. The primary component is the **Measurement Suite** (`app/`), a solar cell characterization system providing:
- **J-V Characterization**: Current-voltage curves using Keithley 2450 SMU
- **EQE (External Quantum Efficiency)**: Spectral response using PicoScope with software lock-in amplifier

## Repository Structure

```
app/                     # Measurement Suite application
├── launcher.py          # Entry point
├── pyproject.toml       # Python package config
├── defaults.json        # Bundled configuration defaults
├── eqe/                 # EQE application
├── jv/                  # J-V application
├── common/              # Shared code
├── ui/                  # Web UI (HTML/CSS/JS)
├── build/               # PyInstaller spec, Inno Setup installer
├── tests/               # Unit and integration tests
├── scripts/             # Utility scripts
└── docs/                # Developer documentation
```

## Commands

All app commands run from the `app/` directory:

```bash
cd app

# Run applications
python launcher.py          # Unified launcher GUI
python -m jv               # J-V measurement directly
python -m eqe              # EQE measurement directly

# Offline mode (GUI testing without hardware)
python -m jv --offline
python -m eqe --offline

# Install dependencies
uv sync                    # Recommended
pip install -r requirements.txt  # Alternative

# Run tests
uv run pytest                                    # All tests
uv run pytest tests/unit/                        # Unit tests only
uv run pytest tests/integration/                 # Integration tests only
uv run pytest -k "test_voltage"                  # Run tests matching pattern
uv run pytest --cov=jv --cov=eqe --cov=common   # With coverage report

# Lint
uv run ruff check .
uv run ruff format .

# Build Windows executable
uv run pyinstaller build/phys2150.spec

# Build Windows installer (requires Inno Setup)
iscc build/installer.iss
```

## Architecture

The codebase follows **MVC (Model-View-Controller)** separation with a web-based UI:

```
View (Web UI via Qt WebEngine) → Model (experiment logic) → Controller (hardware drivers)
```

- **Controllers** (`app/*/controllers/`): ONLY hardware communication (SCPI commands, SDK calls). No experiment logic.
- **Models** (`app/*/models/`): Experiment workflows, parameter validation, orchestration. Uses controllers but never touches GUI.
- **Views** (`app/ui/`): Web-based UI (HTML/CSS/JS) served via Qt WebEngine. Communicates with Python via QWebChannel.

### Key Patterns

- **Thread Safety**: Long-running measurements use QThread workers with Qt signals for GUI updates
- **Offline Mode**: Controllers return mock data when `settings.OFFLINE_MODE = True`
- **Web Bridge**: `web_main.py` exposes Python API to JavaScript via QWebChannel

### Configuration

Centralized JSON config with runtime fallback chain: GitHub fetch (`UCBoulder/PHYS-Lab-Config`) → local cache (`~/.phys2150/cache/`) → bundled copy. Set `PHYS2150_DISABLE_REMOTE_CONFIG=1` to skip remote fetch.

`app/*/config/settings.py` files are thin wrappers re-exporting from `app/common/config/loader.py`.

When adding new config values: add to `defaults.json` → update loader class → re-export from `settings.py` → expose via `get_ui_config()` if needed for JS.

## Key Files

- `app/launcher.py`: Entry point - Qt WebEngine launcher for EQE or J-V
- `app/defaults.json`: Bundled configuration (remote source: UCBoulder/PHYS-Lab-Config)
- `app/common/config/loader.py`: Config loading with fallback chain
- `app/jv/web_main.py` / `app/eqe/web_main.py`: QWebChannel API bridges

## Hardware Dependencies

- **J-V**: NI-VISA Runtime, Keithley 2450
- **EQE**: PicoScope SDK (ps5000a or ps2000), Thorlabs OPM, NI-VISA

## Exception Classes

- Controllers: `Keithley2450Error`, `PicoScopeError`, `MonochromatorError`
- Models: `JVExperimentError`, `EQEExperimentError`

## Adding New Measurements

1. Create model in `app/*/models/new_measurement.py`
2. Add UI elements in `app/ui/*.html` and corresponding CSS/JS
3. Expose API methods in `app/*/web_main.py` via `@Slot` decorators
4. Reuse existing controllers - don't duplicate hardware logic

## Swapping Hardware

1. Create new controller with same interface (method signatures)
2. Update experiment model to use new controller
3. UI remains unchanged

## Versioning

Follows [Semantic Versioning 2.0.0](https://semver.org/spec/v2.0.0.html). Use `/release [version]` for the full release process (version bumps, changelog, tag, GitHub release, build steps).

### Branching Strategy

```
main    → Released versions only (what's installed in the lab)
develop → Integration branch for ongoing work
```

### Changelog

Follow [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/) in `app/CHANGELOG.md`. Categories: Added, Changed, Deprecated, Removed, Fixed, Security. Mark breaking changes with **BREAKING** prefix.
