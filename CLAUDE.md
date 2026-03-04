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

### Layer Responsibilities

- **Controllers** (`app/*/controllers/`): ONLY hardware communication (SCPI commands, SDK calls). No experiment logic.
- **Models** (`app/*/models/`): Experiment workflows, parameter validation, orchestration. Uses controllers but never touches GUI.
- **Views** (`app/ui/`): Web-based UI (HTML/CSS/JS) served via Qt WebEngine. Communicates with Python via QWebChannel.

### Key Patterns

- **Thread Safety**: Long-running measurements use QThread workers with Qt signals for GUI updates
- **Offline Mode**: Controllers return mock data when `settings.OFFLINE_MODE = True`
- **Configuration**: All measurement parameters centralized in `app/*/config/settings.py`
- **Web Bridge**: `web_main.py` exposes Python API to JavaScript via QWebChannel

### Data Flow Example

```
User clicks "Start" → JS calls Python API via QWebChannel → Model validates & orchestrates
→ Model calls Controller methods → Controller sends SCPI/SDK commands
→ Hardware responds → Data flows back via Qt signals → JS callbacks update UI
```

### Configuration Architecture

This project uses a **centralized JSON configuration system**:

**`app/defaults.json`** - Bundled copy of configuration. Remote source of truth hosted at `UCBoulder/PHYS-Lab-Config`:
- Form field defaults (voltages, wavelengths, step sizes)
- Validation patterns (cell number regex, pixel ranges)
- Stability test defaults (duration, interval)
- Hardware communication (timeouts, USB IDs, SCPI settings)
- Physical constants (grating thresholds, filter wavelengths, gains)
- Measurement algorithms (NPLC, lock-in cycles, quality thresholds)
- GUI rendering (window sizes, fonts, colors)
- CSV export formats (headers, precision)
- Error messages

**How it works at runtime:**
```
1. Fetch from GitHub (5 sec timeout)  → FRESH UPDATES
         │                               (UCBoulder/PHYS-Lab-Config)
         ▼ (if fetch fails)
2. Local Cache (~/.phys2150/cache/)   → LAST KNOWN GOOD
         │
         ▼ (if no cache)
3. Bundled Copy (packaged with exe)   → RELEASE DEFAULTS
```

**`app/*/config/settings.py`** - Thin wrappers that re-export from JSON:
- Import values from `common.config.loader`
- Convert JSON types to Python (lists→tuples, string keys→enum keys)
- Provide backward-compatible exports for existing imports
- Define Python-only constructs (enums, OFFLINE_MODE flag)

Set `PHYS2150_DISABLE_REMOTE_CONFIG=1` to use only bundled defaults.json values.

**When adding new configurable values:**

1. Add to `defaults.json` with appropriate section (jv/eqe/common)
2. Update the loader class (`JVConfig` or `EQEConfig`) in `app/common/config/loader.py`
3. Re-export from `app/*/config/settings.py` for backward compatibility
4. If needed for JavaScript, expose via `get_ui_config()` in `app/*/web_main.py`
5. For JavaScript access, use `LabConfig.get()` with fallback defaults in `app/ui/js/config.js`

## App Structure

```
app/
├── ui/                      # Web UI (shared by all apps)
│   ├── eqe.html             # EQE measurement interface
│   ├── jv.html              # J-V measurement interface
│   ├── launcher.html        # Application launcher
│   ├── css/                 # Stylesheets (theme.css, components.css)
│   └── js/                  # JavaScript modules
│
├── jv/                      # J-V Application
│   ├── controllers/         # Keithley 2450 SCPI communication
│   ├── models/              # JVExperimentModel, JVMeasurementModel
│   ├── web_main.py          # Qt WebEngine app, Python-JS bridge
│   └── config/settings.py   # J-V measurement parameters
│
├── eqe/                     # EQE Application
│   ├── controllers/         # PicoScope lock-in, monochromator
│   ├── models/              # EQEExperimentModel, measurement models
│   ├── drivers/             # Low-level PicoScope SDK wrapper
│   ├── web_main.py          # Qt WebEngine app, Python-JS bridge
│   └── config/settings.py   # EQE measurement parameters
│
└── common/                  # Shared code
    ├── config/              # Centralized config loader (loads defaults.json)
    ├── drivers/             # Thorlabs power meter (TLPMX.py)
    └── utils/               # Logging, data export, error messages
```

## Key Files

- `app/launcher.py`: Entry point - Qt WebEngine launcher for EQE or J-V
- `app/defaults.json`: Bundled configuration (remote source: UCBoulder/PHYS-Lab-Config)
- `app/common/config/loader.py`: Config loading with fallback chain (GitHub→cache→bundled)
- `app/jv/web_main.py`: JVWebApplication class, QWebChannel API
- `app/eqe/web_main.py`: EQEWebApplication class, QWebChannel API
- `app/*/config/settings.py`: Thin wrappers re-exporting values from defaults.json

## Hardware Dependencies

J-V requires: NI-VISA Runtime, Keithley 2450

EQE requires: PicoScope SDK (ps5000a or ps2000), Thorlabs OPM, NI-VISA

## Exception Classes

Each layer has custom exceptions:
- `Keithley2450Error`, `PicoScopeError`, `MonochromatorError` (controllers)
- `JVExperimentError`, `EQEExperimentError` (models)

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
- Add comparison links at bottom of app/CHANGELOG.md

### Creating Releases

When ready to release a new version:

#### 1. Version Number Management

**CRITICAL:** The version number must be updated in multiple places for it to display correctly throughout the application:

- **`app/pyproject.toml`**: `[project].version = "X.Y.Z"` - Python package version
- **`app/build/installer.iss`**: `#define MyAppVersion "X.Y.Z"` - Installer metadata

The launcher reads the version from `importlib.metadata.version("phys2150")`, which gets embedded by PyInstaller from `pyproject.toml`. You **must rebuild the PyInstaller executable** after updating `pyproject.toml`, not just the installer.

#### 2. Release Process

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

3. **Update version numbers**
   ```bash
   # Edit app/pyproject.toml: set version = "X.Y.Z"
   # Edit app/build/installer.iss: set MyAppVersion "X.Y.Z"
   git add app/pyproject.toml app/build/installer.iss
   ```

4. **Update app/CHANGELOG.md**
   - Move [Unreleased] content to new version section `## [X.Y.Z] - YYYY-MM-DD`
   - Add release date (ISO 8601 format)
   - Update comparison links at bottom:
     ```
     [Unreleased]: https://github.com/UCBoulder/PHYS-2150/compare/vX.Y.Z...HEAD
     [X.Y.Z]: https://github.com/UCBoulder/PHYS-2150/compare/vX.Y-1.Z-1...vX.Y.Z
     ```
   - Update version history summary table

5. **Commit version changes and create tag**
   ```bash
   git add app/CHANGELOG.md
   git commit -m "Release vX.Y.Z"
   git tag -a vX.Y.Z -m "Version X.Y.Z - brief description"
   git push origin main --tags
   ```

6. **Create GitHub Release**
   ```bash
   gh release create vX.Y.Z --title "vX.Y.Z - Title" --notes "Release notes here"
   ```

7. **Build and upload installer**

   **Important:** Build PyInstaller executable FIRST (to embed correct version metadata), THEN build the installer. Run from the `app/` directory:

   ```bash
   cd app

   # Step 1: Build PyInstaller executable (embeds version from pyproject.toml)
   rm -rf dist/PHYS2150
   uv run pyinstaller build/phys2150.spec

   # Step 2: Build Inno Setup installer (uses version from installer.iss)
   iscc build/installer.iss
   # Or: "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" build\installer.iss

   # Step 3: Upload installer to GitHub Release
   gh release upload vX.Y.Z "dist/PHYS2150-Setup.exe" --clobber
   ```

   **Why this order matters:**
   - PyInstaller embeds package metadata from `pyproject.toml` into the executable
   - The launcher reads version via `importlib.metadata.version("phys2150")`
   - If you only rebuild the installer without rebuilding PyInstaller, the launcher will show the old version
   - Inno Setup just packages the PyInstaller output, so the executable must be built first

8. **Merge release commit back to develop**
   ```bash
   git checkout develop
   git merge main
   git push origin develop
   ```

9. **Commit uv.lock if changed**
   ```bash
   # Check if uv.lock was updated during the build
   git status
   git add app/uv.lock
   git commit -m "Update uv.lock for vX.Y.Z"
   git push origin develop
   git checkout main
   git merge develop
   git push origin main
   git checkout develop
   ```

#### Version Display Checklist

Before finalizing a release, verify the version appears correctly in:

- [ ] Installer title window (from `installer.iss`)
- [ ] Launcher app bottom-left corner (from `pyproject.toml` via PyInstaller metadata)
- [ ] Windows "Add/Remove Programs" list (from `installer.iss`)
- [ ] GitHub Release page
- [ ] app/CHANGELOG.md

#### Known Issue: Metadata Caching on Upgrade

**Problem:** When installing a new version over an existing installation, the launcher may display the old version number even though Windows shows the correct version in "Add/Remove Programs".

**Root Cause:** Python package metadata (`.dist-info` directories) from the old installation may not be fully replaced during upgrade, causing `importlib.metadata` to read stale version information.

**Solution:** If the launcher shows an incorrect version after installation:
1. Uninstall the application completely
2. Reinstall using the new installer
3. The version should now display correctly

**Prevention:** The installer has been updated (v3.3.1+) to force complete removal of all application files during uninstall, which should prevent this issue in future upgrades. Users upgrading from older versions may still experience this once.
