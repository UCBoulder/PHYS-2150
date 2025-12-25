# Staff Guide

Quick reference for TAs and instructors using the PHYS 2150 Measurement Suite.

## Keyboard Shortcuts

These shortcuts work in both EQE and J-V applications:

| Shortcut | Action | When to Use |
|----------|--------|-------------|
| `Ctrl+Shift+T` | Toggle console panel | View real-time log messages without external terminal |
| `Ctrl+Shift+D` | Toggle debug mode | See verbose technical output (SDK calls, raw values) |
| `Ctrl+Shift+E` | Toggle analysis panel | View calculated parameters during/after measurements |

### Console Panel (Ctrl+Shift+T)

Opens a collapsible panel showing application logs in real-time. Useful for:
- Monitoring measurement progress
- Seeing device connection status
- Viewing warnings and errors as they occur

The console shows the same output as the terminal window, but integrated into the UI.

### Debug Mode (Ctrl+Shift+D)

Enables verbose logging that includes:
- Raw ADC values and sample counts
- SDK function calls and return codes
- Lock-in calculation intermediates (X, Y, R, phase)
- Timing information for each operation

**When to enable:**
- Student reports "weird" measurements
- Debugging hardware communication issues
- Verifying lock-in is working correctly

**Note:** Debug output goes to the console panel. Open it with `Ctrl+Shift+T` first.

### Analysis Panel (Ctrl+Shift+E)

Shows calculated parameters that students don't normally see:

**EQE Application:**
- Real-time EQE calculation during wavelength scans
- Helps verify the measurement is producing sensible values

**J-V Application:**
- Solar cell parameters: Voc, Jsc, Fill Factor, PCE
- Extracted from the measured J-V curve

**When to use:**
- Verify EQE values look reasonable (typically 0-100%)
- Quick check of solar cell performance without exporting data

---

## Common Student Issues

### "The measurement won't start"

1. **Check device connections** (console will show connection errors)
2. **Is the chopper running?** - Listen for the hum. If off, you'll see a "Chopper Not Running" error
3. **Is another application using the PicoScope?** - Close PicoScope 7 software

### "EQE values seem wrong"

1. Enable analysis panel (`Ctrl+Shift+E`) to see calculated EQE in real-time
2. Check if EQE > 100% → power calibration may be stale or misaligned
3. Check if EQE ≈ 0% → cell may not be connected or aligned with beam

### "The plot looks noisy"

1. Enable debug mode (`Ctrl+Shift+D`) to see CV% per measurement
2. CV% > 5% suggests:
   - Lamp not warmed up (wait 15 min)
   - Loose cable connections
   - Chopper speed unstable

### "Measurement crashed / froze"

1. Check console (`Ctrl+Shift+T`) for error messages
2. If PicoScope related: unplug and replug USB, restart app
3. Check the log file: `eqe_debug.log` in the application directory

---

## Pre-Lab Checklist

### EQE System

- [ ] Lamp powered on and warmed up (15+ minutes)
- [ ] Chopper running at 81 Hz (listen for steady hum)
- [ ] PicoScope connected (blue LED lit)
- [ ] Monochromator USB connected
- [ ] Power meter USB connected
- [ ] Run a quick power calibration to verify system

### J-V System

- [ ] Keithley 2450 powered on
- [ ] USB cable connected
- [ ] Solar simulator warmed up
- [ ] Probe station contacts clean

### Quick Functional Test

```bash
# Test in offline mode first
uv run python -m eqe --offline
uv run python -m jv --offline

# Then with hardware
uv run python -m eqe
uv run python -m jv
```

---

## Log Files

| File | Contents |
|------|----------|
| `eqe_debug.log` | Full EQE application log with timestamps |
| `jv_debug.log` | Full J-V application log with timestamps |

These files are in the application directory and contain all debug-level messages, even when debug mode is off.

---

## Useful Terminal Commands

### Check device connections

```python
# VISA devices (Keithley, Monochromator)
import pyvisa
rm = pyvisa.ResourceManager()
print(rm.list_resources())

# PicoScope
from eqe.drivers.picoscope_driver import PicoScopeDriver
p = PicoScopeDriver()
p.connect()
print(f"Connected: {p.connected}, Type: {p.device_type}")
```

### Run with visible terminal output

```bash
# Windows - keeps terminal visible
uv run python -m eqe 2>&1 | tee debug.log
```

---

## Getting Help

- **Application issues:** Check [TROUBLESHOOTING.md](../TROUBLESHOOTING.md)
- **Hardware setup:** See [hardware-setup.md](hardware-setup.md)
- **Report bugs:** [GitHub Issues](https://github.com/UCBoulder/PHYS-2150/issues)
