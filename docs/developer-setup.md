# Developer Setup Guide

This guide covers setting up a development environment for the PHYS 2150 Measurement Suite.

## Prerequisites

Before starting, ensure you have:

1. **Windows 10/11** (required for hardware drivers)
2. **Python 3.10+** installed
3. **Git** for version control
4. **Hardware drivers** installed (see [hardware-setup.md](hardware-setup.md))

## Quick Start

### Using UV

[UV](https://github.com/astral-sh/uv) is a fast, modern Python package manager that provides reproducible environments.

```bash
# Install UV (if not already installed)
pip install uv

# Clone the repository
git clone https://github.com/UCBoulder/PHYS-2150.git
cd PHYS-2150

# Create environment and install dependencies
uv sync

# Run the application
uv run python launcher.py

# Or run individual modules
uv run python -m eqe
uv run python -m jv
```

> **Windows Note:** If `uv` is not recognized, use `python -m uv` instead.

## Project Structure

```
PHYS-2150/
├── launcher.py              # Main entry point - measurement selector
├── pyproject.toml           # Project configuration and dependencies
├── requirements.txt         # Alternative pip dependencies
├── remote-defaults.json     # Semester-specific defaults (served via GitHub)
│
├── ui/                      # Web UI (shared by all apps)
│   ├── eqe.html            # EQE measurement interface
│   ├── jv.html             # J-V measurement interface
│   ├── launcher.html       # Application launcher
│   ├── css/                # Stylesheets (theme.css, components.css)
│   └── js/                 # JavaScript modules
│
├── common/                  # Shared infrastructure
│   ├── drivers/            # Hardware drivers (TLPMX.py)
│   └── utils/              # Logging, data export, remote config
│
├── eqe/                    # EQE measurement application
│   ├── web_main.py        # Qt WebEngine app, Python-JS bridge
│   ├── controllers/       # Device controllers
│   ├── models/            # Experiment logic
│   ├── drivers/           # EQE-specific drivers (PicoScope)
│   ├── config/            # Settings
│   └── utils/             # EQE utilities
│
├── jv/                     # J-V measurement application
│   ├── web_main.py        # Qt WebEngine app, Python-JS bridge
│   ├── controllers/       # Keithley 2450 controller
│   ├── models/            # J-V experiment logic
│   ├── config/            # Settings
│   └── utils/             # JV utilities
│
├── assets/                 # Application resources
│   ├── icon.ico           # Windows application icon
│   └── cu_logo.png        # CU Boulder logo
│
├── scripts/                # Utility scripts
│   └── test_measurement_parameters.py
│
├── build/                  # Build configuration
│   ├── phys2150.spec      # PyInstaller spec
│   └── installer.iss      # Inno Setup script
│
└── docs/                   # Documentation
```

## Running the Applications

### Launcher (GUI Selector)

The launcher provides a graphical interface to select which measurement to run:

```bash
uv run python launcher.py
```

### EQE Measurement

Run the EQE application directly:

```bash
# Normal mode (connects to hardware)
uv run python -m eqe

# Offline mode (for GUI testing without hardware)
uv run python -m eqe --offline
```

### J-V Measurement

Run the J-V application directly:

```bash
# Normal mode
uv run python -m jv

# Offline mode
uv run python -m jv --offline
```

## Development Workflow

### Adding Dependencies

```bash
# Add a runtime dependency
uv add numpy

# Add a development dependency
uv add --dev pytest

# Update lock file
uv lock
```

### Code Style

The project uses [Ruff](https://github.com/astral-sh/ruff) for linting:

```bash
# Check code style
uv run ruff check .

# Auto-fix issues
uv run ruff check --fix .
```

### Running Tests

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=eqe --cov=jv

# Run specific test file
uv run pytest tests/test_jv_measurement.py
```

## Building for Distribution

The build process has two steps:
1. **PyInstaller** - Bundles Python + dependencies into a standalone folder
2. **Inno Setup** - Packages that folder into a Windows installer (.exe)

### Build Outputs

| Path | Description |
|------|-------------|
| `build/` | Intermediate PyInstaller files (ignore) |
| `dist/PHYS2150/` | Standalone application folder |
| `dist/PHYS2150/PHYS2150.exe` | The actual executable (can run directly) |
| `dist/PHYS2150-Setup.exe` | Windows installer for distribution |

### Step 1: Build with PyInstaller

```bash
# Build the executable
uv run pyinstaller build/phys2150.spec
```

This creates `dist/PHYS2150/` containing:
- `PHYS2150.exe` - Main executable
- `ui/` - Web UI files (HTML/CSS/JS)
- Python runtime and all dependencies bundled

You can run `dist/PHYS2150/PHYS2150.exe` directly for testing, but for deployment use the installer.

### Step 2: Build Windows Installer

#### Install Inno Setup (one-time)

1. Download from https://jrsoftware.org/isdl.php
2. Run the installer
3. This adds `iscc` (Inno Setup Compiler) to your PATH

#### Build the installer

```bash
# If iscc is in PATH:
iscc build/installer.iss

# Or use full path (PowerShell):
& "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" build/installer.iss
```

This creates `dist/PHYS2150-Setup.exe` which:
- Installs to `C:\Program Files\PHYS-2150\`
- Creates Start Menu shortcuts
- Optionally creates a desktop shortcut
- Registers in Windows "Add/Remove Programs" for clean uninstall
- Checks for NI-VISA and warns if not installed

### Deploying to Lab Computers

1. Copy `dist/PHYS2150-Setup.exe` to the target computer
2. Run the installer (may require admin privileges)
3. The application appears in Start Menu as "PHYS 2150 Measurement Suite"

**Prerequisites on target machines:**
- Windows 10/11 64-bit
- NI-VISA Runtime (for instrument communication)
- PicoScope SDK (for EQE measurements)
- Thorlabs OPM driver (for power meter)

### Version Synchronization

The version number must be updated in two places:
1. `pyproject.toml` - `version = "X.Y.Z"` (source of truth)
2. `build/installer.iss` - `#define MyAppVersion "X.Y.Z"`

The launcher reads the version from `pyproject.toml` at runtime.

### What to Commit

**Commit these build config files:**
- `build/phys2150.spec` - PyInstaller configuration
- `build/installer.iss` - Inno Setup script
- `assets/icon.ico` - Application icon

**Do NOT commit (already in .gitignore):**
- `dist/` - Contains installer and bundled app (~200MB+)
- `build/phys2150/` - PyInstaller intermediate files

### Distributing the Installer

Use **GitHub Releases** to distribute the installer (not git commits):

1. Go to your repo → **Releases** → "Create a new release"
2. **Tag**: `v3.1.0` (create new tag)
3. **Title**: "PHYS 2150 v3.1.0"
4. **Description**: Copy relevant section from CHANGELOG.md
5. **Attach**: Drag `dist/PHYS2150-Setup.exe` to upload (up to 2GB allowed)
6. **Publish release**

Users download from the Releases page, keeping the git repo small.

### Complete Release Process

```bash
# 1. Ensure clean environment
uv sync

# 2. Run tests
uv run pytest

# 3. Update version in pyproject.toml AND installer.iss
# pyproject.toml: version = "3.1.0"
# installer.iss:  #define MyAppVersion "3.1.0"

# 4. Build executable
uv run pyinstaller build/phys2150.spec

# 5. Build installer
iscc build/installer.iss
# Or: & "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" build/installer.iss

# 6. Test installer on a clean machine (VM recommended)

# 7. Commit and tag
git add -A
git commit -m "Release v3.1.0"
git tag -a v3.1.0 -m "Version 3.1.0 - description"
git push origin main --tags

# 8. Create GitHub Release and upload dist/PHYS2150-Setup.exe
```

### Troubleshooting Builds

**NumPy/SciPy DLL errors:**
The spec file uses `collect_all()` to bundle all NumPy/SciPy components. If you see DLL errors, ensure the spec file includes:
```python
from PyInstaller.utils.hooks import collect_all
numpy_datas, numpy_binaries, numpy_hiddenimports = collect_all('numpy')
```

**Missing modules:**
Add to `hiddenimports` in `build/phys2150.spec`.

**Large installer size:**
The installer is ~200-300MB due to Qt WebEngine and scientific libraries. This is expected.

## MVC Architecture

The application follows the Model-View-Controller pattern with a web-based UI:

### Controller (Hardware Layer)
- **What**: Device drivers that communicate with hardware
- **Where**: `*/controllers/`
- **Example**: `keithley_2450.py` - SCPI commands to Keithley SMU

### Model (Business Logic)
- **What**: Experiment logic, data processing, workflows
- **Where**: `*/models/`
- **Example**: `jv_experiment.py` - J-V sweep orchestration

### View (User Interface)
- **What**: Web-based UI (HTML/CSS/JS) served via Qt WebEngine
- **Where**: `ui/` for HTML/CSS/JS, `*/web_main.py` for Python-JS bridge
- **Important**: Views never access controllers directly; they go through models via QWebChannel

## Common Development Tasks

### Adding a New Measurement Type

1. Create a new package directory (e.g., `new_measurement/`)
2. Create the structure:
   - `controllers/` - Hardware communication
   - `models/` - Experiment logic
   - `web_main.py` - Qt WebEngine app with QWebChannel API
   - `config/` - Settings
3. Add UI page in `ui/new_measurement.html` with CSS/JS
4. Add `__main__.py` for module execution
5. Add button to `ui/launcher.html`
6. Update `pyproject.toml` entry points

### Adding a New Hardware Device

1. Create controller in appropriate `controllers/` directory
2. Follow existing patterns (see `keithley_2450.py`)
3. Add configuration to `config/settings.py`
4. Create model methods to use the controller
5. Update views as needed

### Debugging Hardware Issues

1. Run in console mode to see logs:
   ```bash
   uv run python -c "from jv.controllers.keithley_2450 import *; k = Keithley2450Controller(); k.connect()"
   ```

2. Check VISA resources:
   ```python
   import pyvisa
   rm = pyvisa.ResourceManager()
   print(rm.list_resources())
   ```

3. Test PicoScope connection:
   ```bash
   uv run python eqe/drivers/picoscope_driver.py
   ```

### Log Files

Debug logs are written to `%LOCALAPPDATA%\PHYS2150\`:
- `eqe_debug.log` - EQE application logs
- `jv_debug.log` - J-V application logs

Typical location: `C:\Users\<username>\AppData\Local\PHYS2150\`

Logs rotate automatically at 5 MB with 3 backup files kept.

**Viewing logs in the application:**
- `Ctrl+Shift+L` - Opens log viewer modal showing the full debug log file
- `Ctrl+Shift+T` - Opens terminal panel showing real-time INFO+ messages
- `Ctrl+Shift+D` - Captures print() statements to the terminal panel

## Troubleshooting Development Issues

### Import Errors

If you get import errors when running modules:
- Ensure you're running from the repository root
- Use `python -m module_name` instead of `python module_name/main.py`
- Check that `__init__.py` files exist in all packages

### Qt/PySide6 Issues

If the GUI doesn't start:
- Ensure PySide6 is installed: `uv run pip show pyside6`
- Check for conflicting Qt installations (PyQt5, PyQt6)
- Set `QT_QPA_PLATFORM=offscreen` for headless testing

### Hardware Not Found

- Verify drivers are installed (see [hardware-setup.md](hardware-setup.md))
- Check that no other application is using the device
- Run in offline mode to test GUI without hardware: `--offline`

## Useful Commands

```bash
# Check installed packages
uv run pip list

# Show dependency tree
uv tree

# Reinstall all dependencies
uv sync --reinstall

# Run with verbose logging
uv run python -m jv 2>&1 | tee debug.log

# Profile application startup
uv run python -m cProfile -o profile.out launcher.py
```

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Make changes and test
4. Run linting: `uv run ruff check .`
5. Commit with descriptive message
6. Push and create pull request

## Offline Mode

Both applications support an `--offline` flag for GUI testing without physical hardware.

### Usage

```bash
# EQE offline mode
uv run python -m eqe --offline

# J-V offline mode
uv run python -m jv --offline
```

### What Works in Offline Mode

| Feature | EQE | J-V |
|---------|-----|-----|
| GUI display and interaction | ✓ | ✓ |
| Parameter validation | ✓ | ✓ |
| Button/control states | ✓ | ✓ |
| Plot widgets | ✓ | ✓ |
| File dialogs | ✓ | ✓ |
| Tab switching | ✓ | N/A |

### What Doesn't Work

- Device connection (returns mock success)
- Actual measurements (no data acquired)
- Real-time plotting of measurements
- Data export (no real data to export)

### Implementation Details

Offline mode is controlled by a flag in each application's config:

```python
# eqe/config/settings.py
OFFLINE_MODE = False  # Set to True for offline mode

# jv/config/settings.py
OFFLINE_MODE = False
```

When `--offline` is passed on the command line, the flag is set to `True` before device initialization. Controllers check this flag and skip hardware communication.

### When to Use Offline Mode

- **GUI development**: Test layout and styling changes
- **UI/UX testing**: Verify button states, validation messages
- **Demo purposes**: Show the application without hardware
- **Debugging**: Isolate GUI issues from hardware issues

---

## Remote Configuration

The application supports semester-specific defaults via remote configuration, allowing updates without rebuilding.

### How It Works

1. On startup, the launcher fetches `remote-defaults.json` from the GitHub `main` branch
2. Settings are cached locally in `~/.phys2150/cache/` for offline use
3. If fetch fails, cached values are used; if no cache, built-in defaults apply

### Updating Defaults

To change defaults for all users (e.g., new semester cell naming):

1. Edit `remote-defaults.json` in the repository root
2. Push to `main` branch
3. Users get new defaults on next app launch

### File Format

```json
{
  "version": "2025-spring",
  "jv": {
    "cell_number": 1,
    "pixel_number": 1
  },
  "eqe": {
    "cell_number": 1,
    "start_wavelength": 400,
    "end_wavelength": 1100
  }
}
```

### Disabling Remote Config (Development)

When testing new default values locally, you may want to disable remote config fetching so your local changes aren't overwritten. Set this environment variable:

```bash
# PowerShell
$env:PHYS2150_DISABLE_REMOTE_CONFIG = "1"
uv run python -m eqe

# Or in VS Code launch.json:
{
    "env": {
        "PHYS2150_DISABLE_REMOTE_CONFIG": "1"
    }
}
```

When set, `get_remote_config()` returns an empty dict and uses built-in defaults only.

### Implementation

See `common/utils/remote_config.py` for the fetch/cache logic. The `get_remote_config(app)` function returns a dict that models merge with their built-in defaults.

---

## Controller API Reference

The controller layer provides clean interfaces to hardware devices. When extending or modifying the system, these are the key classes and methods.

### EQE Controllers

#### PicoScopeController (`eqe/controllers/picoscope_lockin.py`)

Software lock-in amplifier using PicoScope oscilloscope.

```python
from eqe.controllers.picoscope_lockin import PicoScopeController

# Basic usage
controller = PicoScopeController()
controller.connect()

# Configure
controller.set_reference_frequency(81.0)  # Hz
controller.set_num_cycles(100)            # Integration cycles

# Measurements
result = controller.perform_lockin_measurement()
# Returns: {'X': float, 'Y': float, 'R': float, 'theta': float, 'freq': float}

current = controller.read_current(num_measurements=5)
# Returns: float (Amps) - averaged and filtered

current = controller.read_lockin_current()
# Returns: float (Amps) - single measurement (for stability test)

phase, magnitude, quality = controller.measure_phase_response()
# Returns: (float, float, float) - phase in degrees, magnitude in V, quality 0-1

# Status
status = controller.get_status()
# Returns: {'connected': bool, 'locked': bool, 'has_reference': bool, 'overloaded': bool}

controller.disconnect()
```

#### MonochromatorController (`eqe/controllers/monochromator.py`)

Newport CS130B monochromator with filter wheel control.

```python
from eqe.controllers.monochromator import MonochromatorController

controller = MonochromatorController()
controller.connect()

# Set wavelength (auto-selects grating and filter)
actual_wavelength = controller.configure_for_wavelength(550.0)

# Shutter control
controller.open_shutter()
controller.close_shutter()

# Direct control
controller.set_wavelength(600.0)
controller.set_filter_position(1)  # 1=400nm filter, 2=780nm filter, 3=no filter

controller.disconnect()
```

#### ThorlabsPowerMeterController (`eqe/controllers/thorlabs_power_meter.py`)

Thorlabs PM100USB power meter.

```python
from eqe.controllers.thorlabs_power_meter import ThorlabsPowerMeterController

controller = ThorlabsPowerMeterController()
controller.connect()

# Set measurement wavelength
controller.set_wavelength(550)

# Measure power
power = controller.measure_power()  # Single reading (W)
power_avg = controller.measure_power_average(num_measurements=200, correction_factor=2.0)

controller.disconnect()
```

### J-V Controllers

#### Keithley2450Controller (`jv/controllers/keithley_2450.py`)

Keithley 2450 Source Measure Unit.

```python
from jv.controllers.keithley_2450 import Keithley2450Controller

controller = Keithley2450Controller()
controller.connect()

# Configuration
controller.configure_source_voltage()
controller.set_voltage_range(2.0)
controller.set_current_compliance(1.0)
controller.enable_remote_sensing(True)  # 4-wire mode

# Measurement
controller.set_voltage(0.5)
current = controller.measure_current()  # Returns Amps

# Output control
controller.output_on()
controller.output_off()

controller.disconnect()
```

### Creating New Controllers

When adding support for new hardware:

1. Create a new controller class in the appropriate `controllers/` directory
2. Follow the connect/disconnect pattern
3. Keep methods focused on single device operations
4. Put experiment logic in Models, not Controllers
5. Add configuration to `config/settings.py`

See [architecture.md](architecture.md) for details on the MVC pattern.

---

## Resources

- [PySide6 Documentation](https://doc.qt.io/qtforpython-6/)
- [PyVISA Documentation](https://pyvisa.readthedocs.io/)
- [PicoSDK Documentation](https://www.picotech.com/downloads)
- [UV Documentation](https://github.com/astral-sh/uv)
