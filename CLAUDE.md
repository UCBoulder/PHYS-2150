# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

PHYS 2150 Measurement Suite is a solar cell characterization system for CU Boulder Physics 2150 lab. It provides two measurement applications:
- **J-V Characterization**: Current-voltage curves using Keithley 2450 SMU
- **EQE (External Quantum Efficiency)**: Spectral response using PicoScope with software lock-in amplifier

## Commands

```bash
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
uv run pytest
pytest                     # If using pip

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

### Layer Responsibilities

- **Controllers** (`*/controllers/`): ONLY hardware communication (SCPI commands, SDK calls). No experiment logic.
- **Models** (`*/models/`): Experiment workflows, parameter validation, orchestration. Uses controllers but never touches GUI.
- **Views** (`ui/`): Web-based UI (HTML/CSS/JS) served via Qt WebEngine. Communicates with Python via QWebChannel.

### Key Patterns

- **Thread Safety**: Long-running measurements use QThread workers with Qt signals for GUI updates
- **Offline Mode**: Controllers return mock data when `settings.OFFLINE_MODE = True`
- **Configuration**: All measurement parameters centralized in `*/config/settings.py`
- **Web Bridge**: `web_main.py` exposes Python API to JavaScript via QWebChannel

### Data Flow Example

```
User clicks "Start" → JS calls Python API via QWebChannel → Model validates & orchestrates
→ Model calls Controller methods → Controller sends SCPI/SDK commands
→ Hardware responds → Data flows back via Qt signals → JS callbacks update UI
```

## Project Structure

```
ui/                      # Web UI (shared by all apps)
├── eqe.html             # EQE measurement interface
├── jv.html              # J-V measurement interface
├── launcher.html        # Application launcher
├── css/                 # Stylesheets (theme.css, components.css)
└── js/                  # JavaScript modules

jv/                      # J-V Application
├── controllers/         # Keithley 2450 SCPI communication
├── models/              # JVExperimentModel, JVMeasurementModel
├── web_main.py          # Qt WebEngine app, Python-JS bridge
└── config/settings.py   # J-V measurement parameters

eqe/                     # EQE Application
├── controllers/         # PicoScope lock-in, monochromator
├── models/              # EQEExperimentModel, measurement models
├── drivers/             # Low-level PicoScope SDK wrapper
├── web_main.py          # Qt WebEngine app, Python-JS bridge
└── config/settings.py   # EQE measurement parameters

common/                  # Shared code
├── drivers/             # Thorlabs power meter (TLPMX.py)
└── utils/               # Logging, data export, error messages
```

## Key Files

- `launcher.py`: Entry point - Qt WebEngine launcher for EQE or J-V
- `jv/web_main.py`: JVWebApplication class, QWebChannel API
- `eqe/web_main.py`: EQEWebApplication class, QWebChannel API
- `*/config/settings.py`: Measurement defaults and device configs

## Hardware Dependencies

J-V requires: NI-VISA Runtime, Keithley 2450

EQE requires: PicoScope SDK (ps5000a or ps2000), Thorlabs OPM, NI-VISA

## Exception Classes

Each layer has custom exceptions:
- `Keithley2450Error`, `PicoScopeError`, `MonochromatorError` (controllers)
- `JVExperimentError`, `EQEExperimentError` (models)

## Adding New Measurements

1. Create model in `*/models/new_measurement.py`
2. Add UI elements in `ui/*.html` and corresponding CSS/JS
3. Expose API methods in `*/web_main.py` via `@Slot` decorators
4. Reuse existing controllers - don't duplicate hardware logic

## Swapping Hardware

1. Create new controller with same interface (method signatures)
2. Update experiment model to use new controller
3. UI remains unchanged
