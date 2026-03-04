# Offline Mode for GUI Testing

## Overview

The EQE MVC application supports an **offline mode** that allows you to test and develop the GUI without connecting to hardware. This is particularly useful when working away from the lab.

## Usage

### Running in Offline Mode

To start the application in offline mode, use the `--offline` flag:

```powershell
python eqe/main.py --offline
```

Or with the full Python path:

```powershell
C:/Python312/python.exe eqe/main.py --offline
```

### Running in Normal Mode (with Hardware)

To run with actual hardware connections (default):

```powershell
python eqe/main.py
```

## What Happens in Offline Mode?

### ✅ Enabled Features
- **GUI loads normally** - All windows, widgets, and controls are functional
- **Parameter input** - You can enter and validate measurement parameters
- **Device status display** - Shows "OFFLINE MODE" for all devices
- **File dialogs** - Save and load operations still work
- **Plot widgets** - Displays are available for testing

### ❌ Disabled Features
- **Device initialization** - Hardware connection attempts are skipped
- **Measurements** - Power, current, and phase measurements cannot run
- **Monochromator control** - Cannot move to wavelengths or enable alignment dot
- **Hardware errors** - No device connection errors will appear

## Behavior

When offline mode is active:

1. **Startup**: Application shows "Running in OFFLINE mode" message
2. **Device Status**: All devices show as connected with "OFFLINE MODE" status
3. **Measurement Buttons**: Clicking measurement buttons will show an error:
   ```
   "Cannot perform measurements in OFFLINE mode"
   ```
4. **Controls**: Attempting to control hardware shows:
   ```
   "Cannot control hardware in OFFLINE mode"
   ```

## Configuration

Offline mode can also be enabled programmatically by editing `config/settings.py`:

```python
# Application mode
OFFLINE_MODE = True  # Set to True to run without hardware (for GUI testing)
```

However, using the command-line flag is recommended as it doesn't require editing code.

## Use Cases

### GUI Development
Test layout changes, widget behavior, and user interactions without hardware.

### Parameter Testing
Validate input forms, parameter validation logic, and error messages.

### Documentation
Capture screenshots and create tutorials without needing lab access.

### Remote Work
Develop and test code changes from home or while traveling.

## Technical Details

### Implementation
- Command-line argument parsing in `main.py`
- Global `OFFLINE_MODE` flag in `config/settings.py`
- Device initialization checks in `models/eqe_experiment.py`
- Measurement prevention in all measurement start methods

### Safety
Offline mode includes checks to prevent:
- Attempted hardware communication
- Invalid measurement operations
- Device control commands
- File operations that require hardware data

## Example Session

```powershell
PS> python eqe/main.py --offline
Running in OFFLINE mode - hardware initialization disabled
2025-10-09T05:15:30.123456 [INFO] Model and view components connected
2025-10-09T05:15:30.124567 [INFO] EQE Application initialized
2025-10-09T05:15:30.125678 [INFO] Running in OFFLINE mode - skipping hardware initialization
2025-10-09T05:15:30.126789 [INFO] Offline mode - devices simulated successfully

# GUI opens with all devices showing "OFFLINE MODE" status
# All controls are visible and responsive
# Attempting measurements shows friendly error message
```

## Tips

1. **Always use offline mode** when developing away from the lab
2. **Test with hardware** before deploying changes to ensure compatibility
3. **Document changes** made in offline mode for lab verification
4. **Use version control** to track offline vs. online testing

## Troubleshooting

**Q: I'm in the lab but offline mode is enabled**
- A: Don't use the `--offline` flag, or check `OFFLINE_MODE` in `settings.py`

**Q: Can I test data processing in offline mode?**
- A: Yes! Load existing CSV files and test plotting/analysis features

**Q: Will offline mode work with all Python versions?**
- A: Yes, the `argparse` module is part of the standard library

## Future Enhancements

Potential improvements for offline mode:
- Simulated measurement data generation
- Mock device responses for testing error handling
- Replay mode using recorded measurement sessions
- Configuration profiles for different hardware setups
