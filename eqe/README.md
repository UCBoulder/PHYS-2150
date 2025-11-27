# EQE Measurement Application - MVC Architecture

A professional implementation of External Quantum Efficiency (EQE) measurements for solar cell characterization, built using the Model-View-Controller (MVC) design pattern.

## Overview

This application provides a clean, maintainable solution for EQE measurements by separating device control, experiment logic, and user interface concerns into distinct, reusable components.

## Architecture

### Controllers (`controllers/`)
Device drivers that handle low-level hardware communication:
- **ThorlabsPowerMeterController**: Power measurements and wavelength calibration
- **MonochromatorController**: Wavelength selection and filter management
- **PicoScopeController**: Software lock-in amplifier for photocurrent measurements using PicoScope oscilloscope

### Models (`models/`)
Experiment logic and measurement workflows:
- **PowerMeasurementModel**: Automated power vs wavelength scanning
- **CurrentMeasurementModel**: Photocurrent measurement with automatic sensitivity adjustment
- **PhaseAdjustmentModel**: Automatic lock-in phase optimization
- **EQEExperimentModel**: Complete experiment orchestration

### Views (`views/`)
User interface components with no direct device access:
- **PlotWidgets**: Real-time data visualization (power, current, phase)
- **ControlWidgets**: Parameter input and measurement controls
- **MainView**: Application window coordination

## Installation

1. Clone or navigate to the project directory:
   ```powershell
   cd c:\Users\krbu4353\Github\PHYS-2150\eqe
   ```

2. Install dependencies:
   ```powershell
   pip install -r requirements.txt
   ```

3. Ensure hardware-specific libraries are available:
   - Thorlabs power meter drivers (TLPMX)
   - Cornerstone monochromator library
   - PicoSDK drivers (from Pico Technology website)
   - Appropriate VISA drivers for USB devices

## Usage

### Running the Application

**Normal Mode (with hardware):**
```powershell
python main.py
```

or as a module:
```powershell
python -m eqe.main
```

**Offline Mode (for GUI testing without hardware):**
```powershell
python main.py --offline
```

Perfect for testing the GUI when you're away from the lab! The application will start with simulated devices, allowing you to test UI changes, parameter validation, and file operations without requiring hardware connections. See [OFFLINE_MODE.md](OFFLINE_MODE.md) for complete details.

Note: Recent fixes in `main.py` make the entrypoint resilient when running
`python main.py` directly (it adjusts sys.path to allow package-qualified
imports). The preferred way when developing or installing is to run the
module with `python -m eqe.main`, but running `python main.py` will
also work for quick testing.

### Quick Start
1. Launch the application
2. Configure measurement parameters in the control panel
3. Connect devices (automatic device detection on startup)
4. Run power calibration measurement
5. Perform phase adjustment
6. Execute EQE measurement
7. Save results to CSV

## Device Configuration

Default settings are in `config/settings.py`. Modify device parameters as needed:

```python
DEVICE_CONFIGS = {
    DeviceType.PICOSCOPE_LOCKIN: {
        "default_chopper_freq": 81,    # Hz
        "default_num_cycles": 100,     # Integration cycles
        "correction_factor": 0.45,
    },
    # ... other device settings
}
```

## Features

- **Asynchronous Measurements**: Non-blocking device operations with progress tracking
- **Automatic Device Management**: Connection handling and error recovery
- **Real-time Visualization**: Live plotting of measurement data
- **Data Export**: CSV format compatible with analysis software
- **Error Handling**: Comprehensive error reporting and device status monitoring
- **Extensible Design**: Easy to add new devices or measurement types

## Benefits of MVC Architecture

1. **Maintainability**: Clear separation of concerns makes code easier to understand and modify
2. **Reusability**: Controllers can be used in different experiments or applications
3. **Testability**: Each component can be tested independently
4. **Flexibility**: Easy to swap devices or modify experiment workflows
5. **Scalability**: Simple to add new devices or measurement capabilities

## File Structure

```
eqe/
├── __init__.py           # Package initialization
├── main.py              # Application entry point
├── requirements.txt     # Dependencies
├── controllers/         # Device drivers
│   ├── __init__.py
│   ├── thorlabs_power_meter.py
│   ├── monochromator.py
│   └── picoscope_lockin.py
├── drivers/            # Low-level device drivers
│   ├── __init__.py
│   ├── cornerstone_mono.py
│   └── picoscope_driver.py
├── models/             # Experiment logic
│   ├── __init__.py
│   ├── power_measurement.py
│   ├── current_measurement.py
│   ├── phase_adjustment.py
│   └── eqe_experiment.py
├── views/              # User interface
│   ├── __init__.py
│   ├── plot_widgets.py
│   ├── control_widgets.py
│   └── main_view.py
├── config/             # Configuration
│   ├── __init__.py
│   └── settings.py
└── utils/              # Utilities
    ├── __init__.py
    ├── data_handling.py
    └── math_utils.py
```

Note: The TLPMX driver is now located in `common/drivers/` as shared infrastructure.

## Development

To extend the application:

1. **Add New Device**: Create controller in `controllers/`, follow existing patterns
2. **Add Measurement Type**: Implement model in `models/` with threading support
3. **Modify GUI**: Update views in `views/`, connect to models via signals
4. **Configuration**: Add settings to `config/settings.py`

## Troubleshooting

- **PicoScope Connection Issues**: 
  - Ensure PicoScope is connected via USB
  - Install PicoSDK drivers from Pico Technology website
  - Install Python package: `pip install picosdk`
  - Check that no other application is using the PicoScope
- **Import Errors**: Ensure all dependencies are installed via requirements.txt
- **GUI Issues**: Verify PySide6 installation and matplotlib backend compatibility
- **Low Signal Quality**: Check lamp is on, chopper is running at 81 Hz, and connections are secure

## Recent Changes (October 2025)

### PicoScope Integration
The application has been updated to use a PicoScope oscilloscope as a software lock-in amplifier, replacing the previous SR510 lock-in and Keithley 2110 combination. Key improvements:

- **Simplified Setup**: One device (PicoScope) instead of two (SR510 + Keithley)
- **Better Stability**: 0.66% CV through phase-locked acquisition
- **No Clipping**: ±20V input range handles all signal levels
- **Software Lock-in**: Hilbert transform for phase-independent magnitude measurement
- **Robust Averaging**: Trimmed mean rejects outliers from lamp flicker

See `PICOSCOPE_INTEGRATION.md` for detailed technical documentation.

## Original Application

This MVC implementation refactors the original monolithic application located at:
`c:\Users\krbu4353\Github\PHYS-2150\eqe\eqeguicombined-filters-pyside.py`

The new architecture maintains all original functionality while providing better code organization and maintainability.