# Changelog

All notable changes to the PHYS 2150 Measurement Suite are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Comprehensive WCAG 2.1 AA accessibility improvements:
  - Skip navigation links on all pages (visible on focus)
  - ARIA dialog semantics (`role="dialog"`, `aria-modal`, `aria-labelledby`) on all modals
  - ARIA tabpanel pattern (`role="tablist"`, `role="tab"`, `role="tabpanel"`) on tab interfaces
  - Focus trap in modals to keep keyboard navigation within dialog
  - Semantic `<main>` landmarks and visually-hidden `<h1>` headings
  - `aria-live="polite"` on status messages and device connection text
  - `aria-describedby` linking form inputs to error messages
  - `aria-hidden="true"` on decorative SVG icons
  - Focus-visible styling on console panel buttons
- Console panel Copy button to copy all messages to clipboard
- Console panel drag-to-resize (drag top edge to adjust height)
- Log viewer modal (`Ctrl+Shift+L`) to view debug logs directly in the application
  - Shows last 50 lines from `%LOCALAPPDATA%\PHYS2150\{app}_debug.log`
  - "Open Full Log" button to open complete log in Notepad
  - Copy and Refresh buttons, Esc to close
- Print capture mode (`Ctrl+Shift+D`) redirects print() statements to terminal panel
  - Captures `TieredLogger.debug_output()` and other print() calls
  - Shows `[print]` prefix to distinguish from logger output
- Keyboard dismiss for info/error modals (OK button auto-focused, press Enter to close)
- `PHYS2150_DISABLE_REMOTE_CONFIG` environment variable to skip remote config fetching during development
- Comprehensive test suite with 201 tests (29% code coverage):
  - Unit tests for math utilities, data handling, statistics (86 tests)
  - Model tests with mock controllers (74 tests)
  - Integration tests for measurement workflows (41 tests)
- Mock controllers for testing without hardware (Keithley, PicoScope, Monochromator, Power Meter)
- Stability test model tests (power/current tests, statistics calculation)
- Data export tests (CSV export, JV data, EQE measurements)
- Coverage configuration in pyproject.toml with pytest-cov

### Changed
- Dark mode `--text-muted` color improved from #999999 to #ababab for WCAG AA contrast compliance (4.74:1 ratio)
- Modal titles changed from `<div>` to `<h2>` for proper heading hierarchy
- `Ctrl+Shift+D` now toggles print capture instead of debug log levels (simpler, more useful)
- Debug logs now written to `%LOCALAPPDATA%\PHYS2150\` for Windows compatibility when installed to Program Files
- EQE device status bar now shows clean "Connected"/"Not Connected" text (detailed errors remain in console)
- EQE now attempts all device connections even if some fail (shows complete status instead of stopping at first failure)

### Fixed
- Taskbar showing Python icon instead of app icon when running from source (set Windows AppUserModelID)
- JS syntax errors from unescaped carriage returns in device status messages
- Monochromator showing "Connected (S/N: None)" even when device not found (controller now checks bFound flag)
- Device connection status messages not written to debug log file (only appeared in terminal panel)

## [3.1.0] - 2025-12-25

### Added
- Visual feedback when launching apps from launcher
- Remote config support for semester-specific defaults (fetched from GitHub, cached locally)
- Config bridge to centralize UI defaults in Python config files
- Amplitude check to chopper reference signal validation
- Hidden offline mode toggle in launcher (Ctrl+Shift+D) with visual indicator
- PyInstaller build support with Windows installer (Inno Setup)
- `certifi` dependency for SSL certificates in frozen builds

### Changed
- Stability test current measurement now matches regular measurement method
- Launcher offline mode moved from visible checkbox to hidden hotkey (cleaner UI for students)
- Remote config cache now stored in user home directory (`~/.phys2150/cache/`) for Windows compatibility
- Application icon updated to CU Boulder logo with multi-resolution ICO (16x16 to 256x256)

### Fixed
- J-V pixel input now correctly allows 1-8 instead of 1-9
- Monochromator WaitForIdle infinite loop causing power test hang
- PyInstaller frozen mode now correctly launches EQE/J-V apps via --app argument
- Application icon converted to proper ICO format (was PNG renamed to .ico)
- SSL certificate errors in frozen builds (added certifi CA bundle)
- Remote config cache failing to write in Program Files (Windows permissions)
- Theme not preserved when launching apps from launcher with different theme
- Plots not updating to match theme when launched from launcher
- Installer now shows icon in Windows Add/Remove Programs list

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
- Consolidated CSS into shared components.css for DRY principle
- Extracted inline JavaScript to ES6 modules for maintainability
- Added PlotlyUtils shared module for consistent plot configuration
- Dynamic modal injection replaces hardcoded HTML
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
| 3.1.0 | 2025-12-25 | PyInstaller/Inno Setup build, hidden offline mode toggle |
| 3.0.0 | 2025-12-24 | Web UI with Plotly.js, Qt WebEngine architecture |
| 2.3.0 | 2025-12-23 | Tiered logging, measurement stats export, nanoamps format |
| 2.2.0 | 2025-12-22 | Manual monochromator controls, Live Signal Monitor |
| 2.1.0 | 2025-12-02 | PicoScope 2204A support, lock-in validation, stability test fixes |
| 2.0.0 | 2025-11-27 | MVC refactor, PicoScope software lock-in, PySide6 GUI |
| 1.0.0 | 2025-04-22 | Filter wheel automation, improved workflows |
| 0.1.0 | 2024-09-06 | Initial development release with SR510 lock-in |

[Unreleased]: https://github.com/UCBoulder/PHYS-2150/compare/v3.1.0...HEAD
[3.1.0]: https://github.com/UCBoulder/PHYS-2150/compare/v3.0.0...v3.1.0
[3.0.0]: https://github.com/UCBoulder/PHYS-2150/compare/v2.3.0...v3.0.0
[2.3.0]: https://github.com/UCBoulder/PHYS-2150/compare/v2.2.0...v2.3.0
[2.2.0]: https://github.com/UCBoulder/PHYS-2150/compare/v2.1.0...v2.2.0
[2.1.0]: https://github.com/UCBoulder/PHYS-2150/compare/v2.0.0...v2.1.0
[2.0.0]: https://github.com/UCBoulder/PHYS-2150/compare/v1.0.0...v2.0.0
[1.0.0]: https://github.com/UCBoulder/PHYS-2150/compare/v0.1.0...v1.0.0
[0.1.0]: https://github.com/UCBoulder/PHYS-2150/releases/tag/v0.1.0
