# Correction Factor Analysis for PicoScope Integration

## Executive Summary
**The 0.45 correction factor should be ELIMINATED for PicoScope lock-in measurements.**

## Background: Why SR510 Needed 0.45 Correction Factor

### Analog Lock-in (SR510) Signal Path:
1. **Input**: Square wave photocurrent signal (riding on DC offset from background light)
2. **SR510 Internal Processing**:
   - Multiplies input with internal **sine wave oscillator**
   - Square wave contains fundamental + odd harmonics (33% @ 3f, 20% @ 5f, 14% @ 7f, etc.)
   - Sine reference only extracts fundamental component
   - All harmonic content is rejected as "out of phase"
3. **Result**: Output amplitude is ~45% of true signal amplitude
4. **Correction**: Divide by 0.45 (or multiply by ~2.22) to recover true amplitude

### Mathematical Basis:
For a square wave with amplitude A:
- Fourier series: A * [sin(ωt) + (1/3)sin(3ωt) + (1/5)sin(5ωt) + ...]
- Fundamental component: A * sin(ωt)
- When multiplied with sine reference and time-averaged: ~0.45 * A
- This 0.45 factor comes from the envelope of the square wave harmonics

## PicoScope Software Lock-in: No Correction Needed

### Digital Lock-in Signal Path:
1. **Channel A**: Captures actual photocurrent waveform
2. **Channel B**: Captures actual square wave reference from chopper
3. **Digital Processing**:
   ```python
   ref_normalized = reference_data - np.mean(reference_data)
   ref_normalized = ref_normalized / np.sqrt(np.mean(ref_normalized**2))  # RMS normalize
   
   # Hilbert transform creates quadrature
   ref_cos = ref_normalized  # In-phase = actual square wave
   ref_sin = np.imag(hilbert(ref_normalized))  # Quadrature = 90° shifted
   
   # Mix with signal
   X = 2 * np.mean(signal * ref_cos)  # Factor of 2 for RMS conversion
   Y = 2 * np.mean(signal * ref_sin)
   R = np.sqrt(X**2 + Y**2)  # Magnitude - this is the output!
   ```

4. **Key Difference**: Multiplies with **actual square wave**, not sine approximation!
5. **Result**: All harmonic content is preserved and properly correlated
6. **No correction needed**: The factor of 2 in the algorithm is mathematically correct for RMS

### Why Hilbert Transform Doesn't Reduce Amplitude:
- Hilbert transform is a **phase shift**, not amplitude modification
- It creates the analytic signal: z(t) = x(t) + j*H{x(t)}
- |z(t)| = |x(t)| for real signals
- The quadrature component maintains the same amplitude envelope

## Recommendation

### Remove from PicoScope Code:
✅ **DONE**: Removed correction factor from `PicoScopeController`
✅ **DONE**: Updated current measurement to not apply correction
✅ **DONE**: Updated config to remove correction factor
✅ **DONE**: Updated experiment initialization

### MONOCHROMATOR_CORRECTION_FACTORS Clarification

**CONFIRMED**: The `MONOCHROMATOR_CORRECTION_FACTORS` dict in config/settings.py was **misnamed**. 
Despite the name, these were actually **SR510 lock-in correction factors**, not optical corrections.

```python
# OLD (incorrect with PicoScope):
MONOCHROMATOR_CORRECTION_FACTORS = {
    "130B5203": 0.45,  # These were SR510 corrections!
    "130B5201": 0.45,
    "130B5202": 0.45
}

# NEW (correct with PicoScope):
MONOCHROMATOR_CORRECTION_FACTORS = {
    "130B5203": 1.0,  # No correction needed with software lock-in
    "130B5201": 1.0,
    "130B5202": 1.0
}
```

**All 0.45 factors have been changed to 1.0** since the PicoScope software lock-in 
doesn't need correction (uses actual square wave reference, not sine approximation).

If **true optical corrections** are needed in the future (e.g., for grating/filter efficiency),
they should be measured separately and added as a different configuration parameter.

## Expected Impact on Measurements

### With SR510 (old):
```
True signal amplitude: 1.00 V
SR510 output: 0.45 V (harmonic loss)
After correction (÷0.45): 1.00 V ✓
```

### With PicoScope (new, incorrect if using 0.45):
```
True signal amplitude: 1.00 V
PicoScope output: 1.00 V (no harmonic loss)
After incorrect correction (÷0.45): 2.22 V ✗ (222% too high!)
```

### With PicoScope (correct, no correction):
```
True signal amplitude: 1.00 V
PicoScope output: 1.00 V (no harmonic loss)
No correction: 1.00 V ✓
```

## Verification Test

To verify this is correct, perform the following test:

1. **Set up test signal**: Connect function generator with 81 Hz square wave (0-1V)
2. **Measure with oscilloscope**: Note peak-to-peak amplitude (should be ~1V)
3. **Measure with PicoScope software lock-in**: Note R magnitude output
4. **Expected result**: R should be ~1V (no 0.45 attenuation)
5. **If R ≈ 0.45V**: Something is wrong with the algorithm
6. **If R ≈ 1V**: Correction factor removal is correct! ✓

## References

1. **Square Wave Fourier Series**: 
   - Fundamental: (4/π) ≈ 1.273
   - RMS value: 1.0 (for ±1 square wave)
   - Peak value: 1.0

2. **Lock-in Amplifier Theory**:
   - Analog mixers extract fundamental only
   - Digital mixers can use arbitrary reference waveforms
   - Phase-sensitive detection: R = |X + jY|

3. **Hilbert Transform**:
   - Property: Preserves amplitude, shifts phase by 90°
   - Creates analytic signal for single-sideband representation
   - Does NOT reduce signal magnitude
