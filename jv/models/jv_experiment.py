"""
JV Experiment Model

This model coordinates the complete J-V measurement experiment. It manages
device lifecycle, measurement parameters, and provides a stable interface
for the View layer.

The experiment model:
- Initializes and manages the device controller
- Maintains measurement parameters
- Delegates measurement execution to JVMeasurementModel
- Provides callbacks/signals for GUI updates
- Handles data saving
"""

import pyvisa as visa
from typing import Optional, Dict, Any, Callable
from PySide6.QtCore import QObject, Signal

from ..controllers.keithley_2450 import Keithley2450Controller, Keithley2450Error
from ..models.jv_measurement import JVMeasurementModel, JVMeasurementResult
from ..config.settings import (
    DEFAULT_MEASUREMENT_PARAMS,
    JV_MEASUREMENT_CONFIG,
    VALIDATION_PATTERNS,
    ERROR_MESSAGES,
)
from ..config import settings
from common.utils import get_logger
import re

# Module-level logger for J-V experiment
_logger = get_logger("jv")


class JVExperimentError(Exception):
    """Exception raised for JV experiment specific errors."""
    pass


class JVExperimentModel(QObject):
    """
    High-level model for the complete J-V measurement experiment.

    This model coordinates the device controller and measurement model,
    providing a unified interface for the experimental workflow.
    """

    # Qt Signals for thread-safe GUI updates
    device_status_changed = Signal(bool, str)  # is_connected, message
    measurement_progress = Signal(str, int, int, float, float)  # direction, current, total, V, I
    measurement_point = Signal(str, float, float)  # direction, voltage, current
    measurement_complete = Signal(bool, object)  # success, result

    def __init__(self):
        """Initialize the JV experiment model."""
        super().__init__()

        # VISA resource manager
        self._rm: Optional[visa.ResourceManager] = None

        # Device controller
        self.controller: Optional[Keithley2450Controller] = None

        # Measurement model
        self.measurement_model: Optional[JVMeasurementModel] = None

        # Experiment state
        self._device_initialized = False

        # Measurement parameters
        self.params = DEFAULT_MEASUREMENT_PARAMS.copy()

    def initialize_device(self) -> bool:
        """
        Initialize the Keithley 2450 device.

        Returns:
            bool: True if initialization successful

        Raises:
            JVExperimentError: If initialization fails
        """
        # Check for offline mode
        if settings.OFFLINE_MODE:
            self._device_initialized = True
            self.device_status_changed.emit(True, "OFFLINE MODE")
            return True

        try:
            # Create VISA resource manager
            self._rm = visa.ResourceManager()

            # Create and connect controller
            self.controller = Keithley2450Controller(self._rm)
            self.controller.connect()

            # Get device info
            device_id = self.controller.get_identification()
            address = self.controller.device_address

            # Create measurement model
            self.measurement_model = JVMeasurementModel(
                self.controller,
                JV_MEASUREMENT_CONFIG.copy(),
            )

            # Wire up callbacks
            self.measurement_model.set_progress_callback(self._on_measurement_progress)
            self.measurement_model.set_point_callback(self._on_measurement_point)
            self.measurement_model.set_completion_callback(self._on_measurement_complete)

            self._device_initialized = True
            self.device_status_changed.emit(
                True,
                f"Connected: {address}"
            )

            _logger.info(f"Keithley 2450 connected: {device_id}")
            return True

        except Keithley2450Error as e:
            self.device_status_changed.emit(False, str(e))
            raise JVExperimentError(f"Failed to initialize device: {e}")

    def is_initialized(self) -> bool:
        """Check if device is initialized."""
        return self._device_initialized

    def is_measuring(self) -> bool:
        """Check if measurement is in progress."""
        if self.measurement_model:
            return self.measurement_model.is_measuring()
        return False

    def set_parameter(self, key: str, value: Any) -> None:
        """
        Set a measurement parameter.

        Args:
            key: Parameter name
            value: Parameter value
        """
        if key in self.params:
            self.params[key] = value

    def set_parameters(self, **params) -> None:
        """
        Set multiple measurement parameters.

        Args:
            **params: Parameter key-value pairs
        """
        for key, value in params.items():
            self.set_parameter(key, value)

    def get_parameters(self) -> Dict[str, Any]:
        """Get current measurement parameters."""
        return self.params.copy()

    def validate_parameters(self) -> bool:
        """
        Validate current measurement parameters.

        Returns:
            bool: True if all parameters are valid

        Raises:
            JVExperimentError: If validation fails
        """
        # Validate cell number
        cell_number = self.params.get("cell_number", "")
        cell_pattern = VALIDATION_PATTERNS["cell_number"]
        if not cell_number or not re.match(cell_pattern, str(cell_number)):
            raise JVExperimentError(ERROR_MESSAGES["invalid_cell_number"])

        # Validate pixel number
        pixel_number = self.params.get("pixel_number", 0)
        pixel_min, pixel_max = VALIDATION_PATTERNS["pixel_range"]
        if not (pixel_min <= pixel_number <= pixel_max):
            raise JVExperimentError(
                ERROR_MESSAGES["invalid_pixel_number"].format(min=pixel_min, max=pixel_max)
            )

        # Validate voltage parameters
        start_v = self.params.get("start_voltage", 0)
        stop_v = self.params.get("stop_voltage", 0)
        step_v = self.params.get("step_voltage", 0)

        try:
            start_v = float(start_v)
            stop_v = float(stop_v)
            step_v = float(step_v)
        except (TypeError, ValueError):
            raise JVExperimentError(ERROR_MESSAGES["invalid_voltages"])

        if step_v <= 0:
            raise JVExperimentError("Step voltage must be positive.")

        # Optional: Physics-informed bounds checking
        bounds = VALIDATION_PATTERNS.get("voltage_bounds", {})
        if bounds:
            if start_v < bounds.get("min_start", -float("inf")):
                raise JVExperimentError(
                    f"Start voltage {start_v}V is below safe limit."
                )
            if stop_v > bounds.get("max_stop", float("inf")):
                raise JVExperimentError(
                    f"Stop voltage {stop_v}V exceeds safe limit."
                )

        return True

    def start_measurement(self, pixel_number: int) -> bool:
        """
        Start a J-V measurement.

        Args:
            pixel_number: Pixel number to measure (1-8)

        Returns:
            bool: True if measurement started successfully

        Raises:
            JVExperimentError: If measurement cannot start
        """
        if settings.OFFLINE_MODE:
            raise JVExperimentError("Cannot perform measurement in OFFLINE mode")

        if not self._device_initialized:
            raise JVExperimentError("Device not initialized")

        if self.is_measuring():
            raise JVExperimentError("Measurement already in progress")

        # Update pixel number in params
        self.params["pixel_number"] = pixel_number

        # Validate parameters
        self.validate_parameters()

        # Start measurement
        return self.measurement_model.start_measurement(
            start_voltage=float(self.params["start_voltage"]),
            stop_voltage=float(self.params["stop_voltage"]),
            step_voltage=float(self.params["step_voltage"]),
            pixel_number=pixel_number,
        )

    def stop_measurement(self) -> None:
        """Stop the current measurement."""
        if self.measurement_model:
            self.measurement_model.stop_measurement()

    def get_measurement_result(self) -> Optional[JVMeasurementResult]:
        """Get the current/last measurement result."""
        if self.measurement_model:
            return self.measurement_model.get_measurement_data()
        return None

    def _on_measurement_progress(
        self,
        direction: str,
        current_point: int,
        total_points: int,
        voltage: float,
        current: float,
    ) -> None:
        """Handle measurement progress update."""
        self.measurement_progress.emit(
            direction, current_point, total_points, voltage, current
        )

    def _on_measurement_point(
        self,
        direction: str,
        voltage: float,
        current: float,
    ) -> None:
        """Handle individual measurement point (for real-time plotting)."""
        self.measurement_point.emit(direction, voltage, current)

    def _on_measurement_complete(
        self,
        success: bool,
        result: JVMeasurementResult,
    ) -> None:
        """Handle measurement completion."""
        self.measurement_complete.emit(success, result)

    def cleanup(self) -> None:
        """Clean up resources and disconnect device."""
        try:
            # Stop any running measurement
            if self.measurement_model and self.measurement_model.is_measuring():
                self.measurement_model.stop_measurement()
                self.measurement_model.wait_for_completion(timeout=5)

            # Disconnect controller
            if self.controller:
                self.controller.disconnect()

            # Close VISA resource manager
            if self._rm:
                self._rm.close()

            self._device_initialized = False

        except Exception as e:
            _logger.debug(f"Cleanup error: {e}")

    def __del__(self):
        """Destructor to ensure cleanup."""
        self.cleanup()
