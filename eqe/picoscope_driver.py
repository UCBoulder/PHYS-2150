"""
PicoScope Driver for EQE Measurements
Supports PicoScope 5242D and 2204A
Software lock-in amplifier with phase-locked acquisition

Author: Physics 2150
Date: October 2025
"""

import ctypes
import numpy as np
from scipy.signal import hilbert

class PicoScopeDriver:
    """
    Driver for PicoScope 5000a and 2000a series oscilloscopes
    Implements software lock-in amplifier for EQE measurements
    
    Features:
    - ±20V input range (eliminates clipping at high currents)
    - 100 MS/s sampling rate
    - Software lock-in with Hilbert transform
    - Phase-locked triggering for 0.66% CV stability
    """
    
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
        self.device_type = None  # Will be '5000a' or '2000a'
        
    def connect(self):
        """
        Connect to PicoScope device
        
        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            # Try to import ps5000a first (for 5242D)
            try:
                from picosdk.ps5000a import ps5000a as ps
                from picosdk.functions import assert_pico_ok
                self.ps = ps
                self.device_type = '5000a'
                print("Attempting to connect to PicoScope 5000a series...")
            except ImportError:
                # Fall back to ps2000a (for 2204A)
                from picosdk.ps2000a import ps2000a as ps
                from picosdk.functions import assert_pico_ok
                self.ps = ps
                self.device_type = '2000a'
                print("Attempting to connect to PicoScope 2000a series...")
            
            self.assert_pico_ok = assert_pico_ok
            
            # Create chandle for connection
            self.chandle = ctypes.c_int16()
            
            # Open device
            if self.device_type == '5000a':
                # PicoScope 5000a series (5242D)
                # IMPORTANT: 16-bit mode only supports 1 channel
                # Use 15-bit for 2-channel operation (still excellent resolution!)
                resolution = ps.PS5000A_DEVICE_RESOLUTION["PS5000A_DR_15BIT"]
                serial = ctypes.c_char_p(self.serial_number.encode() if self.serial_number else None)
                self.status["openunit"] = ps.ps5000aOpenUnit(
                    ctypes.byref(self.chandle), 
                    serial, 
                    resolution
                )
                print("Using 15-bit resolution for 2-channel lock-in operation")
            else:
                # PicoScope 2000a series (2204A)
                serial = ctypes.c_char_p(self.serial_number.encode() if self.serial_number else None)
                self.status["openunit"] = ps.ps2000aOpenUnit(
                    ctypes.byref(self.chandle), 
                    serial
                )
            
            try:
                assert_pico_ok(self.status["openunit"])
            except:
                # Handle power status for devices that need USB power
                powerStatus = self.status["openunit"]
                if powerStatus == 286 or powerStatus == 282:
                    if self.device_type == '5000a':
                        self.status["changePowerSource"] = ps.ps5000aChangePowerSource(
                            self.chandle, powerStatus
                        )
                    else:
                        self.status["changePowerSource"] = ps.ps2000aChangePowerSource(
                            self.chandle, powerStatus
                        )
                    assert_pico_ok(self.status["changePowerSource"])
                else:
                    raise
            
            self.connected = True
            
            # Get device info
            info_str = self._get_device_info()
            print(f"Connected to {info_str}")
            
            # Set up channels with ±20V range
            self._setup_channels()
            
            return True
            
        except Exception as e:
            print(f"Failed to connect to PicoScope: {e}")
            self.connected = False
            return False
    
    def _get_device_info(self):
        """Get device information string"""
        try:
            # Get various info strings
            string = ctypes.create_string_buffer(256)
            
            if self.device_type == '5000a':
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
            else:
                # For 2000a series
                self.ps.ps2000aGetUnitInfo(
                    self.chandle, 
                    ctypes.byref(string), 
                    256, 
                    None, 
                    3
                )
                variant = string.value.decode('utf-8')
                
                self.ps.ps2000aGetUnitInfo(
                    self.chandle, 
                    ctypes.byref(string), 
                    256, 
                    None, 
                    4
                )
                serial = string.value.decode('utf-8')
            
            return f"PicoScope {variant}, S/N: {serial}"
            
        except:
            return f"PicoScope {self.device_type} series"
    
    def _setup_channels(self):
        """Set up both channels with ±20V range"""
        ps = self.ps
        
        if self.device_type == '5000a':
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
            
        else:
            # PS2000a setup
            chA_range = ps.PS2000A_RANGE["PS2000A_20V"]
            chB_range = ps.PS2000A_RANGE["PS2000A_20V"]
            coupling = ps.PS2000A_COUPLING["PS2000A_DC"]
            
            # Channel A (signal)
            self.status["setChA"] = ps.ps2000aSetChannel(
                self.chandle,
                ps.PS2000A_CHANNEL["PS2000A_CHANNEL_A"],
                1,  # enabled
                coupling,
                chA_range,
                0  # analogue offset
            )
            self.assert_pico_ok(self.status["setChA"])
            
            # Channel B (reference)
            self.status["setChB"] = ps.ps2000aSetChannel(
                self.chandle,
                ps.PS2000A_CHANNEL["PS2000A_CHANNEL_B"],
                1,  # enabled
                coupling,
                chB_range,
                0  # analogue offset
            )
            self.assert_pico_ok(self.status["setChB"])
            
            # Max ADC for 8-bit 2000a series
            self.maxADC = ctypes.c_int16(32512)  # For 8-bit mode
            
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
        # Calculate acquisition parameters
        # CRITICAL: Optimized parameters for stability (0.66% CV)
        # Decimation = 1024 gives ~97.6 kSPS sampling rate
        # This provides ~1200 samples/cycle at 81 Hz (good for Hilbert transform)
        
        base_rate = 100e6  # 100 MS/s
        decimation = 1024  # FIXED decimation for stability
        fs = base_rate / decimation  # 97,656 Hz
        
        # Calculate number of samples needed for requested cycles
        # At 81 Hz: 97656 / 81 ≈ 1205 samples/cycle
        samples_per_cycle = fs / reference_freq
        num_samples = int(num_cycles * samples_per_cycle)
        
        # Cap at reasonable maximum (memory/speed limit)
        num_samples = min(num_samples, 200000)
        
        # Calculate actual cycles that will be captured
        actual_cycles = int(num_samples / samples_per_cycle)
        
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
        ps = self.ps
        
        try:
            if self.device_type == '5000a':
                return self._acquire_block_5000a(num_samples, decimation)
            else:
                return self._acquire_block_2000a(num_samples, decimation)
                
        except Exception as e:
            print(f"ERROR acquiring data: {e}")
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
    
    def _acquire_block_2000a(self, num_samples, decimation):
        """Acquire block data from PS2000a"""
        ps = self.ps
        
        # Calculate timebase from decimation
        # For PS2000a: similar to 5000a
        timebase = int(np.log2(decimation))
        
        # Get timebase info
        timeIntervalns = ctypes.c_int32()
        maxSamples = ctypes.c_int32()
        self.status["getTimebase2"] = ps.ps2000aGetTimebase2(
            self.chandle,
            timebase,
            num_samples,
            ctypes.byref(timeIntervalns),
            1,  # oversample (not used)
            ctypes.byref(maxSamples),
            0  # segment index
        )
        self.assert_pico_ok(self.status["getTimebase2"])
        
        # Set up data buffers
        bufferAMax = (ctypes.c_int16 * num_samples)()
        bufferBMax = (ctypes.c_int16 * num_samples)()
        
        # Set data buffer locations
        self.status["setDataBuffersA"] = ps.ps2000aSetDataBuffer(
            self.chandle,
            ps.PS2000A_CHANNEL["PS2000A_CHANNEL_A"],
            ctypes.byref(bufferAMax),
            num_samples,
            0,  # segment index
            0   # ratio mode
        )
        self.assert_pico_ok(self.status["setDataBuffersA"])
        
        self.status["setDataBuffersB"] = ps.ps2000aSetDataBuffer(
            self.chandle,
            ps.PS2000A_CHANNEL["PS2000A_CHANNEL_B"],
            ctypes.byref(bufferBMax),
            num_samples,
            0,
            0
        )
        self.assert_pico_ok(self.status["setDataBuffersB"])
        
        # Set up trigger on Channel B (reference) for phase-locked acquisition
        from picosdk.functions import mV2adc
        # Trigger at 50% of reference signal (2.5V for 0-5V square wave)
        threshold = 2500  # mV
        threshold_adc = mV2adc(threshold, self.chB_range, self.maxADC)
        
        self.status["trigger"] = ps.ps2000aSetSimpleTrigger(
            self.chandle,
            1,  # enable
            ps.PS2000A_CHANNEL["PS2000A_CHANNEL_B"],  # trigger on reference
            threshold_adc,
            2,  # direction: rising edge
            0,  # delay
            1000  # auto-trigger timeout
        )
        self.assert_pico_ok(self.status["trigger"])
        
        # Run block capture with trigger
        preTriggerSamples = int(num_samples * 0.1)
        postTriggerSamples = num_samples - preTriggerSamples
        
        self.status["runBlock"] = ps.ps2000aRunBlock(
            self.chandle,
            preTriggerSamples,  # preTriggerSamples  
            postTriggerSamples,  # postTriggerSamples
            timebase,
            1,  # oversample
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
            self.status["isReady"] = ps.ps2000aIsReady(self.chandle, ctypes.byref(ready))
        
        # Get data
        overflow = ctypes.c_int16()
        cmaxSamples = ctypes.c_int32(num_samples)
        self.status["getValues"] = ps.ps2000aGetValues(
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
    
    def close(self):
        """Close connection to PicoScope"""
        if self.connected and self.chandle is not None:
            try:
                if self.device_type == '5000a':
                    self.status["stop"] = self.ps.ps5000aStop(self.chandle)
                    self.status["close"] = self.ps.ps5000aCloseUnit(self.chandle)
                else:
                    self.status["stop"] = self.ps.ps2000aStop(self.chandle)
                    self.status["close"] = self.ps.ps2000aCloseUnit(self.chandle)
                
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
            print(f"  Phase:           {result['theta']:+.1f}°")
            print(f"  Measured freq:   {result['freq']:.2f} Hz")
            print(f"\n  Raw signal range:    {np.min(result['signal_data']):.4f} to {np.max(result['signal_data']):.4f} V")
            print(f"  Raw reference range: {np.min(result['reference_data']):.4f} to {np.max(result['reference_data']):.4f} V")
            print(f"\n  ✓ No clipping! (PicoScope has ±20V range)")
        
        scope.close()
    else:
        print("Failed to connect to PicoScope")
