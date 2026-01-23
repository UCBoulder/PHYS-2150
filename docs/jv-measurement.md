# J-V Measurement Guide

This document explains the J-V (current density vs. voltage) measurement system, including the physics background, measurement workflow, and configuration options.

## Overview

J-V characterization is the primary method for evaluating solar cell performance. By sweeping voltage and measuring current under illumination, we extract key performance metrics:

| Parameter | Symbol | Description |
|-----------|--------|-------------|
| Open-circuit voltage | V_oc | Voltage at zero current |
| Short-circuit current | J_sc | Current density at zero voltage |
| Fill Factor | FF | Ratio of max power to V_oc × J_sc |
| Power Conversion Efficiency | PCE | Fraction of incident power converted to electricity |

## Physics Background

### The J-V Curve

Under illumination, a solar cell generates photocurrent. When a voltage is applied:

```
        Current
           ↑
           │     ←── Photocurrent (light-generated)
    Jsc ───┤━━━━━━━━●
           │        ┃
           │        ┃  ←── Operating region
           │        ┃
           │        ●━━━ Maximum Power Point (MPP)
           │        ┃
           │        ┃
           │        ●━━━━━━━━━━━━━━━━●──────→ Voltage
           │                        Voc
           │
```

The shape of this curve reveals:
- **Material quality** - Sharp "knee" indicates good diode behavior
- **Recombination losses** - Slope affects fill factor
- **Series/shunt resistance** - Distort the ideal curve shape

### Hysteresis in Perovskite Solar Cells

Perovskite solar cells often show different J-V curves depending on scan direction:

```
        Current
           ↑
           │    Forward scan ──→
    Jsc ───┤━━━━━━●
           │       ╲
           │        ╲  ←── Hysteresis gap
           │         ╲
           │          ●
           │           ╲
           │            ●━━━━━━━━━━━━━●──→ Voltage
           │              ←── Reverse scan
           │
```

**Causes of hysteresis:**
- Ion migration in the perovskite lattice
- Charge trapping at interfaces
- Capacitive effects

**Why we measure both directions:**
- Forward sweep: negative → positive voltage
- Reverse sweep: positive → negative voltage
- Comparing both reveals cell stability and ion migration effects

## Equipment

### Keithley 2450 Source Measure Unit

The Keithley 2450 is a precision instrument that can both source voltage and measure current simultaneously.

**Key specifications:**
- Voltage range: ±200V
- Current range: ±1A
- Measurement resolution: 6½ digits (1 µV, 10 pA)
- 4-wire sensing for accurate low-resistance measurements

**Connection diagram:**

```
┌─────────────────────────────────────────────┐
│              Keithley 2450                  │
├─────────────────────────────────────────────┤
│                                             │
│   HI ──────────●────────● Sense HI          │
│                │        │                   │
│                │        │                   │
│            ┌───┴────────┴───┐               │
│            │   Solar Cell   │               │
│            │      (+)       │               │
│            │                │               │
│            │      (-)       │               │
│            └───┬────────┬───┘               │
│                │        │                   │
│   LO ──────────●────────● Sense LO          │
│                                             │
└─────────────────────────────────────────────┘
```

**4-wire vs 2-wire sensing:**
- 2-wire: Current flows through same wires as voltage measurement (includes lead resistance)
- 4-wire: Separate wires for current and voltage (eliminates lead resistance error)

Always use 4-wire sensing for accurate J-V measurements.

## Measurement Workflow

### 1. Device Initialization

When the application starts:

1. Searches for Keithley 2450 via USB (VISA pattern configured in `defaults.json`)
2. Resets device to known state
3. Configures for voltage sourcing, current measurement
4. Enables 4-wire sensing

### 2. Cell/Pixel Selection

The system tracks which cell and pixel is being measured:

- **Cell number**: Letter + 2 digits (e.g., "A03", "R26")
- **Pixel number**: 1-8 (substrates have 8 individual pixels)

This information is embedded in the output filename for data organization.

### 3. Parameter Setup

Configure the voltage sweep (defaults are defined in `defaults.json`):

| Parameter | Description |
|-----------|-------------|
| Start voltage | Reverse bias starting point |
| Stop voltage | Forward bias endpoint |
| Step size | Voltage increment |

### 4. Measurement Sequence

```
1. Set initial voltage (start_voltage)
2. Wait for initial stabilization
3. FORWARD SWEEP:
   For each voltage from start → stop:
     a. Set voltage
     b. Wait source delay (device-native settling time)
     c. Take multiple current readings
     d. Calculate mean and standard deviation
     e. Record (V, I_mean, I_std, n) point
     f. Update plot

4. Wait inter-sweep delay

5. REVERSE SWEEP:
   For each voltage from stop → start:
     a. Set voltage
     b. Wait source delay
     c. Take multiple current readings
     d. Calculate mean and standard deviation
     e. Record (V, I_mean, I_std, n) point
     f. Update plot

6. Turn off output
7. Save data to CSV
```

Timing parameters (stabilization delays, source delay, number of measurements per point) are configured in `defaults.json`.

### 5. Data Export

Output CSV format (includes measurement statistics):

```csv
Voltage (V),Forward Scan (mA),Forward Std (mA),Forward n,Reverse Scan (mA),Reverse Std (mA),Reverse n
-0.20,12.450,0.012,10,12.480,0.015,10
-0.18,12.440,0.011,10,12.470,0.013,10
...
1.10,0.150,0.008,10,0.180,0.009,10
```

- **Std (mA)**: Standard deviation of the multiple measurements at each point
- **n**: Number of measurements averaged

Filename format: `YYYY_MM_DD_IV_cell{cell}_pixel{pixel}.csv`

Example: `2025_03_15_IV_cellA03_pixel3.csv`

## Configuration

All parameters are defined in `defaults.json` at the repository root. The file `jv/config/settings.py` re-exports these values for use in Python code.

### Measurement Timing

Key timing parameters in `defaults.json` under `jv.measurement`:

| Parameter | Description |
|-----------|-------------|
| `source_delay_s` | Device-native delay after voltage change before measuring |
| `initial_stabilization_s` | Stabilization time at start voltage before sweep begins |
| `inter_sweep_delay_s` | Pause between forward and reverse sweeps |
| `num_measurements` | Number of current readings averaged per voltage point |
| `nplc` | Integration time as Number of Power Line Cycles (at 60 Hz: NPLC 1 = 16.7ms) |

**Timing considerations:**
- Too short delays: Cell hasn't stabilized, noisy data
- Too long delays: Measurement takes excessively long
- Perovskites may need longer settling times due to ion migration

### Device Configuration

Key device parameters in `defaults.json` under `jv.device` and `jv.measurement`:

| Parameter | Description |
|-----------|-------------|
| `timeout_ms` | VISA communication timeout |
| `usb_id_pattern` | Device identifier for USB discovery |
| `voltage_range` | Voltage range in Volts (auto-ranges if exceeded) |
| `current_range` | Current range in mA |
| `current_compliance` | Safety limit in Amps |
| `remote_sensing` | Enable 4-wire sensing for accuracy |

### Validation Bounds

Physics-informed limits in `defaults.json` under `jv.validation.voltage_bounds` prevent obviously wrong parameters:

| Bound | Description |
|-------|-------------|
| `min_start` | Minimum allowed start voltage (extreme reverse bias) |
| `max_stop` | Maximum allowed stop voltage (extreme forward bias) |
| `min_step` | Minimum voltage step resolution |
| `max_step` | Maximum voltage step size |

## Interpreting Results

### Typical J-V Curve Shapes

**Healthy cell:**
- Sharp transition at V_oc
- Flat current plateau near J_sc
- Square-ish corner (high fill factor)

**Shunted cell:**
- Current decreases toward V_oc (slope in plateau)
- Low V_oc
- Indicates current leakage paths

**High series resistance:**
- Curved transition at V_oc
- Reduced fill factor
- May indicate poor contacts

### Hysteresis Analysis

Compare forward and reverse sweeps:

- **Minimal hysteresis**: Curves nearly overlap - stable cell
- **Moderate hysteresis**: 5-10% difference - typical for perovskites
- **Severe hysteresis**: >20% difference - may indicate degradation or measurement issues

## Troubleshooting

### Device Not Found

```
Keithley 2450 device not found.
```

**Solutions:**
1. Check USB cable connection
2. Verify device is powered on
3. Open NI MAX to confirm VISA detection
4. Try different USB port

### Unstable Readings

**Symptoms:** Noisy current measurements, inconsistent values

**Solutions:**
1. Increase `num_measurements` for more averaging
2. Check probe contacts
3. Shield from light fluctuations
4. Verify 4-wire connections

### Compliance Reached

**Symptoms:** Current readings plateau unexpectedly

**Cause:** Cell current exceeds safety limit

**Solution:** Increase current compliance (carefully) or reduce illumination

## Best Practices

### Before Measurement

1. **Warm up illumination source** (15+ minutes)
2. **Verify cell position** under illumination
3. **Clean contacts** if necessary
4. **Check cable connections**

### During Measurement

1. **Don't disturb setup** - vibrations affect readings
2. **Maintain stable temperature**
3. **Shield from ambient light changes**

### After Measurement

1. **Review data** for obvious problems
2. **Compare forward/reverse** sweeps
3. **Archive raw data** with metadata

## Code Structure

```
defaults.json               # All configuration parameters (single source of truth)

ui/
├── jv.html                 # J-V web interface
├── css/                    # Stylesheets
└── js/                     # JavaScript modules

jv/
├── web_main.py             # Qt WebEngine app, Python-JS bridge
├── controllers/
│   └── keithley_2450.py    # SCPI communication
├── models/
│   ├── jv_experiment.py    # Experiment orchestration
│   ├── jv_measurement.py   # Sweep logic
│   └── jv_stability_test.py # Stability test at fixed voltage
├── config/
│   └── settings.py         # Re-exports from defaults.json
└── utils/
    └── data_export.py      # CSV handling
```

See [architecture.md](architecture.md) for details on the MVC pattern.

## References

- Keithley 2450 User Manual
- "Solar Cells: Operating Principles, Technology and System Applications" - Green
- "Perovskite Solar Cells" - Park et al.
