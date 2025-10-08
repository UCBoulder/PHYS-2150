# EQE Measurement Application - MVC Architecture

A professional implementation of External Quantum Efficiency (EQE) measurements for solar cell characterization, built using the Model-View-Controller (MVC) design pattern.

## Overview

This application provides a clean, maintainable solution for EQE measurements by separating device control, experiment logic, and user interface concerns into distinct, reusable components.

## Architecture

### Controllers (`controllers/`)
Device drivers that handle low-level hardware communication:
- **ThorlabsPowerMeterController**: Power measurements and wavelength calibration
- **Keithley2110Controller**: Voltage and current measurements via VISA
- **MonochromatorController**: Wavelength selection and filter management
- **SR510Controller**: Lock-in amplifier control for photocurrent measurements

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
   cd c:\Users\krbu4353\Github\PHYS-2150\eqe_mvc
   ```

2. Install dependencies:
   ```powershell
   pip install -r requirements.txt
   ```

3. Ensure hardware-specific libraries are available:
   - Thorlabs power meter drivers (TLPMX)
   - Cornerstone monochromator library
   - Appropriate VISA drivers for Keithley instruments

## Usage

### Running the Application
```powershell
python main.py
```

or as a module:
```powershell
python -m eqe_mvc.main
```

### Quick Start
1. Launch the application
2. Configure measurement parameters in the control panel
3. Connect devices (automatic device detection on startup)
4. Run power calibration measurement
5. Perform phase adjustment
6. Execute EQE measurement
7. Save results to CSV

## Device Configuration

Default settings are in `config/settings.py`. Modify device addresses and parameters as needed:

```python
DEVICE_CONFIG = {
    'keithley_address': 'USB0::0x05E6::0x2110::9203835::INSTR',
    'sr510_port': 'COM3',
    'sr510_baudrate': 9600,
    # ... other settings
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
eqe_mvc/
├── __init__.py           # Package initialization
├── main.py              # Application entry point
├── requirements.txt     # Dependencies
├── controllers/         # Device drivers
│   ├── __init__.py
│   ├── thorlabs_power_meter.py
│   ├── keithley_2110.py
│   ├── monochromator.py
│   └── sr510_lockin.py
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

## Development

To extend the application:

1. **Add New Device**: Create controller in `controllers/`, follow existing patterns
2. **Add Measurement Type**: Implement model in `models/` with threading support
3. **Modify GUI**: Update views in `views/`, connect to models via signals
4. **Configuration**: Add settings to `config/settings.py`

## Troubleshooting

- **Device Connection Issues**: Check VISA addresses and COM ports in settings
- **Import Errors**: Ensure all dependencies are installed via requirements.txt
- **GUI Issues**: Verify PySide6 installation and matplotlib backend compatibility

## Original Application

This MVC implementation refactors the original monolithic application located at:
`c:\Users\krbu4353\Github\PHYS-2150\eqe\eqeguicombined-filters-pyside.py`

The new architecture maintains all original functionality while providing better code organization and maintainability.