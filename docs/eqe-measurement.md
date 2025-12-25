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

1. **Chopper** modulates the light at known frequency (81 Hz)
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
| Chopper | Optical chopper | Modulate light at 81 Hz |
| Monochromator | Newport Cornerstone 130 | Select wavelength |
| Reference detector | Thorlabs PM100D | Measure incident power |
| Test detector | Solar cell under test | Generate photocurrent |
| Signal acquisition | PicoScope 5242D | Software lock-in |

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

2. PHASE ADJUSTMENT (Optional)
   └── Optimizes lock-in phase

3. CURRENT MEASUREMENT (Solar cell)
   └── Measures photocurrent I(λ)

4. CALCULATE EQE
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
2. Scan wavelength range (e.g., 350-750 nm)
3. At each wavelength:
   - Wait for monochromator to settle
   - Record power reading
4. Save P(λ) data

**Output:** `YYYY_MM_DD_power_cell{N}.csv`

### Step 2: Phase Adjustment (Optional)

The lock-in extracts both magnitude (R) and phase (θ). While magnitude is phase-independent with our software lock-in, phase adjustment can optimize signal quality.

**When to use:**
- First measurement of the day
- After changing optical alignment
- If measurements seem noisy

**Procedure:**
1. Set monochromator to alignment wavelength (532 nm)
2. Place sample in beam
3. Run phase sweep (0° to 360°)
4. Software determines optimal phase

### Step 3: Current Measurement

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

### Step 4: EQE Calculation

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

All parameters are in `eqe/config/settings.py`:

### Wavelength Range

```python
DEFAULT_MEASUREMENT_PARAMS = {
    "start_wavelength": 350.0,  # nm
    "end_wavelength": 750.0,    # nm
    "step_size": 10.0,          # nm
}
```

### Lock-in Settings

```python
DEVICE_CONFIGS = {
    DeviceType.PICOSCOPE_LOCKIN: {
        "default_chopper_freq": 81,    # Hz
        "default_num_cycles": 100,     # Integration cycles
        "num_measurements": 5,         # Averages per point
        "correction_factor": 0.5,      # Validated via AWG testing
    }
}
```

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
    1: {"name": "400 nm filter", "wavelength_range": (420, 800)},
    2: {"name": "780 nm filter", "wavelength_range": (800, float('inf'))},
    3: {"name": "no filter", "wavelength_range": (0, 420)},
}
```

Filters prevent second-order diffraction from contaminating measurements.

## Performance Specifications

### Stability

- **Coefficient of Variation:** 0.66% (20 measurements)
- **Long-term drift:** <2% over 10 minutes
- **Target:** CV <10%
- **Result:** 15× better than target

### Acquisition Parameters

| Parameter | Value |
|-----------|-------|
| Sampling rate | 97,656 Hz |
| Samples per measurement | ~120,563 |
| Lock-in cycles | 100 |
| Measurements per point | 5 |
| Time per wavelength | ~6 seconds |

### Input Range

- **PicoScope range:** ±20V
- **Resolution:** 15-bit (2-channel mode)
- **No clipping** up to ±20V signals

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

```csv
Wavelength (nm),Power (W)
350.0,1.234e-6
360.0,1.456e-6
...
```

### Current Measurement File

Current measurements are saved in **nanoamps (nA)** with measurement statistics for uncertainty analysis:

```csv
Wavelength (nm),Current_mean (nA),Current_std (nA),n,CV_percent
350.0,4.24,1.78,5,42.0
400.0,24.60,2.52,5,10.2
550.0,276.00,2.21,5,0.8
...
```

| Column | Description |
|--------|-------------|
| `Current_mean (nA)` | Average of n lock-in measurements |
| `Current_std (nA)` | Standard deviation of measurements |
| `n` | Number of measurements averaged |
| `CV_percent` | Coefficient of variation (std/mean × 100) |

This format teaches students that **uncertainty is part of every measurement**, not separate from it. High CV% at band edge wavelengths (350nm, 750nm) is expected due to low signal-to-noise ratio.

> **Note:** Statistics export can be disabled in `eqe/config/settings.py` by setting `DATA_EXPORT_CONFIG["include_measurement_stats"] = False`, which reverts to a simpler two-column format.

### File Naming Convention

- Power: `YYYY_MM_DD_power_cell{N}.csv`
- Current: `YYYY_MM_DD_current_cell{N}_pixel{P}.csv`
- Phase: `YYYY_MM_DD_phase_cell{N}.csv`

## Code Structure

```
ui/
├── eqe.html                   # EQE web interface
├── css/                       # Stylesheets
└── js/                        # JavaScript modules

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
│   └── phase_adjustment.py    # Phase optimization
├── drivers/
│   └── picoscope_driver.py    # Low-level PicoScope SDK
└── config/
    └── settings.py            # All parameters
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

| Parameter | Default | Description |
|-----------|---------|-------------|
| Test Type | Current | Power test (lamp) or Current test (lock-in) |
| Wavelength | 550 nm | Fixed wavelength for all measurements |
| Duration | 5 min | Total test duration |
| Interval | 2 s | Time between measurements |
| Pixel # | 1 | Pixel number (current test only) |

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
- PicoScope 5000 Series Manual
