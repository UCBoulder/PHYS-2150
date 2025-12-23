"""
Oriel Cornerstone Monochromator Controller

This controller provides a clean interface to the Oriel Cornerstone monochromator.
It handles wavelength control, grating selection, filter management, and shutter control.
"""

import pyvisa as visa
from typing import Optional, Dict, Any
from ..drivers.cornerstone_mono import Cornerstone_Mono


class MonochromatorError(Exception):
    """Exception raised for monochromator specific errors."""
    pass


class MonochromatorController:
    """
    Controller for Oriel Cornerstone monochromator device.
    
    This controller reflects exactly what the monochromator does:
    - Wavelength control
    - Grating selection
    - Filter positioning
    - Shutter control
    - Position querying
    """
    
    def __init__(self, resource_manager: Optional[visa.ResourceManager] = None):
        """
        Initialize the controller.
        
        Args:
            resource_manager: Optional VISA resource manager instance
        """
        self._rm = resource_manager or visa.ResourceManager()
        self._device: Optional[Cornerstone_Mono] = None
        self._is_connected = False
        self._serial_number: Optional[str] = None
        self._current_filter: Optional[int] = None  # Track current filter position
    
    def connect(self, interface: str = "usb", timeout_msec: int = 29000) -> bool:
        """
        Connect to the monochromator.
        
        Args:
            interface: Connection interface ("usb" or "serial")
            timeout_msec: Communication timeout in milliseconds
            
        Returns:
            bool: True if connection successful, False otherwise
            
        Raises:
            MonochromatorError: If connection fails
        """
        try:
            self._device = Cornerstone_Mono(
                self._rm, 
                rem_ifc=interface, 
                timeout_msec=timeout_msec
            )
            self._serial_number = self._device.serial_number
            self._is_connected = True
            return True
            
        except Exception as e:
            raise MonochromatorError(f"Failed to connect to monochromator: {e}")
    
    def disconnect(self) -> None:
        """Disconnect from the device."""
        if self._device and self._is_connected:
            try:
                # Close shutter before disconnecting
                self.close_shutter()
                self._is_connected = False
            except Exception as e:
                raise MonochromatorError(f"Failed to disconnect: {e}")
    
    def is_connected(self) -> bool:
        """Check if device is connected."""
        return self._is_connected
    
    @property
    def serial_number(self) -> Optional[str]:
        """Get the device serial number."""
        return self._serial_number
    
    def send_command(self, command: str, wait_for_idle: bool = True) -> None:
        """
        Send a command to the monochromator.
        
        Args:
            command: Command string to send
            wait_for_idle: Whether to wait for device to be idle after command
            
        Raises:
            MonochromatorError: If not connected or command fails
        """
        if not self._is_connected:
            raise MonochromatorError("Device not connected")
        
        try:
            self._device.SendCommand(command, False)
            if wait_for_idle:
                self._device.WaitForIdle()
        except Exception as e:
            raise MonochromatorError(f"Failed to send command '{command}': {e}")
    
    def query_response(self, command: str) -> str:
        """
        Send a query command and get the response.
        
        Args:
            command: Query command string
            
        Returns:
            str: Device response
            
        Raises:
            MonochromatorError: If query fails
        """
        if not self._is_connected:
            raise MonochromatorError("Device not connected")
        
        try:
            return self._device.GetQueryResponse(command)
        except Exception as e:
            raise MonochromatorError(f"Failed to query '{command}': {e}")
    
    def set_wavelength(self, wavelength: float) -> None:
        """
        Set the monochromator wavelength.
        
        Args:
            wavelength: Target wavelength in nanometers
        """
        self.send_command(f"gowave {wavelength}")
    
    def get_wavelength(self) -> float:
        """
        Get the current wavelength.
        
        Returns:
            float: Current wavelength in nanometers
        """
        response = self.query_response("wave?")
        return float(response)
    
    def set_grating(self, grating_number: int) -> None:
        """
        Set the active grating.
        
        Args:
            grating_number: Grating number (1 or 2)
        """
        if grating_number not in [1, 2]:
            raise MonochromatorError("Grating number must be 1 or 2")
        self.send_command(f"grating {grating_number}")
    
    def set_filter(self, filter_number: int) -> None:
        """
        Set the filter position.
        Only sends command if filter position has changed to avoid unnecessary filter wheel movement.
        
        Args:
            filter_number: Filter position (1, 2, 3, etc.)
        """
        # Only send command if filter position has actually changed
        if self._current_filter != filter_number:
            self.send_command(f"filter {filter_number}")
            self._current_filter = filter_number
    
    def open_shutter(self) -> None:
        """Open the monochromator shutter."""
        self.send_command("shutter o")
    
    def close_shutter(self) -> None:
        """Close the monochromator shutter."""
        self.send_command("shutter c")
    
    def set_wavelength_with_grating_auto(self, wavelength: float) -> None:
        """
        Set wavelength with automatic grating selection.
        
        Args:
            wavelength: Target wavelength in nanometers
        """
        # Auto-select grating based on wavelength
        if wavelength < 685:
            self.set_grating(1)
        else:
            self.set_grating(2)
        
        self.set_wavelength(wavelength)
    
    def set_filter_for_wavelength(self, wavelength: float) -> None:
        """
        Set appropriate filter based on wavelength.
        
        Args:
            wavelength: Wavelength in nanometers
        """
        if wavelength <= 420:
            self.set_filter(3)  # No filter
        elif wavelength <= 800:
            self.set_filter(1)  # 400 nm filter
        else:
            self.set_filter(2)  # 780 nm filter
    
    def configure_for_wavelength(self, wavelength: float) -> float:
        """
        Configure monochromator for specified wavelength.
        Sets grating, filter, and wavelength, then returns confirmed wavelength.
        
        Args:
            wavelength: Target wavelength in nanometers
            
        Returns:
            float: Confirmed wavelength from device
        """
        # Set appropriate grating
        self.set_wavelength_with_grating_auto(wavelength)
        
        # Set appropriate filter
        self.set_filter_for_wavelength(wavelength)
        
        # Get confirmed wavelength
        return self.get_wavelength()
    
    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect()