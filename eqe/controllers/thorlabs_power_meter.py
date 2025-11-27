"""
Thorlabs Power Meter Controller

This controller provides a clean interface to the Thorlabs Power Meter device.
It handles device initialization, configuration, and measurement operations.
"""

from ctypes import c_double, byref, c_uint32, create_string_buffer, c_bool
from typing import Optional, List
from ..drivers.TLPMX import TLPMX, TLPM_DEFAULT_CHANNEL


class ThorlabsPowerMeterError(Exception):
    """Exception raised for Thorlabs Power Meter specific errors."""
    pass


class ThorlabsPowerMeterController:
    """
    Controller for Thorlabs Power Meter device.
    
    This controller reflects exactly what the Thorlabs power meter does:
    - Device discovery and connection
    - Wavelength setting
    - Power measurements
    - Device configuration
    """
    
    def __init__(self):
        """Initialize the controller without connecting to device."""
        self._device: Optional[TLPMX] = None
        self._is_connected = False
        
    def connect(self) -> bool:
        """
        Connect to the first available Thorlabs power meter.
        
        Returns:
            bool: True if connection successful, False otherwise
            
        Raises:
            ThorlabsPowerMeterError: If connection fails
        """
        try:
            self._device = TLPMX()
            device_count = c_uint32()
            
            # Find available devices
            self._device.findRsrc(byref(device_count))
            if device_count.value == 0:
                raise ThorlabsPowerMeterError("No Thorlabs power meter devices found")
            
            # Connect to first device
            resource_name = create_string_buffer(1024)
            self._device.getRsrcName(0, resource_name)
            self._device.open(resource_name, c_bool(True), c_bool(True))
            
            self._is_connected = True
            return True
            
        except Exception as e:
            raise ThorlabsPowerMeterError(f"Failed to connect to power meter: {e}")
    
    def disconnect(self) -> None:
        """Disconnect from the device."""
        if self._device and self._is_connected:
            try:
                self._device.close()
                self._is_connected = False
            except Exception as e:
                raise ThorlabsPowerMeterError(f"Failed to disconnect: {e}")
    
    def is_connected(self) -> bool:
        """Check if device is connected."""
        return self._is_connected
    
    def set_wavelength(self, wavelength: float) -> None:
        """
        Set the wavelength for power measurement calibration.
        
        Args:
            wavelength: Wavelength in nanometers
            
        Raises:
            ThorlabsPowerMeterError: If not connected or setting fails
        """
        if not self._is_connected:
            raise ThorlabsPowerMeterError("Device not connected")
        
        try:
            self._device.setWavelength(c_double(wavelength), TLPM_DEFAULT_CHANNEL)
        except Exception as e:
            raise ThorlabsPowerMeterError(f"Failed to set wavelength: {e}")
    
    def measure_power(self) -> float:
        """
        Measure power in watts.
        
        Returns:
            float: Power measurement in watts
            
        Raises:
            ThorlabsPowerMeterError: If measurement fails
        """
        if not self._is_connected:
            raise ThorlabsPowerMeterError("Device not connected")
        
        try:
            power = c_double()
            self._device.measPower(byref(power), TLPM_DEFAULT_CHANNEL)
            return power.value
        except Exception as e:
            raise ThorlabsPowerMeterError(f"Failed to measure power: {e}")
    
    def measure_power_multiple(self, num_measurements: int = 200) -> List[float]:
        """
        Take multiple power measurements.
        
        Args:
            num_measurements: Number of measurements to take
            
        Returns:
            List[float]: List of power measurements in watts
        """
        measurements = []
        for _ in range(num_measurements):
            measurements.append(self.measure_power())
        return measurements
    
    def measure_power_average(self, num_measurements: int = 200, 
                             correction_factor: float = 2.0) -> float:
        """
        Measure average power with multiple readings.
        
        Args:
            num_measurements: Number of measurements to average
            correction_factor: Correction factor to apply
            
        Returns:
            float: Average power measurement in watts
        """
        measurements = self.measure_power_multiple(num_measurements)
        average_power = sum(measurements) / len(measurements)
        return average_power * correction_factor
    
    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect()