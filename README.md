# PHYS-2150

## EQE Measurement System

Python-based External Quantum Efficiency (EQE) measurement system using:
- **Newport Cornerstone monochromator** for wavelength selection
- **Thorlabs power meter** for incident light measurement  
- **PicoScope oscilloscope** with software lock-in amplifier for photodetector current measurement

### Key Features
- Software lock-in amplifier (81 Hz chopper frequency)
- Phase-independent magnitude measurement (no phase drift issues)
- ±20V input range (no signal clipping)
- Automated wavelength scanning
- Real-time plotting and data export

## Software Requirements

### Hardware Drivers
- [Thorlabs OPM](https://www.thorlabs.com/software_pages/ViewSoftwarePage.cfm?Code=OPM) - Power meter drivers
- [Newport MonoUtility](https://www.newport.com/f/cs130b-configured-monochromators) - Monochromator drivers
- [USB to Serial Adaptor Driver](http://bit.ly/elecable3) - For monochromator communication
- **[PicoSDK](https://www.picotech.com/downloads)** - PicoScope oscilloscope drivers

### Python Packages
```bash
pip install numpy scipy matplotlib pandas PySide6 picosdk
```

## Hardware Setup

### Supported PicoScopes
- **Development:** PicoScope 5242D (16-bit, recommended)
- **Production:** PicoScope 2204A (8-bit, lower cost)

Both provide ±20V input range - no clipping issues!

### Connections
- **CH A:** Transimpedance amplifier output (photodetector signal)
- **CH B:** Chopper reference signal (81 Hz TTL)

## Quick Start

1. **Install drivers** (see Software Requirements above)
2. **Install Python packages:**
   ```powershell
   pip install numpy scipy matplotlib pandas PySide6 picosdk
   ```
3. **Connect hardware:**
   - PicoScope via USB
   - Thorlabs power meter via USB
   - Newport monochromator via USB-to-Serial adapter
   - Chopper reference signal (0-5V square wave) to PicoScope CH B
   - Transimpedance amplifier output to PicoScope CH A

4. **Run GUI:**
   ```powershell
   cd c:\Users\krbu4353\GitHub\PHYS-2150\eqe
   python eqeguicombined-filters-pyside.py
   ```

5. **Enter chopper frequency** (default: 81 Hz) when prompted

6. **Perform measurements:**
   - Power calibration (scan wavelength range to measure lamp spectrum)
   - Phase adjustment (optimize lock-in phase for maximum signal)
   - Current measurement (EQE scan)

## Project Structure

### Main Application
- **`eqe/eqeguicombined-filters-pyside.py`** - Production GUI application (PicoScope version)
- **`eqe/eqeguicombined-filters-pyside-pico.py`** - Alternative PicoScope GUI (development)
- **`eqe/picoscope_driver.py`** - PicoScope driver with software lock-in amplifier

### Test & Diagnostic Tools
- **`eqe/test_longterm_stability.py`** - Long-term stability validation (phase adjustment + repeated measurements)
- **`eqe/test_picoscope_stability.py`** - Quick 20-measurement stability test
- **`eqe/check_reference.py`** - Reference waveform diagnostic (determines trigger threshold)
- **`eqe/plot_stability.py`** - Plots stability test results from CSV files

### Data Analysis
- **`eqe/calceqe.py`** - Calculate EQE from current and power measurements
- **`eqe/compare_plots.py`** - Compare multiple EQE datasets

### Legacy Files
- **`eqe_mvc/`** - MVC architecture implementation (development/reference)
- **`eqe/eqeguicombined-filters.py`** - Older GUI version (superseded)

## Documentation

- **[TROUBLESHOOTING.md](TROUBLESHOOTING.md)** - Comprehensive troubleshooting guide
- **[Documentation.md](Documentation.md)** - Development notes and timing data
- **[PARAMETER_VERIFICATION.md](eqe/PARAMETER_VERIFICATION.md)** - Validation that GUI and test parameters match

## Performance Metrics

### Stability (Validated October 2025)
- **Coefficient of Variation (CV):** 0.66% (20 measurements over 2 minutes)
- **Long-term drift:** < 0.2% over measurement duration
- **Target:** CV < 10% for reliable EQE measurements
- **Result:** 15× better than target, suitable for precision measurements

### Acquisition Parameters
- **Sampling rate:** 97,656 Hz (decimation=1024 from 100 MS/s)
- **Samples per measurement:** ~120,563 (100 cycles at 81 Hz)
- **Measurements per wavelength:** 5 (averaged with 2σ outlier rejection)
- **Total integration time:** ~6 seconds per wavelength point
- **Trigger threshold:** 2500 mV (midpoint of 0-5V reference square wave)

### Input Range
- **PicoScope range:** ±20V
- **No clipping** up to ±20V signals
- **Resolution:** 15-bit (32,768 levels) in 2-channel mode

## Recent Changes

**October 2025:** Migrated to PicoScope 5242D with software lock-in amplifier. Achieved 0.66% CV stability (15× better than 10% target) through optimized acquisition parameters and phase-locked triggering at 2.5V threshold. System validated with long-term stability testing over multiple wavelength points.

## License

This software is released under the **MIT License**. See [LICENSE](LICENSE) for details.

### Third-Party Dependencies

This software uses several third-party libraries with their own licenses:

- **PicoScope SDK** - Proprietary (Pico Technology Limited) - For use with Pico products only
- **PySide6** - LGPL v3 (The Qt Company)
- **matplotlib, NumPy, SciPy, pandas** - BSD-style licenses
- **PyVISA, pyserial** - MIT/BSD licenses

See the [LICENSE](LICENSE) file for complete third-party notices.

### Usage Restrictions

The PicoScope SDK is proprietary software by Pico Technology Limited and may only be used with Pico Technology hardware products. This software is designed specifically for use with PicoScope oscilloscopes and Thorlabs/Newport laboratory equipment.

## Citation

If you use this software in your research, please cite:

```
EQE Measurement System
University of Colorado Boulder
https://github.com/UCBoulder/PHYS-2150
```