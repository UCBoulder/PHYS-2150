# PicoScope Integration into MVC EQE Application

## Summary
This document summarizes the changes made to integrate PicoScope software lock-in amplifier functionality into the MVC-structured EQE measurement application, replacing the previous SR510 lock-in amplifier and Keithley 2110 multimeter combination.

## Changes Made

### 1. New Files Created

#### `eqe_mvc/drivers/picoscope_driver.py`
- Copied from `eqe/picoscope_driver.py`
- Low-level driver for PicoScope 5000a and 2000a series oscilloscopes
- Implements software lock-in amplifier using Hilbert transform
- Features:
  - ±20V input range (eliminates clipping)
  - 100 MS/s sampling rate with optimized decimation
  - Phase-locked triggering for 0.66% CV stability
  - Returns X, Y, R (magnitude), and theta (phase) from lock-in measurement

#### `eqe_mvc/controllers/picoscope_lockin.py`
- New controller following MVC patterns
- Wraps the PicoScope driver with a clean interface
- Key methods:
  - `connect()`: USB connection to PicoScope
  - `set_reference_frequency(freq)`: Set chopper frequency
  - `set_num_cycles(cycles)`: Set integration time
  - `perform_lockin_measurement()`: Execute software lock-in, returns X, Y, R, theta
  - `read_current()`: Robust current reading with trimmed mean averaging
  - `measure_phase_response()`: Phase and magnitude measurement

### 2. Modified Files

#### `eqe_mvc/models/phase_adjustment.py`
**Changes:**
- Replaced `SR510Controller` with `PicoScopeController`
- Removed phase sweeping logic (no longer needed with software lock-in)
- Updated `_sample_phase_response()`:
  - Now performs single software lock-in measurement
  - Extracts X, Y, R, theta components directly
  - Generates visualization data by projecting signal onto different phase angles
- Updated `_set_optimal_phase()`:
  - No longer sets hardware phase (software lock-in is phase-independent)
  - Returns magnitude R from lock-in measurement
- Updated `_fit_sine_wave()`:
  - Uses actual measured phase from software lock-in
  - R² is calculated for visualization quality check

**Key Insight:** Software lock-in returns magnitude R = sqrt(X² + Y²) which is phase-independent, eliminating phase drift issues!

#### `eqe_mvc/models/current_measurement.py`
**Changes:**
- Removed `Keithley2110Controller` dependency
- Replaced `SR510Controller` with `PicoScopeController`
- Removed `_read_lock_in_with_keithley_check()` method
- Added `_read_lockin_current()` method:
  - Uses PicoScope's robust averaging (5 measurements with trimmed mean)
  - No sensitivity adjustment needed (±20V range handles all signals)
  - Returns current directly from magnitude R
- Removed lock-in parameter configuration (software-based, no config needed)
- Updated device connection check (removed Keithley)

**Key Improvement:** Simplified measurement chain - one device instead of two!

#### `eqe_mvc/models/eqe_experiment.py`
**Changes:**
- Removed imports for `Keithley2110Controller` and `SR510Controller`
- Added import for `PicoScopeController`
- Removed `self.keithley` attribute
- Changed `self.lockin` type to `PicoScopeController`
- Removed `_initialize_keithley()` method
- Updated `_initialize_lockin()`:
  - Connects to PicoScope via USB
  - Configures chopper frequency, num_cycles, and correction factor
  - Uses `PICOSCOPE_LOCKIN` device config
- Updated `_create_measurement_models()`:
  - Removed Keithley parameter from `CurrentMeasurementModel` instantiation

#### `eqe_mvc/config/settings.py`
**Changes:**
- Updated `DeviceType` enum:
  - Removed `KEITHLEY_2110` and `SR510_LOCKIN`
  - Added `PICOSCOPE_LOCKIN`
- Updated `CURRENT_MEASUREMENT_CONFIG`:
  - Removed `num_voltage_readings` and `voltage_threshold`
  - Added `num_measurements` (for averaging)
- Updated `PHASE_ADJUSTMENT_CONFIG`:
  - Removed `num_phase_points` and `phase_range` (not needed for software lock-in)
  - Added `num_visualization_points` (for phase plot)
- Updated `DEVICE_CONFIGS`:
  - Removed `KEITHLEY_2110` and `SR510_LOCKIN` configurations
  - Added `PICOSCOPE_LOCKIN` configuration:
    - `default_chopper_freq`: 81 Hz
    - `default_num_cycles`: 100
    - `num_measurements`: 5
    - `correction_factor`: 0.45

#### `eqe_mvc/requirements.txt`
**Changes:**
- Added `picosdk>=1.1.0` for PicoScope SDK

### 3. Files Unchanged
- `eqe_mvc/main.py`: No changes needed (uses `EQEExperimentModel` which handles device initialization)
- `eqe_mvc/models/power_measurement.py`: Unchanged (uses Thorlabs power meter)
- `eqe_mvc/controllers/thorlabs_power_meter.py`: Unchanged
- `eqe_mvc/controllers/monochromator.py`: Unchanged
- All view files: Unchanged (pure GUI, no device logic)

## Technical Details

### Software Lock-in Algorithm
The PicoScope implementation uses a sophisticated software lock-in amplifier:

1. **Acquisition**: Captures waveforms from both channels (signal and reference)
2. **Hilbert Transform**: Generates quadrature reference (90° phase shift)
3. **Mixing**: Multiplies signal with in-phase and quadrature references
4. **Integration**: Averages over multiple cycles for noise rejection
5. **Output**: Returns X (in-phase), Y (quadrature), R (magnitude), θ (phase)

### Key Advantages
- **Phase Independence**: R = sqrt(X² + Y²) is independent of phase drift
- **No Clipping**: ±20V range handles all signal levels
- **Robust Averaging**: Trimmed mean rejects outliers from lamp flicker
- **Simplified Setup**: One device instead of two
- **Better Stability**: 0.66% CV achieved through phase-locked triggering

### Measurement Parameters
- **Chopper Frequency**: 81 Hz (configurable)
- **Integration Cycles**: 100 cycles (optimal for stability vs. speed)
- **Averaging**: 5 measurements with trimmed mean
- **Correction Factor**: 0.45 (monochromator-specific)

## Migration Notes

### For Developers
1. The PicoScope driver is located in `drivers/` (not `controllers/`)
2. Controller wraps driver and provides high-level interface
3. Models use controller, never directly access driver
4. All configuration is centralized in `config/settings.py`

### For Users
1. Ensure PicoScope is connected via USB before starting application
2. Install PicoSDK drivers (from Pico Technology website)
3. Install Python packages: `pip install picosdk scipy`
4. Chopper frequency can be configured in settings (default: 81 Hz)
5. Phase adjustment now shows software lock-in phase response

## Testing Recommendations
1. Verify PicoScope connection on startup
2. Test phase adjustment at 532 nm (green alignment dot)
3. Verify current measurements across full wavelength range
4. Check stability with CV < 1%
5. Confirm R² > 0.90 for phase adjustment

## Compatibility
- PicoScope 5000a series (e.g., 5242D) - 15-bit resolution
- PicoScope 2000a series (e.g., 2204A) - 8-bit resolution
- Both series supported with automatic detection

## Future Enhancements
1. Add PicoScope-specific diagnostics (signal amplitude, clipping detection)
2. Implement adaptive num_cycles based on signal strength
3. Add real-time waveform visualization
4. Support for multiple PicoScope devices (via serial number)
5. Advanced triggering options (external trigger, etc.)

## References
- Original implementation: `eqe/eqeguicombined-filters-pyside-pico.py`
- PicoScope documentation: PicoSDK Python wrappers
- Software lock-in theory: Hilbert transform for quadrature detection
