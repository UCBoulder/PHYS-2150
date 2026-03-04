# Stability Testing Guide

## Overview

The `test_stability.py` script tests the stability of power and current measurements over time using the **exact same models and methods** as the main EQE application. This ensures that test results directly reflect the stability of actual measurements.

**Note**: Power and current measurements require different hardware setups and must be tested separately. You cannot run both in a single test session.

## Purpose

Use this test to:
- **Diagnose measurement variability** - Identify if variations are from hardware, environment, or software
- **Optimize settings** - Test different `num_measurements` and `stabilization_time` values
- **Validate stability** - Ensure measurements are repeatable before running full EQE scans
- **Troubleshoot issues** - Isolate problems (lamp flicker, chopper stability, detector noise, etc.)

## Hardware Requirements

### Power Test Setup
- **Detector**: Thorlabs power meter connected to monochromator output
- **Use case**: Testing lamp stability and monochromator reproducibility
- **Setup time**: Align power meter to monochromator output port

### Current Test Setup
- **Detector**: Photocell connected to PicoScope lock-in amplifier
- **Use case**: Testing actual EQE measurement stability (chopper, lock-in, photocell)
- **Setup time**: Position photocell in light path with chopper active

**You must change hardware configuration between power and current tests.**

## Features

- ✅ Uses the same measurement models as the main application
- ✅ Tests at a fixed wavelength over extended time periods
- ✅ Provides real-time statistics (mean, std dev, CV%)
- ✅ Saves results to CSV with metadata
- ✅ Generates plots showing time series and distribution
- ✅ Supports power and current measurements (run separately)

## Usage

**Important**: Run the script from the `eqe` directory:
```bash
cd eqe
python test_stability.py [options]
```

### Basic Usage (Current Test)

Test current stability for 5 minutes at 550 nm (default):
```bash
cd eqe
python test_stability.py
```

### Test Power Stability

```bash
cd eqe
python test_stability.py --test-type power --wavelength 550 --duration 5 --interval 2
```

### Test Current Stability

```bash
cd eqe
python test_stability.py --test-type current --wavelength 550 --duration 5 --interval 2 --pixel 1
```

### Longer Test with Faster Sampling

Test for 10 minutes with 1-second intervals:
```bash
cd eqe
python test_stability.py --duration 10 --interval 1
```

### Custom Wavelength

Test at 700 nm (near band edge):
```bash
cd eqe
python test_stability.py --wavelength 700 --duration 5
```

## Command-Line Options

| Option | Description | Default |
|--------|-------------|---------|
| `--test-type` | Type of test: `power` or `current` (separate hardware setups) | `current` |
| `--wavelength` | Test wavelength in nm | `550.0` |
| `--duration` | Test duration in minutes | `5.0` |
| `--interval` | Time between measurements in seconds | `2.0` |
| `--pixel` | Pixel number for current test (documentation only) | `1` |
| `--output` | Custom output CSV filename | Auto-generated |
| `--no-plot` | Skip plotting (saves plot file only) | Plot shown |

## Output Files

The script generates two files per test in the `stability_tests/` subdirectory:

1. **CSV Data File**: `stability_tests/stability_test_<type>_<wavelength>nm_<timestamp>.csv`
   - Contains timestamped measurements
   - Includes metadata and statistics in header
   
2. **Plot File**: `stability_tests/stability_plot_<type>_<wavelength>nm_<timestamp>.png`
   - Time series with mean and ±1σ bands
   - Histogram showing distribution
   - Statistics summary

**Note**: The `stability_tests/` directory will be created automatically if it doesn't exist.

## Understanding Results

### Console Output

During the test, you'll see real-time output:
```
Time (s)   |      Power (W)  |     Power (μW)  |               Notes
--------------------------------------------------------------------------
       0.0 | 5.234567e-06    |         5.235   |             Initial
       2.0 | 5.241234e-06    |         5.241   |           CV: 0.13%
       4.0 | 5.238901e-06    |         5.239   |           CV: 0.15%
```

### Key Metrics

**Coefficient of Variation (CV%)**:

The CV% is a standardized measure of measurement dispersion that expresses the standard deviation as a percentage of the mean. It's calculated as:

```
CV% = (Standard Deviation / Mean) × 100%
```

**Why CV% is useful**: Unlike absolute standard deviation, CV% is normalized by the signal level, making it easy to compare stability across different measurement conditions (e.g., comparing stability at 450 nm where signal is high vs. 700 nm where signal is low).

**Interpretation guidelines**:
- **< 1%**: Excellent stability - measurement system is highly reproducible
- **1-3%**: Good stability, typical for optical measurements with proper setup
- **3-5%**: Acceptable but investigate causes - may need optimization
- **> 5%**: Poor stability, investigate immediately - do not proceed with EQE measurements

**Standard Deviation**:
- Absolute measure of variation
- Compare to signal level to assess signal-to-noise ratio

**Range (Max - Min)**:
- Shows peak-to-peak variation
- Large range suggests drift or intermittent issues

## Example Test Scenarios

### 1. Quick Current Stability Check (Default)
```bash
cd eqe
python test_stability.py
```
**Purpose**: Quick 5-minute check of current stability at mid-range wavelength (550 nm)

### 2. Detailed Current Stability Analysis
```bash
cd eqe
python test_stability.py --test-type current --duration 10 --interval 1 --wavelength 600
```
**Purpose**: Detailed 10-minute analysis of current stability with 1-second sampling

### 3. Band Edge Stability Test
```bash
cd eqe
python test_stability.py --test-type current --wavelength 700 --duration 5
```
**Purpose**: Test stability near band edge where signal is weaker

### 4. Long-Term Drift Test
```bash
cd eqe
python test_stability.py --duration 30 --interval 5
```
**Purpose**: Check for long-term drift over 30 minutes

### 5. Short Wavelength Test (High Signal)
```bash
cd eqe
python test_stability.py --wavelength 450 --duration 5 --interval 1
```
**Purpose**: Test at short wavelength where signal is typically strong

## Troubleshooting Stability Issues

### High CV% in Power Measurements (> 3%)

**Possible causes**:
1. **Lamp flicker** - Check lamp power supply and connections
2. **Mechanical vibration** - Ensure optical table is stable
3. **Thermal drift** - Allow lamp to warm up (>30 min)
4. **Detector noise** - Check power meter settings and connections

**Solutions**:
- Increase `num_measurements` in `POWER_MEASUREMENT_CONFIG`
- Check lamp stabilization time
- Verify optical alignment

### High CV% in Current Measurements (> 3%)

**Possible causes**:
1. **Chopper instability** - Check chopper speed and mechanical condition
2. **Lock-in noise** - Increase integration time (`num_cycles`)
3. **Sample/device instability** - Check electrical connections to photocell
4. **Light level variation** - See power measurement issues above
5. **Insufficient stabilization** - Signal hasn't settled after wavelength change

**Solutions**:
- Increase `num_measurements` in `CURRENT_MEASUREMENT_CONFIG`
- Increase `stabilization_time` (try 0.5 or 1.0 seconds)
- Increase `num_cycles` in `DEVICE_CONFIGS[DeviceType.PICOSCOPE_LOCKIN]`
- Check chopper frequency lock

### Systematic Drift (Trend in Time Series)

**Possible causes**:
1. **Lamp warming up** - Allow longer warm-up time
2. **Thermal effects** - Temperature changes in lab
3. **Sample degradation** - Light-induced changes in photocell

**Solutions**:
- Run test after 30-60 minute lamp warm-up
- Control lab temperature
- Reduce light exposure between measurements

## Best Practices

1. **Warm up lamp** - Run lamp for at least 30 minutes before testing
2. **Stabilize environment** - Minimize vibrations, temperature changes, and air currents
3. **Test at multiple wavelengths** - Check stability across measurement range
4. **Baseline before full scan** - Run stability test before important measurements
5. **Document conditions** - Note lamp hours, environmental conditions, etc.

## Interpreting Results for EQE Measurements

### Good Stability (CV < 1%)
- ✅ Measurements are highly repeatable
- ✅ EQE scans will have low noise
- ✅ Run-to-run variation should be minimal

### Acceptable Stability (CV 1-3%)
- ⚠️ Some measurement noise expected
- ⚠️ Consider averaging multiple scans
- ⚠️ Watch for systematic errors

### Poor Stability (CV > 3%)
- ❌ Do NOT proceed with EQE measurements
- ❌ Troubleshoot hardware and environment
- ❌ Results will have high uncertainty

## Technical Details

### What the Test Measures

**Power Test**:
- Uses `PowerMeasurementModel._read_power()`
- Same averaging as full EQE scan
- Configured by `POWER_MEASUREMENT_CONFIG["num_measurements"]`

**Current Test**:
- Uses `CurrentMeasurementModel._read_lockin_current()`
- Same lock-in parameters as full EQE scan
- Configured by `CURRENT_MEASUREMENT_CONFIG["num_measurements"]`
- Uses PicoScope software lock-in with outlier rejection

### Configuration Dependencies

The test uses settings from `config/settings.py`:
- `POWER_MEASUREMENT_CONFIG["num_measurements"]`
- `CURRENT_MEASUREMENT_CONFIG["num_measurements"]`
- `CURRENT_MEASUREMENT_CONFIG["stabilization_time"]`
- `DEVICE_CONFIGS[DeviceType.PICOSCOPE_LOCKIN]["default_num_cycles"]`

**To test with different settings**, modify `settings.py` before running the test.

## Example: Optimizing num_measurements

To find optimal `num_measurements` for current:

1. Set `num_measurements = 2` in `settings.py`
2. Run: `python test_stability.py --test-type current --duration 5`
3. Note the CV%
4. Increase to `5`, `10`, `20` and repeat
5. Choose the value where CV% plateaus (more measurements don't help)

**Trade-off**: More measurements = better stability but slower scans

## Keyboard Interrupt

You can stop a test at any time with `Ctrl+C`. The script will:
- Save data collected so far
- Close shutter and disconnect devices safely
- Generate plots and statistics for partial data

## Questions or Issues?

If you encounter problems or have questions about interpreting results, consult the documentation or contact a TA.
