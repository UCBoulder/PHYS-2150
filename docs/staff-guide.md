# Staff Guide

Quick reference for TAs and instructors using the PHYS 2150 Measurement Suite.

## Keyboard Shortcuts

### Global Shortcuts (work everywhere)

| Shortcut | Action | When to Use |
|----------|--------|-------------|
| `Ctrl+Shift+C` | Toggle light/dark theme | Personal preference or screen glare |

### Launcher Shortcuts

| Shortcut | Action | When to Use |
|----------|--------|-------------|
| `Ctrl+Shift+D` | Toggle offline mode | Test GUI without hardware (indicator appears in UI) |
| `E` | Launch EQE | Quick launch |
| `I` | Launch J-V | Quick launch |

### In-App Shortcuts (EQE and J-V)

| Shortcut | Action | When to Use |
|----------|--------|-------------|
| `Ctrl+Shift+T` | Toggle terminal panel | View real-time log messages |
| `Ctrl+Shift+L` | Open log viewer | View full debug logs from file |
| `Ctrl+Shift+D` | Toggle print capture | See print() statements in terminal |
| `Ctrl+Shift+E` | Toggle analysis panel | View calculated parameters during/after measurements |

### Terminal Panel (Ctrl+Shift+T)

Opens a collapsible panel showing application logs in real-time. Shows:
- INFO, WARNING, and ERROR level messages
- Device connection status
- Measurement progress updates

### Log Viewer (Ctrl+Shift+L)

Opens a modal showing the full debug log file from `%LOCALAPPDATA%\PHYS2150\`. This includes ALL log messages (including DEBUG level) and persists across sessions. Features:
- **Copy** button to copy logs for sharing
- **Refresh** button to reload
- Press **Esc** to close

**When to use:**
- Reviewing what happened during a failed measurement
- Sharing logs with developers for bug reports
- Seeing detailed technical output

### Print Capture (Ctrl+Shift+D)

Captures `print()` statements and shows them in the terminal panel. These are low-level debug messages that normally only appear in the system console.

**When to enable:**
- Debugging stability test issues (shows `[STAB]` messages)
- Seeing raw hardware communication details
- When log viewer doesn't show enough detail

**Note:** Open the terminal panel (`Ctrl+Shift+T`) first to see captured output.

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

1. Open terminal panel (`Ctrl+Shift+T`) to see CV% per measurement
2. CV% > 5% suggests:
   - Lamp not warmed up (wait 15 min)
   - Loose cable connections
   - Chopper speed unstable

### "Measurement crashed / froze"

1. Check terminal panel (`Ctrl+Shift+T`) for error messages
2. Open log viewer (`Ctrl+Shift+L`) for detailed history
3. If PicoScope related: unplug and replug USB, restart app
4. Log files are in `%LOCALAPPDATA%\PHYS2150\` (e.g., `eqe_debug.log`)

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

Log files are stored in `%LOCALAPPDATA%\PHYS2150\` (typically `C:\Users\<username>\AppData\Local\PHYS2150\`). They contain ALL log messages including DEBUG level and rotate automatically at 5 MB. Use the **Log Viewer** (`Ctrl+Shift+L`) to view these files directly in the application.

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
