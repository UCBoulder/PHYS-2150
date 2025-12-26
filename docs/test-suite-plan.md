# Test Suite Implementation Plan for PHYS 2150

## Overview

Build a comprehensive test suite for the PHYS 2150 Measurement Suite with:
- Regression testing for CI/CD pipeline
- Realistic physics-based mock data for J-V curves and EQE spectra
- Phased implementation from quick wins to full coverage

## Current State

- **pytest configured** in `pyproject.toml` (`testpaths = ["tests"]`, `qt_api = "pyside6"`)
- **No `tests/` directory exists** - needs to be created
- **Dependencies ready**: `pytest>=7.0`, `pytest-qt>=4.2` already in dev dependencies
- **Offline mode exists** but only skips hardware init, doesn't generate mock data

---

## Test Directory Structure

```
tests/
├── conftest.py                      # Mock controllers, fixtures, data generators
├── unit/                            # Pure function tests (Phase 1)
│   ├── test_math_utils.py
│   ├── test_data_handling.py
│   ├── test_jv_voltage_array.py
│   └── test_statistics.py
├── models/                          # Business logic tests (Phase 2)
│   ├── jv/
│   │   ├── test_jv_experiment.py
│   │   └── test_jv_measurement.py
│   └── eqe/
│       ├── test_current_measurement.py
│       ├── test_power_measurement.py
│       └── test_phase_adjustment.py
├── integration/                     # End-to-end tests (Phase 3)
│   ├── test_jv_workflow.py
│   └── test_eqe_workflow.py
└── mocks/
    ├── mock_controllers.py          # Mock Keithley, PicoScope, Monochromator
    └── mock_data_generators.py      # Physics-based J-V, EQE data
```

---

## Implementation Phases

### Phase 1: Pure Function Tests (Quick Wins)

**Effort: LOW | Value: HIGH | No mocking required**

| File | Target | Key Tests |
|------|--------|-----------|
| `test_math_utils.py` | `eqe/utils/math_utils.py` | `MathUtils`: `fit_sine_wave()`, `calculate_r_squared()`, `find_optimal_phase()`, `moving_average()`, `calculate_statistics()`, `normalize_data()`; `CalibrationUtils`: `wavelength_to_energy()`, `energy_to_wavelength()` |
| `test_data_handling.py` | `eqe/utils/data_handling.py` | `DataHandler`: `validate_cell_number()`, `validate_pixel_number()`, `generate_filename()` |
| `test_jv_voltage_array.py` | `jv/models/jv_measurement.py` | `JVMeasurementModel.generate_voltage_array()` - inclusive endpoints, decimal rounding |
| `test_statistics.py` | `eqe/models/stability_test.py` | `StabilityTestModel.calculate_statistics()` - mean, std, CV%, range |

### Phase 2: Model Layer Tests (Mocked Controllers)

**Effort: MEDIUM | Value: HIGH**

| File | Target | Key Tests |
|------|--------|-----------|
| `test_jv_experiment.py` | `jv/models/jv_experiment.py` | `validate_parameters()` - cell number, pixel, voltage ranges |
| `test_current_measurement.py` | `eqe/models/current_measurement.py` | Filter switching at 420nm/800nm thresholds |
| `test_phase_adjustment.py` | `eqe/models/phase_adjustment.py` | R² threshold validation, phase calculation |

### Phase 3: Integration & CI/CD

**Effort: HIGH | Value: HIGH**

1. End-to-end J-V measurement workflow
2. End-to-end EQE measurement workflow
3. GitHub Actions workflow (`.github/workflows/test.yml`)
4. Coverage reporting

---

## Mock Data Strategy

### J-V Curves (Diode Equation)

Generate realistic solar cell I-V curves using the single-diode model:

```python
# Solar cell diode equation
J = J_ph - J_0 * (exp((V + J*R_s) / (n*V_t)) - 1) - (V + J*R_s) / R_sh

DEFAULT_PARAMS = {
    'jsc': 0.035,    # Short-circuit current (A) - typical 1cm² Si cell
    'voc': 1.1,      # Open-circuit voltage (V) - perovskite
    'n': 1.5,        # Ideality factor
    'rs': 0.5,       # Series resistance (Ohm)
    'rsh': 1000,     # Shunt resistance (Ohm)
    'vt': 0.026,     # Thermal voltage at 300K
}
```

Support for generating degraded cells, shunted cells, and various material types.

### EQE Spectra

Generate realistic EQE spectra with:
- **Bandgap absorption edge** (Si: 1.12 eV / 1107nm, Perovskite: 1.59 eV / 780nm)
- **UV absorption losses** - reduced response below 400nm
- **Thin-film interference fringes** - oscillations typical of thin absorbers
- **Configurable noise levels** for testing robustness

```python
# Silicon EQE model
energies = 1239.84 / wavelengths  # nm to eV
eqe = max_eqe * (1 - np.exp(-(energies - bandgap_ev) / 0.05))
```

---

## Key Files to Create

### Test Infrastructure

| File | Purpose |
|------|---------|
| `tests/conftest.py` | Mock controllers, shared fixtures, data generators |
| `tests/mocks/mock_controllers.py` | MockKeithley, MockPicoScope, MockMonochromator, MockPowerMeter |
| `tests/mocks/mock_data_generators.py` | JVDataGenerator, EQEDataGenerator classes |

### Unit Tests (Phase 1)

| File | Test Count | Target |
|------|------------|--------|
| `tests/unit/test_math_utils.py` | ~15 | MathUtils, SignalProcessing, CalibrationUtils |
| `tests/unit/test_data_handling.py` | ~10 | DataHandler validation functions |
| `tests/unit/test_jv_voltage_array.py` | ~6 | generate_voltage_array() edge cases |
| `tests/unit/test_statistics.py` | ~5 | calculate_statistics() |

### Model Tests (Phase 2)

| File | Test Count | Target |
|------|------------|--------|
| `tests/models/jv/test_jv_experiment.py` | ~8 | Parameter validation |
| `tests/models/eqe/test_current_measurement.py` | ~10 | Filter switching, measurement validation |
| `tests/models/eqe/test_phase_adjustment.py` | ~6 | R² validation, phase calculation |

### CI/CD (Phase 3)

| File | Purpose |
|------|---------|
| `.github/workflows/test.yml` | GitHub Actions for automated testing |

---

## conftest.py Fixture Design

```python
# tests/conftest.py

import pytest
import numpy as np
from unittest.mock import Mock

@pytest.fixture
def mock_keithley_controller():
    """
    Mock Keithley 2450 returning physics-based I-V data.
    Uses diode equation for realistic current responses.
    """
    controller = Mock()
    controller.is_connected.return_value = True
    # ... implementation with JVDataGenerator
    return controller

@pytest.fixture
def mock_picoscope_controller():
    """
    Mock PicoScope lock-in with configurable signal level.
    Returns realistic X, Y, R, theta with noise.
    """
    controller = Mock()
    controller.is_connected.return_value = True
    controller._signal_level = 0.1  # 100mV default
    # ... implementation
    return controller

@pytest.fixture
def mock_monochromator_controller():
    """
    Mock monochromator tracking wavelength, grating, filter, shutter state.
    Implements automatic filter/grating selection logic.
    """
    controller = Mock()
    controller._wavelength = 500.0
    controller._grating = 1
    controller._filter = 1
    controller._shutter_open = False
    # ... implementation
    return controller

@pytest.fixture
def mock_power_meter_controller():
    """
    Mock Thorlabs power meter returning lamp spectrum power.
    Wavelength-dependent based on Xe lamp model.
    """
    controller = Mock()
    # ... implementation with EQEDataGenerator.generate_lamp_spectrum()
    return controller

@pytest.fixture
def jv_data_generator():
    """Factory for generating realistic J-V curve data."""
    return JVDataGenerator()

@pytest.fixture
def eqe_data_generator():
    """Factory for generating realistic EQE spectral data."""
    return EQEDataGenerator()

@pytest.fixture
def valid_cell_params():
    """Standard valid measurement parameters."""
    return {
        'cell_number': '195',
        'pixel_number': 1,
        'start_voltage': -0.2,
        'stop_voltage': 1.5,
        'step_voltage': 0.02,
    }

@pytest.fixture
def sample_wavelength_range():
    """Standard EQE wavelength range."""
    return {'start': 350.0, 'end': 750.0, 'step': 10.0}
```

---

## GitHub Actions Workflow

```yaml
# .github/workflows/test.yml

name: Test Suite

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: windows-latest

    steps:
    - uses: actions/checkout@v4

    - name: Set up Python
      uses: actions/setup-python@v5
      with:
        python-version: '3.10'

    - name: Install uv
      run: pip install uv

    - name: Install dependencies
      run: uv sync --dev

    - name: Run linting
      run: |
        uv run ruff check .
        uv run ruff format --check .

    - name: Run unit tests
      run: uv run pytest tests/unit -v --tb=short

    - name: Run model tests
      run: uv run pytest tests/models -v --tb=short

    - name: Run integration tests
      run: uv run pytest tests/integration -v --tb=short

    - name: Generate coverage report
      run: |
        uv run pytest tests/ --cov=jv --cov=eqe --cov=common --cov-report=xml

    - name: Upload coverage to Codecov
      uses: codecov/codecov-action@v4
      with:
        file: ./coverage.xml
        fail_ci_if_error: false

  lint:
    runs-on: ubuntu-latest

    steps:
    - uses: actions/checkout@v4

    - name: Set up Python
      uses: actions/setup-python@v5
      with:
        python-version: '3.10'

    - name: Install ruff
      run: pip install ruff

    - name: Run ruff
      run: |
        ruff check .
        ruff format --check .
```

---

## pyproject.toml Updates

Add to existing `[tool.pytest.ini_options]`:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
qt_api = "pyside6"
addopts = "-v --tb=short"
markers = [
    "slow: marks tests as slow (deselect with '-m \"not slow\"')",
    "hardware: marks tests that require actual hardware",
]

[tool.coverage.run]
source = ["jv", "eqe", "common"]
omit = [
    "*/drivers/*",
    "*/__main__.py",
    "*/config/*",
]

[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "if __name__ == .__main__.:",
    "raise NotImplementedError",
]
```

---

## Execution Checklist

- [x] Create `tests/` directory structure
- [x] Write `tests/conftest.py` with mock controllers
- [ ] Write `tests/mocks/mock_data_generators.py` (not needed - physics in mock controllers)
- [x] **Phase 1**: Pure function tests (66 tests)
  - [x] `test_math_utils.py` (25 tests)
  - [x] `test_data_handling.py` (17 tests)
  - [x] `test_jv_voltage_array.py` (12 tests)
  - [x] `test_statistics.py` (12 tests)
- [x] **Phase 2**: Model layer tests (49 tests)
  - [x] `test_jv_experiment.py` (17 tests)
  - [x] `test_current_measurement.py` (16 tests)
  - [x] `test_phase_adjustment.py` (16 tests)
- [x] **Phase 3**: Integration & CI/CD (41 tests)
  - [x] `test_jv_workflow.py` (16 tests)
  - [x] `test_eqe_workflow.py` (25 tests)
  - [ ] `.github/workflows/test.yml` (skipped per user request)
- [x] Update `pyproject.toml` with coverage config
- [x] Verify all tests pass with `uv run pytest`

**Total: 156 tests passing with 23% code coverage**

---

## Critical Source Files Reference

| File | What to Test |
|------|--------------|
| `eqe/utils/math_utils.py` | MathUtils, SignalProcessing, CalibrationUtils pure functions |
| `eqe/utils/data_handling.py` | DataHandler.validate_cell_number(), validate_pixel_number(), generate_filename() |
| `eqe/models/current_measurement.py` | Filter switching at 420nm/800nm thresholds |
| `eqe/models/stability_test.py` | StabilityTestModel.calculate_statistics() |
| `eqe/models/phase_adjustment.py` | R² threshold validation, is_r_squared_acceptable() |
| `jv/models/jv_experiment.py` | JVExperimentModel.validate_parameters() |
| `jv/models/jv_measurement.py` | JVMeasurementModel.generate_voltage_array() |
