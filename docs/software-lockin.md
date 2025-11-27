# Software Lock-in Amplifier

This document explains the software lock-in amplifier implemented using the PicoScope oscilloscope for EQE measurements.

## Overview

Traditional EQE systems use external lock-in amplifiers (e.g., Stanford Research SR510) - expensive, specialized instruments. Our system replaces this with a **software lock-in** running on a PicoScope oscilloscope, achieving:

- **0.66% coefficient of variation** (15× better than 10% target)
- **±20V input range** (no signal clipping)
- **Lower cost** (oscilloscope vs dedicated lock-in)
- **Digital precision** (no analog drift)

## Lock-in Amplifier Basics

### The Problem: Signal Buried in Noise

The solar cell produces a tiny AC signal (nanoamps) modulated at the chopper frequency (81 Hz). This signal is buried in:

- 60 Hz power line noise
- Broadband thermal noise
- 1/f (flicker) noise
- Random interference

```
Signal Spectrum:
     Amplitude
        ↑
        │    Noise floor
        │░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
        │░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
        │░░░░░░█░░░░░░░░░░░░░░░░░░░░░░░░░░  ← Signal at 81 Hz
        │░░░░░░█░░░░░░░░░░░░░░░░░░░░░░░░░░
        │░░░░░░█░░░░░░░░░░░░░░░░░░░░░░░░░░
        └──────┼──────────────────────────→ Frequency
              81 Hz
```

### The Solution: Lock-in Detection

Lock-in amplifiers extract signals at a specific frequency by:

1. **Multiply** signal by reference at same frequency
2. **Average** (low-pass filter) the result
3. **Result**: Only signal at reference frequency survives

```
Signal × Reference → Average = DC output proportional to signal
```

Mathematically:
- Signal: S(t) = A·sin(ωt + φ)
- Reference: R(t) = sin(ωt)
- Product: S×R = (A/2)·[cos(φ) - cos(2ωt + φ)]
- Average: ⟨S×R⟩ = (A/2)·cos(φ)

The cos(φ) term depends on phase - that's why we need quadrature detection.

## Quadrature Detection

To get both magnitude and phase, we use two references 90° apart:

```
Signal × cos(ωt) → Average → X (in-phase component)
Signal × sin(ωt) → Average → Y (quadrature component)

Magnitude: R = √(X² + Y²)   ← Phase-independent!
Phase:     θ = arctan(Y/X)
```

The magnitude R is independent of phase - crucial for stable measurements when phase drifts.

## Our Implementation

### Hilbert Transform for Quadrature Generation

Traditional lock-ins use analog circuits to generate the 90° shifted reference. We use the **Hilbert transform** - a digital signal processing technique:

```python
from scipy.signal import hilbert

# Reference signal from chopper (square wave)
reference = acquire_channel_B()

# Generate quadrature using Hilbert transform
analytic_signal = hilbert(reference)
ref_cos = reference                    # In-phase (0°)
ref_sin = np.imag(analytic_signal)     # Quadrature (90°)
```

The Hilbert transform creates the "analytic signal" - a complex signal where:
- Real part = original signal
- Imaginary part = 90° phase-shifted signal

### Complete Algorithm

```python
def software_lockin(signal, reference):
    # 1. Remove DC offsets
    signal = signal - np.mean(signal)
    reference = reference - np.mean(reference)

    # 2. Normalize reference
    ref_rms = np.sqrt(np.mean(reference**2))
    reference = reference / ref_rms

    # 3. Generate quadrature reference
    analytic = hilbert(reference)
    ref_cos = reference
    ref_sin = np.imag(analytic)

    # 4. Mix signal with references
    mixed_cos = signal * ref_cos
    mixed_sin = signal * ref_sin

    # 5. Low-pass filter (average)
    X = 2 * np.mean(mixed_cos)
    Y = 2 * np.mean(mixed_sin)

    # 6. Calculate magnitude and phase
    R = np.sqrt(X**2 + Y**2)
    theta = np.arctan2(Y, X)

    return R, theta
```

### Why Factor of 2?

The factor of 2 in step 5 compensates for the mixing process. When you multiply two sinusoids:

```
sin(ωt) × sin(ωt) = ½[1 - cos(2ωt)]
```

The average is ½, not 1. The factor of 2 recovers the original amplitude.

## Acquisition Parameters

### Optimized for Stability

After extensive testing, these parameters achieve 0.66% CV:

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| Decimation | 1024 | ~97.6 kHz sampling rate |
| Samples/cycle | ~1205 | Good Hilbert transform resolution |
| Cycles | 100 | Sufficient averaging |
| Total samples | ~120,563 | ~1.2 seconds integration |

### Why These Values?

**Decimation = 1024:**
- PicoScope 5242D base rate: 100 MS/s
- Effective rate: 100 MS/s ÷ 1024 = 97,656 Hz
- At 81 Hz chopper: 97,656 ÷ 81 ≈ 1205 samples/cycle
- Hilbert transform needs ~10+ samples/cycle for accuracy
- 1205 samples/cycle provides excellent resolution

**100 Cycles Integration:**
- More cycles = better noise averaging
- 100 cycles at 81 Hz = 1.23 seconds
- Balances accuracy vs measurement time
- Lock-in equivalent time constant: ~1 second

## Phase-Locked Triggering

### The Stability Secret

Early versions had ~5% CV. The key improvement: **phase-locked triggering**.

```
Reference signal (chopper TTL):
    ┌───┐   ┌───┐   ┌───┐   ┌───┐   ┌───┐
    │   │   │   │   │   │   │   │   │   │
────┘   └───┘   └───┘   └───┘   └───┘   └───

Trigger at 2.5V (midpoint):
    ─────────►
         ↑
    Consistent trigger point
```

By triggering on the reference signal's rising edge at a fixed threshold (2.5V), every acquisition starts at the same phase of the chopper cycle.

### Trigger Configuration

```python
# Trigger on Channel B (reference) at 2.5V rising edge
threshold_mV = 2500  # Midpoint of 0-5V TTL
direction = "RISING"
```

Without phase-locked triggering, random starting phases cause ~5× worse stability.

## Why No Correction Factor Needed?

### The SR510 Problem

The previous system used an SR510 analog lock-in. It required a 0.45 correction factor because:

1. **Sine wave reference**: SR510 uses pure sine reference
2. **Square wave signal**: Chopper produces square wave
3. **Harmonic loss**: Sine reference only detects fundamental
4. **Missing energy**: Harmonics (3rd, 5th, 7th...) are lost

```
Square wave Fourier series:
    4/π × [sin(ωt) + sin(3ωt)/3 + sin(5ωt)/5 + ...]

Fundamental only = π/4 ≈ 0.785 of RMS
SR510 correction = 0.45 (empirically measured)
```

### Our Solution

The software lock-in uses the **actual square wave reference**:

1. **Square wave reference**: Direct from chopper TTL
2. **Square wave signal**: From modulated light
3. **All harmonics preserved**: Hilbert transform works on actual waveform
4. **No correction needed**: Digital precision

```python
# We use the actual chopper waveform as reference
# NOT a synthesized sine wave
reference = acquire_channel_B()  # Real square wave
```

## Measurement Averaging

### Trimmed Mean for Robustness

Each wavelength point averages 5 measurements. To handle outliers:

```python
def trimmed_mean(values, trim_fraction=0.2):
    """Average after removing extreme values"""
    sorted_vals = sorted(values)
    n = len(sorted_vals)
    trim = int(n * trim_fraction)
    return np.mean(sorted_vals[trim:n-trim])
```

This removes the highest and lowest values, providing robust averaging against occasional glitches.

## Hardware Configuration

### PicoScope 5242D (Recommended)

| Specification | Value |
|--------------|-------|
| Resolution | 15-bit (2-channel mode) |
| Bandwidth | 60 MHz |
| Max sample rate | 125 MS/s |
| Input range | ±20V |
| Memory | 128 MS |

### PicoScope 2204A (Alternative)

| Specification | Value |
|--------------|-------|
| Resolution | 8-bit |
| Bandwidth | 10 MHz |
| Max sample rate | 50 MS/s |
| Input range | ±20V |
| Memory | 8 kS |

Both provide ±20V input range - no clipping issues.

### Channel Configuration

```
PicoScope
├── Channel A: Solar cell signal
│   └── via transimpedance amplifier
│   └── Range: ±20V (auto-ranging)
│
└── Channel B: Chopper reference
    └── TTL square wave (0-5V)
    └── Trigger source
```

## Performance Validation

### Stability Test Results

```
Measurement    Value (V)    Deviation
1              0.4521       +0.2%
2              0.4518       -0.1%
3              0.4515       -0.2%
4              0.4522       +0.2%
5              0.4519        0.0%
...
20             0.4520       +0.1%

Mean:          0.4519 V
Std Dev:       0.0030 V
CV:            0.66%
```

### Comparison to SR510

| Metric | SR510 (Analog) | PicoScope (Digital) |
|--------|---------------|---------------------|
| CV | ~2-5% | 0.66% |
| Drift | Noticeable | Negligible |
| Input range | ±1V | ±20V |
| Correction factor | 0.45 | 1.0 |
| Cost | $3,000+ | $1,500 |

## Troubleshooting

### High CV (>5%)

1. **Check trigger threshold**: Should be 2.5V for 0-5V reference
2. **Verify reference signal**: Clean square wave on oscilloscope
3. **Check connections**: All cables secure
4. **Lamp stability**: Wait 15+ minutes warm-up

### No Signal

1. **Chopper running?**: Visual check
2. **Reference on CH B?**: Check oscilloscope display
3. **Signal on CH A?**: Should see modulated waveform
4. **Correct frequency?**: Must match chopper (81 Hz default)

### Erratic Readings

1. **Ground loops**: Check grounding configuration
2. **Interference**: Move cables away from power lines
3. **Preamp saturation**: Check signal levels

## Code Location

```
eqe/
├── drivers/
│   └── picoscope_driver.py    # Low-level SDK interface
│       └── software_lockin()  # Main lock-in function
│       └── _acquire_block()   # Data acquisition
│
└── controllers/
    └── picoscope_lockin.py    # High-level controller
        └── measure()          # User-facing measurement
```

## References

- "The Art of Electronics" - Horowitz & Hill (lock-in amplifier chapter)
- Hilbert Transform: scipy.signal.hilbert documentation
- PicoScope SDK Programmer's Guide
- Stanford Research SR510 Manual (for comparison)
