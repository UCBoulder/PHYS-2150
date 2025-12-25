# Changelog

All notable changes to the PHYS 2150 Measurement Suite are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]

### Added
- **Web-based user interface** using HTML/CSS/JavaScript with Plotly.js for interactive plots
- Qt WebEngine + QWebChannel architecture replaces Qt widgets for Python-JavaScript communication
- In-app debug console panel (Ctrl+Shift+T) for viewing application logs without external terminal
- Chopper frequency validation detects when chopper is off and aborts gracefully with student-friendly error message
- Web-based unified launcher with streamlined application selection

### Changed
- **Complete UI overhaul**: Migrated from PySide6 Qt widgets to web technologies (HTML/CSS/JS)
- Modern CSS theming with consistent component styling across all applications
- Interactive plots now use Plotly.js instead of Matplotlib (zoom, pan, hover tooltips)
- PicoScope ps2000 SDK stability improvements (settling time between acquisitions, proper stop calls)

### Removed
- Legacy Qt widget UI code (~5,500 lines removed): `*/views/`, `*/main.py`, `common/ui/`
- Matplotlib-based plot widgets replaced by Plotly.js

## [2.3.0] - 2025-12-23

### Added
- Tiered logging system with measurement statistics display (mean, std dev, n, CV%)
- Optional measurement statistics export in CSV files (std_dev, n, CV% columns)
- Staff debug mode (Ctrl+Shift+D) to view technical debug messages in console
- Staff EQE visualization mode (Ctrl+Shift+E) for viewing calculated EQE during scans

### Changed
- Current measurements now exported in nanoamps (nA) for readability instead of scientific notation
- Removed outlier rejection from measurements - students now see honest statistics including variability
- Measurement statistics (CV%) displayed in real-time during wavelength scans
- Improved window sizing for better fit on various screen resolutions
- Cell number dialog now pre-selects text for faster entry
- Monochromator controls disabled during active measurements to prevent conflicts

### Fixed
- Console output now shows human-readable units (nA, µA) instead of scientific notation

### Removed
- Newport MonoUtility no longer required as a dependency

## [2.2.0] - 2025-12-22

### Added
- Manual monochromator controls: wavelength setting, shutter open/close, filter status display
- Live Signal Monitor for real-time photocurrent viewing during alignment
- Green Dot alignment button moved to Monochromator Controls panel

### Fixed
- CSV export now preserves nanoamp-scale current values (was rounding to zero)
- Application closes cleanly when launched from unified launcher

### Changed
- Lock-in correction factor validated at 0.5 via AWG testing
- Launcher UI simplified (removed problematic description text)
- Documentation updated with validated lock-in parameters and phase sensitivity notes

## [2.1.0] - 2025-12-02

### Fixed
- Fixed stability test stop button not responding during test execution
- Fixed alignment button handler accessing undefined `status_display` attribute
- Fixed Qt focus issues when PicoScope 2204A shows firmware upload splash screen
- Buttons are now disabled during device initialization to prevent focus problems

### Added
- Added `read_lockin_current()` method to PicoScopeController for stability test compatibility
- Added PicoScope 2204A support using the ps2000 SDK (different API from ps2000a)

### Changed
- Stability test now disables individual input widgets instead of entire config group (allows stop button to remain active)
- Matplotlib canvas focus policy set to NoFocus to prevent focus capture issues

## [2.0.0] - 2025-11-27

### Added
- Complete MVC (Model-View-Controller) architecture refactor
- PicoScope software lock-in amplifier (replaces SR510 hardware lock-in)
- Stability test GUI for validating system performance
- Offline mode (`--offline` flag) for GUI testing without hardware
- PySide6-based GUI (migrated from tkinter)
- Automated filter wheel switching based on wavelength
- Phase adjustment visualization with R² quality metric
- Unified launcher for EQE and J-V applications

### Changed
- Software lock-in eliminates need for 0.45 correction factor (uses actual square wave reference)
- Improved measurement stability: 0.66% CV (15× better than 10% target)
- ±20V input range prevents signal clipping
- Cell/pixel numbering convention updated (8 pixels per substrate)

### Removed
- SR510 analog lock-in amplifier support (legacy)
- Keithley 2110 DMM support (was used with SR510)
- tkinter GUI

## [1.0.0] - 2025-04-22

### Added
- Initial release
- EQE measurement with SR510 lock-in amplifier
- J-V measurement with Keithley 2450 SMU
- Basic GUI for measurements
- CSV data export

---

## Version History Summary

| Version | Date | Key Changes |
|---------|------|-------------|
| 2.3.0 | 2025-12-23 | Tiered logging, measurement stats export, nanoamps format |
| 2.2.0 | 2025-12-22 | Manual monochromator controls, Live Signal Monitor, CSV bug fix |
| 2.1.0 | 2025-12-02 | Bug fixes for stability test and PicoScope 2204A support |
| 2.0.0 | 2025-11-27 | MVC refactor, PicoScope software lock-in, PySide6 GUI |
| 1.0.0 | 2025-04-22 | Initial release with SR510 lock-in |
