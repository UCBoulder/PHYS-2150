# Physics Education Research (PER) Suggestions for PHYS 2150 Measurement Applications

This document outlines recommendations for enhancing the EQE and J-V measurement applications from a physics education research perspective, aligned with the course goals of the CURE (Course-based Undergraduate Research Experience).

## Course Context

### Course Goals (from syllabus)
- Explain the main components of the research process
- Use Python for basic experimental data analysis
- Identify a research question and conduct analysis to answer it
- Iterate on proposals based on feedback
- Work collaboratively with a team

### Measurement Uncertainty Learning Goals
- Fit a line to experimental data and extract meaning from fit results
- Determine if two measurements (with uncertainty) agree with each other
- Propagate uncertainties using formulas
- Articulate that repeated measurements will give a distribution of results
- Estimate size of random/statistical uncertainty by considering instrument precision
- Calculate and report the mean of a distribution for the best estimate
- Appropriately use and differentiate between standard deviation and standard error

### Non-Goals
- This course is NOT meant to make students Python programmers
- This course is NOT meant to teach all details of solar cells
- This course is NOT meant to reinforce PHYS 2170 concepts

---

## Current State Summary

| Component | J-V App | EQE App | Status |
|-----------|---------|---------|--------|
| **Uncertainty** | Single measurements only | ✅ 5 measurements with stats exposed | EQE done, J-V pending |
| **Transparency** | Minimal status messages | ✅ Lock-in Lab tab demystifies PSD | EQE done |
| **Parameter Extraction** | None | External script only | Not implemented |
| **Data Export** | Basic CSV | ✅ CSV with mean, std, n, CV% | EQE done, J-V pending |
| **Quality Indicators** | None | ✅ CV% per point + quality colors | EQE done |

### What's Been Implemented (December 2025)

1. **EQE Statistics Exposure** - `read_current()` now returns full statistics via `return_stats=True`
   - Location: `eqe/controllers/picoscope_lockin.py:260-344`
   - Returns: `{current, std_dev, n, cv_percent}`
   - Uses `MeasurementStats` dataclass for structured data
   - Calls `_logger.student_stats()` for real-time UI display

2. **Enhanced CSV Export** - Current measurements include uncertainty data
   - Location: `eqe/utils/data_handling.py:94-161`
   - Headers: `Wavelength (nm), Current_mean (A), Current_std (A), n, CV_percent`
   - Controlled by `include_measurement_stats` config flag
   - Values converted to nanoamps for student readability

---

## 1. Measurement Uncertainty Integration

### 1.1 J-V: Configurable Repeat Measurements

**Current state:** Single measurement per voltage point.

Add option for N measurements per voltage point (default can be 1):
```python
# In jv/config/settings.py
JV_MEASUREMENT_CONFIG = {
    "num_measurements_per_point": 1,  # User-adjustable
    "show_statistics": True,          # Display mean/std/stderr in real-time
}
```

**Important consideration for perovskites:** Multiple measurements at the same voltage point may change cell state due to hysteresis. This feature should be optional and its implications documented.

### 1.2 EQE: Expose the Hidden Uncertainty ✅ IMPLEMENTED

**Status:** ✅ Completed December 2025

**What was done:**
- `read_current()` now calculates and returns `{current, std_dev, n, cv_percent}`
- `MeasurementStats` dataclass provides structured statistics
- `_logger.student_stats()` displays stats in real-time UI
- No outlier rejection - students see honest measurement variability
- Comment in code: *"High CV at low signal wavelengths teaches them about SNR"*

**Implementation:** `eqe/controllers/picoscope_lockin.py:260-344`

**Future enhancement:** Option B (live histogram) not yet implemented

### 1.3 Live Statistics Display (Both Apps)

When repeat measurements are enabled/exposed, show in real-time:
- Current mean value
- Standard deviation (spread of measurements)
- Standard error (uncertainty in the mean)
- Coefficient of variation (CV%)

This directly supports the learning goal of differentiating standard deviation vs. standard error.

**Status:** ✅ Implemented for EQE (mean, SD, SE, n, CV% shown via `student_stats()`). J-V not implemented.

### 1.4 Enhanced CSV Export Format (Both Apps)

Expand data export to include uncertainty information:

**J-V format (not yet implemented):**
```csv
Voltage (V), Forward_mean (mA), Forward_std (mA), Forward_n, Reverse_mean (mA), Reverse_std (mA), Reverse_n
```

**EQE format:** ✅ IMPLEMENTED
```csv
Wavelength (nm), Current_mean (nA), Current_std (nA), n, CV_percent
```

**Status:** ✅ EQE implemented in `eqe/utils/data_handling.py:94-161`
- Controlled by `include_measurement_stats` config flag
- Values in nanoamps for student readability
- J-V not yet implemented

### 1.5 Data Quality Indicators (Both Apps)

Display quality metrics that help students evaluate their measurements:
- CV% (coefficient of variation) for each data point
- Warning if CV exceeds threshold (e.g., >10%)
- Overall measurement quality summary

**Status:** ✅ Partially implemented - CV% calculated and exported for EQE. Threshold warnings not yet implemented.

---

## 2. Measurement Transparency & Sensemaking

### PER Background
Research shows students often treat lab equipment as "black boxes" and miss opportunities for conceptual understanding. The E-CLASS survey reveals that students who understand *why* measurements work perform better on uncertainty tasks.

### 2.1 "About This Measurement" Information Panels

Add accessible explanations (expandable/collapsible) covering:

**For J-V Measurements:**
- What J-V characterization reveals about solar cells
- Why we do forward and reverse sweeps (hysteresis in perovskites)
- What the Keithley 2450 source-measure unit actually does
- What voltage compliance and current limits mean

**For EQE Measurements:**
- What external quantum efficiency means physically (electrons out / photons in)
- Why we need both power and current measurements
- How the lock-in amplifier extracts signal from noise
- Why phase adjustment matters

### 2.2 Demystify the Lock-in Amplifier (EQE - High Priority) ✅ IMPLEMENTED

**Status:** ✅ Completed December 2025 via **Lock-in Lab tab**

**What was built:**

1. ✅ **Context-sensitive explanations** that update with each processing step
2. ✅ **Raw waveform display** showing signal buried in noise
3. ✅ **X-Y phasor diagram** showing R and θ in real-time
4. ✅ **FFT spectrum** showing frequency selectivity
5. ✅ **Deconstructed algorithm** - toggle processing steps to build up PSD incrementally
6. ✅ **Simulated data mode** with adjustable signal parameters (modulation, DC offset, noise)
7. ✅ **Live data mode** to apply learned concepts to real PicoScope measurements
8. ✅ **Reference phase slider** to demonstrate phase sensitivity
9. ✅ **Expected vs Extracted value comparison** for verification

**Note:** Phase adjustment step was removed from the measurement workflow (Hilbert transform provides phase-independent magnitude R = √(X² + Y²)), but the Lock-in Lab tab teaches the concepts.

### 2.3 Real-Time Status Messages (Both Apps)

Show explanatory status messages during measurements:

**J-V:**
```
"Setting voltage to 0.5V..."
"Waiting 500ms for cell to stabilize before measurement..."
"Measuring current using 4-wire sensing for accuracy..."
"Voltage step complete. Moving to next point..."
```

**EQE:**
```
"Moving monochromator to 500 nm..."
"Switching to 400nm longpass filter to block second-order diffraction..."
"Performing lock-in measurement (averaging 5 readings)..."
"Wavelength complete. Current: 1.23 nA"
```

These messages help students understand the measurement process without requiring them to read code.

### 2.4 Automatic Parameter Extraction

**J-V:** After measurement completes, automatically calculate and display:

| Parameter | Symbol | Description |
|-----------|--------|-------------|
| Open-circuit voltage | Voc | Voltage where current = 0 |
| Short-circuit current | Isc | Current where voltage = 0 |
| Current density | Jsc | Isc / active area (if area known) |
| Fill factor | FF | (Vmp × Imp) / (Voc × Isc) |
| Power conversion efficiency | PCE | Pmax / Pin |
| Hysteresis index | HI | Quantifies forward/reverse difference |

**Why this matters:** These are the parameters students will discuss with their research mentor and report in publications. Connecting raw measurement to research-relevant quantities builds understanding.

---

## 3. EQE-Specific Enhancements

### 3.1 Integrate EQE Calculation (Medium-High Priority)

**Current state:** EQE calculation is a separate script (`calceqe.py`). Students must:
1. Run power measurement → save CSV
2. Run current measurement → save CSV
3. Run separate Python script to combine

**Problem:** Disconnects the measurement from its meaning. Students may not understand that EQE = (electrons out) / (photons in).

**Recommendations:**

1. **Add EQE calculation to the app** (or at least make it accessible):
   ```
   After current measurement: "Calculate EQE?"
   → Select power data file
   → Show EQE curve with explanation
   ```

2. **Show the formula and intermediate values:**
   ```
   EQE(λ) = (I_sc / q) / (P_inc / E_photon)

   At 500 nm:
   - Photocurrent: 1.23 nA
   - Incident power: 45.6 µW
   - Photon energy: 2.48 eV
   - EQE: 67.2%
   ```

3. **Add context:** "EQE of 67% means 67 electrons collected for every 100 photons incident"

### 3.2 Connect to AM1.5G and Jsc (Medium Priority)

**Course context:** Students measure EQE to understand solar cell performance. The connection to real-world performance is through AM1.5G integration.

**Recommendation:** Add feature to calculate predicted Jsc from EQE:
```
Jsc = q ∫ EQE(λ) × Φ_AM1.5G(λ) dλ

Predicted Jsc from your EQE data: 18.3 mA/cm²
(Compare this to J-V measurement Jsc to validate!)
```

This creates a powerful cross-check between the two measurement techniques - a key validation step in solar cell research.

### 3.3 Enhanced Phase Plot Educational Value - SUPERSEDED

**Status:** ⚠️ Phase plot removed from Measurement tab (December 2025)

**Reason:** The Hilbert transform algorithm computes magnitude R = √(X² + Y²) which is phase-independent. Phase adjustment is no longer needed in the measurement workflow.

**Educational replacement:** The **Lock-in Lab tab** now teaches phase concepts interactively:
- Reference phase slider demonstrates how phase affects X and Y components
- Phasor diagram shows R remains constant regardless of phase
- Students can explore phase sensitivity without it affecting actual measurements

### 3.4 Power Measurement Context

**Current state:** Power measurement shows progress but limited context.

**Recommendations:**

1. **Explain the lamp spectrum** - it's not flat because xenon arc has emission lines

2. **Add reference to AM1.5G** - overlay or show comparison to solar spectrum

3. **Flag any anomalies:**
   - Sudden drops (lamp flicker?)
   - Unusually low power (lamp degraded?)
   - Missing data points

### 3.5 Wavelength Filter Transitions

**Current state:** Filters auto-switch at 420nm and 800nm with log messages, but students may not understand why.

**Recommendation:** Brief status message explaining:
```
"Switching to 400nm longpass filter to block second-order diffraction from grating..."
```

This teaches about a real experimental consideration.

---

## 4. Error Prevention & Educational Feedback

### PER Background
Well-designed error messages are learning opportunities. "Productive failure" research shows students learn from mistakes when given appropriate scaffolding.

### 4.1 Physics-Informed Parameter Validation

Replace generic error messages with context-aware feedback:

**Instead of:**
```
"Please enter valid numerical values for voltages and step size."
```

**Use:**
```
"Start voltage of -1.0V is below the typical safe range for perovskite cells
(-0.5V to 0V). Excessive reverse bias may damage the cell.
Recommended range: -0.2V to 0V for reverse bias start."
```

```
"Stop voltage of 2.0V exceeds typical perovskite Voc (~1.1-1.2V).
High forward bias beyond Voc provides limited information and may stress the cell.
Recommended maximum: 1.3-1.5V"
```

### 4.2 Pre-Measurement Checklist

Prompt students before starting measurement:

**J-V Measurement Checklist:**
- [ ] Is the probe correctly positioned on the pixel?
- [ ] Is the light source on and stable?
- [ ] Have you recorded the cell temperature?
- [ ] Is the correct cell number entered?

**EQE Measurement Checklist:**
- [ ] Is the lamp warmed up (>15 minutes)?
- [ ] Has the power calibration been done today?
- [ ] Is the chopper running at the correct frequency?
- [ ] Is the probe making good contact with the pixel?

These checklists reinforce good experimental practice.

### 4.3 Intelligent Warnings During/After Measurement

**Low signal warning (both apps):**
```
"Measured current is very low (<1 nA). Possible causes:
- Probe not making contact with pixel
- Light source not on
- Dead pixel
Check connections and try again, or consult a TA."
```

**J-V Hysteresis warning:**
```
"Large hysteresis detected (HI = 0.35). This is common in perovskite cells
and may indicate:
- Ion migration in the perovskite layer
- Interface charging effects
Consider noting environmental conditions (temperature, humidity, light soak time)."
```

**EQE Low R² warning (already exists - good!):**
```
"Is the lamp on? If it is, pixel {pixel} might be dead. Check in with a TA."
```

---

## 5. Data Provenance & Research Practice

### PER Background
Authentic research involves documenting methods, conditions, and decisions. Teaching good data practices early builds professional habits.

### 5.1 Enhanced Metadata in Data Files

Add header section to saved CSV files:

**J-V Example:**
```csv
# PHYS 2150 J-V Measurement
# Date: 2025-11-27 14:32:15
# Cell: 195, Pixel: 3
# Operator: [initials]
#
# Measurement Parameters:
# Start Voltage: -0.2 V
# Stop Voltage: 1.5 V
# Step Size: 0.02 V
# Dwell Time: 500 ms
# Compliance: 1 A
#
# Extracted Parameters:
# Voc: 1.08 V
# Isc: 2.34 mA
# FF: 0.72
# PCE: 18.2% (assuming 100 mW/cm² illumination)
#
# Notes: After 30 min light soak
# Software Version: 2.0.0
#
Voltage (V), Forward Scan (mA), Reverse Scan (mA)
-0.20, -0.0023, -0.0021
...
```

**EQE Example:**
```csv
# PHYS 2150 EQE Current Measurement
# Date: 2025-11-27 15:45:00
# Cell: 195, Pixel: 3
# Operator: [initials]
#
# Measurement Parameters:
# Start Wavelength: 350 nm
# End Wavelength: 850 nm
# Step Size: 10 nm
# Chopper Frequency: 81 Hz
# Measurements per point: 5
#
# Phase Adjustment:
# Optimal Phase: 127.3°
# R²: 0.9823
#
# Software Version: 2.0.0
#
Wavelength (nm), Current (A)
350, 1.234e-09
...
```

### 5.2 Optional Notes Field

Allow students to add context:
- Environmental conditions
- Sample history (e.g., "post 85°C stress test")
- Observations during measurement
- Reason for re-measurement

### 5.3 Session Log

Create timestamped log file tracking all measurements in a session:
```
2025-11-27 14:30:00 - Application started
2025-11-27 14:30:05 - Keithley 2450 connected (USB0::0x05E6::0x2450::...)
2025-11-27 14:32:15 - J-V measurement started: Cell 195, Pixel 3
2025-11-27 14:35:42 - J-V measurement completed
2025-11-27 14:35:45 - Data saved to: 2025_11_27_JV_cell195_pixel3.csv
...
```

Useful for reconstructing experimental history and debugging issues.

---

## 6. Visual Design for Learning

### PER Background
Cognitive load theory suggests that visual design significantly impacts learning. Well-designed graphs help students extract meaning from data.

### 6.1 Meaningful Color Coding

**J-V:** Current implementation uses blue for forward, orange for reverse scans. Enhance with:
- Legend explaining what hysteresis means for perovskites
- Option to highlight the maximum power point
- Visual indication of Voc, Isc on the curve

**EQE:** Consider showing:
- Band gap energy (where EQE drops off)
- Comparison to theoretical maximum

### 6.2 Reference Overlays (Optional)

Allow students to overlay:
- Previous measurement on same pixel (see degradation)
- Measurement from different pixel on same cell (compare uniformity)
- Ideal diode behavior (J-V) or theoretical EQE limit

### 6.3 Interactive Data Exploration

- Hover to read exact values
- Click to mark points of interest
- Zoom to regions of interest (already available via matplotlib toolbar)

### 6.4 Consistent Units and Labels

- Always show units on axes
- Use SI prefixes consistently (mA not A×10⁻³, nA for current)
- Consider current density (mA/cm²) if active area is known
- Match units between display and exported data

---

## 7. Integration Opportunities

### 7.1 Shared Cell Metadata

When students enter cell number in one app, offer to share with the other:
- Reduces re-entry errors
- Maintains consistent identification
- Could use shared config file or clipboard

### 7.2 Data Consistency Checks

Explain in documentation how J-V and EQE relate:
- Jsc from J-V should correlate with integrated EQE × AM1.5G spectrum
- This is a key validation step in solar cell research
- Discrepancies indicate measurement or cell issues

### 7.3 Combined Analysis Tool (Future)

Standalone utility that:
- Loads both J-V and EQE data for a cell
- Performs consistency calculations (predicted Jsc from EQE vs. measured Jsc)
- Generates summary report suitable for lab notebook

---

## Implementation Priority Matrix

| Enhancement | App | Learning Impact | Effort | Status |
|------------|-----|-----------------|--------|--------|
| Expose EQE 5-measurement statistics | EQE | High | Low | ✅ **Done** |
| Enhanced CSV export with stats | EQE | Medium | Low | ✅ **Done** |
| Live statistics display | EQE | High | Low | ✅ **Done** |
| CV% quality indicator | EQE | Medium | Low | ✅ **Done** |
| Lock-in amplifier explanation | EQE | High | Medium | ✅ **Done** (Lock-in Lab tab) |
| Physics-informed error messages | Both | Medium | Low | Pending |
| Automatic parameter extraction (Voc, Jsc, FF) | J-V | High | Low | Pending |
| EQE calculation integration | EQE | High | Medium | Pending |
| Pre-measurement checklist | Both | Medium | Medium | Pending |
| Info/About panels | Both | Medium | Low | Pending |
| Real-time status messages | Both | Medium | Low | Partial |
| AM1.5G Jsc prediction | EQE | Medium | Medium | Pending |
| ~~Enhanced phase plot annotations~~ | EQE | - | - | Superseded (phase plot removed) |
| J-V repeat measurements option | J-V | High | Medium | Pending (consider hysteresis) |
| J-V enhanced CSV export | J-V | Medium | Low | Pending |
| Session logging | Both | Low | Low | Pending |
| Interactive cursor | Both | Low | Medium | Pending |
| Reference overlays | Both | Low | High | Future |
| Cross-app integration | Both | Low | High | Future |

---

## Implementation Notes

### What to Build Into Architecture Now

These affect core data structures and are hard to retrofit:

1. **CSV export format** - ✅ Done for EQE; decide on J-V column structure
2. **Config-driven parameters** - ✅ Done; all measurement settings in config
3. **Clean Model separation** - ✅ Done; allows adding analysis features without touching View
4. **Uncertainty data flow** - ✅ Done for EQE; `MeasurementStats` dataclass flows through system

### What Can Wait

These are modular additions that don't require architectural changes:

1. All UI enhancements (panels, messages, checklists)
2. Analysis calculations (can be added to Model layer)
3. Documentation and help text
4. Logging infrastructure
5. EQE calculation integration (separate model, connect to existing view)

### What the Apps Already Do Well (Keep These!)

**EQE:**
- R² quality metric for phase adjustment - directly teaches about fit quality
- Clear progress indication - students know measurement status
- Automatic filter switching - handles complexity so students focus on physics
- Green alignment dot - practical experimental aid
- Structured workflow - power first, then phase + current per pixel

**J-V:**
- Forward/reverse sweep visualization - shows hysteresis clearly
- Color-coded curves - easy to distinguish scan directions
- Simple interface - not overwhelming

### Pedagogical Considerations

- Don't overwhelm students with features; start simple
- Make advanced features optional/hidden by default
- Test with actual students before finalizing
- Gather feedback each semester and iterate
- Remember: students should focus on physics, not fighting the software

---

## Code Locations for Key Enhancements

| Enhancement | File | Status |
|-------------|------|--------|
| EQE statistics calculation | `eqe/controllers/picoscope_lockin.py:260-344` | ✅ Done |
| EQE CSV export with stats | `eqe/utils/data_handling.py:94-161` | ✅ Done |
| MeasurementStats dataclass | `common/utils/tiered_logger.py` | ✅ Done |
| EQE phase plot | `ui/eqe.html` + JavaScript | Exists |
| EQE R² threshold | `eqe/config/settings.py` | Exists |
| J-V measurement loop | `jv/models/jv_measurement.py` | Exists |
| J-V CSV export | `jv/utils/data_export.py` | Needs stats |

---

## References

### PER Literature
- AAPT Recommendations for the Undergraduate Physics Laboratory Curriculum (2015)
- E-CLASS: Colorado Learning Attitudes about Science Survey for Experimental Physics
- Physics Measurement Questionnaire (PMQ) - Allie et al.
- "Structured Quantitative Inquiry Labs" - Holmes et al.

### Course-Specific
- PHYS 2150 Syllabus and Course Goals
- CURE Framework for undergraduate research experiences

---

*Document created: November 2025*
*Last updated: January 2026*
*To be reviewed and updated based on instructor and student feedback each semester*
