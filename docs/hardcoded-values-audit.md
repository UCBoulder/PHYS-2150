# Hardcoded Values Audit

This document tracks hardcoded values in the codebase that should reference `defaults.json` instead.

**Audit Date:** 2026-01-22

---

## Critical Issues (Causing Bugs)

These hardcoded values use the **wrong pattern** and cause validation failures.

### Cell Number Validation Regex

The cell number format changed from 3 digits (`195`) to letter + 2 digits (`A12`), but several locations still use the old pattern.

| File | Line | Hardcoded Value | Should Reference |
|------|------|-----------------|------------------|
| `ui/js/jv-app.js` | 318 | `/^\d{3}$/` | `validation.cell_input.pattern` |
| `ui/js/jv-app.js` | 477 | `/^\d{3}$/` | `validation.cell_input.pattern` |
| `ui/js/eqe-app.js` | 600 | `/^\d{3}$/` | `validation.cell_input.pattern` |
| `ui/js/eqe-app.js` | 634 | `/^\d{3}$/` | `validation.cell_input.pattern` |

**Config value:** `"^[A-Z]\\d{2}$"` (letter + 2 digits)

---

## High Priority (Inconsistent UI)

These values show outdated examples or don't match the current config.

### Cell Number Placeholders

| File | Line | Hardcoded Value | Should Be |
|------|------|-----------------|-----------|
| `ui/jv.html` | 91 | `placeholder="e.g. 140"` | `placeholder="e.g. A12"` (from config) |
| `ui/jv.html` | 181 | `placeholder="e.g. 140"` | `placeholder="e.g. A12"` (from config) |
| `ui/eqe.html` | 110 | `placeholder="e.g. 140"` | `placeholder="e.g. A12"` (from config) |

### Pixel Validation Message (Static)

| File | Line | Hardcoded Value | Should Be |
|------|------|-----------------|-----------|
| `ui/eqe.html` | 538 | `"Pixel must be between 1 and 8"` | Dynamic from `validation.pixel_range` |

### Cell Input maxlength

| File | Line | Hardcoded Value | Notes |
|------|------|-----------------|-------|
| `ui/jv.html` | 91 | `maxlength="3"` | Correct for `A12` format |
| `ui/jv.html` | 181 | `maxlength="3"` | Correct for `A12` format |
| `ui/eqe.html` | 110 | `maxlength="3"` | Correct for `A12` format |

---

## Medium Priority (Missing from Config)

These values are hardcoded but could be moved to `defaults.json` for consistency.

### Lock-in Lab Parameters (eqe-app.js)

Currently hardcoded in the JavaScript state object. Should be added to `defaults.json` under `eqe.lockinlab`.

| Line | Parameter | Hardcoded Value | Suggested Config Key |
|------|-----------|-----------------|---------------------|
| 61 | Integration cycles | `10` | `eqe.lockinlab.default_cycles` |
| 62 | Noise level | `30` (%) | `eqe.lockinlab.default_noise_percent` |
| 65 | Pk-Pk amplitude | `150` (mV) | `eqe.lockinlab.default_amplitude_mv` |
| 66 | DC offset | `100` (mV) | `eqe.lockinlab.default_dcoffset_mv` |
| 63 | Phase offset | `0` (degrees) | `eqe.lockinlab.default_phase_offset` |

### Lock-in Lab Slider Ranges (eqe.html)

| Line | Parameter | Hardcoded Range | Suggested Config Key |
|------|-----------|-----------------|---------------------|
| 375 | Amplitude | `min="10" max="500"` | `eqe.lockinlab.amplitude_range` |
| 380 | DC Offset | `min="0" max="300"` | `eqe.lockinlab.dcoffset_range` |
| 385 | Noise | `min="0" max="100"` | `eqe.lockinlab.noise_range` |
| 390 | Phase | `min="-180" max="180"` | `eqe.lockinlab.phase_range` |
| 395 | Cycles | `min="1" max="50"` | `eqe.lockinlab.cycles_range` |

### Chopper Frequency Labels

The value `81` exists in config at `eqe.devices.picoscope_lockin.default_chopper_freq`, but UI labels hardcode the string.

| File | Line | Hardcoded Value | Should Use Config |
|------|------|-----------------|-------------------|
| `ui/eqe.html` | 427 | `"Reference (81 Hz)"` | Dynamic from config |
| `ui/js/eqe-app.js` | 1507 | `"81 Hz"` in explanation text | Dynamic from config |
| `ui/js/eqe-app.js` | 2096 | `"Reference (81 Hz)"` plot label | Dynamic from config |

---

## Low Priority (Acceptable Fallbacks)

These use `LabConfig.get()` with hardcoded fallbacks. The fallbacks are acceptable since `defaults.json` is bundled with the app.

### modals.js Fallbacks

| Line | Fallback Value | Config Key |
|------|----------------|------------|
| 146 | `'^[A-Z][0-9]{2}$'` | `validation.cell_input.pattern` |
| 231 | `[1, 8]` | `validation.pixel_range` |
| 597-602 | Cell input defaults | `validation.cell_input.*` |
| 636 | `[1, 8]` | `validation.pixel_range` |

### eqe-app.js Fallbacks

| Line | Fallback Value | Config Key |
|------|----------------|------------|
| 524 | `[200, 1200]` | `devices.monochromator.wavelength_range` |
| 1213 | `[200, 1200]` | `devices.monochromator.wavelength_range` |

---

## Error Messages Not in Config

These error messages are hardcoded in JavaScript. Consider adding to `defaults.json` under `error_messages`.

### Common to Both Apps

| Message | Files |
|---------|-------|
| `"Cannot Switch"` / `"Please stop the current measurement before switching tabs."` | jv-app.js, eqe-app.js |
| `"Cannot Switch"` / `"Please stop the stability test before switching tabs."` | jv-app.js, eqe-app.js |
| `"No Data"` / `"No data to save"` | jv-app.js |
| `"No Data"` / `"No measurement data to save"` | eqe-app.js |
| `"Save Failed"` (title) | jv-app.js, eqe-app.js |
| `"Measurement Failed"` (title) | jv-app.js, eqe-app.js |

### J-V Specific

| Message | Line |
|---------|------|
| `"No Device"` / `"No device connected. Use --offline flag for testing."` | 367 |
| `"Invalid Input"` / `"Please enter valid test parameters"` | 471 |
| `"Stability Test Failed"` / `"Stability Test Error"` (titles) | 538, 630 |

### EQE Specific

| Message | Line |
|---------|------|
| `"Invalid Wavelength"` (title) | 526, 1215 |
| `"Test Failed"` (title) | 1253, 1422 |
| `"Error"` (generic title) | 538, 568 |

### Launcher

| Message | Line |
|---------|------|
| `"Connection Error"` / `"Not connected to backend"` | 112, 132 |
| `"Launch Failed"` (title) | 122, 142 |

---

## Python Hardcoded Values

### Voltage Bounds (jv_experiment.py)

| File | Line | Hardcoded Value | Config Key |
|------|------|-----------------|------------|
| `jv/models/jv_experiment.py` | 367 | `-1.0 <= target_voltage <= 2.0` | `validation.voltage_bounds` |

---

## Data That Should Stay Hardcoded

These are constants that don't need to be configurable:

- **AM1.5G Spectral Data** (`eqe-app.js` lines 106-117): Scientific reference data
- **Unit labels** (`mV`, `nA`, `µW`, etc.): Standard SI units
- **Device names** (`Keithley 2450`, `PicoScope`, etc.): Hardware identifiers

---

## Resolution Status

| Category | Count | Status |
|----------|-------|--------|
| Critical (wrong pattern) | 4 | ❌ Not fixed |
| High (inconsistent UI) | 4 | ❌ Not fixed |
| Medium (missing from config) | 15+ | ❌ Not fixed |
| Low (acceptable fallbacks) | 6 | ✅ Acceptable |
| Error messages | 15+ | ⚠️ Consider adding |

---

## Next Steps

1. **Immediate:** Fix the 4 critical cell validation regex issues in jv-app.js and eqe-app.js
2. **Short-term:** Update HTML placeholders to use config values via JavaScript
3. **Medium-term:** Add Lock-in Lab parameters to defaults.json
4. **Optional:** Add error message strings to defaults.json for internationalization
