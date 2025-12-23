# Lock-In Amplifier Validation Plan

## Overview

This document captures our analysis of the software lock-in amplifier implementation and outlines a testing plan to validate its accuracy using the PicoScope 2204A's built-in AWG.

## Current Implementation Summary

**Location:** `eqe/drivers/picoscope_driver.py` (lines 513-566)

The software lock-in uses a **Hilbert transform** approach:
1. Acquire signal + square-wave reference from chopper
2. Remove DC offset from both channels
3. Normalize reference to unit RMS
4. Generate 90° quadrature via Hilbert transform
5. Multiply signal × reference (in-phase & quadrature)
6. Average to get X, Y components
7. Compute R = √(X² + Y²)

### Key Code Sections
- Lock-in algorithm: `eqe/drivers/picoscope_driver.py:513-566`
- Current calculation: `eqe/controllers/picoscope_lockin.py:195-273`
- Configuration: `eqe/config/settings.py:66-73`

---

## Identified Limitations

| Limitation | Description | Severity |
|------------|-------------|----------|
| **No true low-pass filter** | Uses simple averaging instead of proper time-constant filter | Medium |
| **Hilbert edge effects** | Hilbert transform has artifacts at signal boundaries | Low-Medium |
| **Square wave reference normalization** | Normalizes to unit RMS, which affects amplitude scaling | **High** |
| **Limited samples per cycle** | ~15 samples/cycle at 81 Hz with current settings | Medium |
| **Hardcoded transimpedance gain** | Assumes exactly 1 MΩ (line 268) | Medium |

---

## Key Question: Is the Reported Current Correct?

### The Scaling Concern

The code normalizes the reference signal to unit RMS:
```python
ref_rms = np.sqrt(np.mean(ref_normalized**2))
ref_normalized = ref_normalized / ref_rms
```

For a square wave, this affects the mixing result differently than for a sine wave. The current implementation claims "no correction factor needed" compared to the old SR510 analog lock-in, but the math suggests there may still be a systematic scaling error of **10-25%**.

### What We Don't Know
1. The exact calibration factor for the current algorithm
2. Whether the Hilbert transform introduces additional scaling
3. If the transimpedance amplifier is actually 1 MΩ

### Impact on EQE Measurements
- **Relative measurements** (comparing wavelengths): Likely unaffected if error is systematic
- **Absolute current values**: May be off by a constant factor
- **EQE calculation**: Depends on power measurement accuracy too

---

## Proposed Test Setup

### Hardware: PicoScope 2204A AWG

**Specifications:**
- Signal generator: Up to 100 kHz (81 Hz test frequency is easy)
- Waveforms: Sine, square, triangle, DC, arbitrary
- Output: Separate BNC connector from Ch A/B
- Buffer: 4096 samples

### Physical Wiring

```
┌─────────────────────────┐
│    PicoScope 2204A      │
│                         │
│  [AWG Out]  [Ch A] [Ch B]
│      │        │      │
└──────┼────────┼──────┼──┘
       │        │      │
       │   ┌────┴──────┘
       │   │
       └───┴──→ BNC Tee ──┬──→ Ch A (signal)
                          └──→ Ch B (reference)
```

**Hardware needed:** One BNC Tee (or two BNC cables from a splitter)

### Test Concept

1. **AWG generates:** 81 Hz square wave, known amplitude (e.g., 2V peak-to-peak)
2. **Both channels receive:** Identical signal via BNC tee
3. **Lock-in processes:** Should report a predictable R value
4. **Compare:** Measured R vs. expected R based on input amplitude

Since signal and reference are identical and phase-locked, this isolates the lock-in algorithm from real-world noise or hardware variations.

---

## Test Suite

| Test | Purpose | Equipment |
|------|---------|-----------|
| **AWG Self-Test** | Validate lock-in math and scaling | PicoScope only + BNC tee |
| **Linearity Test** | Verify linear response over dynamic range | PicoScope + attenuators |
| **Frequency Response** | Confirm independence from chopper frequency | PicoScope (sweep 50-200 Hz) |
| **Noise Floor** | Determine detection limit | PicoScope (input grounded) |
| **TIA Gain Validation** | Verify transimpedance amplifier is 1 MΩ | Keithley 2450 |

---

## Implementation Plan

### Phase 1: Simulation (No Hardware)
- [ ] Create synthetic square wave data matching AWG output
- [ ] Run through exact lock-in algorithm from `picoscope_driver.py`
- [ ] Calculate expected R value for given input amplitude
- [ ] Derive theoretical calibration factor

### Phase 2: AWG Driver Implementation
- [ ] Add `ps2000_set_sig_gen_built_in()` wrapper to driver
- [ ] Create test mode that generates known waveform
- [ ] Function signature for ps2000:
  ```python
  ps2000.ps2000_set_sig_gen_built_in(
      handle,
      offset_uV,      # Offset voltage in µV
      pk_to_pk_uV,    # Peak-to-peak voltage in µV
      wave_type,      # 0=sine, 1=square, 2=triangle
      start_freq,     # Start frequency in Hz
      stop_freq,      # Stop frequency in Hz
      freq_change,    # Frequency change per interval
      interval,       # Interval of frequency change
      sweep_dir,      # 0=up
      num_sweeps      # Number of sweeps
  )
  ```

### Phase 3: Hardware Validation
- [ ] Connect AWG → BNC tee → Ch A + Ch B
- [ ] Run AWG self-test at multiple amplitudes
- [ ] Compare measured R to predicted R
- [ ] Calculate empirical calibration factor if needed

### Phase 4: Keithley Cross-Validation (Optional)
- [ ] Source known DC currents into transimpedance amp
- [ ] Verify 1 MΩ gain assumption
- [ ] Full-chain test with Keithley + analog switch for chopped current

---

## Mathematical Background

### Square Wave Fourier Series
```
square(t) = (4/π) × [sin(ωt) + (1/3)sin(3ωt) + (1/5)sin(5ωt) + ...]
```

### Expected Lock-In Response

For identical square waves on both channels after normalization:

1. Reference: ±A volts → normalized to ±1 (unit RMS)
2. Signal: ±A volts, DC removed
3. Mixing: `signal × ref_normalized`
4. The factor of 2 in `X = 2 * np.mean(mixed_cos)` is for RMS conversion

**Key question to answer via simulation:** What is the exact ratio R/A for a square wave input of amplitude A?

---

## Algorithm Improvement Ideas

Based on our analysis, the lock-in algorithm itself is the best place to focus improvements (rather than changing chopper frequency from 81 Hz).

### Current Weaknesses

1. **Simple averaging as low-pass filter**
   - Current: `X = 2 * np.mean(mixed_cos)`
   - Problem: Equivalent to a sinc filter with poor stopband rejection
   - Improvement: Use proper IIR/FIR low-pass filter with defined time constant

2. **Hilbert transform edge effects**
   - Problem: Hilbert transform has Gibbs-like ringing at signal boundaries
   - Improvement: Apply window function (Hann, Blackman) before Hilbert, or use synthesized reference

3. **Square wave reference normalization**
   - Current: Normalizes measured reference to unit RMS
   - Problem: Introduces scaling that depends on waveform shape
   - Improvement: Use synthesized sine reference at measured frequency

4. **No explicit time constant**
   - Current: Integration time = num_cycles / frequency
   - Problem: No standard "time constant" like analog lock-ins (100ms, 300ms, 1s)
   - Improvement: Implement configurable time constant with proper filter rolloff

### Proposed Algorithm: Synthesized Reference Lock-In

Instead of using the actual (noisy, imperfect) square wave reference, synthesize clean sine/cosine at the measured frequency:

```python
def improved_lockin(signal_data, reference_data, fs):
    # 1. Measure reference frequency from actual signal
    freq = measure_frequency(reference_data, fs)

    # 2. Generate synthesized sine/cosine reference (clean, no harmonics)
    t = np.arange(len(signal_data)) / fs
    ref_cos = np.cos(2 * np.pi * freq * t)
    ref_sin = np.sin(2 * np.pi * freq * t)

    # 3. Remove DC from signal
    signal_ac = signal_data - np.mean(signal_data)

    # 4. Mix with synthesized references
    mixed_cos = signal_ac * ref_cos
    mixed_sin = signal_ac * ref_sin

    # 5. Low-pass filter (proper filter, not just averaging)
    # Butterworth filter with cutoff << reference frequency
    from scipy.signal import butter, filtfilt
    cutoff = freq / 10  # e.g., 8 Hz for 81 Hz reference
    b, a = butter(2, cutoff / (fs/2), btype='low')
    X = 2 * np.mean(filtfilt(b, a, mixed_cos))
    Y = 2 * np.mean(filtfilt(b, a, mixed_sin))

    # 6. Magnitude and phase
    R = np.sqrt(X**2 + Y**2)
    theta = np.arctan2(Y, X)

    return R, theta, freq
```

### Advantages of Synthesized Reference

| Aspect | Current (Hilbert) | Proposed (Synthesized) |
|--------|-------------------|------------------------|
| Reference purity | Contains harmonics, noise | Pure sine, no harmonics |
| Scaling | Depends on square wave shape | Predictable: R = signal amplitude |
| Edge effects | Hilbert ringing | None |
| Phase alignment | Automatic via Hilbert | Requires frequency measurement |
| Harmonic rejection | None (locks to all harmonics) | Excellent (only fundamental) |

### Trade-off: Harmonic Content

The current algorithm preserves harmonic content from the chopped signal, which may be desirable since the photocurrent is essentially a square-wave-modulated DC signal. However, this makes the scaling factor dependent on the square wave duty cycle and shape.

The synthesized reference approach gives cleaner, more predictable results but only extracts the fundamental frequency component.

**Recommendation:** Implement both and compare via AWG testing. The synthesized approach should give more accurate absolute measurements.

### Other Improvements to Consider

1. **Phase-locked loop (PLL)** - Track frequency variations in real-time
2. **Adaptive filtering** - Adjust filter bandwidth based on signal SNR
3. **Harmonic analysis** - Measure 2nd, 3rd harmonics for diagnostics
4. **Noise estimation** - Report measurement uncertainty from Y component variance
5. **Saturation detection** - Better handling of clipped signals

---

## References

- [PicoScope 2204A Specifications](https://www.picotech.com/oscilloscope/2000/picoscope-2000-overview?model=2204A)
- [PicoScope 2000 Series Data Sheet](https://www.picotech.com/download/datasheets/picoscope-2000-series-data-sheet-en.pdf)
- [ps2000 Python Examples](https://www.picotech.com/library/knowledge-bases/oscilloscopes/python-examples-for-picoscope-2000-series-ps2000-api-scopes)
- [PicoScope 2204A Waveform Generator Forum](https://www.picotech.com/support/viewtopic.php?t=42134)

---

## Files to Modify

When implementing:
- `eqe/drivers/picoscope_driver.py` - Add AWG control methods
- `eqe/controllers/picoscope_lockin.py` - Add test/calibration mode
- New file: `eqe/tests/test_lockin_validation.py` - Simulation and hardware tests

---

## Notes

*Last updated: December 2025*

*Status: Planning phase - ready to implement simulation*
