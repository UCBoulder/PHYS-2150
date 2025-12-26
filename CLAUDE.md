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

## Versioning

This project follows [Semantic Versioning 2.0.0](https://semver.org/spec/v2.0.0.html):

- **MAJOR** (X.0.0): Incompatible API changes or breaking architectural changes
  - Examples: UI framework changes (tkinter to PySide6, PySide6 to WebEngine), hardware removal
- **MINOR** (x.Y.0): Backward-compatible new functionality
  - Examples: New measurement modes, new hardware support, new UI features
- **PATCH** (x.y.Z): Backward-compatible bug fixes
  - Examples: Bug fixes, documentation updates, minor UI tweaks

### Branching Strategy

This project uses a simplified Git Flow model:

```
main    → Released versions only (what's installed in the lab)
develop → Integration branch for ongoing work
```

**Day-to-day development:**
```bash
git checkout develop
# make changes, commit, push to develop
```

**Feature branches (optional, for larger changes):**
```bash
git checkout develop
git checkout -b feature/my-feature
# work on feature
git checkout develop
git merge feature/my-feature
git branch -d feature/my-feature
```

### Changelog Guidelines

Follow [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/):

- Categories: Added, Changed, Deprecated, Removed, Fixed, Security
- Use ISO 8601 dates (YYYY-MM-DD)
- Mark breaking changes with **BREAKING** prefix
- Keep [Unreleased] section at top for in-progress work
- Add comparison links at bottom of CHANGELOG.md

### Creating Releases

When ready to release a new version:

1. **Ensure develop is up to date and tested**
   ```bash
   git checkout develop
   git pull
   ```

2. **Merge develop into main**
   ```bash
   git checkout main
   git merge develop
   ```

3. **Update CHANGELOG.md**
   - Move [Unreleased] content to new version section
   - Add release date
   - Update comparison links at bottom

4. **Commit changelog, tag, and push**
   ```bash
   git add CHANGELOG.md
   git commit -m "Release vX.Y.Z"
   git tag -a vX.Y.Z -m "Version X.Y.Z - brief description"
   git push origin main --tags
   ```

5. **Merge release commit back to develop**
   ```bash
   git checkout develop
   git merge main
   git push origin develop
   ```
