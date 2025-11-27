"""
Keithley 2450 Source Measure Unit Controller

This controller provides a clean interface to the Keithley 2450 SMU.
It handles VISA communication and exposes device capabilities as methods.

The controller reflects exactly what the device does:
- Voltage sourcing
- Current measurement
- Range and compliance configuration
- Output control

It does NOT contain experiment logic - that belongs in the Model layer.
"""

import pyvisa as visa
from typing import Optional, Tuple
from decimal import Decimal, ROUND_HALF_UP

from ..config.settings import DEVICE_CONFIG


class Keithley2450Error(Exception):
    """Exception raised for Keithley 2450 specific errors."""
    pass


class Keithley2450Controller:
    """
    Controller for Keithley 2450 Source Measure Unit.

    This controller handles VISA communication with the Keithley 2450 and
    exposes its capabilities for voltage sourcing and current measurement.
    """

    def __init__(self, resource_manager: Optional[visa.ResourceManager] = None):
        """
        Initialize the controller.

        Args:
            resource_manager: Optional VISA resource manager instance.
                             If not provided, one will be created.
        """
        self._rm = resource_manager
        self._device: Optional[visa.Resource] = None
        self._is_connected = False
        self._device_address: Optional[str] = None

    def connect(self, address: Optional[str] = None) -> bool:
        """
        Connect to the Keithley 2450.

        Args:
            address: Optional VISA resource address. If not provided,
                    will search for device using USB ID pattern.

        Returns:
            bool: True if connection successful

        Raises:
            Keithley2450Error: If connection fails or device not found
        """
        try:
            # Create resource manager if not provided
            if self._rm is None:
                self._rm = visa.ResourceManager()

            # Find device address if not provided
            if address is None:
                address = self._find_device()
                if address is None:
                    raise Keithley2450Error(
                        "Keithley 2450 not found. Please check connection."
                    )

            # Open resource
            self._device = self._rm.open_resource(address)
            self._device.timeout = DEVICE_CONFIG["timeout_ms"]
            self._device_address = address
            self._is_connected = True

            return True

        except visa.VisaIOError as e:
            raise Keithley2450Error(f"VISA communication error: {e}")
        except Exception as e:
            raise Keithley2450Error(f"Failed to connect: {e}")

    def _find_device(self) -> Optional[str]:
        """
        Search for Keithley 2450 in available VISA resources.

        Returns:
            Optional[str]: Device address if found, None otherwise
        """
        usb_pattern = DEVICE_CONFIG["usb_id_pattern"]
        for resource in self._rm.list_resources():
            if resource.startswith(usb_pattern):
                return resource
        return None

    def disconnect(self) -> None:
        """Disconnect from the device."""
        if self._device and self._is_connected:
            try:
                # Turn off output before disconnecting
                self.output_off()
                self._device.close()
            except Exception:
                pass  # Best effort cleanup
            finally:
                self._is_connected = False
                self._device = None

    def is_connected(self) -> bool:
        """Check if device is connected."""
        return self._is_connected

    @property
    def device_address(self) -> Optional[str]:
        """Get the device VISA address."""
        return self._device_address

    def _check_connected(self) -> None:
        """Verify device is connected before operations."""
        if not self._is_connected or self._device is None:
            raise Keithley2450Error("Device not connected")

    def write(self, command: str) -> None:
        """
        Send a SCPI command to the device.

        Args:
            command: SCPI command string
        """
        self._check_connected()
        try:
            self._device.write(command)
        except visa.VisaIOError as e:
            raise Keithley2450Error(f"Write command failed: {e}")

    def query(self, command: str) -> str:
        """
        Send a query and return the response.

        Args:
            command: SCPI query command

        Returns:
            str: Device response
        """
        self._check_connected()
        try:
            return self._device.query(command).strip()
        except visa.VisaIOError as e:
            raise Keithley2450Error(f"Query failed: {e}")

    def reset(self) -> None:
        """Reset device to default state."""
        self.write("*RST")

    def configure_voltage_source(
        self,
        voltage_range: float = 2,
        current_limit: float = 1,
    ) -> None:
        """
        Configure device as a voltage source.

        Args:
            voltage_range: Voltage source range in Volts
            current_limit: Current compliance limit in Amps
        """
        self.write("SOUR:FUNC VOLT")
        self.write(f"SOUR:VOLT:RANG {voltage_range}")
        self.write(f"SOUR:VOLT:ILIM {current_limit}")

    def configure_current_measurement(
        self,
        current_range: float = 10,
        remote_sensing: bool = True,
    ) -> None:
        """
        Configure current measurement settings.

        Args:
            current_range: Current measurement range in mA
            remote_sensing: Enable 4-wire (remote) sensing for accuracy
        """
        self.write('SENS:FUNC "CURR"')
        self.write(f"SENS:CURR:RANG {current_range}")
        if remote_sensing:
            self.write("SENS:CURR:RSEN ON")
        else:
            self.write("SENS:CURR:RSEN OFF")

    def set_voltage(self, voltage: float) -> None:
        """
        Set the source voltage.

        Args:
            voltage: Voltage in Volts
        """
        self.write(f"SOUR:VOLT {voltage}")

    def measure_current(self) -> float:
        """
        Measure current at current source voltage.

        Returns:
            float: Measured current in Amps
        """
        response = self.query("MEAS:CURR?")
        return float(response)

    def measure_current_precise(self) -> Decimal:
        """
        Measure current with high precision using Decimal.

        Returns:
            Decimal: Measured current in Amps with full precision
        """
        response = self.query("MEAS:CURR?")
        return Decimal(response)

    def output_on(self) -> None:
        """Enable the output."""
        self.write("OUTP ON")

    def output_off(self) -> None:
        """Disable the output."""
        self.write("OUTP OFF")

    def get_output_state(self) -> bool:
        """
        Query the output state.

        Returns:
            bool: True if output is on, False otherwise
        """
        response = self.query("OUTP?")
        return response == "1" or response.upper() == "ON"

    def get_voltage(self) -> float:
        """
        Query the current source voltage setting.

        Returns:
            float: Source voltage in Volts
        """
        response = self.query("SOUR:VOLT?")
        return float(response)

    def get_identification(self) -> str:
        """
        Get device identification string.

        Returns:
            str: Device identification (manufacturer, model, serial, firmware)
        """
        return self.query("*IDN?")

    def configure_for_jv_measurement(
        self,
        voltage_range: float = 2,
        current_range: float = 10,
        current_limit: float = 1,
        remote_sensing: bool = True,
    ) -> None:
        """
        Configure device for J-V characterization measurement.

        This is a convenience method that sets up all necessary parameters
        for a typical solar cell J-V measurement.

        Args:
            voltage_range: Voltage source range in Volts
            current_range: Current measurement range in mA
            current_limit: Current compliance limit in Amps
            remote_sensing: Enable 4-wire sensing
        """
        self.reset()
        self.configure_current_measurement(current_range, remote_sensing)
        self.configure_voltage_source(voltage_range, current_limit)
        self.output_on()

    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect()
