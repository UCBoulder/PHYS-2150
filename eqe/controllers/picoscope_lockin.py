"""
PicoScope Lock-in Amplifier Controller

This controller provides a clean interface to the PicoScope oscilloscope
configured as a software lock-in amplifier for EQE measurements.
It handles device connection, configuration, and lock-in signal measurement.
"""

import time
from typing import Optional, Dict, Tuple
import numpy as np

from ..drivers.picoscope_driver import PicoScopeDriver
from ..config.settings import DEVICE_CONFIGS, DeviceType


class PicoScopeError(Exception):
    """Exception raised for PicoScope lock-in amplifier specific errors."""
    pass


class PicoScopeController:
    """
    Controller for PicoScope oscilloscope operating as a software lock-in amplifier.
    
    This controller reflects what the PicoScope does:
    - USB connection management
    - Software lock-in measurement using Hilbert transform
    - Signal and reference channel acquisition
    - Phase and magnitude extraction
    """
    
    def __init__(self, serial_number: Optional[str] = None):
        """
        Initialize the controller.

        Args:
            serial_number: Optional serial number to connect to specific device
        """
        self._driver = PicoScopeDriver(serial_number=serial_number)
        self._is_connected = False

        # Load configuration from settings
        config = DEVICE_CONFIGS[DeviceType.PICOSCOPE_LOCKIN]
        self._reference_freq = config["default_chopper_freq"]
        self._num_cycles = config["default_num_cycles"]
        # Correction factor compensates for RMS normalization in Hilbert algorithm
        # Value of 0.5 validated via AWG testing - see docs/lockin_validation_handoff.md
        self._correction_factor = config["correction_factor"]
        
    def connect(self) -> bool:
        """
        Connect to the PicoScope via USB.
        
        Returns:
            bool: True if connection successful, False otherwise
            
        Raises:
            PicoScopeError: If connection fails
        """
        try:
            success = self._driver.connect()
            if success:
                self._is_connected = True
                return True
            else:
                raise PicoScopeError("Failed to connect to PicoScope")
                
        except Exception as e:
            raise PicoScopeError(f"Failed to connect to PicoScope: {e}")
    
    def disconnect(self) -> None:
        """Disconnect from the device."""
        if self._is_connected:
            try:
                self._driver.close()
                self._is_connected = False
            except Exception as e:
                raise PicoScopeError(f"Failed to disconnect: {e}")
    
    def is_connected(self) -> bool:
        """Check if device is connected."""
        return self._is_connected
    
    def set_reference_frequency(self, frequency: float) -> None:
        """
        Set the reference frequency (chopper frequency).
        
        Args:
            frequency: Reference frequency in Hz
            
        Raises:
            PicoScopeError: If frequency is invalid
        """
        if frequency <= 0:
            raise PicoScopeError("Frequency must be positive")
        
        self._reference_freq = frequency
        self._driver.set_reference_frequency(frequency)
    
    def get_reference_frequency(self) -> float:
        """
        Get the current reference frequency.
        
        Returns:
            float: Reference frequency in Hz
        """
        return self._reference_freq
    
    def set_num_cycles(self, num_cycles: int) -> None:
        """
        Set the number of cycles for lock-in integration.
        More cycles = better noise rejection but slower measurement.
        
        Args:
            num_cycles: Number of cycles to integrate over (typical: 50-100)
            
        Raises:
            PicoScopeError: If num_cycles is invalid
        """
        if num_cycles <= 0:
            raise PicoScopeError("Number of cycles must be positive")
        
        self._num_cycles = num_cycles
    
    def get_num_cycles(self) -> int:
        """
        Get the current number of cycles for integration.
        
        Returns:
            int: Number of cycles
        """
        return self._num_cycles

    def get_correction_factor(self) -> float:
        """
        Get the correction factor for lock-in amplitude scaling.

        Returns:
            float: Correction factor (typically 0.5 for Hilbert algorithm)
        """
        return self._correction_factor

    def perform_lockin_measurement(self) -> Optional[Dict[str, float]]:
        """
        Perform a software lock-in measurement.
        
        This acquires waveforms from both channels (signal and reference),
        performs Hilbert transform for quadrature generation, and extracts
        the in-phase (X), quadrature (Y), magnitude (R), and phase (theta).
        
        Returns:
            Optional[Dict[str, float]]: Dictionary containing:
                - 'X': In-phase component (V)
                - 'Y': Quadrature component (V)
                - 'R': Magnitude (V)
                - 'theta': Phase in degrees
                - 'freq': Measured reference frequency (Hz)
                Or None if measurement fails
                
        Raises:
            PicoScopeError: If not connected or measurement fails
        """
        if not self._is_connected:
            raise PicoScopeError("Device not connected")
        
        try:
            result = self._driver.software_lockin(
                self._reference_freq,
                num_cycles=self._num_cycles,
                correction_factor=self._correction_factor
            )

            if result is None:
                raise PicoScopeError("Lock-in measurement returned None")
            
            return {
                'X': result['X'],
                'Y': result['Y'],
                'R': result['R'],
                'theta': result['theta'],
                'freq': result['freq']
            }
            
        except Exception as e:
            raise PicoScopeError(f"Failed to perform lock-in measurement: {e}")
    
    def read_lockin_current(self, num_measurements: int = 1) -> Optional[float]:
        """
        Read a single photocurrent measurement using software lock-in.

        This is an alias for read_current() with num_measurements=1, provided
        for compatibility with stability test code that expects this method name.

        Args:
            num_measurements: Number of measurements to average (default: 1)

        Returns:
            Optional[float]: Measured current in Amps, or None if error

        Raises:
            PicoScopeError: If measurement fails
        """
        return self.read_current(num_measurements=num_measurements)

    def read_current_fast(self, num_cycles: int = 20) -> Optional[float]:
        """
        Read photocurrent with reduced cycles for fast live monitoring.

        Uses fewer integration cycles for faster updates (~0.3s vs ~1.5s).
        Less accurate but suitable for alignment and quick checks.

        Args:
            num_cycles: Number of cycles to integrate (default: 20 for speed)

        Returns:
            Optional[float]: Measured current in Amps, or None if error

        Raises:
            PicoScopeError: If measurement fails
        """
        if not self._is_connected:
            raise PicoScopeError("Device not connected")

        # Temporarily use fewer cycles
        original_cycles = self._num_cycles
        self._num_cycles = num_cycles

        try:
            result = self.perform_lockin_measurement()
            if result is None:
                return None

            # Convert R (voltage) to current using TIA gain
            # R is in volts, TIA gain is 1 MΩ, so I = V / R_tia = V * 1e-6
            from ..config.settings import CURRENT_MEASUREMENT_CONFIG
            tia_gain = CURRENT_MEASUREMENT_CONFIG.get("transimpedance_gain", 1e-6)
            current = result['R'] * tia_gain

            return current

        except Exception as e:
            raise PicoScopeError(f"Fast current measurement failed: {e}")

        finally:
            # Restore original cycles
            self._num_cycles = original_cycles

    def read_current(self, num_measurements: int = 5) -> Optional[float]:
        """
        Read photocurrent using software lock-in with robust averaging.

        This performs multiple lock-in measurements and uses trimmed mean
        averaging to reject outliers from lamp flicker and chopper variations.

        Args:
            num_measurements: Number of measurements to average (default: 5)

        Returns:
            Optional[float]: Measured current in Amps, or None if error

        Raises:
            PicoScopeError: If measurement fails
        """
        if not self._is_connected:
            raise PicoScopeError("Device not connected")
        
        try:
            R_values = []
            
            for i in range(num_measurements):
                result = self.perform_lockin_measurement()
                
                if result is not None:
                    # Use the magnitude (R) directly - this is phase-independent!
                    # R = sqrt(X^2 + Y^2) gives us the signal amplitude regardless of phase
                    R_values.append(result['R'])
                else:
                    print(f"Warning: Lock-in measurement {i+1}/{num_measurements} failed")
            
            if not R_values:
                raise PicoScopeError("All lock-in measurements failed")
            
            # Use MEDIAN and TRIMMED MEAN for robust averaging
            R_array = np.array(R_values)
            
            # Calculate median for reference
            median_signal = np.median(R_array)
            
            # Trimmed mean: remove outliers beyond 2 standard deviations from median
            deviations = np.abs(R_array - median_signal)
            threshold = 2 * np.std(deviations)
            mask = deviations <= threshold
            R_trimmed = R_array[mask]
            
            # Use trimmed mean if we have enough measurements remaining
            if len(R_trimmed) >= 3:
                average_signal = np.mean(R_trimmed)
                std_signal = np.std(R_trimmed)
                n_outliers = len(R_values) - len(R_trimmed)
            else:
                # If too many outliers, use median (most robust)
                average_signal = median_signal
                std_signal = np.std(R_array)
                n_outliers = 0
            
            # Calculate coefficient of variation for quality metric
            cv = 100 * std_signal / average_signal if average_signal > 0 else 0
            
            print(f"Lock-in measurement: {average_signal:.6f} ± {std_signal:.6f} V "
                  f"(n={len(R_trimmed)}/{num_measurements}, outliers={n_outliers}, CV={cv:.2f}%)")
            
            # Check for saturation
            if abs(average_signal) > 0.95:
                print(f"Warning: Signal near saturation ({average_signal:.3f} V)")
            
            # Apply transimpedance amplifier gain
            # Note: The correction factor (0.5) is already applied in perform_lockin_measurement
            # via the driver. Here we just convert voltage to current using TIA gain.
            # Assuming 1 MΩ transimpedance gain (see settings.py transimpedance_gain)
            current = average_signal * 10 ** -6  # Convert to Amps (from V with 1MΩ gain)
            
            return current
            
        except Exception as e:
            raise PicoScopeError(f"Failed to read current: {e}")
    
    def measure_phase_response(self) -> Tuple[float, float, float]:
        """
        Measure the signal phase and magnitude using software lock-in.
        
        The software lock-in calculates X, Y components and finds the phase
        that maximizes the signal magnitude. Returns the optimal phase angle,
        signal magnitude, and a quality metric.
        
        Returns:
            Tuple[float, float, float]: (optimal_phase_deg, signal_magnitude_V, quality_metric)
            
        Raises:
            PicoScopeError: If measurement fails
        """
        if not self._is_connected:
            raise PicoScopeError("Device not connected")
        
        try:
            # Perform software lock-in measurement
            result = self.perform_lockin_measurement()
            
            if result is None:
                raise PicoScopeError("Phase response measurement failed")
            
            # Extract results
            X = result['X']
            Y = result['Y']
            R = result['R']
            theta_deg = result['theta']
            
            # The optimal phase is where the signal is maximum
            # This is the phase of the signal itself
            optimal_phase = theta_deg % 360
            signal_magnitude = R
            
            # Calculate signal quality (SNR estimate)
            # For now, we'll use a simplified quality metric
            # Higher R indicates better signal
            quality_metric = min(1.0, R / 0.1)  # Normalized to 0.1V reference
            
            print(f"Phase response: Phase={optimal_phase:.1f}°, Magnitude={signal_magnitude:.6f} V, Quality={quality_metric:.4f}")
            
            return optimal_phase, signal_magnitude, quality_metric
            
        except Exception as e:
            raise PicoScopeError(f"Failed to measure phase response: {e}")
    
    def get_status(self) -> Dict[str, bool]:
        """
        Get device status.
        
        For PicoScope, we always have signal when connected and measuring.
        This is provided for API compatibility with SR510 controller.
        
        Returns:
            Dict[str, bool]: Status dictionary
        """
        return {
            'connected': self._is_connected,
            'locked': self._is_connected,  # Software lock-in always "locked"
            'has_reference': self._is_connected,
            'overloaded': False  # Would need to check signal amplitude
        }
    
    def __enter__(self):
        """Context manager entry."""
        if not self._is_connected:
            self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect()
