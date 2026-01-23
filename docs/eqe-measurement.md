# EQE Measurement Guide

This document explains the External Quantum Efficiency (EQE) measurement system, including the physics background, measurement workflow, and configuration options.

## Overview

EQE measures the spectral response of a solar cell - what fraction of incident photons at each wavelength are converted to collected electrons.

```
                    Number of collected electrons
EQE(λ) = ─────────────────────────────────────────────
                Number of incident photons
```

This reveals:
- **Bandgap** - Where absorption begins
- **Collection efficiency** - How well carriers are extracted
- **Optical losses** - Reflection, parasitic absorption
- **Material quality** - Defects that reduce carrier collection

## Physics Background

### The EQE Spectrum

A typical silicon solar cell EQE spectrum:

```
    EQE (%)
       ↑
  100 ─┤          ┌──────────────┐
       │         /                \
   80 ─┤        /                  \
       │       /                    \
   60 ─┤      /                      \
       │     /                        \
   40 ─┤    /                          \
       │   /                            \
   20 ─┤  /                              \
       │ /                                \
    0 ─┼───┬───┬───┬───┬───┬───┬───┬───┬──→ Wavelength (nm)
         400 500 600 700 800 900 1000 1100
```

**Key features:**
- **Blue response (400-500 nm)**: Surface recombination effects
- **Green response (500-600 nm)**: Typically highest EQE
- **Red response (600-800 nm)**: Bulk material quality
- **Near-IR cutoff (~1100 nm for Si)**: Bandgap determines absorption edge

### Lock-in Measurement

The solar cell produces a very small AC signal buried in noise. Lock-in detection extracts this signal:

1. **Chopper** modulates the light at a known frequency (configured in `defaults.json`)
2. **Solar cell** produces AC current at chopper frequency
3. **Lock-in amplifier** multiplies signal by reference, filters noise
4. **Result**: Only signal at chopper frequency remains

```
Light source ──► Chopper ──► Monochromator ──► Sample ──► Lock-in ──► Computer
                    │                                        ↑
                    └──────── Reference signal ──────────────┘
```

Our system uses a **software lock-in** implemented on PicoScope - no external lock-in amplifier needed. See [software-lockin.md](software-lockin.md) for details.

## Equipment

### System Components

| Component | Model | Purpose |
|-----------|-------|---------|
| Light source | Xenon arc lamp | Broadband illumination |
| Chopper | Optical chopper | Modulate light at configured frequency |
| Monochromator | Newport Cornerstone 130 | Select wavelength |
| Reference detector | Thorlabs PM100D | Measure incident power |
| Test detector | Solar cell under test | Generate photocurrent |
| Signal acquisition | PicoScope 2204A or 5242D | Software lock-in |

### Connection Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                       EQE System Layout                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   ┌────────┐    ┌─────────┐    ┌──────────────┐                │
│   │  Lamp  │───►│ Chopper │───►│Monochromator │                │
│   └────────┘    └────┬────┘    └──────┬───────┘                │
│                      │                 │                        │
│              TTL Reference        Wavelength-                   │
│                      │           selected light                 │
│                      │                 │                        │
│                      │          ┌──────┴──────┐                 │
│                      │          │             │                 │
│                      │          ▼             ▼                 │
│                      │    ┌──────────┐  ┌──────────┐           │
│                      │    │Reference │  │  Solar   │           │
│                      │    │Power     │  │  Cell    │           │
│                      │    │Meter     │  │          │           │
│                      │    └────┬─────┘  └────┬─────┘           │
│                      │         │             │                  │
│                      │         │USB       Preamp                │
│                      │         │             │                  │
│                      │         ▼             ▼                  │
│                      │    ┌──────────────────────┐              │
│                      └───►│     PicoScope        │              │
│                           │  CH A: Signal        │              │
│                           │  CH B: Reference     │              │
│                           └──────────┬───────────┘              │
│                                      │ USB                      │
│                                      ▼                          │
│                              ┌──────────────┐                   │
│                              │   Computer   │                   │
│                              └──────────────┘                   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## GUI Controls

### Manual Monochromator Controls

The EQE application includes manual monochromator controls for alignment and troubleshooting:

| Control | Function |
|---------|----------|
| **Wavelength** | Set monochromator to specific wavelength (auto-selects grating and filter) |
| **Go Button** | Apply wavelength setting |
| **Shutter Open/Close** | Control monochromator shutter for beam blocking |
| **Filter Status** | Display current filter position (1, 2, or 3) |

These controls are useful for:
- Initial optical alignment
- Checking beam position at specific wavelengths
- Troubleshooting without running full scans

### Live Signal Monitor

The **Live Signal Monitor** displays real-time photocurrent readings from the lock-in amplifier. This is essential for:

- **Beam alignment** - Maximize signal by adjusting sample position
- **Signal verification** - Confirm the system is working before scanning
- **Troubleshooting** - Identify noise or instability issues

The monitor shows:
- Current reading in nanoamps (nA)
- Update rate synchronized with lock-in measurements

### Green Dot Alignment

The **Green Dot** button (in the Monochromator Controls panel) sets the monochromator to 532 nm - a visible wavelength useful for optical alignment. Combined with the Live Signal Monitor, this allows precise positioning of samples.

## Measurement Workflow

### Complete EQE Measurement Process

```
1. POWER CALIBRATION (Reference detector)
   └── Measures lamp spectrum P(λ)

2. CURRENT MEASUREMENT (Solar cell)
   └── Validates chopper, then measures photocurrent I(λ)

3. CALCULATE EQE
   └── EQE(λ) = (I/q) / (P/E_photon)
```

### Step 1: Power Calibration

Measures the incident optical power at each wavelength using a calibrated reference detector.

**Purpose:**
- Characterize lamp spectrum
- Account for monochromator efficiency
- Normalize current measurements

**Procedure:**
1. Position reference detector in beam
2. Scan the configured wavelength range
3. At each wavelength:
   - Wait for monochromator to settle
   - Record power reading
4. Save P(λ) data

**Output:** `YYYY_MM_DD_power_cell{N}.csv`

### Step 2: Current Measurement

Measures the photocurrent from the solar cell at each wavelength.

**Procedure:**
1. Position solar cell in beam
2. Scan same wavelength range as power calibration
3. At each wavelength:
   - Wait for monochromator to settle
   - Perform lock-in measurement
   - Average multiple readings
4. Save I(λ) data

**Output:** `YYYY_MM_DD_current_cell{N}_pixel{P}.csv`

### Step 3: EQE Calculation

```
         I(λ) / q          I(λ) × hc
EQE(λ) = ────────── = ──────────────────
         P(λ) / Eₚ      P(λ) × λ × q
```

Where:
- I(λ) = measured photocurrent (A)
- P(λ) = measured power (W)
- q = electron charge (1.602 × 10⁻¹⁹ C)
- h = Planck's constant (6.626 × 10⁻³⁴ J·s)
- c = speed of light (3 × 10⁸ m/s)
- λ = wavelength (m)

## Configuration

All parameters are defined in `defaults.json` (the single source of truth) and re-exported via `eqe/config/settings.py` for backward compatibility. See [CLAUDE.md](../CLAUDE.md) for the configuration architecture.

### Wavelength Range

```python
DEFAULT_MEASUREMENT_PARAMS = {
    "start_wavelength": ...,  # nm (see defaults.json)
    "end_wavelength": ...,    # nm (see defaults.json)
    "step_size": ...,         # nm (see defaults.json)
}
```

> **Note:** Default values are defined in `defaults.json` under `eqe.defaults` and may change between semesters.

### Lock-in Settings

```python
DEVICE_CONFIGS = {
    DeviceType.PICOSCOPE_LOCKIN: {
        "default_chopper_freq": ...,   # Hz (must match physical chopper)
        "default_num_cycles": ...,     # Integration cycles
        "num_measurements": ...,       # Averages per point
        "correction_factor": 0.5,      # Validated via AWG testing (don't change)
    }
}
```

> **Note:** Device settings are in `defaults.json` under `eqe.devices.picoscope_lockin`. The correction factor (0.5) is validated and should not be changed without re-validation.

See [software-lockin.md](software-lockin.md) for details on the correction factor and validation.

### Measurement Averaging

```python
CURRENT_MEASUREMENT_CONFIG = {
    "num_measurements": 5,         # Measurements to average
    "transimpedance_gain": 1e-6,   # Preamp gain (1 MΩ)
    "stabilization_time": 0.2,     # Wait after wavelength change
}
```

### Filter Configuration

The monochromator uses order-sorting filters:

```python
FILTER_CONFIG = {
    1: {"name": "400 nm filter", "wavelength_range": (threshold_lower, threshold_upper)},
    2: {"name": "780 nm filter", "wavelength_range": (threshold_upper, infinity)},
    3: {"name": "no filter", "wavelength_range": (0, threshold_lower)},
}
```

Filter thresholds are configured in `defaults.json` under `eqe.filter.threshold_lower` and `eqe.filter.threshold_upper`. Filters prevent second-order diffraction from contaminating measurements.

## Performance Specifications

### Stability

- **Coefficient of Variation:** 0.66% (20 measurements)
- **Long-term drift:** <2% over 10 minutes
- **Target:** CV <10%
- **Result:** 15× better than target

### Acquisition Parameters

The system supports two PicoScope models with different characteristics:

| Parameter | PicoScope 5242D | PicoScope 2204A |
|-----------|-----------------|-----------------|
| Sampling rate | 97,656 Hz | ~24 kHz (dynamic) |
| Signal input range | ±20V | ±2V |
| Reference input range | ±20V | ±5V |
| Resolution | 15-bit | 8-bit |
| Buffer size | 200,000 samples | 2,000 samples |

| Parameter | Source |
|-----------|--------|
| Lock-in cycles | `eqe.devices.picoscope_lockin.default_num_cycles` |
| Measurements per point | `eqe.devices.picoscope_lockin.num_measurements` |

### Input Range

**PicoScope 5242D:**
- Signal & reference range: ±20V
- Resolution: 15-bit (2-channel mode)
- No clipping up to ±20V signals

**PicoScope 2204A:**
- Signal range: ±2V (optimized for TIA output)
- Reference range: ±5V (for TTL chopper signal)
- Resolution: 8-bit
- Dynamic timebase adjustment for optimal cycles/samples tradeoff

## Troubleshooting

### Low Signal

**Symptoms:** Current readings near zero

**Checks:**
1. Lamp on and warmed up?
2. Chopper running?
3. Beam aligned with detector?
4. Correct wavelength range?

### High Noise (CV > 10%)

**Symptoms:** Inconsistent readings

**Checks:**
1. Reference signal clean square wave?
2. Trigger threshold correct (2.5V)?
3. All cables secure?
4. Chopper speed stable?

### EQE > 100%

**Symptoms:** Physically impossible results

**Causes:**
1. Power calibration at different position
2. Stray light during current measurement
3. Wrong transimpedance gain in config
4. Data file mismatch

### Monochromator Not Responding

**Checks:**
1. USB-to-Serial adapter connected
2. Correct COM port selected
3. Newport drivers installed

See [TROUBLESHOOTING.md](../TROUBLESHOOTING.md) for comprehensive troubleshooting guide.

## Data Files

### Power Calibration File

Power measurements are saved in **microwatts (µW)** with optional statistics:

```csv
Wavelength (nm),Power_mean (uW),Power_std (uW),n
350.0,1.234,0.045,200
360.0,1.456,0.052,200
...
```

Or in simple format (when statistics are disabled):

```csv
Wavelength (nm),Power (uW)
350.0,1.234
360.0,1.456
...
```

### Current Measurement File

Current measurements are saved in **nanoamps (nA)** with measurement statistics for uncertainty analysis:

```csv
Wavelength (nm),Current_mean (nA),Current_std (nA),n
350.0,4.240,1.780,5
400.0,24.600,2.520,5
550.0,276.000,2.210,5
...
```

| Column | Description |
|--------|-------------|
| `Current_mean (nA)` | Average of n lock-in measurements |
| `Current_std (nA)` | Standard deviation of measurements |
| `n` | Number of measurements averaged |

This format teaches students that **uncertainty is part of every measurement**, not separate from it. High standard deviation at band edge wavelengths (near the start and end of the scan range) is expected due to low signal-to-noise ratio.

> **Note:** Statistics export can be disabled in `defaults.json` by setting `eqe.export.include_measurement_stats` to `false`, which reverts to a simpler two-column format.

### File Naming Convention

- Power: `YYYY_MM_DD_power_cell{N}.csv`
- Current: `YYYY_MM_DD_current_cell{N}_pixel{P}.csv`
- Phase: `YYYY_MM_DD_phase_cell{N}.csv`

## Code Structure

```
ui/
├── eqe.html                   # EQE web interface
├── css/                       # Stylesheets
│   ├── theme.css              # Color themes
│   ├── components.css         # Reusable components
│   └── eqe-layout.css         # EQE-specific layout
└── js/                        # JavaScript modules
    ├── eqe-app.js             # Main application logic
    ├── config.js              # Configuration loader
    └── plotly-utils.js        # Plot helpers

eqe/
├── web_main.py                # Qt WebEngine app, Python-JS bridge
├── controllers/
│   ├── picoscope_lockin.py    # Lock-in controller
│   ├── monochromator.py       # Newport Cornerstone
│   └── thorlabs_power_meter.py # Reference detector
├── models/
│   ├── eqe_experiment.py      # Experiment orchestration
│   ├── current_measurement.py # Lock-in measurements
│   ├── power_measurement.py   # Power calibration
│   ├── phase_adjustment.py    # Phase optimization
│   └── stability_test.py      # Stability test model
├── drivers/
│   └── picoscope_driver.py    # Low-level PicoScope SDK (2204A & 5242D)
├── utils/
│   └── data_handling.py       # CSV export and validation
└── config/
    └── settings.py            # Re-exports from defaults.json
```

See [architecture.md](architecture.md) for MVC pattern details.
See [software-lockin.md](software-lockin.md) for lock-in implementation details.

## Stability Test

The EQE application includes a built-in stability test for validating system performance and troubleshooting measurement issues.

### Purpose

The stability test measures power or current at a fixed wavelength over time to assess:

- **Lamp stability** - Is the light source output consistent?
- **Lock-in performance** - Is the software lock-in providing stable readings?
- **System drift** - Are measurements drifting over the test duration?
- **Coefficient of variation (CV)** - Overall measurement precision

### Accessing the Stability Test

The stability test is available as a separate tab in the EQE application GUI.

### Test Parameters

| Parameter | Description |
|-----------|-------------|
| Test Type | Power test (lamp) or Current test (lock-in) |
| Wavelength | Fixed wavelength for all measurements (see `eqe.stability_test.default_wavelength`) |
| Duration | Total test duration (see `eqe.stability_test.default_duration_min`) |
| Interval | Time between measurements (see `eqe.stability_test.default_interval_sec`) |
| Pixel # | Pixel number (current test only) |

### Interpreting Results

The stability test displays real-time statistics:

| Metric | Good | Warning | Poor |
|--------|------|---------|------|
| CV (Coefficient of Variation) | <1% | 1-3% | >3% |

**CV interpretation:**
- **<1% (green)**: Excellent stability - system is performing optimally
- **1-3% (orange)**: Acceptable - may indicate minor issues
- **>3% (red)**: Poor stability - troubleshooting needed

### Output

Results are displayed as:
- **Time series plot**: Measurement values vs. time with mean and ±1σ bands
- **Histogram**: Distribution of measured values
- **Statistics**: Mean, std dev, CV%, count, range

Results can be saved to CSV with the "Save Results" button. A PNG plot is also saved automatically.

### When to Use

Run a stability test when:
- Setting up the system for the first time
- After optical realignment
- If EQE measurements seem noisy or inconsistent
- To validate system performance (target: CV <1%)

---

## Best Practices

### Before Measurement

1. **Warm up lamp** (15+ minutes)
2. **Verify chopper frequency** matches config
3. **Check optical alignment**
4. **Run stability test** if uncertain

### During Measurement

1. **Don't disturb optical setup**
2. **Monitor for stray light**
3. **Watch for saturation** (signal near limits)

### After Measurement

1. **Compare power and current** wavelength ranges
2. **Check EQE values** are reasonable (0-100%)
3. **Archive raw data** before calculating EQE

## References

- "Solar Cell Device Physics" - Fonash
- Thorlabs PM100D Manual
- Newport Cornerstone 130 Manual
- PicoScope 5000 Series Programmer's Guide
- PicoScope 2000 Series Programmer's Guide
