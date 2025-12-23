# PHYS-2150 Troubleshooting Guide

Comprehensive troubleshooting for both J-V and EQE measurement systems.

## Table of Contents

1. [General Issues](#general-issues)
2. [J-V Measurement Issues](#j-v-measurement-issues)
3. [EQE Measurement Issues](#eqe-measurement-issues)
4. [Hardware Problems](#hardware-problems)
5. [Software Errors](#software-errors)
6. [Diagnostic Tools](#diagnostic-tools)
7. [Performance Benchmarks](#performance-benchmarks)

---

## General Issues

### Application Won't Start

**Symptoms:** Error on launch, window doesn't appear

**Solutions:**

```bash
# Check Python version (requires 3.10+)
python --version

# Reinstall dependencies
pip install -r requirements.txt

# Or with UV
uv sync
```

### GUI Freezes

**Cause:** Long operation blocking main thread

**Solutions:**

1. Wait for current operation to complete
2. Check console for error messages
3. Restart application
4. Try offline mode: `python -m jv --offline` or `python -m eqe --offline`

---

## J-V Measurement Issues

### Device Not Found

```text
Keithley 2450 device not found.
```

**Checks:**

1. USB cable connected?
2. Device powered on?
3. NI-VISA Runtime installed?

**Diagnostic:**

```python
import pyvisa
rm = pyvisa.ResourceManager()
print(rm.list_resources())
# Should show USB0::0x05E6::0x2450::...
```

**Solutions:**

- Open NI MAX to verify device appears
- Try different USB port
- Restart Keithley 2450
- Reinstall NI-VISA Runtime

### Unstable Current Readings

**Symptoms:** Noisy, jumping values

**Checks:**

1. 4-wire connections secure?
2. Cell contacts clean?
3. Cables properly shielded?

**Solutions:**

- Increase dwell time in `jv/config/settings.py`:

  ```python
  "dwell_time_ms": 1000,  # Increase from 500
  ```

- Use 4-wire sensing (enabled by default)
- Check for ground loops
- Shield from light fluctuations

### Current Compliance Reached

**Symptoms:** Current plateaus at unexpected value

**Cause:** Cell current exceeds safety limit (default 1A)

**Solutions:**

1. Increase compliance in config (carefully):

   ```python
   "current_compliance": 2,  # Amps
   ```

2. Reduce illumination intensity
3. Check for short circuit in cell

### Large Hysteresis (>20%)

**Symptoms:** Forward and reverse scans differ significantly

**Causes:**

1. Perovskite ion migration
2. Measurement too fast
3. Cell degradation

**Solutions:**

- Increase dwell time (500ms → 1000ms)
- Increase inter-sweep delay
- Let cell stabilize before measurement
- Check cell condition

### No Data File Created

**Checks:**

1. Valid cell number? (must be 3 digits)
2. Write permissions on folder?
3. Disk space available?

---

## EQE Measurement Issues

### PicoScope Connection Failed

```text
Failed to connect to PicoScope
```

**Checks:**

1. PicoScope connected via USB
2. PicoSDK drivers installed
3. `picosdk` Python package installed

**Solutions:**

```bash
pip install picosdk
```

- Try USB 3.0 port
- Close PicoScope 7 software if running (it locks the device)
- Restart computer

### PicoScope 2204A Specific Issues

The PicoScope 2204A uses a **different SDK** than newer models. This is a common source of connection problems.

#### PICO_NOT_FOUND or PICO_OPEN_OPERATION_IN_PROGRESS (Error 3)

**Symptom:** Connection fails with status code 3, or device not found even though PicoScope software works.

**Root Cause:** The 2204A uses `ps2000` SDK, NOT `ps2000a`. The API is different:

| Feature | ps2000 (2204A) | ps2000a (newer) |
|---------|----------------|-----------------|
| Open function | Returns handle directly | Returns via pointer |
| Assertion | `assert_pico2000_ok()` | `assert_pico_ok()` |
| Success value | Non-zero = success | Zero = success |

**Solution:** The driver automatically tries ps2000 first. If you're writing custom code:

```python
# CORRECT for PicoScope 2204A
from picosdk.ps2000 import ps2000 as ps
from picosdk.functions import assert_pico2000_ok

# Open returns handle directly (not via pointer!)
handle_value = ps.ps2000_open_unit()
if handle_value > 0:
    chandle = ctypes.c_int16(handle_value)
    print(f"Connected with handle: {handle_value}")
```

**Reference:** [Official ps2000 examples](https://github.com/picotech/picosdk-python-wrappers/tree/master/ps2000Examples)

#### Timebase Query Fails with Dual Channels

**Symptom:** `ps2000_get_timebase` returns status 0 (failure) when both channels are enabled.

**Cause:** The 2204A has limited buffer memory (~8KB total). With both channels, each gets ~4KB. Requesting too many samples fails.

**Solution:** Limit sample count to 2000 for dual-channel mode:

```python
# Max samples for dual-channel on 2204A
num_samples = min(num_samples, 2000)
```

#### USB Disconnect/Reconnect Sounds

**Symptom:** Windows plays USB disconnect/connect sounds when PicoScope software opens.

**Cause:** This is normal! The 2204A uploads firmware on each connection. The splash screen indicates firmware upload is in progress.

**Solution:** Wait for the splash screen to close before attempting API calls. The driver handles this automatically.

#### PicoScope Software Works, Python Doesn't

**Symptom:** PicoScope 7 software connects fine, but Python code fails.

**Causes:**

1. PicoScope software is still running (locks the device)
2. Using wrong SDK (ps2000a instead of ps2000)
3. Calling `ps2000_open_unit()` multiple times

**Solutions:**

1. Close PicoScope 7 completely
2. Wait 5-10 seconds after closing
3. Ensure only one call to `open_unit()` per session

### High CV (>10%)

**Expected:** CV < 5% (typically 0.66-2%)

**Diagnostic steps:**

1. **Check trigger threshold** - Should be 2500 mV for 0-5V TTL reference
2. **Verify reference signal** - Clean 0-5V square wave at 81 Hz
3. **Check lamp** - Warmed up 15+ minutes?
4. **Check connections** - All cables secure?

**Solutions:**

- Adjust trigger threshold in `eqe/drivers/picoscope_driver.py`
- Let lamp warm up longer
- Tighten all BNC connections
- Check chopper is running smoothly

### Measurements Drifting

**Symptoms:** Values change over measurement duration

**Causes:**

1. Lamp not fully warmed (wait 15+ min)
2. Temperature changes
3. Chopper speed drift

**Solutions:**

- Extended lamp warm-up
- Control room temperature
- Verify chopper frequency

### Very Low Signal (<0.01V)

**Checks:**

1. Lamp on?
2. Chopper running?
3. Correct wavelength?
4. Beam aligned?
5. Preamp powered?

### Signal Saturating (>1V)

**Cause:** Too much light or preamp gain too high

**Solutions:**

- Add neutral density filter
- Reduce preamp gain
- Check for stray light

### EQE > 100%

**Causes:**

1. Power calibration at wrong position
2. Stray light during current measurement
3. Wrong transimpedance gain in config
4. Mismatched data files

**Solutions:**

- Recalibrate power at sample position
- Block stray light
- Check `transimpedance_gain` in settings
- Verify using same wavelength range

---

## Hardware Problems

### Monochromator Not Responding

**Checks:**

1. USB-to-Serial adapter connected
2. Correct COM port
3. Drivers installed

**Find COM port:**

```python
import serial.tools.list_ports
print([p.device for p in serial.tools.list_ports.comports()])
```

### Power Meter Not Reading

**Checks:**

1. Device powered on
2. Sensor head attached securely
3. USB connected
4. Wavelength set correctly

**Solutions:**

- Test in standalone Thorlabs OPM software
- Reinstall Thorlabs drivers

### Chopper Reference Missing

**Symptoms:** No trigger, flat reference signal

**Checks:**

1. Chopper powered on
2. TTL output connected to PicoScope CH B
3. Speed set to 81 Hz

**Solutions:**

- Check reference with oscilloscope
- Verify 0-5V square wave
- Check ground connection

---

## Software Errors

### Import Errors

```python
ImportError: No module named 'PySide6'
```

**Solution:**

```bash
pip install PySide6 numpy scipy pandas matplotlib pyvisa picosdk
```

### VISA Resource Not Found

**Solution:**

1. Install NI-VISA Runtime
2. `pip install pyvisa`

### Qt Platform Error

**Symptoms:** `qt.qpa.plugin: Could not load the Qt platform plugin`

**Solutions:**

- Reinstall PySide6
- Check for conflicting Qt installations (PyQt5, PyQt6)

---

## Diagnostic Tools

### Test VISA Connection

```python
import pyvisa
rm = pyvisa.ResourceManager()
print(rm.list_resources())
```

### Test Keithley

```python
from jv.controllers.keithley_2450 import Keithley2450Controller
k = Keithley2450Controller()
k.connect()
print(k.get_identification())
```

### Test PicoScope

```python
from eqe.drivers.picoscope_driver import PicoScopeDriver
p = PicoScopeDriver()
p.connect()
print(f"Connected: {p.connected}, Type: {p.device_type}")
```

### Offline Mode

Test GUI without hardware:

```bash
python -m jv --offline
python -m eqe --offline
```

---

## Performance Benchmarks

### J-V Expected Performance

| Metric | Expected |
|--------|----------|
| Full sweep time | ~30 seconds |
| Voltage resolution | 0.001V |
| Current noise | <1 µA |
| Hysteresis | <10% (perovskites may be higher) |

### EQE Expected Performance

| Metric | Expected |
|--------|----------|
| CV | <5% (typical 0.66%) |
| Drift | <2% over 10 min |
| Signal range | 0.01-1.0V |
| Phase R² | >0.95 |

### Red Flags

| Issue | Threshold | Action |
|-------|-----------|--------|
| J-V noise | >10 µA | Check connections |
| EQE CV | >10% | Check trigger/reference |
| Drift | >5% | Check lamp/temperature |
| Signal | <0.001V | Increase light/gain |
| Signal | >1V | Reduce light/gain |

---

## Getting Help

### Information to Collect

1. Full error message from console
2. What operation was being performed
3. Hardware configuration
4. Software versions (`pip list`)
5. Recent changes to setup

### File Locations

| File | Purpose |
|------|---------|
| `jv/config/settings.py` | J-V parameters |
| `eqe/config/settings.py` | EQE parameters |
| `eqe/drivers/picoscope_driver.py` | PicoScope settings |

### Report Issues

[GitHub Issues](https://github.com/UCBoulder/PHYS-2150/issues)
