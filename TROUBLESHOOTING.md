# EQE System Troubleshooting Guide

## Table of Contents
1. [PicoScope Connection Issues](#picoscope-connection-issues)
2. [Stability Problems](#stability-problems)
3. [Signal Issues](#signal-issues)
4. [Hardware Problems](#hardware-problems)
5. [Software Errors](#software-errors)
6. [Data Quality Issues](#data-quality-issues)

---

## PicoScope Connection Issues

### Problem: "Failed to connect to PicoScope"

**Possible Causes:**
1. PicoScope not connected via USB
2. PicoSDK drivers not installed
3. Python picosdk package not installed
4. USB power issue
5. Device in use by another application

**Solutions:**
```powershell
# Check if picosdk is installed
pip list | findstr picosdk

# Install if missing
pip install picosdk

# Check PicoScope is detected by Windows
# (Device Manager → Sound, video and game controllers → PicoScope)
```

**Additional steps:**
- Try a different USB port (USB 3.0 recommended)
- Restart PicoScope (unplug/replug USB)
- Close PicoScope 6 software if running
- Reboot computer if persistent

### Problem: "Using 15-bit resolution for 2-channel operation"

**This is NORMAL:** The PicoScope 5242D uses 15-bit resolution when capturing 2 channels simultaneously. This is a hardware limitation and still provides excellent performance (32,768 levels).

**Not an error** - just informational.

---

## Stability Problems

### Problem: High Coefficient of Variation (CV > 10%)

**Expected Performance:** CV should be < 5% (typically 0.66-2%)

**Diagnostic Steps:**

1. **Check trigger threshold:**
   ```powershell
   python check_reference.py
   ```
   - Look at "Midpoint (for trigger)" value
   - Should be ~2.5V for 0-5V square wave
   - If different, update `picoscope_driver.py` line 454:
     ```python
     threshold = 2500  # mV - adjust to match your reference midpoint
     ```

2. **Verify reference signal:**
   - Check reference waveform is clean square wave
   - Amplitude should be 0-5V (TTL logic levels)
   - Frequency should match chopper (typically 81 Hz)
   - No noise or ringing on edges

3. **Run stability test:**
   ```powershell
   python test_picoscope_stability.py
   ```
   - Should show CV < 5%
   - If CV > 10%, check:
     - Lamp stability (warm up 10-15 minutes)
     - Chopper running smoothly
     - All cables securely connected
     - No vibrations or air currents

4. **Check for saturation:**
   - Lock-in output should be 0.1-0.9V
   - If near ±1V, signal may be saturating
   - Reduce light intensity or change transimpedance gain

### Problem: Measurements drifting over time

**Symptoms:** First half of measurement different from second half

**Causes:**
1. Lamp not warmed up (wait 15+ minutes)
2. Temperature changes in room
3. Loose connections
4. Chopper speed drift

**Solutions:**
- Let system warm up fully before measurements
- Control room temperature
- Check all cable connections
- Verify chopper speed with oscilloscope
- Run long-term stability test to quantify drift:
  ```powershell
  python test_longterm_stability.py
  ```

---

## Signal Issues

### Problem: Very low signal (< 0.01V)

**Possible Causes:**
1. No light reaching detector
2. Wrong wavelength
3. Chopper off
4. Detector not biased correctly
5. Transimpedance amplifier issue

**Checks:**
- Verify lamp is on and warmed up
- Check monochromator is at correct wavelength
- Confirm chopper is running (visual check)
- Verify detector bias voltage
- Check transimpedance amplifier output with oscilloscope

### Problem: Signal saturating (near ±20V)

**Cause:** Too much light or transimpedance gain too high

**Solutions:**
- Reduce light intensity (add ND filter)
- Reduce transimpedance amplifier gain
- Check for stray light entering detector

### Problem: Noisy signal (large variations)

**Possible Causes:**
1. Lamp flicker
2. Loose connections
3. Ground loops
4. Electrical interference

**Solutions:**
- Use lamp with stable power supply
- Check and tighten all BNC connections
- Use proper grounding (star ground configuration)
- Shield signal cables
- Keep power cables away from signal cables

---

## Hardware Problems

### Problem: Monochromator not responding

**Checks:**
1. USB-to-Serial adapter connected and powered
2. Correct COM port selected
3. Drivers installed properly

**Solutions:**
```powershell
# List available COM ports
python -c "import serial.tools.list_ports; print([p.device for p in serial.tools.list_ports.comports()])"
```

- Try different COM port
- Check Device Manager for COM port number
- Reinstall USB-to-Serial driver
- Try different USB port

### Problem: Power meter not reading

**Checks:**
1. Power meter powered on
2. USB cable connected
3. Wavelength set correctly on power meter
4. Sensor connected properly

**Solutions:**
- Verify sensor head is plugged in securely
- Set wavelength on power meter to match monochromator
- Check power meter displays reading in manual mode
- Reinstall Thorlabs OPM software

### Problem: Chopper not detected

**Symptoms:** Reference signal flat or noisy

**Checks:**
1. Chopper powered on
2. TTL output connected to PicoScope CH B
3. Chopper speed set correctly (81 Hz typical)

**Solutions:**
- Check reference signal with oscilloscope
- Verify 0-5V square wave at chopper frequency
- Clean TTL output signal may need pull-up resistor
- Check ground connection between chopper and PicoScope

---

## Software Errors

### Problem: "ImportError: No module named 'picosdk'"

**Solution:**
```powershell
pip install picosdk
```

### Problem: "ImportError: No module named 'PySide6'"

**Solution:**
```powershell
pip install PySide6
```

### Problem: "VISA resource not found"

**Symptoms:** Error when connecting to Keithley or other VISA instruments

**Solution:**
```powershell
# Install NI-VISA or Keysight IO Libraries
# Then install Python VISA wrapper
pip install pyvisa
```

### Problem: GUI freezes during measurement

**Cause:** Threading issue or measurement taking too long

**Solutions:**
- Close and restart GUI
- Check no errors in terminal/console output
- Reduce number of wavelength points for testing
- Check all devices responding (test individually)

### Problem: "Error reading from PicoScope"

**Check:**
1. PicoScope still connected (USB cable)
2. Device not in error state
3. Memory not full
4. Timeout settings appropriate

**Solutions:**
- Reconnect PicoScope
- Restart application
- Check Windows Event Viewer for USB errors
- Try different USB port

---

## Data Quality Issues

### Problem: EQE values unrealistically high (> 100%)

**Possible Causes:**
1. Incorrect power calibration
2. Wrong wavelength units
3. Stray light
4. Calculation error

**Checks:**
- Verify power measurement was done at same wavelengths
- Check units (nm vs μm, A vs μA)
- Block light and verify current goes to zero
- Recalculate EQE manually for one point

### Problem: EQE spectrum has unexpected features

**Possible Causes:**
1. Filter changes not handled correctly
2. Grating changes not handled correctly
3. Stray light at certain wavelengths
4. Detector artifacts

**Solutions:**
- Check filter transitions (420 nm, 800 nm)
- Verify grating change (685 nm)
- Run power measurement to characterize lamp spectrum
- Compare to expected spectrum for device type

### Problem: Phase adjustment fails (R² < 0.9)

**Symptoms:** Warning dialog appears during phase adjustment

**Causes:**
1. Very low signal (below noise floor)
2. No chopper signal
3. Detector not working
4. Wrong wavelength

**Solutions:**
- Check signal level is reasonable (> 0.01V)
- Verify chopper is running
- Test at wavelength with known response (e.g., 550 nm for Si)
- Increase light intensity temporarily for phase adjustment

---

## Diagnostic Tools

### Check Reference Signal
```powershell
python check_reference.py
```
**Use when:** Debugging trigger or stability issues  
**Output:** Reference signal statistics and recommended trigger threshold

### Quick Stability Test (1 minute)
```powershell
python test_picoscope_stability.py
```
**Use when:** Quick check of measurement stability  
**Output:** CV from 20 consecutive measurements

### Long-term Stability Test (2-10 minutes)
```powershell
python test_longterm_stability.py
```
**Use when:** Validating system before important measurements  
**Output:** Comprehensive stability analysis with drift detection

### Plot Stability Results
```powershell
python plot_stability.py longterm_stability_YYYYMMDD_HHMMSS.csv
```
**Use when:** Analyzing stability test results  
**Output:** Publication-quality plots and statistics

---

## Performance Benchmarks

### Expected Performance
- **CV:** < 5% (typically 0.66-2%)
- **Drift:** < 2% over 10 minutes
- **Signal range:** 0.01V to 1V (no saturation)
- **Phase adjustment R²:** > 0.95

### Red Flags
- CV > 10% → Investigate stability
- Drift > 5% → Check lamp/temperature
- Signal < 0.001V → Too low (increase light/gain)
- Signal > 1V → Approaching saturation (reduce light/gain)
- R² < 0.9 → Phase adjustment problem

---

## Getting Help

### Information to Collect
When reporting issues, include:
1. Error message (full text from console)
2. CV value from stability test
3. Reference signal characteristics (from check_reference.py)
4. Hardware configuration (PicoScope model, software versions)
5. When problem started (after what change?)

### Log Files
Application log file location:
```
eqe_mvc/eqe_application.log
```

Check for error messages and timestamps matching when problem occurred.

---

## Quick Reference: Common Parameter Values

### Typical Operating Parameters
- **Chopper frequency:** 81 Hz
- **Trigger threshold:** 2500 mV (for 0-5V reference)
- **Decimation:** 1024 (fixed)
- **Sampling rate:** 97,656 Hz
- **Samples per measurement:** ~120,563
- **Measurements per wavelength:** 5
- **Cycles per measurement:** 100

### File Locations
- **Main GUI:** `eqe/eqeguicombined-filters-pyside.py`
- **Driver:** `eqe/picoscope_driver.py`
- **Diagnostics:** `eqe/check_reference.py`, `eqe/test_*_stability.py`

### Important Settings
- **Trigger threshold:** `picoscope_driver.py` line 454
- **Decimation:** `picoscope_driver.py` line 294
- **Measurements:** `eqeguicombined-filters-pyside.py` line 302
