# Architecture Guide

This document explains the Model-View-Controller (MVC) architecture used in the PHYS 2150 Measurement Suite and how it applies to laboratory instrumentation software.

## Why MVC for Lab Software?

Laboratory software has three distinct concerns:

1. **Hardware Communication** - Talking to instruments
2. **Experiment Logic** - What measurements to take and when
3. **User Interface** - How users interact with the system

The MVC pattern separates these concerns, making code:

- **Reusable** - Swap hardware without changing experiment logic
- **Testable** - Test GUI without physical hardware (`--offline` mode)
- **Maintainable** - Clear organization for future developers

## The Three Layers

```
┌─────────────────────────────────────────────────────────────┐
│                         VIEW                                │
│    PySide6 GUI - buttons, plots, status displays            │
│    (Never talks to hardware directly)                       │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                         MODEL                               │
│    Experiment logic - measurement workflows, data handling  │
│    (Orchestrates controllers, provides clean API to View)   │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                       CONTROLLER                            │
│    Device drivers - SCPI commands, SDK calls                │
│    (Reflects exactly what hardware does)                    │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                        HARDWARE                             │
│    Keithley 2450, PicoScope, Power Meter, Monochromator     │
└─────────────────────────────────────────────────────────────┘
```

### Controller Layer

**Purpose:** Communicate with hardware - nothing more.

Controllers reflect exactly what a device can do. They handle:

- VISA/SCPI communication
- SDK function calls
- Data type conversion
- Error handling for communication failures

**Key principle:** Controllers contain NO experiment logic. If you want to do a voltage sweep, that logic belongs in the Model, not the Controller.

**Examples:**

```python
# jv/controllers/keithley_2450.py
class Keithley2450Controller:
    def set_voltage(self, voltage: float) -> None:
        """Set source voltage (SCPI command)."""
        self.write(f"SOUR:VOLT {voltage}")

    def measure_current(self) -> float:
        """Measure current (SCPI query)."""
        return float(self.query("MEAS:CURR?"))

    def output_on(self) -> None:
        """Enable output."""
        self.write("OUTP ON")
```

Notice: No loops, no sweep logic, no data storage - just device commands.

### Model Layer

**Purpose:** Experiment logic and workflow orchestration.

Models define how measurements are performed:

- What sequence of operations to execute
- How to process acquired data
- Parameter validation
- Coordination between multiple controllers

**Key principle:** Models provide a clean, stable API for the View. If hardware changes, the Model adapts internally while keeping the same interface.

**Examples:**

```python
# jv/models/jv_measurement.py
class JVMeasurement:
    def perform_sweep(self, start_v, end_v, step_v) -> SweepResult:
        """Perform voltage sweep - this is experiment logic."""
        voltages = []
        currents = []

        for voltage in self._generate_voltages(start_v, end_v, step_v):
            self.controller.set_voltage(voltage)
            time.sleep(self.dwell_time)
            current = self.controller.measure_current()
            voltages.append(voltage)
            currents.append(current)

        return SweepResult(voltages, currents)
```

The sweep logic lives in the Model, using the Controller for individual operations.

### View Layer

**Purpose:** User interface - display data, accept input.

Views handle:

- GUI layout and styling
- User input validation (basic)
- Real-time data visualization
- Status updates and progress indication

**Key principle:** Views NEVER access Controllers directly. All hardware interaction goes through Models.

**Examples:**

```python
# jv/views/main_window.py
class JVMainWindow(QMainWindow):
    def __init__(self):
        # Set up GUI components
        self.start_button.clicked.connect(self._on_start_clicked)

    def _on_start_clicked(self):
        # Get parameters from GUI
        params = self.controls_panel.get_parameters()

        # Call Model (not Controller!)
        self.experiment_model.start_measurement(params)

    def _on_measurement_complete(self, result):
        # Update GUI with results
        self.plot_widget.update_plot(result)
```

## Project Structure

```
PHYS-2150/
├── common/                      # Shared across applications
│   ├── drivers/                # Hardware drivers (e.g., TLPMX.py)
│   ├── ui/                     # Shared GUI components
│   └── utils/                  # Logging, data export
│
├── jv/                          # J-V Measurement Application
│   ├── controllers/
│   │   └── keithley_2450.py   # Keithley SMU communication
│   ├── models/
│   │   ├── jv_experiment.py   # Experiment orchestration
│   │   └── jv_measurement.py  # Sweep logic
│   ├── views/
│   │   ├── main_window.py     # Main GUI
│   │   ├── plot_widget.py     # J-V curve display
│   │   └── controls_panel.py  # Parameter input
│   └── config/
│       └── settings.py        # Measurement parameters
│
├── eqe/                         # EQE Measurement Application
│   ├── controllers/
│   │   ├── picoscope_lockin.py    # Lock-in controller
│   │   ├── monochromator.py       # Wavelength control
│   │   └── power_meter.py         # Reference power
│   ├── models/
│   │   ├── eqe_experiment.py      # Experiment orchestration
│   │   ├── current_measurement.py # Lock-in measurement
│   │   └── power_measurement.py   # Reference calibration
│   ├── views/
│   │   ├── main_view.py           # Main GUI
│   │   └── plot_widgets.py        # EQE plots
│   ├── drivers/
│   │   └── picoscope_driver.py    # Low-level SDK interface
│   └── config/
│       └── settings.py
│
└── launcher.py                  # Application selector
```

## Data Flow Example: J-V Measurement

```
User clicks "Start Measurement"
         │
         ▼
┌─────────────────────────────────────┐
│ VIEW: main_window.py                │
│ - Validates GUI inputs              │
│ - Calls experiment_model.start()    │
└─────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│ MODEL: jv_experiment.py             │
│ - Configures measurement parameters │
│ - Calls jv_measurement.perform()    │
│ - Handles data saving               │
└─────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│ MODEL: jv_measurement.py            │
│ - Implements sweep logic            │
│ - Calls controller methods          │
│ - Returns measurement result        │
└─────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│ CONTROLLER: keithley_2450.py        │
│ - Sends SCPI commands               │
│ - Returns raw measurements          │
└─────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│ HARDWARE: Keithley 2450             │
│ - Sets voltage                      │
│ - Measures current                  │
└─────────────────────────────────────┘
```

## Benefits in Practice

### Swapping Hardware

If you replace the Keithley 2450 with a different SMU:

1. Create new controller: `new_smu.py`
2. Implement same interface: `set_voltage()`, `measure_current()`, etc.
3. Update Model to use new controller
4. **View remains unchanged**

### Offline Testing

The `--offline` mode works because:

1. Controllers can be replaced with mock objects
2. Models work with any object implementing the controller interface
3. Views only see Model results, not hardware

```bash
python -m jv --offline  # Test GUI without Keithley connected
```

### Adding New Measurements

To add a new measurement type (e.g., stability test):

1. Create new Model class with measurement logic
2. Connect to existing View or create new tab
3. Reuse existing Controllers

## Configuration Layer

Measurement parameters live in `config/settings.py`:

```python
# jv/config/settings.py
MEASUREMENT_CONFIG = {
    "voltage_start": -0.2,
    "voltage_end": 1.2,
    "voltage_step": 0.02,
    "dwell_time_ms": 100,
}
```

This separation means:

- Parameters can be changed without modifying code
- Future: Could load from config file or GUI presets
- Clear documentation of all tunable values

## Threading and Responsiveness

Long measurements run in background threads:

```python
# Model runs measurement in QThread
class MeasurementWorker(QObject):
    progress = Signal(float)
    complete = Signal(object)

    def run(self):
        result = self.model.perform_measurement()
        self.complete.emit(result)

# View stays responsive
worker = MeasurementWorker(self.model)
worker.complete.connect(self._on_complete)
thread.start()
```

This keeps the GUI responsive during measurements.

## Further Reading

- [developer-setup.md](developer-setup.md) - Development environment
- [hardware-setup.md](hardware-setup.md) - Hardware configuration
- [jv-measurement.md](jv-measurement.md) - J-V measurement details
- [eqe-measurement.md](eqe-measurement.md) - EQE measurement details
