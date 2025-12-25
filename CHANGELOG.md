# Changelog

All notable changes to the PHYS 2150 Measurement Suite are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [3.0.0] - 2025-12-24

### Added
- **Web-based user interface** using HTML/CSS/JavaScript with Plotly.js for interactive plots
- Qt WebEngine + QWebChannel architecture for Python-JavaScript communication
- In-app debug console panel (Ctrl+Shift+T) for viewing application logs without external terminal
- I-V Analysis staff tab with solar cell parameter extraction (Voc, Isc, Jsc, FF, PCE, Pmax, Rs, Rsh)
- EQE Analysis staff tab with integrated Jsc calculation from spectral response
- Stability Test tab for system validation with time series and histogram views
- Save Results buttons for analysis data export
- Web-based unified launcher with streamlined application selection
- Application icons for launcher and web interfaces
- GPU acceleration for web UI components
- Keyboard shortcuts from launcher (E for EQE, I for I-V)
- Modern scrollbar styling for console panel
- Staff guide with keyboard shortcuts and diagnostic tips
- Chopper frequency validation to prevent crash when chopper is off

### Changed
- **BREAKING**: Complete UI architecture change from PySide6 Qt widgets to web technologies (HTML/CSS/JS)
- **BREAKING**: Python-JS communication now uses QWebChannel instead of Qt signals/slots
- Interactive plots now use Plotly.js instead of Matplotlib (zoom, pan, hover tooltips)
- Modern CSS theming with consistent component styling across all applications
- PicoScope ps2000 SDK stability improvements (settling time between acquisitions, proper stop calls)

### Removed
- **BREAKING**: Legacy Qt widget UI code (~5,500 lines removed): `*/views/`, `*/main.py`, `common/ui/`
- **BREAKING**: Matplotlib-based plot widgets (replaced by Plotly.js)
- Redundant qtwebengine_launcher.py prototype file

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
- Console output now shows human-readable units (nA, uA) instead of scientific notation

### Removed
- Newport MonoUtility no longer required as a dependency
- Deprecated MONOCHROMATOR_CORRECTION_FACTORS configuration

## [2.2.0] - 2025-12-22

### Added
- Manual monochromator controls: wavelength setting, shutter open/close, filter status display
- Live Signal Monitor for real-time photocurrent viewing during alignment
- Green Dot alignment button moved to Monochromator Controls panel
- Comprehensive test suite implementation plan documentation

### Changed
- Lock-in correction factor validated at 0.5 via AWG testing
- Launcher UI simplified (removed problematic description text)
- Documentation updated with validated lock-in parameters and phase sensitivity notes
- Documentation standardized naming from "PHYS-2150" to "PHYS 2150"
- Configuration values centralized to eliminate DRY violations

### Fixed
- CSV export now preserves nanoamp-scale current values (was rounding to zero)
- Application closes cleanly when launched from unified launcher
- Cell number now syncs properly to model when set via dialog

## [2.1.0] - 2025-12-02

### Added
- PicoScope 2204A support using the ps2000 SDK (different API from ps2000a, limit 2000 samples for dual-channel)
- `read_lockin_current()` method to PicoScopeController for stability test compatibility
- Lock-in validation module with AWG control scripts
- Corrected lock-in algorithms with configuration selection (Hilbert: 0.5 correction factor, Synthesized: -2.5% error)
- Keysight EDU33212A AWG validation test for lock-in verification
- Lab session handoff document for EQE validation
- PicoSDK DLL path added to environment on Windows

### Changed
- Stability test now disables individual input widgets instead of entire config group (allows stop button to remain active)
- Matplotlib canvas focus policy set to NoFocus to prevent focus capture issues

### Fixed
- Stability test stop button not responding during test execution
- Alignment button handler accessing undefined `status_display` attribute
- Qt focus issues when PicoScope 2204A shows firmware upload splash screen
- Buttons now disabled during device initialization to prevent focus problems

## [2.0.0] - 2025-11-27

### Added
- Complete MVC (Model-View-Controller) architecture refactor
- PicoScope software lock-in amplifier (replaces SR510 hardware lock-in)
- Stability test GUI for validating system performance
- Offline mode (`--offline` flag) for GUI testing without hardware
- PySide6-based GUI (migrated from tkinter)
- Automated filter wheel switching based on wavelength
- Phase adjustment visualization with R-squared quality metric
- Unified launcher for EQE and J-V applications
- Cell/pixel numbering convention updated (8 pixels per substrate)
- Detailed comments added to all configuration parameters
- License file (MIT)

### Changed
- **BREAKING**: Software architecture completely restructured into MVC pattern
- **BREAKING**: Software lock-in eliminates need for 0.45 correction factor (uses actual square wave reference)
- Improved measurement stability: 0.66% CV (15x better than 10% target)
- +/-20V input range prevents signal clipping

### Removed
- **BREAKING**: SR510 analog lock-in amplifier support (legacy hardware)
- **BREAKING**: Keithley 2110 DMM support (was used with SR510)
- **BREAKING**: tkinter GUI

## [1.0.0] - 2025-04-22

### Added
- Filter wheel hardware support with automated wavelength-based switching
- Cell and pixel naming conventions for file output
- Phase adjustment and plotting functionality
- Correction factors for measurement accuracy

### Changed
- Improved GUI layout and usability
- Enhanced measurement workflows

## [0.1.0] - 2024-09-06

### Added
- Initial development release deployed for student use
- EQE measurement with SR510 hardware lock-in amplifier
- J-V measurement with Keithley 2450 SMU
- Monochromator control for wavelength scanning
- Basic tkinter GUI for measurements
- CSV data export
- Transimpedance amplifier integration
- Threading for non-blocking measurements

---

## Version History Summary

| Version | Date | Key Changes |
|---------|------|-------------|
| 3.0.0 | 2025-12-24 | Web UI with Plotly.js, Qt WebEngine architecture |
| 2.3.0 | 2025-12-23 | Tiered logging, measurement stats export, nanoamps format |
| 2.2.0 | 2025-12-22 | Manual monochromator controls, Live Signal Monitor |
| 2.1.0 | 2025-12-02 | PicoScope 2204A support, lock-in validation, stability test fixes |
| 2.0.0 | 2025-11-27 | MVC refactor, PicoScope software lock-in, PySide6 GUI |
| 1.0.0 | 2025-04-22 | Filter wheel automation, improved workflows |
| 0.1.0 | 2024-09-06 | Initial development release with SR510 lock-in |

[Unreleased]: https://github.com/UCBoulder/PHYS-2150/compare/v3.0.0...HEAD
[3.0.0]: https://github.com/UCBoulder/PHYS-2150/compare/v2.3.0...v3.0.0
[2.3.0]: https://github.com/UCBoulder/PHYS-2150/compare/v2.2.0...v2.3.0
[2.2.0]: https://github.com/UCBoulder/PHYS-2150/compare/v2.1.0...v2.2.0
[2.1.0]: https://github.com/UCBoulder/PHYS-2150/compare/v2.0.0...v2.1.0
[2.0.0]: https://github.com/UCBoulder/PHYS-2150/compare/v1.0.0...v2.0.0
[1.0.0]: https://github.com/UCBoulder/PHYS-2150/compare/v0.1.0...v1.0.0
[0.1.0]: https://github.com/UCBoulder/PHYS-2150/releases/tag/v0.1.0
