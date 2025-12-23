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

The driver automatically optimizes parameters based on the PicoScope model:

### PicoScope 5242D Parameters

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| Decimation | 1024 | ~97.6 kHz sampling rate |
| Samples/cycle | ~1205 | Excellent Hilbert transform resolution |
| Max samples | 200,000 | Large buffer allows many cycles |
| Typical cycles | 100 | ~1.2 seconds integration |

**Why These Values (5242D):**

- Base rate: 100 MS/s
- Effective rate: 100 MS/s ÷ 1024 = 97,656 Hz
- At 81 Hz chopper: 97,656 ÷ 81 ≈ 1205 samples/cycle
- Hilbert transform needs ~10+ samples/cycle for accuracy
- 1205 samples/cycle provides excellent resolution

### PicoScope 2204A Parameters

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| Timebase | 12 | ~24.4 kHz sample rate (40960 ns/sample) |
| Samples/cycle | ~301 | Adequate for Hilbert transform |
| Max samples | 2000 | Limited buffer in dual-channel mode |
| Typical cycles | 6 | ~82 ms of data per acquisition |

**Why These Values (2204A):**

- The 2204A has limited buffer memory (~8 KB total, ~4 KB per channel)
- With both channels enabled, max samples ≈ 4000 per channel
- We use 2000 to stay safely within limits
- Timebase 12 provides slower sampling to capture more cycles
- At 81 Hz chopper: 24,414 ÷ 81 ≈ 301 samples/cycle
- Still sufficient for accurate Hilbert transform (needs ~10+)

**2204A Limitations:**

- Fewer samples per acquisition means less averaging per measurement
- The EQE controller compensates by taking multiple acquisitions
- CV is slightly higher than 5242D but still adequate for measurements

### Common Parameters

**Cycles Integration:**

- More cycles = better noise averaging
- PicoScope 5242D: ~100 cycles at 81 Hz = 1.23 seconds
- PicoScope 2204A: ~6 cycles at 81 Hz = 74 ms (driver takes multiple readings)
- Balances accuracy vs measurement time

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

## Correction Factor

### Why 0.5 Correction Factor?

The software lock-in requires a **0.5 correction factor** to report accurate amplitudes. This was validated through AWG testing (see Validation Results below).

The correction compensates for the RMS normalization in the Hilbert algorithm:

```python
# In the algorithm, reference is normalized to unit RMS
ref_rms = np.sqrt(np.mean(ref_normalized**2))
ref_normalized = ref_normalized / ref_rms
```

For a square wave, this normalization introduces a 2× scaling that the 0.5 factor corrects.

### Configuration

The correction factor is set in `eqe/config/settings.py`:

```python
DeviceType.PICOSCOPE_LOCKIN: {
    "correction_factor": 0.5,  # Validated via AWG testing
    # ...
}
```

### Comparison to SR510

The previous SR510 analog lock-in required a 0.45 correction factor for a different reason - it used a sine wave reference with a square wave signal, losing harmonic content. Our software lock-in uses the actual square wave reference, but still requires correction due to the RMS normalization math.

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
| SDK | `ps5000a` |

### PicoScope 2204A (Alternative)

| Specification | Value |
|--------------|-------|
| Resolution | 8-bit |
| Bandwidth | 10 MHz |
| Max sample rate | 100 MS/s (single), 50 MS/s (dual) |
| Input range | ±20V |
| Memory | 8 KB (shared between channels) |
| SDK | `ps2000` (NOT ps2000a!) |

Both provide ±20V input range - no clipping issues.

> **Important:** The 2204A uses the `ps2000` SDK with a different API than newer models. The driver handles this automatically, selecting the correct SDK based on what's available. See [TROUBLESHOOTING.md](../TROUBLESHOOTING.md#picoscope-2204a-specific-issues) for 2204A-specific issues.

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
| Correction factor | 0.45 | 0.5 |
| Cost | $3,000+ | $1,500 |

### AWG Validation Results

The lock-in algorithm was validated using known test signals from function generators:

**PicoScope AWG Test (81 Hz square wave):**

| Metric | Result |
|--------|--------|
| Amplitude accuracy | ±0.7% (with 0.5 correction) |
| Linearity R² | 0.999998 |
| Noise floor | 0.36 mV |

**Keysight EDU33212A AWG Test:**

| Metric | Result |
|--------|--------|
| Amplitude accuracy | +0.73% |
| Frequency response (50-200 Hz) | -0.77% stable |

**Transimpedance Amplifier Verification:**

| Metric | Result |
|--------|--------|
| Measured TIA gain | 1.004 MΩ |
| Expected | 1.000 MΩ |
| Error | 0.4% |

### Phase Sensitivity Note

The Hilbert algorithm's R value depends on phase alignment between signal and reference:

- **0° offset**: Correct amplitude
- **90° offset**: ~29% low
- **180° offset**: Correct amplitude (but negative X)

This is not an issue when signal and reference both come from the same physical chopper, as they maintain constant phase relationship.

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
- [Official ps2000 Python examples](https://github.com/picotech/picosdk-python-wrappers/tree/master/ps2000Examples) - Reference for 2204A implementation
- [PicoScope 2000 Series Programmer's Guide](https://www.picotech.com/download/manuals/picoscope-2000-series-a-api-programmers-guide.pdf)
