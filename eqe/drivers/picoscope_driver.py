"""
PicoScope Driver for EQE Measurements
Supports PicoScope 5242D (ps5000a) and 2204A (ps2000)
Software lock-in amplifier with phase-locked acquisition

Author: Physics 2150
Date: October 2025

IMPORTANT NOTES:
================
1. PicoScope 2204A uses ps2000 SDK (NOT ps2000a!)
2. ps2000_open_unit() returns handle directly, not via pointer
3. Use assert_pico2000_ok() for ps2000 series (NOT assert_pico_ok())
4. See: https://github.com/picotech/picosdk-python-wrappers/tree/master/ps2000Examples
"""

import ctypes
import numpy as np
from scipy.signal import hilbert
import os
import sys
import contextlib
import platform
import time

class PicoScopeDriver:
    """
    Driver for PicoScope 5000a and 2000 series oscilloscopes
    Implements software lock-in amplifier for EQE measurements

    Supported devices:
    - PicoScope 5242D (ps5000a SDK)
    - PicoScope 2204A (ps2000 SDK - note: NOT ps2000a!)

    Features:
    - ±20V input range (eliminates clipping at high currents)
    - Software lock-in with Hilbert transform
    - Phase-locked triggering for stable measurements
    """
    
    @staticmethod
    def hide_splash_windows():
        """
        Attempt to hide any PicoScope splash windows on Windows.
        Uses Windows API to find and hide windows with specific titles.
        """
        if platform.system() != 'Windows':
            return

        try:
            import threading

            # Define window titles that might be splash screens
            splash_titles = [
                'Pico Technology',
                'PicoScope',
                'PicoSDK',
                'Pico SDK',
                'PicoScope SDK',
            ]

            def hide_window_thread():
                """Background thread to hide splash windows"""
                try:
                    # Import Windows API functions
                    user32 = ctypes.windll.user32

                    # Constants for ShowWindow
                    SW_HIDE = 0

                    # Check frequently for splash windows (100 checks over 5 seconds)
                    for i in range(100):
                        if i > 0:
                            time.sleep(0.05)  # 50ms intervals

                        # Try to find and hide splash windows by exact title
                        for title in splash_titles:
                            hwnd = user32.FindWindowW(None, title)
                            if hwnd:
                                user32.ShowWindow(hwnd, SW_HIDE)

                except Exception:
                    pass  # Silently fail if we can't hide windows

            # Start background thread to hide windows
            thread = threading.Thread(target=hide_window_thread, daemon=True)
            thread.start()

        except Exception:
            pass  # Silently fail if Windows API not available
    
    @staticmethod
    @contextlib.contextmanager
    def suppress_picoscope_splash():
        """
        Context manager to suppress PicoScope SDK splash window and messages.
        On Windows, sets environment variables to disable PicoScope GUI elements.
        Also redirects stdout/stderr to devnull during device initialization.
        """
        # Save original environment variables
        original_env = {}
        env_vars_to_set = {
            'PICO_SUPPRESS_SPLASH': '1',
            'PICO_NO_GUI': '1',
            'PICO_SILENT': '1',
        }
        
        # Set environment variables to suppress GUI (if on Windows)
        if platform.system() == 'Windows':
            for key, value in env_vars_to_set.items():
                original_env[key] = os.environ.get(key)
                os.environ[key] = value
        
        # Save original stdout/stderr
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        
        # Redirect to devnull
        devnull = open(os.devnull, 'w')
        sys.stdout = devnull
        sys.stderr = devnull
        
        try:
            yield
        finally:
            # Restore stdout/stderr
            sys.stdout = old_stdout
            sys.stderr = old_stderr
            devnull.close()
            
            # Restore environment variables
            if platform.system() == 'Windows':
                for key, original_value in original_env.items():
                    if original_value is None:
                        os.environ.pop(key, None)
                    else:
                        os.environ[key] = original_value
    
    def __init__(self, serial_number=None):
        """
        Initialize PicoScope driver
        
        Args:
            serial_number: Optional serial number to connect to specific device
        """
        self.chandle = None
        self.status = {}
        self.serial_number = serial_number
        self.connected = False
        self.ps = None
        self.device_type = None  # Will be '5000a', '2000', or '2000a'
        self.assert_pico_ok = None  # Will be set based on device type
        
    def connect(self):
        """
        Connect to PicoScope device

        Tries different SDK versions in order:
        1. ps2000 (for PicoScope 2204A - most common in this lab)
        2. ps5000a (for PicoScope 5242D)

        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            # Start background thread to hide splash windows
            self.hide_splash_windows()
            time.sleep(0.5)  # Let window-hiding thread start

            # Set environment variables to suppress splash
            if platform.system() == 'Windows':
                os.environ['PICO_SUPPRESS_SPLASH'] = '1'
                os.environ['PICO_NO_GUI'] = '1'
                os.environ['PICO_SILENT'] = '1'

            connection_successful = False

            # Suppress PicoScope splash window during device opening
            with self.suppress_picoscope_splash():
                # Try ps2000 first (for PicoScope 2204A)
                if not connection_successful:
                    connection_successful = self._try_connect_ps2000()

                # Try ps5000a (for PicoScope 5242D)
                if not connection_successful:
                    connection_successful = self._try_connect_ps5000a()

            if not connection_successful:
                raise Exception("Failed to connect with any supported PicoScope SDK")

            # Print success message
            if self.device_type == '5000a':
                print("Using 15-bit resolution for 2-channel lock-in operation")
            else:
                print("Using 8-bit resolution for 2-channel lock-in operation")

            self.connected = True

            # Get device info
            info_str = self._get_device_info()
            print(f"Connected to {info_str}")

            # Set up channels
            self._setup_channels()

            return True

        except Exception as e:
            print(f"Failed to connect to PicoScope: {e}")
            self.connected = False
            return False

    def _try_connect_ps2000(self):
        """
        Try to connect using ps2000 SDK (for PicoScope 2204A).

        IMPORTANT: ps2000 API is different from ps2000a!
        - ps2000_open_unit() returns handle directly (not via pointer)
        - Use assert_pico2000_ok() not assert_pico_ok()

        Returns:
            bool: True if connection successful
        """
        try:
            print("Attempting to connect to PicoScope 2000 series (2204A)...")

            from picosdk.ps2000 import ps2000 as ps
            from picosdk.functions import assert_pico2000_ok

            self.ps = ps
            self.device_type = '2000'
            self.assert_pico_ok = assert_pico2000_ok

            # ps2000_open_unit() returns handle directly (not via pointer!)
            # A positive value means success
            self.status["openunit"] = ps.ps2000_open_unit()
            handle_value = self.status["openunit"]

            if handle_value > 0:
                # Success! Store the handle
                self.chandle = ctypes.c_int16(handle_value)
                print(f"Successfully connected to PicoScope 2000 series (handle: {handle_value})")
                return True
            elif handle_value == 0:
                print("  ps2000: No device found")
                return False
            else:
                print(f"  ps2000: Error code {handle_value}")
                return False

        except ImportError as e:
            print(f"  ps2000 SDK not available: {e}")
            return False
        except Exception as e:
            print(f"  ps2000 connection failed: {e}")
            return False

    def _try_connect_ps5000a(self):
        """
        Try to connect using ps5000a SDK (for PicoScope 5242D).

        Returns:
            bool: True if connection successful
        """
        try:
            print("Attempting to connect to PicoScope 5000a series (5242D)...")

            from picosdk.ps5000a import ps5000a as ps
            from picosdk.functions import assert_pico_ok

            self.ps = ps
            self.device_type = '5000a'
            self.assert_pico_ok = assert_pico_ok

            # Create handle for ps5000a (uses pointer)
            self.chandle = ctypes.c_int16()

            # ps5000a needs resolution parameter
            resolution = ps.PS5000A_DEVICE_RESOLUTION["PS5000A_DR_15BIT"]
            serial = ctypes.c_char_p(self.serial_number.encode() if self.serial_number else None)

            self.status["openunit"] = ps.ps5000aOpenUnit(
                ctypes.byref(self.chandle),
                serial,
                resolution
            )

            status_code = self.status["openunit"]

            # Handle power status for USB-powered devices
            if status_code == 286 or status_code == 282:
                self.status["changePowerSource"] = ps.ps5000aChangePowerSource(
                    self.chandle, status_code
                )
                assert_pico_ok(self.status["changePowerSource"])
                status_code = 0  # Treat as success after power change

            if status_code == 0:
                print(f"Successfully connected to PicoScope 5000a series")
                return True
            else:
                print(f"  ps5000a: Error code {status_code}")
                try:
                    ps.ps5000aCloseUnit(self.chandle)
                except:
                    pass
                return False

        except ImportError as e:
            print(f"  ps5000a SDK not available: {e}")
            return False
        except Exception as e:
            print(f"  ps5000a connection failed: {e}")
            return False
    
    def _get_device_info(self):
        """Get device information string"""
        try:
            if self.device_type == '2000':
                # ps2000 series - simpler API
                # ps2000 doesn't have a get_unit_info function in the same way
                # Just return a basic description
                return f"PicoScope 2204A (ps2000 series), Handle: {self.chandle.value}"

            elif self.device_type == '5000a':
                # Get various info strings
                string = ctypes.create_string_buffer(256)

                # Variant info
                self.ps.ps5000aGetUnitInfo(
                    self.chandle,
                    ctypes.byref(string),
                    256,
                    None,
                    3  # PICO_VARIANT_INFO
                )
                variant = string.value.decode('utf-8')

                # Serial number
                self.ps.ps5000aGetUnitInfo(
                    self.chandle,
                    ctypes.byref(string),
                    256,
                    None,
                    4  # PICO_BATCH_AND_SERIAL
                )
                serial = string.value.decode('utf-8')

                return f"PicoScope {variant}, S/N: {serial}"
            else:
                return f"PicoScope {self.device_type} series"

        except Exception:
            return f"PicoScope {self.device_type} series"

    def _setup_channels(self):
        """Set up both channels for measurement"""
        ps = self.ps

        if self.device_type == '2000':
            # PS2000 setup (for 2204A)
            # ps2000_set_channel(handle, channel, enabled, coupling, range)
            # channel: 0=A, 1=B
            # coupling: 0=AC, 1=DC
            # range: 1=50mV, 2=100mV, 3=200mV, 4=500mV, 5=1V, 6=2V, 7=5V, 8=10V, 9=20V
            chA_range = 7  # PS2000_2V - 2204A max is 20V but 2V is good for signals
            chB_range = 7  # PS2000_2V

            # Channel A (signal)
            self.status["setChA"] = ps.ps2000_set_channel(
                self.chandle,
                0,  # PS2000_CHANNEL_A
                1,  # enabled
                1,  # DC coupling
                chA_range
            )
            self.assert_pico_ok(self.status["setChA"])

            # Channel B (reference)
            self.status["setChB"] = ps.ps2000_set_channel(
                self.chandle,
                1,  # PS2000_CHANNEL_B
                1,  # enabled
                1,  # DC coupling
                chB_range
            )
            self.assert_pico_ok(self.status["setChB"])

            # Max ADC for PS2000 series (8-bit)
            self.maxADC = ctypes.c_int16(32767)

            self.chA_range = chA_range
            self.chB_range = chB_range

            print(f"Channels configured: 2V range, DC coupling")

        elif self.device_type == '5000a':
            # PS5000a setup
            chA_range = ps.PS5000A_RANGE["PS5000A_20V"]
            chB_range = ps.PS5000A_RANGE["PS5000A_20V"]
            coupling = ps.PS5000A_COUPLING["PS5000A_DC"]

            # Channel A (signal)
            self.status["setChA"] = ps.ps5000aSetChannel(
                self.chandle,
                ps.PS5000A_CHANNEL["PS5000A_CHANNEL_A"],
                1,  # enabled
                coupling,
                chA_range,
                0  # analogue offset
            )
            self.assert_pico_ok(self.status["setChA"])

            # Channel B (reference)
            self.status["setChB"] = ps.ps5000aSetChannel(
                self.chandle,
                ps.PS5000A_CHANNEL["PS5000A_CHANNEL_B"],
                1,  # enabled
                coupling,
                chB_range,
                0  # analogue offset
            )
            self.assert_pico_ok(self.status["setChB"])

            # Get max ADC value
            self.maxADC = ctypes.c_int16()
            self.status["maximumValue"] = ps.ps5000aMaximumValue(
                self.chandle,
                ctypes.byref(self.maxADC)
            )
            self.assert_pico_ok(self.status["maximumValue"])

            self.chA_range = chA_range
            self.chB_range = chB_range

            print(f"Channels configured: ±20V range (no clipping!)")
    
    def set_reference_frequency(self, frequency):
        """
        Store reference frequency for lock-in calculations
        (PicoScope doesn't need this for acquisition, but kept for API compatibility)
        
        Args:
            frequency: Reference frequency in Hz
        """
        self.reference_freq = frequency
    
    def software_lockin(self, reference_freq, num_cycles=100):
        """
        Perform software lock-in amplifier measurement
        
        This is the main measurement function that:
        1. Acquires waveforms from both channels
        2. Performs Hilbert transform for quadrature generation
        3. Mixes signal with reference
        4. Returns magnitude and phase
        
        Args:
            reference_freq: Frequency of chopper in Hz (e.g., 81 Hz)
            num_cycles: Number of cycles to integrate over (default 100)
        
        Returns:
            dict: {
                'X': float - In-phase component (V)
                'Y': float - Quadrature component (V)
                'R': float - Magnitude (V)
                'theta': float - Phase in degrees
                'freq': float - Measured reference frequency
                'signal_data': np.array - Raw signal waveform
                'reference_data': np.array - Raw reference waveform
            }
        """
        # Calculate acquisition parameters based on device type
        if self.device_type == '2000':
            # PicoScope 2204A parameters
            # Timebase 8 = 2560ns per sample = ~390 kHz sample rate
            # With 2000 samples, we get ~5ms of data
            # At 81 Hz, that's about 0.4 cycles - so we need higher timebase (slower rate)
            # Timebase 12 = 40960ns = ~24 kHz, gives ~300 samples/cycle at 81 Hz
            # With 2000 samples, we get about 6.6 cycles
            fs = 1e9 / 40960  # Sample rate at timebase 12 (~24.4 kHz)
            decimation = 1  # Not used for ps2000, just for compatibility
            samples_per_cycle = fs / reference_freq  # ~301 samples/cycle at 81 Hz
            num_samples = min(int(num_cycles * samples_per_cycle), 2000)
            # Ensure at least 1 cycle
            if num_samples < samples_per_cycle:
                num_samples = min(int(samples_per_cycle * 2), 2000)
        else:
            # PicoScope 5000 series parameters
            # CRITICAL: Optimized parameters for stability (0.66% CV)
            # Decimation = 1024 gives ~97.6 kSPS sampling rate
            # This provides ~1200 samples/cycle at 81 Hz (good for Hilbert transform)
            base_rate = 100e6  # 100 MS/s
            decimation = 1024  # FIXED decimation for stability
            fs = base_rate / decimation  # 97,656 Hz
            samples_per_cycle = fs / reference_freq  # ~1205 samples/cycle at 81 Hz
            num_samples = min(int(num_cycles * samples_per_cycle), 200000)

        # Calculate actual cycles that will be captured
        actual_cycles = max(1, int(num_samples / samples_per_cycle))
        
        # Acquire waveforms
        signal_data, reference_data = self._acquire_block(num_samples, decimation)
        
        if signal_data is None or reference_data is None:
            print("ERROR: Failed to acquire data")
            return None
        
        # Calculate actual sampling rate
        actual_samples_per_cycle = len(signal_data) / actual_cycles
        print(f"Lock-in: {len(signal_data)} samples, {actual_samples_per_cycle:.1f} samples/cycle @ {reference_freq} Hz ({actual_cycles} cycles)")
        
        # SOFTWARE LOCK-IN ALGORITHM
        # Digital lock-in with Hilbert transform for quadrature generation
        
        # Remove DC offsets
        signal_normalized = signal_data - np.mean(signal_data)
        ref_normalized = reference_data - np.mean(reference_data)
        
        # Normalize reference signal
        ref_rms = np.sqrt(np.mean(ref_normalized**2))
        if ref_rms > 0:
            ref_normalized = ref_normalized / ref_rms
        else:
            print("ERROR: Reference signal has zero amplitude!")
            return None
        
        # Create quadrature reference using Hilbert transform
        analytic_signal = hilbert(ref_normalized)
        ref_cos = ref_normalized  # In-phase reference
        ref_sin = np.imag(analytic_signal)  # Quadrature reference (90° shifted)
        
        # Mix signal with reference
        mixed_cos = signal_normalized * ref_cos
        mixed_sin = signal_normalized * ref_sin
        
        # Low-pass filter by averaging
        X = 2 * np.mean(mixed_cos)  # In-phase component (factor of 2 for RMS)
        Y = 2 * np.mean(mixed_sin)  # Quadrature component
        
        # Calculate magnitude and phase
        R = np.sqrt(X**2 + Y**2)
        theta = np.arctan2(Y, X)
        theta_deg = np.rad2deg(theta)
        
        # Measure actual reference frequency using FFT
        freqs = np.fft.rfftfreq(len(reference_data), 1/fs)
        fft_ref = np.fft.rfft(reference_data)
        freq_range = (reference_freq * 0.5, reference_freq * 1.5)
        mask = (freqs >= freq_range[0]) & (freqs <= freq_range[1])
        
        if np.any(mask):
            peak_idx = np.argmax(np.abs(fft_ref[mask]))
            measured_freq = freqs[mask][peak_idx]
        else:
            measured_freq = freqs[np.argmax(np.abs(fft_ref[1:]))+1]  # Skip DC
        
        return {
            'X': X,
            'Y': Y,
            'R': R,
            'theta': theta_deg,
            'freq': measured_freq,
            'signal_data': signal_data,
            'reference_data': reference_data
        }
    
    def _acquire_block(self, num_samples, decimation):
        """
        Acquire block of data from both channels

        Args:
            num_samples: Number of samples to acquire
            decimation: Decimation factor (1 = 100 MS/s, 2 = 50 MS/s, etc.)

        Returns:
            tuple: (signal_data, reference_data) as numpy arrays in Volts
        """
        try:
            if self.device_type == '2000':
                return self._acquire_block_2000(num_samples, decimation)
            elif self.device_type == '5000a':
                return self._acquire_block_5000a(num_samples, decimation)
            else:
                print(f"ERROR: Unknown device type {self.device_type}")
                return None, None

        except Exception as e:
            print(f"ERROR acquiring data: {e}")
            import traceback
            traceback.print_exc()
            return None, None
    
    def _acquire_block_5000a(self, num_samples, decimation):
        """Acquire block data from PS5000a"""
        ps = self.ps
        
        # Calculate timebase from decimation
        # For PS5000a: timebase = log2(decimation)
        timebase = int(np.log2(decimation))
        
        # Get timebase info
        timeIntervalns = ctypes.c_float()
        returnedMaxSamples = ctypes.c_int32()
        self.status["getTimebase2"] = ps.ps5000aGetTimebase2(
            self.chandle, 
            timebase, 
            num_samples, 
            ctypes.byref(timeIntervalns), 
            ctypes.byref(returnedMaxSamples), 
            0
        )
        self.assert_pico_ok(self.status["getTimebase2"])
        
        # Set up data buffers
        bufferAMax = (ctypes.c_int16 * num_samples)()
        bufferAMin = (ctypes.c_int16 * num_samples)()
        bufferBMax = (ctypes.c_int16 * num_samples)()
        bufferBMin = (ctypes.c_int16 * num_samples)()
        
        # Set data buffer locations
        self.status["setDataBuffersA"] = ps.ps5000aSetDataBuffers(
            self.chandle, 
            ps.PS5000A_CHANNEL["PS5000A_CHANNEL_A"],
            ctypes.byref(bufferAMax), 
            ctypes.byref(bufferAMin), 
            num_samples, 
            0,  # segment index
            0   # ratio mode
        )
        self.assert_pico_ok(self.status["setDataBuffersA"])
        
        self.status["setDataBuffersB"] = ps.ps5000aSetDataBuffers(
            self.chandle,
            ps.PS5000A_CHANNEL["PS5000A_CHANNEL_B"],
            ctypes.byref(bufferBMax),
            ctypes.byref(bufferBMin),
            num_samples,
            0,
            0
        )
        self.assert_pico_ok(self.status["setDataBuffersB"])
        
        # Set up trigger on Channel B (reference) for phase-locked acquisition
        # This ensures all acquisitions start at the same phase of the chopper cycle
        # CRITICAL for stable lock-in measurements!
        from picosdk.functions import mV2adc
        
        # Trigger at 50% of reference signal
        # For 0-5V square wave, midpoint is ~2.5V
        threshold = 2500  # mV (2.5V midpoint for 0-5V square wave)
        threshold_adc = mV2adc(threshold, self.chB_range, self.maxADC)
        
        self.status["trigger"] = ps.ps5000aSetSimpleTrigger(
            self.chandle,
            1,  # enable
            ps.PS5000A_CHANNEL["PS5000A_CHANNEL_B"],  # trigger on reference channel
            threshold_adc,  # threshold in ADC counts
            2,  # direction: PS5000A_RISING
            0,  # delay (0 = no delay)
            1000  # auto-trigger after 1000 ms if no trigger found
        )
        self.assert_pico_ok(self.status["trigger"])
        
        # Run block capture with trigger
        preTriggerSamples = int(num_samples * 0.1)  # 10% pre-trigger
        postTriggerSamples = num_samples - preTriggerSamples
        
        self.status["runBlock"] = ps.ps5000aRunBlock(
            self.chandle,
            preTriggerSamples,  # preTriggerSamples
            postTriggerSamples,  # postTriggerSamples
            timebase,
            None,  # timeIndisposedMs
            0,  # segment index
            None,  # lpReady callback
            None  # pParameter
        )
        self.assert_pico_ok(self.status["runBlock"])
        
        # Wait for acquisition to complete
        ready = ctypes.c_int16(0)
        check = ctypes.c_int16(0)
        while ready.value == check.value:
            self.status["isReady"] = ps.ps5000aIsReady(self.chandle, ctypes.byref(ready))
        
        # Get data
        overflow = ctypes.c_int16()
        cmaxSamples = ctypes.c_int32(num_samples)
        self.status["getValues"] = ps.ps5000aGetValues(
            self.chandle, 
            0,  # start index
            ctypes.byref(cmaxSamples), 
            0,  # downsample ratio
            0,  # downsample ratio mode
            0,  # segment index
            ctypes.byref(overflow)
        )
        self.assert_pico_ok(self.status["getValues"])
        
        # Convert ADC counts to volts
        from picosdk.functions import adc2mV
        signal_mV = adc2mV(bufferAMax, self.chA_range, self.maxADC)
        reference_mV = adc2mV(bufferBMax, self.chB_range, self.maxADC)
        
        # Convert to volts
        signal_data = np.array(signal_mV) / 1000.0
        reference_data = np.array(reference_mV) / 1000.0
        
        return signal_data, reference_data
    
    def _acquire_block_2000(self, num_samples, decimation):
        """
        Acquire block data from PS2000 (for 2204A).

        Based on official PicoTech ps2000 examples:
        https://github.com/picotech/picosdk-python-wrappers/tree/master/ps2000Examples

        NOTE: ps2000_get_timebase fails when requested samples > available memory.
        With both channels enabled, the 2204A has ~4K samples per channel.
        We cap to 2000 samples to stay well within limits.

        Args:
            num_samples: Number of samples to acquire
            decimation: Decimation factor (used to calculate timebase)
        """
        ps = self.ps
        from picosdk.functions import adc2mV

        # Timebase 12 gives good sample rate for lock-in at 81 Hz
        # (approx 40960ns per sample = 24.4 kHz sample rate)
        # With 2000 samples, this gives ~6.6 cycles at 81 Hz
        timebase = 12

        # Cap samples to 2000 for dual-channel mode on 2204A
        # The device has ~4K samples with both channels but we stay conservative
        num_samples = min(num_samples, 2000)

        # Get timebase info
        timeInterval = ctypes.c_int32()
        timeUnits = ctypes.c_int32()
        oversample = ctypes.c_int16(1)
        maxSamplesReturn = ctypes.c_int32()

        self.status["getTimebase"] = ps.ps2000_get_timebase(
            self.chandle,
            timebase,
            num_samples,
            ctypes.byref(timeInterval),
            ctypes.byref(timeUnits),
            oversample,
            ctypes.byref(maxSamplesReturn)
        )
        self.assert_pico_ok(self.status["getTimebase"])

        # Set up trigger with auto-trigger
        # ps2000_set_trigger(handle, source, threshold, direction, delay, auto_trigger_ms)
        self.status["trigger"] = ps.ps2000_set_trigger(
            self.chandle,
            0,     # trigger on Channel A (signal)
            64,    # threshold in ADC counts
            0,     # direction: rising
            0,     # delay
            1000   # auto-trigger after 1000ms
        )
        self.assert_pico_ok(self.status["trigger"])

        # Run block capture
        timeIndisposedms = ctypes.c_int32()
        self.status["runBlock"] = ps.ps2000_run_block(
            self.chandle,
            num_samples,
            timebase,
            oversample,
            ctypes.byref(timeIndisposedms)
        )
        self.assert_pico_ok(self.status["runBlock"])

        # Wait for data collection to finish
        ready = ctypes.c_int16(0)
        check = ctypes.c_int16(0)
        while ready.value == check.value:
            self.status["isReady"] = ps.ps2000_ready(self.chandle)
            ready = ctypes.c_int16(self.status["isReady"])

        # Create buffers for data
        bufferA = (ctypes.c_int16 * num_samples)()
        bufferB = (ctypes.c_int16 * num_samples)()

        # Get data from scope
        cmaxSamples = ctypes.c_int32(num_samples)
        self.status["getValues"] = ps.ps2000_get_values(
            self.chandle,
            ctypes.byref(bufferA),
            ctypes.byref(bufferB),
            None,  # buffer C (not used)
            None,  # buffer D (not used)
            ctypes.byref(oversample),
            cmaxSamples
        )
        self.assert_pico_ok(self.status["getValues"])

        # Convert ADC counts to mV then to V
        signal_mV = adc2mV(bufferA, self.chA_range, self.maxADC)
        reference_mV = adc2mV(bufferB, self.chB_range, self.maxADC)

        signal_data = np.array(signal_mV) / 1000.0
        reference_data = np.array(reference_mV) / 1000.0

        return signal_data, reference_data

    def close(self):
        """Close connection to PicoScope"""
        if self.connected and self.chandle is not None:
            try:
                if self.device_type == '2000':
                    # PS2000 series
                    self.status["stop"] = self.ps.ps2000_stop(self.chandle)
                    self.assert_pico_ok(self.status["stop"])
                    self.status["close"] = self.ps.ps2000_close_unit(self.chandle)
                    self.assert_pico_ok(self.status["close"])
                elif self.device_type == '5000a':
                    # PS5000a series
                    self.status["stop"] = self.ps.ps5000aStop(self.chandle)
                    self.status["close"] = self.ps.ps5000aCloseUnit(self.chandle)

                print("PicoScope connection closed")
                self.connected = False
            except Exception as e:
                print(f"Error closing PicoScope: {e}")


if __name__ == "__main__":
    # Simple test
    print("Testing PicoScope driver...")
    
    scope = PicoScopeDriver()
    
    if scope.connect():
        print("\nPerforming test lock-in measurement at 81 Hz...")
        scope.set_reference_frequency(81)
        
        result = scope.software_lockin(81, num_cycles=50)
        
        if result:
            print(f"\nLock-in results:")
            print(f"  X (in-phase):    {result['X']:+.6f} V")
            print(f"  Y (quadrature):  {result['Y']:+.6f} V")
            print(f"  R (magnitude):   {result['R']:.6f} V")
            print(f"  Phase:           {result['theta']:+.1f} deg")
            print(f"  Measured freq:   {result['freq']:.2f} Hz")
            print(f"\n  Raw signal range:    {np.min(result['signal_data']):.4f} to {np.max(result['signal_data']):.4f} V")
            print(f"  Raw reference range: {np.min(result['reference_data']):.4f} to {np.max(result['reference_data']):.4f} V")
            print(f"\n  [OK] No clipping! (PicoScope has +/-20V range)")
        
        scope.close()
    else:
        print("Failed to connect to PicoScope")
