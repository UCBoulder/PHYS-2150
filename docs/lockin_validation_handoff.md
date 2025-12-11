# Lock-In Amplifier Validation - Lab Session Handoff

## Overview

This document provides context for continuing lock-in amplifier validation on the lab computer with access to the full EQE measurement system.

**Branch:** `lockin-validation`
**Last updated:** December 2025

---

## What Was Done

### 1. Validation Framework Created

New module at `eqe/validation/` with:
- `lockin_simulator.py` - Synthetic signal testing (no hardware)
- `lockin_tester.py` - PicoScope AWG validation
- `keysight_awg_test.py` - External AWG validation (EDU33212A)
- `improved_lockin.py` - Algorithm experiments

### 2. Lock-In Algorithm Corrected

**Problem Found:** The original algorithm had a 2x scaling error (+97% error in measured R).

**Solution:** Added 0.5 correction factor, validated via AWG testing.

**Code Changes:**
- `eqe/drivers/picoscope_driver.py` - Refactored with two algorithms:
  - `_lockin_hilbert()` - Original + correction factor (default)
  - `_lockin_synthesized()` - Alternative using synthesized sine reference
- `eqe/config/settings.py` - Added algorithm selection config

### 3. AWG Control Added

PicoScope driver now supports built-in AWG:
```python
scope.set_awg(frequency=81.0, amplitude_vpp=2.0, waveform='square')
scope.stop_awg()
```

### 4. PicoSDK Path Fix

Added automatic PATH setup for Windows so PicoSDK DLLs are found.

---

## Validation Results Summary

### PicoScope AWG Test (81 Hz square wave)

| Metric | Hilbert (corrected) | Synthesized |
|--------|---------------------|-------------|
| Mean error | -1.3% | -2.5% |
| Linearity R² | 0.999998 | ~0.9999 |
| Noise floor | 0.36 mV | - |

### Keysight EDU33212A AWG Test

| Test | Hilbert | Synthesized | Notes |
|------|---------|-------------|-------|
| Amplitude accuracy | +0.73% | -0.17% | Both good |
| Frequency response (50-200 Hz) | -0.77% stable | Up to +25% error | Hilbert better |
| Phase offset sensitivity | R varies with phase | R constant | **Important finding** |
| Sine wave signal | -37% error | -22% error | Both calibrated for square |

### Key Finding: Phase Sensitivity

The Hilbert algorithm's R value depends on the phase relationship between signal and reference:
- **0° offset:** R = 0.496V (correct)
- **90° offset:** R = 0.355V (29% low!)
- **180° offset:** R = 0.495V (correct, but negative X)

**Implication:** If your chopper reference and photocurrent have varying phase offset, measurements will fluctuate. This should NOT be an issue if both come from the same physical chopper.

---

## What Still Needs Testing

### 1. Real EQE Measurement Validation

Run actual EQE measurements and compare to known good data:
- [ ] Measure a reference solar cell with known EQE
- [ ] Compare new measurements to historical data
- [ ] Verify the 0.5 correction factor gives correct absolute currents

### 2. Transimpedance Amplifier Verification

The code assumes 1 MΩ TIA gain (`eqe/config/settings.py:45`):
```python
"transimpedance_gain": 1e-6,  # 1 MΩ
```

To verify:
- [ ] Source known DC current into TIA with Keithley/DC supply
- [ ] Measure output voltage
- [ ] Calculate actual gain: `gain = V_out / I_in`

### 3. Full-Chain Photocurrent Test (Optional)

If you have a Keithley 2450 and relay/switch:
- [ ] Source known DC current
- [ ] Chop it at 81 Hz using relay driven by AWG
- [ ] Measure with lock-in
- [ ] Verify current matches source

### 4. Long-Term Stability

- [ ] Run repeated measurements over 30+ minutes
- [ ] Check for drift or instability
- [ ] Verify coefficient of variation < 1%

---

## How to Run Validation Tests

### Prerequisites

```bash
# Ensure you're on the right branch
git checkout lockin-validation

# Install dependencies if needed
pip install picosdk pyvisa pyvisa-py
```

### Run Simulation (No Hardware)

```bash
python -m eqe.validation.lockin_simulator
```

### Run PicoScope AWG Test

**Setup:** Connect PicoScope AWG output → BNC tee → Ch A + Ch B

```bash
python -m eqe.validation.lockin_tester
```

### Run Keysight AWG Test

**Setup:**
- EDU33212A Ch1 → PicoScope Ch A (signal)
- EDU33212A Ch2 → PicoScope Ch B (reference)

```bash
python -m eqe.validation.keysight_awg_test
```

### Quick Manual Test

```python
from eqe.drivers.picoscope_driver import PicoScopeDriver

scope = PicoScopeDriver()
scope.connect()

# Test with AWG
scope.set_awg(81.0, 2.0, 'square')  # 81 Hz, 2 Vpp
result = scope.software_lockin(81.0, num_cycles=50, algorithm='hilbert', correction_factor=0.5)
print(f"R = {result['R']:.4f} V (expected ~1.0 V)")

scope.stop_awg()
scope.close()
```

---

## Configuration Reference

### Lock-In Settings (`eqe/config/settings.py`)

```python
DeviceType.PICOSCOPE_LOCKIN: {
    "default_chopper_freq": 81,           # Hz
    "default_num_cycles": 100,            # Integration cycles
    "num_measurements": 5,                # Averages per point
    "algorithm": "hilbert",               # or "synthesized"
    "hilbert_correction_factor": 0.5,     # Validated via AWG
}
```

### Algorithm Selection

In code:
```python
# Default (Hilbert with correction)
result = scope.software_lockin(81.0, num_cycles=100)

# Explicit Hilbert
result = scope.software_lockin(81.0, algorithm='hilbert', correction_factor=0.5)

# Alternative (Synthesized)
result = scope.software_lockin(81.0, algorithm='synthesized')
```

---

## File Locations

| File | Purpose |
|------|---------|
| `eqe/drivers/picoscope_driver.py` | Main driver with lock-in algorithms |
| `eqe/config/settings.py` | Configuration including correction factor |
| `eqe/validation/` | All validation test scripts |
| `docs/lockin_validation_plan.md` | Original analysis and test plan |

---

## Troubleshooting

### "PicoSDK not found"

The driver should auto-add the SDK path, but if not:
```python
import os
os.environ['PATH'] += ';C:\\Program Files\\Pico Technology\\SDK\\lib'
```

### "No device found"

- Check USB connection
- Try unplugging and reconnecting PicoScope
- Run PicoScope 6 software to verify device works

### Lock-in returns None

- Check that both channels have signal
- Verify reference signal has non-zero amplitude
- Try increasing num_cycles

---

## Decision Points for Lab Session

1. **Does the corrected algorithm give accurate EQE values?**
   - Compare to known reference cell
   - If not, may need to adjust correction factor

2. **Is the TIA gain actually 1 MΩ?**
   - Verify with DC current source
   - Update config if different

3. **Which algorithm to use going forward?**
   - Hilbert: Better frequency response, phase-sensitive
   - Synthesized: Phase-insensitive, less accurate at some frequencies

4. **Ready to merge to main?**
   - After validation, merge `lockin-validation` branch to `main`

---

## Contact/Notes

*Add any notes from the lab session here for future reference.*

---

## Commit History (This Branch)

```
289004e Add Keysight EDU33212A AWG validation test
6bee91f Add corrected lock-in algorithms with config selection
f790494 Add PicoSDK DLL path to environment on Windows
9f06bde Add lock-in validation module and AWG control
```
