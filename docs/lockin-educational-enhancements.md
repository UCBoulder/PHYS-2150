# Lock-in Educational Enhancements Plan

This document captures recommendations from PER (Physics Education Research) consultation for enhancing the software lock-in system to improve student learning outcomes.

**Status:** Planning phase - awaiting implementation decisions
**Last updated:** 2025-12-11
**Related:** [per-suggestions.md](per-suggestions.md), [software-lockin.md](software-lockin.md)

---

## Executive Summary

The software lock-in achieves excellent technical performance (0.66% CV), but several enhancements could better support course learning goals around measurement uncertainty. The key insight: **the 5 measurements per wavelength are already being collected but hidden from students** - this directly contradicts the learning goal "articulate that repeated measurements will give a distribution of results."

---

## Course Learning Goals (Reference)

From the PHYS 2150 syllabus:
- Articulate that repeated measurements will give a distribution of results
- Calculate and report the mean of a distribution for the best estimate
- Appropriately use and differentiate between standard deviation and standard error
- Fit a line to experimental data and extract meaning from fit results

---

## Part 1: Lock-in Validation & Diagnostic Experiments

### 1.1 Frequency Response Test

**Purpose:** Verify lock-in only responds to reference frequency (81 Hz), rejects other frequencies (60 Hz power line noise).

**Implementation:**
- Add diagnostic mode that shows FFT spectrum alongside lock-in result
- Students observe peak at 81 Hz, absence of response at 60 Hz
- Demonstrates frequency-selective nature of phase-sensitive detection

**Code location:** `eqe/drivers/picoscope_driver.py` - `software_lockin()` already computes FFT for frequency detection

**Effort:** Medium

---

### 1.2 Phase Independence Verification

**Purpose:** Demonstrate that R = √(X² + Y²) is constant regardless of phase.

**Implementation:**
- During phase adjustment, show that R remains stable even as phase drifts
- Add R as horizontal line on phase plot (currently shows projected signal vs phase)

**Code location:** `eqe/models/phase_adjustment.py`

**Effort:** Low

---

### 1.3 Noise Injection Test

**Purpose:** Demonstrate lock-in noise rejection in real conditions.

**Test protocol:**
1. Measure signal with lab lights off (baseline)
2. Measure signal with lab lights on (120 Hz flicker)
3. Measure while someone walks past optical table

**Expected result:** CV% should remain similar across all conditions

**Implementation:** Document as a recommended student activity; no code changes needed

**Effort:** None (documentation only)

---

### 1.4 Known Signal Test (Calibration Check)

**Purpose:** Validate entire signal chain before measuring unknown cells.

**Implementation:**
- Measure reference detector at fixed wavelength before cell measurements
- Compare to expected value
- Provides "sanity check" before research measurements

**Effort:** Low (add to workflow documentation)

---

## Part 2: Educational Visualizations

### 2.1 Raw Waveform Display (HIGH PRIORITY)

**Purpose:** Show students the signal buried in noise, demystify lock-in detection.

**Display:**
```
Left panel:   Raw signal waveform (noise + modulated signal)
Middle panel: Reference waveform (clean square wave from chopper)
Right panel:  Product of signal × reference (shows mixing)
```

**Implementation:**
- Data already captured in `software_lockin()` result dict (`signal_data`, `reference_data`)
- Add new "Diagnostics" or "Waveforms" tab to display

**Code location:** Add to `ui/eqe.html` with JavaScript visualization

**Effort:** Medium

---

### 2.2 X-Y Phasor Diagram (MEDIUM PRIORITY)

**Purpose:** Visual explanation of quadrature detection.

**Display:**
```
       Y (quadrature)
       ^
       |    /R
       |   /
       |  /θ
       +--------> X (in-phase)
```

**Implementation:**
- Plot X, Y components as vector
- Show R as vector magnitude
- Update in real-time during phase adjustment

**Code location:** Enhance phase visualization in `ui/eqe.html` JavaScript

**Effort:** Low

---

### 2.3 FFT Spectrum Display (LOWER PRIORITY)

**Purpose:** Show frequency selectivity of lock-in.

**Display:**
- FFT of acquired signal
- Clear peak at 81 Hz (chopper frequency)
- Absence of response at other frequencies

**Implementation:**
- FFT already computed in driver
- Add visualization option

**Effort:** Medium

---

### 2.4 Hilbert Transform Visualization (ADVANCED)

**Purpose:** Explain quadrature reference generation for interested students.

**Display:**
1. Original reference signal (square wave)
2. Hilbert-transformed reference (90° shifted)
3. Overlay showing phase relationship

**Implementation:** Optional advanced feature

**Effort:** Medium

---

## Part 3: Exposing Measurement Statistics (CRITICAL)

### 3.1 The Problem

Current code at `eqe/controllers/picoscope_lockin.py:195-270`:

```python
def read_current(self, num_measurements: int = 5) -> Optional[float]:
    R_values = []
    for i in range(num_measurements):
        result = self.perform_lockin_measurement()
        if result is not None:
            R_values.append(result['R'])

    # ...averaging and filtering...

    return current  # Only returns final averaged value!
```

**Issue:** The 5 individual measurements are collected but discarded. Students only see the final average, never the distribution.

---

### 3.2 Recommended Changes

#### A. Return Full Statistics from read_current()

**Change return value from:**
```python
return current
```

**To:**
```python
return {
    'current': average_current,
    'current_std': std_current,
    'current_n': len(R_trimmed),
    'cv_percent': cv,
    'individual_values': R_values
}
```

**Effort:** Low - data already collected

---

#### B. Real-time Distribution Display

**During measurement, show:**
```
[Measurement at 550 nm]

Individual readings:     Distribution:
  1: 1.234 nA            |
  2: 1.241 nA            |    ***
  3: 1.238 nA       =>   |   *****
  4: 1.229 nA            |    ***
  5: 1.237 nA            |
                         +----------
Mean: 1.236 nA           1.22  1.24  1.26 nA
Std:  0.004 nA
SE:   0.002 nA
```

**Effort:** Medium

---

#### C. Enhanced CSV Export

**Current format:**
```csv
Wavelength (nm), Current (A)
350, 1.234e-09
```

**Proposed format:**
```csv
Wavelength (nm), Current_mean (A), Current_std (A), Current_n, Current_CV%
350, 1.234e-09, 4.1e-12, 5, 0.33
```

**Effort:** Low

---

#### D. Per-Point Quality Indicator

**Color-coded CV% for each data point:**

| CV% | Color | Interpretation |
|-----|-------|----------------|
| <1% | Green | Excellent |
| 1-5% | Yellow | Acceptable |
| >5% | Red | Check measurement |

**Effort:** Low

---

### 3.3 Teaching SD vs SE

This is a specific course learning goal. Display during/after measurement:

```
5 measurements at 550 nm:
Individual values: 1.234, 1.241, 1.238, 1.229, 1.237 nA

Standard Deviation (σ) = 0.004 nA
  → Describes the SPREAD of individual measurements
  → "If I took one more measurement, it would probably be
     within ±0.008 nA of the mean"

Standard Error (SE) = σ/√n = 0.004/√5 = 0.002 nA
  → Describes UNCERTAINTY in the mean
  → "The true average is probably within ±0.004 nA of 1.236 nA"
```

**Effort:** Low (UI text addition)

---

## Part 4: Pedagogical Consideration

### The "Too Stable" Problem

**Observation:** 0.66% CV is excellent for research but may be pedagogically problematic.

**Risk:** If measurements never vary, students may conclude "measurements always give the same answer" - technically true for this system but wrong lesson.

### Proposed Solution: Educational Mode

Add optional "educational mode" with reduced integration time:
1. Student experiences visible variation (higher CV%)
2. Student increases integration time
3. Student observes CV% decrease
4. Student learns: averaging improves precision

**Implementation:**
- Add `num_cycles` slider/dropdown (default: 100, educational: 10-25)
- Show CV% in real-time
- Document the tradeoff: fewer cycles = faster but noisier

**Effort:** Medium

---

## Implementation Priority Matrix

| Enhancement | Learning Impact | Effort | Priority |
|------------|-----------------|--------|----------|
| Expose 5 individual measurements | HIGH | LOW | **CRITICAL** |
| Add SD and SE to display | HIGH | LOW | **HIGH** |
| CV% per wavelength point | MEDIUM | LOW | **HIGH** |
| Enhanced CSV export | MEDIUM | LOW | **HIGH** |
| Raw waveforms tab | HIGH | MEDIUM | **MEDIUM** |
| X-Y phasor display | MEDIUM | LOW | **MEDIUM** |
| Adjustable integration time | HIGH | MEDIUM | **MEDIUM** |
| FFT spectrum display | MEDIUM | MEDIUM | **LOWER** |
| Hilbert visualization | LOW | MEDIUM | **FUTURE** |

---

## PER Literature References

### Lock-in Teaching
- Singh & Zwickl (2016) - [Lock-in Tutorial (PRPER)](https://doi.org/10.1103/PhysRevPhysEducRes.12.020127) - Students treat lock-ins as black boxes
- [Low-Cost Pedagogical LIA (J. Chem. Ed.)](https://pubs.acs.org/doi/10.1021/acs.jchemed.9b00859) - Building understanding through transparency
- [TeachSpin Design Philosophy](https://www.teachspin.com/signal-processor-lock-in) - Teaching requires exposing internals

### Measurement Uncertainty
- Geschwind et al. (2024) - [SPRUCE (PRPER)](https://doi.org/10.1103/PhysRevPhysEducRes.20.020105) - Students struggle comparing measurements with uncertainty
- [SPRUCE for Instructors (JILA)](https://jila.colorado.edu/lewandowski/research/spruce-instructors-0) - Assessment tool
- [E-CLASS (JILA)](https://jila.colorado.edu/lewandowski/research/eclass-instructors-0) - Classroom vs professional practice gap

### Student Agency
- Holmes et al. (2020) - [Student Agency (PRPER)](https://journals.aps.org/prper/abstract/10.1103/PhysRevPhysEducRes.16.010109) - Students need to see consequences of decisions
- Holmes et al. - [Iteration and Learning (PRPER)](https://journals.aps.org/prper/abstract/10.1103/PhysRevPhysEducRes.17.020128) - Learning through parameter choices

---

## Next Steps

1. **Decision needed:** Which enhancements to implement for next semester?
2. **Decision needed:** Implement "educational mode" with visible variation?
3. **Action:** Modify `read_current()` to return statistics dict
4. **Action:** Update CSV export format
5. **Action:** Add statistics display to measurement UI

---

## Code Locations for Implementation

| File | What to Change |
|------|----------------|
| `eqe/controllers/picoscope_lockin.py` | Return stats dict from `read_current()` |
| `eqe/models/current_measurement.py` | Propagate individual values |
| `ui/eqe.html` + JavaScript | Add statistics display |
| `eqe/utils/data_handling.py` | Enhanced CSV export |
| `eqe/config/settings.py` | Add educational mode flag |

---

*Document created from PER mentor consultation, 2025-12-11*
