# Hardware Setup Guide

This guide covers the installation of hardware drivers required for the PHYS-2150 Measurement Suite. All drivers must be installed **before** running the application.

## Overview

The PHYS-2150 Measurement Suite communicates with several pieces of laboratory equipment:

| Equipment | Driver Required | Used For |
|-----------|-----------------|----------|
| Keithley 2450 SMU | NI-VISA Runtime | J-V measurements |
| PicoScope 5242D/2204A | PicoScope SDK | EQE lock-in amplifier |
| Thorlabs PM100USB | Thorlabs OPM | Reference power measurement |
| Newport CS130B Monochromator | Newport MonoUtility | Wavelength selection |
| Newport USFW-100 Filter Wheel | Newport MonoUtility | Order-sorting filters |

## Driver Installation

### 1. NI-VISA Runtime

NI-VISA provides the communication layer for USB/GPIB instruments (Keithley 2450).

**Download:**
- Visit: https://www.ni.com/en-us/support/downloads/drivers/download.ni-visa.html
- Download the latest NI-VISA Runtime (not the full development package)

**Installation:**
1. Run the downloaded installer
2. Select "Typical" installation
3. Reboot if prompted

**Verification:**
1. Connect the Keithley 2450 via USB
2. Open NI MAX (NI Measurement & Automation Explorer)
3. Under "Devices and Interfaces", the Keithley should appear as `USB0::0x05E6::0x2450::...`

### 2. PicoScope SDK

The PicoScope SDK provides drivers for the PicoScope oscilloscope used in EQE measurements.

**Supported Models:**

| Model | SDK | Software | Notes |
|-------|-----|----------|-------|
| PicoScope 5242D | ps5000a | PicoScope 6/7 | Higher resolution (15-bit), more memory |
| PicoScope 2204A | ps2000 | PicoScope 7 | Basic model, uses different API |

> **Important:** The 2204A uses the `ps2000` SDK, which has a different API than `ps2000a`. The driver handles this automatically, but custom code must use the correct SDK.

**Download:**

- Visit: https://www.picotech.com/downloads
- Select your PicoScope model (5000A series or 2000 series)
- Download "PicoScope 7" (recommended) or "PicoSDK" for Windows

**Installation:**

1. Run the downloaded installer
2. Install the full SDK (includes drivers and libraries)
3. Reboot if prompted

**Verification:**

1. Connect the PicoScope via USB
2. Open PicoScope 7 software
3. The scope should connect and display live waveforms
4. **Important:** Close PicoScope 7 before running Python code (it locks the device)

**Python Bindings:**

The Python SDK (`picosdk` package) is installed automatically with the application dependencies. It requires the native SDK to be installed first.

```bash
pip install picosdk
```

**2204A Firmware Upload:**

The PicoScope 2204A uploads firmware on each connection. You may notice:

- USB disconnect/reconnect sounds when connecting
- A brief splash screen during initialization
- Status code 3 (PICO_OPEN_OPERATION_IN_PROGRESS) during firmware upload

This is normal behavior. The driver waits for initialization to complete.

### 3. Thorlabs OPM (Optical Power Meter)

The Thorlabs Optical Power Meter software provides drivers for the PM100USB power meter with S120VC sensor head.

**Download:**
- Visit: https://www.thorlabs.com/software_pages/ViewSoftwarePage.cfm?Code=OPM
- Download "Optical Power Monitor" for Windows

**Installation:**
1. Run the downloaded installer
2. Complete the installation wizard
3. No reboot typically required

**Verification:**

1. Connect the PM100USB via USB
2. Attach the S120VC sensor head
3. Open the Thorlabs Optical Power Monitor software
4. The power meter should appear and display readings

**Note:** The TLPMX.py driver in this application communicates directly with the Thorlabs DLLs installed by the OPM software.

### 4. Newport MonoUtility

Newport MonoUtility provides control software for the CS130B monochromator and USFW-100 filter wheel.

**Download:**
- Contact Newport/MKS Instruments for software access
- Or check: https://www.newport.com/f/cornerstone-130-1-8-m-monochromator

**Installation:**

1. Run the installer provided by Newport
2. Follow the installation wizard
3. Install USB drivers when prompted

**Verification:**

1. Connect the CS130B monochromator via USB
2. Connect the USFW-100 filter wheel via USB
3. Open Newport MonoUtility
4. Both devices should connect and respond to commands

## Physical Connections

### EQE Measurement Setup

```
┌─────────────────────────────────────────────────────────────┐
│                    EQE Measurement Setup                     │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Light Source ──► Chopper ──► Monochromator ──► Sample      │
│       │              │              │              │         │
│       │              ▼              │              ▼         │
│       │         Reference          │         Preamp         │
│       │           Signal           │              │         │
│       │              │              │              ▼         │
│       │              │              │         PicoScope      │
│       │              ▼              │          Ch A          │
│       │         PicoScope          │                        │
│       │          Ch B              │                        │
│       │                            │                        │
│       └────────────────────────────┼──► Power Meter         │
│                                    │    (reference path)    │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

**Connections:**
1. **PicoScope Channel A**: Solar cell signal (via preamplifier if needed)
2. **PicoScope Channel B**: Chopper reference signal (TTL output from chopper)
3. **Power Meter**: Reference path for absolute power calibration
4. **Monochromator**: USB to computer

### J-V Measurement Setup

```
┌─────────────────────────────────────────────────────────────┐
│                    J-V Measurement Setup                     │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Solar Simulator ──────────────────────► Solar Cell         │
│                                              │               │
│                                              ▼               │
│                                        Keithley 2450         │
│                                         (4-wire)            │
│                                              │               │
│                                              ▼               │
│                                          USB ──► Computer   │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

**Connections:**
1. **Keithley 2450 HI/LO**: Connect to solar cell (positive to anode)
2. **Keithley 2450 Sense HI/LO**: Connect for 4-wire sensing (more accurate)
3. **USB**: Keithley to computer

## Troubleshooting

### Device Not Found

If the application cannot find a device:

1. **Check USB connection**: Try a different USB port or cable
2. **Check driver installation**: Open the device's native software to verify it works
3. **Check Windows Device Manager**: Look for any devices with warning icons
4. **Restart the application**: Close and reopen after connecting devices

### NI-VISA Issues

If VISA communication fails:

1. Open NI MAX and refresh the device list
2. Right-click the device and select "Reset"
3. Check that no other application is using the device
4. Verify the device address matches what NI MAX shows

### PicoScope Issues

If the PicoScope doesn't connect:

1. Close PicoScope 7 software (it locks the device exclusively)
2. Wait 5-10 seconds after closing the software
3. Unplug and replug the USB cable
4. Check that PicoSDK is properly installed

**For PicoScope 5242D:** Look for `ps5000a.dll` in System32

**For PicoScope 2204A:** Look for `ps2000.dll` in System32 (note: NOT ps2000a.dll)

See [TROUBLESHOOTING.md](../TROUBLESHOOTING.md#picoscope-2204a-specific-issues) for 2204A-specific issues.

### Power Meter Issues

If the Thorlabs power meter isn't detected:

1. Verify the TLPM DLLs are installed: Check `C:\Program Files\IVI Foundation\VISA\Win64\Bin\`
2. Try running the Thorlabs OPM software first
3. Check the sensor head is properly attached to the meter

## Equipment Specifications

### J-V Measurement Equipment

#### Keithley 2450 SMU

- Voltage range: ±200V
- Current range: ±1A
- Measurement resolution: 6½ digits
- Interface: USB (USBTMC)

#### Ossila LED Solar Simulator

- Spectrum: AM1.5G
- Illumination area: 50mm × 50mm
- Intensity: 1 Sun (100 mW/cm²)
- More info: [Ossila Product Page](https://www.ossila.com/products/solar-simulator)

### EQE Measurement Equipment

#### Newport 66502-250Q-R1 QTH Light Source

- Type: Quartz Tungsten Halogen
- Power: 250W
- Spectrum: Broadband visible/NIR

#### Newport CS130B Monochromator

- Wavelength range: 200-1400 nm (grating dependent)
- Resolution: 0.1 nm
- Interface: USB-Serial

#### Newport USFW-100 Filter Wheel

- Positions: 6 filter positions
- Interface: USB-Serial
- Used for: Order-sorting filters

#### PicoScope 5242D (Recommended)

- Bandwidth: 60 MHz
- Resolution: 15-bit (2 channels)
- Sampling rate: 125 MS/s
- Input range: ±20V (no clipping)
- Buffer memory: 128 MS
- SDK: `ps5000a`

#### PicoScope 2204A (Alternative)

- Bandwidth: 10 MHz
- Resolution: 8-bit
- Sampling rate: 100 MS/s (single channel), 50 MS/s (dual channel)
- Input range: ±20V
- Buffer memory: 8 KB (shared between channels)
- SDK: `ps2000` (NOT ps2000a!)
- Interface: USB 2.0

**2204A Limitations for EQE:**

- Limited to ~2000 samples per acquisition in dual-channel mode
- Lower sample rate means fewer samples per chopper cycle (~300 at 81 Hz)
- Still provides adequate performance for EQE measurements
- Driver automatically adjusts parameters for this model

#### Thorlabs PM100USB with S120VC Sensor

- Wavelength range: 200-1100 nm (S120VC)
- Power range: 50 nW to 50 mW
- Interface: USB
