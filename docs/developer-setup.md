# Developer Setup Guide

This guide covers setting up a development environment for the PHYS-2150 Measurement Suite.

## Prerequisites

Before starting, ensure you have:

1. **Windows 10/11** (required for hardware drivers)
2. **Python 3.10+** installed
3. **Git** for version control
4. **Hardware drivers** installed (see [hardware-setup.md](hardware-setup.md))

## Quick Start

### Using UV (Recommended)

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

### Using pip (Alternative)

If you prefer traditional pip:

```bash
# Clone the repository
git clone https://github.com/UCBoulder/PHYS-2150.git
cd PHYS-2150

# Create virtual environment
python -m venv .venv

# Activate virtual environment
# On Windows:
.venv\Scripts\activate
# On Unix/macOS:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run the application
python launcher.py
```

## Project Structure

```
PHYS-2150/
├── launcher.py              # Main entry point - measurement selector
├── pyproject.toml           # Project configuration and dependencies
├── requirements.txt         # Pip fallback dependencies
│
├── common/                  # Shared infrastructure
│   ├── drivers/            # Hardware drivers (TLPMX.py)
│   ├── ui/                 # Shared GUI components
│   └── utils/              # Shared utilities
│
├── eqe/                    # EQE measurement application
│   ├── main.py            # EQE entry point
│   ├── controllers/       # Device controllers
│   ├── models/            # Experiment logic
│   ├── views/             # GUI components
│   ├── drivers/           # EQE-specific drivers (PicoScope)
│   ├── config/            # Settings
│   └── utils/             # EQE utilities
│
├── jv/                     # J-V measurement application
│   ├── main.py            # JV entry point
│   ├── controllers/       # Keithley 2450 controller
│   ├── models/            # J-V experiment logic
│   ├── views/             # GUI components
│   ├── config/            # Settings
│   └── utils/             # JV utilities
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

With UV:
```bash
# Add a runtime dependency
uv add numpy

# Add a development dependency
uv add --dev pytest

# Update lock file
uv lock
```

With pip:
```bash
# Add to requirements.txt manually, then:
pip install -r requirements.txt
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

### 1. Build with PyInstaller

```bash
# Build the executable
uv run pyinstaller build/phys2150.spec

# Output: dist/PHYS2150/ folder
```

### 2. Build Windows Installer

Requires [Inno Setup](https://jrsoftware.org/isinfo.php) installed:

```bash
# Build installer (from command line)
iscc build/installer.iss

# Output: dist/PHYS2150-Setup.exe
```

### 3. Complete Release Process

```bash
# 1. Ensure clean environment
uv sync

# 2. Run tests
uv run pytest

# 3. Update version in pyproject.toml
# Edit: version = "2.1.0"

# 4. Build executable
uv run pyinstaller build/phys2150.spec

# 5. Build installer
iscc build/installer.iss

# 6. Test on clean machine
# 7. Create git tag
git tag -a v2.1.0 -m "Release 2.1.0"
git push origin v2.1.0
```

## MVC Architecture

The application follows the Model-View-Controller pattern:

### Controller (Hardware Layer)
- **What**: Device drivers that communicate with hardware
- **Where**: `*/controllers/`
- **Example**: `keithley_2450.py` - SCPI commands to Keithley SMU

### Model (Business Logic)
- **What**: Experiment logic, data processing, workflows
- **Where**: `*/models/`
- **Example**: `jv_experiment.py` - J-V sweep orchestration

### View (User Interface)
- **What**: GUI components, visualization, user input
- **Where**: `*/views/`
- **Important**: Views never access controllers directly; they go through models

## Common Development Tasks

### Adding a New Measurement Type

1. Create a new package directory (e.g., `new_measurement/`)
2. Create the MVC structure:
   - `controllers/` - Hardware communication
   - `models/` - Experiment logic
   - `views/` - GUI components
   - `config/` - Settings
3. Add entry point in `main.py`
4. Add `__main__.py` for module execution
5. Add button to `launcher.py`
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

## Resources

- [PySide6 Documentation](https://doc.qt.io/qtforpython-6/)
- [PyVISA Documentation](https://pyvisa.readthedocs.io/)
- [PicoSDK Documentation](https://www.picotech.com/downloads)
- [UV Documentation](https://github.com/astral-sh/uv)
