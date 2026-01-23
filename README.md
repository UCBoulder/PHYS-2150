# PHYS 2150 Measurement Suite

A comprehensive solar cell characterization system for the CU Boulder PHYS 2150 lab course. This suite provides two complementary measurements for complete solar cell analysis:

| Measurement | Purpose | Key Equipment |
|-------------|---------|---------------|
| **I-V Characterization** | Power conversion efficiency, fill factor, Voc, Isc | Keithley 2450 SMU + Solar Simulator |
| **EQE (External Quantum Efficiency)** | Spectral response across wavelengths | PicoScope + Monochromator + Power Meter |

## Quick Start

### Installation

**Requires Python 3.10 or later.**

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
git clone https://github.com/UCBoulder/PHYS-2150.git
cd PHYS-2150
uv sync
uv run python launcher.py
```

> **Note:** Restart your terminal after installing uv for it to be available in PATH.

### Running the Applications

```bash
# Unified launcher (select EQE or I-V)
uv run python launcher.py

# Run directly
uv run python -m eqe
uv run python -m jv   # I-V measurement

# Offline mode (GUI testing without hardware)
uv run python -m eqe --offline
uv run python -m jv --offline   # I-V offline
```

> **Staff Tip:** In the launcher, press `Ctrl+Shift+D` to toggle offline mode without command-line flags.

## Hardware Requirements

### I-V Measurement System

| Component | Model | Connection | Purpose |
|-----------|-------|------------|---------|
| Source Measure Unit | Keithley 2450 | USB | Voltage sourcing & current measurement |
| Solar Simulator | [Ossila LED Solar Simulator](https://www.ossila.com/products/solar-simulator) | - | AM1.5G illumination |

**Driver Required:** [NI-VISA Runtime](https://www.ni.com/en-us/support/downloads/drivers/download.ni-visa.html)

### EQE Measurement System

| Component | Model | Connection | Purpose |
|-----------|-------|------------|---------|
| Light Source | Newport 66502-250Q-R1 QTH | - | Quartz Tungsten Halogen broadband source |
| Optical Chopper | (User provided) | TTL to PicoScope CH B | Modulation & reference signal (81 Hz) |
| Monochromator | Newport CS130B | USB-Serial | Wavelength selection |
| Filter Wheel | Newport USFW-100 | USB-Serial | Automated order-sorting filters |
| Power Meter | Thorlabs PM100USB | USB | Reference power measurement |
| Photodiode Sensor | Thorlabs S120VC | to PM100USB | Calibrated silicon reference detector |
| Transimpedance Amp | Custom | Signal to PicoScope CH A | Current-to-voltage conversion |
| Oscilloscope | PicoScope 5242D or 2204A | USB | Signal acquisition & software lock-in |

**Drivers Required:**

- [PicoScope SDK](https://www.picotech.com/downloads)
- [Thorlabs OPM](https://www.thorlabs.com/software_pages/ViewSoftwarePage.cfm?Code=OPM)
- [NI-VISA Runtime](https://www.ni.com/en-us/support/downloads/drivers/download.ni-visa.html) (for serial communication)

See [docs/hardware-setup.md](docs/hardware-setup.md) for detailed installation instructions.

## Project Structure

```
PHYS 2150/
├── launcher.py              # Unified launcher - select EQE or I-V
├── pyproject.toml           # Project dependencies (uv sync)
├── requirements.txt         # Alternative pip dependencies
├── defaults.json            # All configuration (fetched from GitHub, bundled with app)
│
├── ui/                      # Web UI (shared by all apps)
│   ├── eqe.html            # EQE measurement interface
│   ├── jv.html             # I-V measurement interface
│   ├── launcher.html       # Application launcher
│   ├── css/                # Stylesheets (theme.css, components.css, layout.css)
│   └── js/                 # JavaScript modules (api.js, plotly-utils.js, etc.)
│
├── jv/                      # I-V Measurement Application
│   ├── web_main.py         # Qt WebEngine app, Python-JS bridge
│   ├── controllers/        # Keithley 2450 communication
│   ├── models/             # Sweep logic, experiment orchestration
│   ├── utils/              # I-V data export utilities
│   └── config/             # Measurement parameters
│
├── eqe/                     # EQE Measurement Application
│   ├── web_main.py         # Qt WebEngine app, Python-JS bridge
│   ├── controllers/        # Device controllers
│   ├── models/             # Measurement logic
│   ├── drivers/            # PicoScope software lock-in
│   ├── validation/         # Lock-in testing and verification tools
│   └── config/             # Settings
│
├── common/                  # Shared Infrastructure
│   ├── config/             # Centralized config loader (defaults.json)
│   ├── drivers/            # Thorlabs power meter driver
│   ├── ui/                 # Shared web window and API base classes
│   └── utils/              # Data export, logging, error messages
│
├── assets/                  # Application resources
│   ├── icon.ico            # Windows application icon
│   └── cu_logo.png         # CU Boulder logo
│
├── scripts/                 # Utility scripts
│   ├── test_measurement_parameters.py
│   └── optimize_lockin_cycles.py
│
├── build/                   # Build Configuration
│   ├── phys2150.spec       # PyInstaller spec
│   └── installer.iss       # Windows installer script (Inno Setup)
│
├── docs/                    # Documentation (see table below)
│
└── tests/                   # Test Suite (221 tests)
    ├── unit/               # Pure function tests
    ├── models/             # Model tests with mocks
    ├── integration/        # Workflow tests
    └── mocks/              # Mock hardware controllers
```

## I-V Measurement

The I-V (current vs. voltage) measurement characterizes solar cell performance under illumination.

### I-V Capabilities

- Forward and reverse voltage sweeps (hysteresis analysis)
- Configurable voltage range and step size
- Real-time I-V curve plotting
- Automatic data export to CSV
- Cell/pixel tracking for multi-device substrates

### I-V Parameters

- **Voltage Range:** -0.2V to 1.5V (configurable)
- **Step Size:** 0.02V (configurable)
- **Dwell Time:** 500ms per point (configurable)
- **4-Wire Sensing:** Enabled for accuracy

### I-V Output

- CSV file with forward and reverse scan data
- Filename format: `YYYY_MM_DD_IV_cell{N}_pixel{P}.csv`

## EQE Measurement

External Quantum Efficiency measures the spectral response - the fraction of incident photons converted to collected electrons at each wavelength.

### EQE Capabilities

- Software lock-in amplifier (no external lock-in required)
- Phase-locked acquisition for stability
- Automated wavelength scanning
- Reference power calibration
- Real-time EQE plotting

### EQE Specifications

- **Stability:** 0.66% CV (coefficient of variation)
- **Input Range:** ±20V (no clipping)
- **Resolution:** 15-bit in 2-channel mode
- **Chopper Frequency:** 81 Hz (configurable)

### EQE Workflow

1. **Power Calibration** - Scan reference detector to measure lamp spectrum
2. **Current Measurement** - Measure solar cell photocurrent (chopper validated automatically)
3. **EQE Calculation** - Compute quantum efficiency from power and current data

## Architecture

The application follows the Model-View-Controller (MVC) pattern with a web-based UI:

- **Controller:** Hardware communication (what devices physically do)
- **Model:** Experiment logic, measurement workflows
- **View:** Web UI (HTML/CSS/JS) served via Qt WebEngine, communicates with Python via QWebChannel

This separation enables:

- Easy hardware swapping (different SMU models, etc.)
- GUI testing without hardware (`--offline` mode)
- Clear code organization for maintenance
- Modern web-based interface with Plotly.js visualizations

## Testing

The test suite covers measurement logic, data export, and parameter validation.

```bash
# Run all tests
uv run pytest

# Run with coverage report
uv run pytest --cov=jv --cov=eqe --cov=common

# Run specific test categories
uv run pytest tests/unit/           # Pure function tests
uv run pytest tests/models/         # Model layer tests
uv run pytest tests/integration/    # Workflow tests
```

### Test Structure

| Directory | Tests | Purpose |
|-----------|-------|---------|
| `tests/unit/` | 106 | Math utilities, data handling, statistics |
| `tests/models/` | 74 | Measurement models with mock controllers |
| `tests/integration/` | 41 | End-to-end measurement workflows |

### What's Tested

- **Measurement models** (74-86% coverage): I-V sweeps, EQE current/power/phase
- **Data export** (56-100%): CSV generation, filename formatting
- **Parameter validation**: Cell numbers, pixel ranges, voltage/wavelength limits
- **Stability test**: Power and current stability measurements

Mock controllers simulate hardware behavior for testing without physical devices.

## Building for Distribution

```bash
# Build Windows executable
uv run pyinstaller build/phys2150.spec

# Build Windows installer (requires Inno Setup)
# If iscc is in PATH:
iscc build/installer.iss
# Or use full path (PowerShell):
& "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" build/installer.iss

# Output: dist/PHYS2150-Setup.exe
```

The Windows installer (`PHYS2150-Setup.exe`) provides a complete installation including desktop shortcuts and Start Menu entries. Lab computers can run the installed application without Python.

See [docs/developer-setup.md](docs/developer-setup.md) for complete build instructions.

## Configuration

All configuration is centralized in `defaults.json` with a fallback chain:

1. **GitHub fetch** (5 sec timeout) - Fresh updates for all lab computers
2. **Local cache** (`~/.phys2150/cache/`) - Last known good config for offline use
3. **Bundled copy** - Release defaults packaged with the installer

To update defaults for all users, edit `defaults.json` in the repo root and push to `main`.

## Documentation

| Document | Description |
|----------|-------------|
| [hardware-setup.md](docs/hardware-setup.md) | Driver installation and hardware connections |
| [developer-setup.md](docs/developer-setup.md) | Development environment, offline mode, controller API |
| [architecture.md](docs/architecture.md) | MVC pattern and code organization |
| [jv-measurement.md](docs/jv-measurement.md) | I-V measurement theory and workflow |
| [eqe-measurement.md](docs/eqe-measurement.md) | EQE measurement theory, workflow, and stability test |
| [software-lockin.md](docs/software-lockin.md) | PicoScope software lock-in implementation |
| [staff-guide.md](docs/staff-guide.md) | Keyboard shortcuts, diagnostic modes, common student issues |
| [offline-testing.md](docs/offline-testing.md) | Testing the GUI without hardware |
| [CHANGELOG.md](CHANGELOG.md) | Version history and release notes |
| [TROUBLESHOOTING.md](TROUBLESHOOTING.md) | Common issues and solutions |

## Performance

### I-V Performance

- Full forward+reverse sweep: ~30 seconds
- Voltage resolution: 0.001V
- Current resolution: 6½ digits

### EQE Performance

- Per-wavelength measurement: ~6 seconds
- Full spectrum (400-1100nm, 10nm steps): ~7 minutes
- Stability: 0.66% CV (15× better than 10% target)

## License

This software is released under the **MIT License**. See [LICENSE](LICENSE) for details.

### Third-Party Dependencies

- **PicoScope SDK** - Proprietary (Pico Technology Limited) - For use with Pico products only
- **PySide6** - LGPL v3 (The Qt Company)
- **NumPy, SciPy, pandas, matplotlib** - BSD-style licenses
- **PyVISA** - MIT License

## Citation

If you use this software, please cite:

```
PHYS 2150 Measurement Suite
University of Colorado Boulder
https://github.com/UCBoulder/PHYS-2150
```

## Contributing

See [docs/developer-setup.md](docs/developer-setup.md) for development environment setup and contribution guidelines.
