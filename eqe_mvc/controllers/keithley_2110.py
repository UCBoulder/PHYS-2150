"""
Keithley 2110 Multimeter Controller

This controller provides a clean interface to the Keithley 2110 multimeter.
It handles device discovery, VISA communication, and measurement operations.
"""

import pyvisa as visa
from typing import Optional, List


class Keithley2110Error(Exception):
    """Exception raised for Keithley 2110 specific errors."""
    pass


class Keithley2110Controller:
    """
    Controller for Keithley 2110 multimeter device.
    
    This controller reflects exactly what the Keithley 2110 does:
    - VISA connection management
    - Voltage and current measurements
    - Measurement function configuration
    """
    
    def __init__(self, resource_manager: Optional[visa.ResourceManager] = None):
        """
        Initialize the controller.
        
        Args:
            resource_manager: Optional VISA resource manager instance
        """
        self._rm = resource_manager or visa.ResourceManager()
        self._device: Optional[visa.Resource] = None
        self._is_connected = False
    
    def connect(self) -> bool:
        """
        Connect to the first available Keithley 2110.
        
        Returns:
            bool: True if connection successful, False otherwise
            
        Raises:
            Keithley2110Error: If connection fails
        """
        try:
            resources = self._rm.list_resources()
            keithley_resource = None
            
            # Find Keithley 2110 in available resources
            for resource in resources:
                if '2110' in resource:
                    keithley_resource = resource
                    break
            
            if not keithley_resource:
                raise Keithley2110Error("Keithley 2110 not found in available resources")
            
            # Open connection
            self._device = self._rm.open_resource(keithley_resource)
            self._is_connected = True
            return True
            
        except Exception as e:
            raise Keithley2110Error(f"Failed to connect to Keithley 2110: {e}")
    
    def disconnect(self) -> None:
        """Disconnect from the device."""
        if self._device and self._is_connected:
            try:
                self._device.close()
                self._is_connected = False
            except Exception as e:
                raise Keithley2110Error(f"Failed to disconnect: {e}")
    
    def is_connected(self) -> bool:
        """Check if device is connected."""
        return self._is_connected
    
    def set_measurement_function(self, function: str) -> None:
        """
        Set the measurement function.
        
        Args:
            function: Measurement function ('VOLT:DC', 'CURR:DC', etc.)
            
        Raises:
            Keithley2110Error: If not connected or command fails
        """
        if not self._is_connected:
            raise Keithley2110Error("Device not connected")
        
        try:
            self._device.write(f":SENS:FUNC '{function}'")
        except Exception as e:
            raise Keithley2110Error(f"Failed to set measurement function: {e}")
    
    def read_measurement(self) -> float:
        """
        Read a single measurement.
        
        Returns:
            float: Measurement value
            
        Raises:
            Keithley2110Error: If measurement fails
        """
        if not self._is_connected:
            raise Keithley2110Error("Device not connected")
        
        try:
            result = self._device.query(":READ?")
            return float(result)
        except Exception as e:
            raise Keithley2110Error(f"Failed to read measurement: {e}")
    
    def measure_voltage_dc(self) -> float:
        """
        Measure DC voltage.
        
        Returns:
            float: DC voltage in volts
        """
        self.set_measurement_function('VOLT:DC')
        return self.read_measurement()
    
    def measure_current_dc(self) -> float:
        """
        Measure DC current.
        
        Returns:
            float: DC current in amperes
        """
        self.set_measurement_function('CURR:DC')
        return self.read_measurement()
    
    def measure_voltage_multiple(self, num_measurements: int = 100) -> List[float]:
        """
        Take multiple DC voltage measurements.
        
        Args:
            num_measurements: Number of measurements to take
            
        Returns:
            List[float]: List of voltage measurements in volts
        """
        self.set_measurement_function('VOLT:DC')
        measurements = []
        for _ in range(num_measurements):
            measurements.append(self.read_measurement())
        return measurements
    
    def measure_voltage_average(self, num_measurements: int = 100) -> float:
        """
        Measure average DC voltage over multiple readings.
        
        Args:
            num_measurements: Number of measurements to average
            
        Returns:
            float: Average voltage in volts
        """
        measurements = self.measure_voltage_multiple(num_measurements)
        return sum(measurements) / len(measurements)
    
    def measure_current_multiple(self, num_measurements: int = 150, 
                                scale_factor: float = 1e6) -> List[float]:
        """
        Take multiple DC current measurements with scaling.
        
        Args:
            num_measurements: Number of measurements to take
            scale_factor: Factor to scale current (e.g., 1e6 for microamps)
            
        Returns:
            List[float]: List of scaled current measurements
        """
        self.set_measurement_function('CURR:DC')
        measurements = []
        for _ in range(num_measurements):
            current = self.read_measurement() * scale_factor
            measurements.append(current)
        return measurements
    
    def measure_current_average(self, num_measurements: int = 150, 
                               scale_factor: float = 1e6) -> float:
        """
        Measure average DC current over multiple readings.
        
        Args:
            num_measurements: Number of measurements to average
            scale_factor: Factor to scale current
            
        Returns:
            float: Average scaled current
        """
        measurements = self.measure_current_multiple(num_measurements, scale_factor)
        return sum(measurements) / len(measurements)
    
    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect()