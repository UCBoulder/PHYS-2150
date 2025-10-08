"""
SR510 Lock-in Amplifier Controller

This controller provides a clean interface to the SR510 lock-in amplifier.
It handles serial communication, parameter configuration, and signal measurement.
"""

import serial
import serial.tools.list_ports
import time
from typing import Optional, Dict, Tuple
import numpy as np


class SR510Error(Exception):
    """Exception raised for SR510 lock-in amplifier specific errors."""
    pass


class SR510Controller:
    """
    Controller for SR510 lock-in amplifier device.
    
    This controller reflects exactly what the SR510 does:
    - Serial communication
    - Parameter configuration (sensitivity, phase, etc.)
    - Signal measurement
    - Status monitoring
    """
    
    # Sensitivity mapping from device codes to values
    SENSITIVITY_MAP = {
        1: 10e-9, 2: 20e-9, 3: 50e-9, 4: 100e-9, 5: 200e-9, 6: 500e-9,
        7: 1e-6, 8: 2e-6, 9: 5e-6, 10: 10e-6, 11: 20e-6, 12: 50e-6,
        13: 100e-6, 14: 200e-6, 15: 500e-6, 16: 1e-3, 17: 2e-3, 18: 5e-3,
        19: 10e-3, 20: 20e-3, 21: 50e-3, 22: 100e-3, 23: 200e-3, 24: 500e-3
    }
    
    def __init__(self):
        """Initialize the controller without connecting to device."""
        self._serial: Optional[serial.Serial] = None
        self._is_connected = False
    
    def connect(self, port: Optional[str] = None, baudrate: int = 19200,
                parity: str = serial.PARITY_ODD, stopbits: int = serial.STOPBITS_TWO,
                bytesize: int = serial.EIGHTBITS, timeout: float = 2.0) -> bool:
        """
        Connect to the SR510 via serial port.
        
        Args:
            port: Specific port to connect to, or None for auto-detection
            baudrate: Serial communication baud rate
            parity: Parity setting
            stopbits: Stop bits setting
            bytesize: Byte size setting
            timeout: Communication timeout in seconds
            
        Returns:
            bool: True if connection successful, False otherwise
            
        Raises:
            SR510Error: If connection fails
        """
        try:
            if port is None:
                port = self._find_sr510_port()
            
            self._serial = serial.Serial(
                port=port,
                baudrate=baudrate,
                parity=parity,
                stopbits=stopbits,
                bytesize=bytesize,
                timeout=timeout
            )
            
            self._is_connected = True
            return True
            
        except Exception as e:
            raise SR510Error(f"Failed to connect to SR510: {e}")
    
    def _find_sr510_port(self) -> str:
        """
        Auto-detect the SR510 COM port.
        
        Returns:
            str: COM port device name
            
        Raises:
            SR510Error: If port not found
        """
        ports = serial.tools.list_ports.comports()
        for port in ports:
            if "Prolific PL2303GT USB Serial COM Port" in port.description:
                return port.device
        
        raise SR510Error("COM port not found for SR510 lock-in amplifier")
    
    def disconnect(self) -> None:
        """Disconnect from the device."""
        if self._serial and self._is_connected:
            try:
                self._serial.close()
                self._is_connected = False
            except Exception as e:
                raise SR510Error(f"Failed to disconnect: {e}")
    
    def is_connected(self) -> bool:
        """Check if device is connected."""
        return self._is_connected
    
    def send_command(self, command: str) -> None:
        """
        Send a command to the SR510.
        
        Args:
            command: Command string (should end with \\r)
            
        Raises:
            SR510Error: If not connected or send fails
        """
        if not self._is_connected:
            raise SR510Error("Device not connected")
        
        try:
            if not command.endswith('\\r'):
                command += '\\r'
            self._serial.write(command.encode())
        except Exception as e:
            raise SR510Error(f"Failed to send command: {e}")
    
    def read_response(self) -> str:
        """
        Read response from the SR510.
        
        Returns:
            str: Response string (stripped of \\r)
            
        Raises:
            SR510Error: If read fails
        """
        if not self._is_connected:
            raise SR510Error("Device not connected")
        
        try:
            response = ""
            while True:
                char = self._serial.read().decode()
                response += char
                if char == '\\r':
                    break
            return response.strip()
        except Exception as e:
            raise SR510Error(f"Failed to read response: {e}")
    
    def query(self, command: str) -> str:
        """
        Send command and read response.
        
        Args:
            command: Command string
            
        Returns:
            str: Device response
        """
        self.send_command(command)
        time.sleep(0.5)  # Allow time for device to process
        return self.read_response()
    
    def wait_for_ready(self) -> None:
        """Wait for the device to be ready."""
        while True:
            status_response = self.query('Y')
            if status_response:
                try:
                    status_byte = int(status_response)
                    if status_byte & (1 << 0):  # Ready bit
                        break
                except ValueError:
                    pass
            time.sleep(1)
    
    def set_sensitivity(self, sensitivity_code: int) -> None:
        """
        Set the sensitivity.
        
        Args:
            sensitivity_code: Sensitivity code (1-24)
        """
        if sensitivity_code not in self.SENSITIVITY_MAP:
            raise SR510Error(f"Invalid sensitivity code: {sensitivity_code}")
        
        self.send_command(f'G {sensitivity_code}')
        self.wait_for_ready()
    
    def get_sensitivity(self) -> Tuple[int, float]:
        """
        Get current sensitivity.
        
        Returns:
            Tuple[int, float]: (sensitivity_code, sensitivity_value)
        """
        response = self.query("G")
        sensitivity_code = int(response.strip())
        sensitivity_value = self.SENSITIVITY_MAP.get(sensitivity_code, 1)
        return sensitivity_code, sensitivity_value
    
    def set_phase(self, phase: float) -> None:
        """
        Set the phase.
        
        Args:
            phase: Phase in degrees
        """
        self.send_command(f'P {phase}')
        self.wait_for_ready()
    
    def read_output(self) -> float:
        """
        Read the output signal.
        
        Returns:
            float: Output signal value
        """
        response = self.query('Q')
        return float(response)
    
    def configure_standard_parameters(self) -> None:
        """Configure standard parameters for EQE measurement."""
        commands = [
            'G 24',    # Set sensitivity to 500 mV
            'B 0',     # Bandpass: OUT
            'L 1,0',   # Line: OUT
            'L 2,0',   # LINE x2: OUT
            'D 0',     # DYN RES: LOW
            'S 0',     # DISPLAY: X
            'E 0',     # Expand: X1 (OFF)
            'O 0',     # Offset: OFF
            'T 1,5',   # Pre Time constant: 100ms
            'T 2,1',   # Post Time constant: 0.1s
            'M 0',     # Reference frequency: f
            'R 0',     # Input: Square wave
        ]
        
        for command in commands:
            self.send_command(command)
        
        self.wait_for_ready()
    
    def get_status(self) -> Dict[str, bool]:
        """
        Get device status.
        
        Returns:
            Dict[str, bool]: Status dictionary with lock, reference, overload status
        """
        response = self.query('Y')
        if not response:
            return {'locked': False, 'has_reference': False, 'overloaded': True}
        
        try:
            status_byte = int(response.split('\\r')[0].strip())
            return {
                'locked': not (status_byte & (1 << 3)),
                'has_reference': not (status_byte & (1 << 2)),
                'overloaded': bool(status_byte & (1 << 4))
            }
        except (ValueError, IndexError):
            return {'locked': False, 'has_reference': False, 'overloaded': True}
    
    def increase_sensitivity(self) -> None:
        """Increase sensitivity (decrease sensitivity code)."""
        self.send_command('K 22')
        time.sleep(5)  # Wait for sensitivity change to take effect
    
    def flush_input(self) -> None:
        """Flush the input buffer."""
        if self._serial:
            self._serial.flushInput()
    
    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect()