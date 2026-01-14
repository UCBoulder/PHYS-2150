"""
JV Measurement Model

This model defines the measurement strategy for J-V characterization.
It handles voltage sweep generation and point-by-point data acquisition.

Design Notes:
- This model implements the current measurement approach (manual point-by-point)
- It's designed to be replaceable with alternative strategies (e.g., Keithley built-in sweeps)
- Parameters come from config, not hardcoded values
- Perovskite hysteresis concerns: forward/reverse sweeps are scientifically meaningful
"""

import time
import threading
import numpy as np
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, Callable, List, Tuple, Dict, Any
from dataclasses import dataclass, field

from ..controllers.keithley_2450 import Keithley2450Controller, Keithley2450Error
from ..config.settings import JV_MEASUREMENT_CONFIG
from common.utils import get_logger, get_error

# Module-level logger for J-V measurement
_logger = get_logger("jv")


class JVMeasurementError(Exception):
    """Exception raised for JV measurement specific errors."""
    pass


@dataclass
class SweepData:
    """Container for sweep measurement data."""
    voltages: List[float] = field(default_factory=list)
    currents: List[float] = field(default_factory=list)
    direction: str = "forward"  # "forward" or "reverse"

    def clear(self) -> None:
        """Clear all data."""
        self.voltages.clear()
        self.currents.clear()

    def add_point(self, voltage: float, current: float) -> None:
        """Add a measurement point."""
        self.voltages.append(voltage)
        self.currents.append(current)

    def __len__(self) -> int:
        return len(self.voltages)


@dataclass
class JVMeasurementResult:
    """Complete J-V measurement result with forward and reverse sweeps."""
    forward: SweepData = field(default_factory=lambda: SweepData(direction="forward"))
    reverse: SweepData = field(default_factory=lambda: SweepData(direction="reverse"))
    pixel_number: int = 0
    measurement_complete: bool = False

    def clear(self) -> None:
        """Clear all measurement data."""
        self.forward.clear()
        self.reverse.clear()
        self.pixel_number = 0
        self.measurement_complete = False


class JVMeasurementModel:
    """
    Model for J-V measurement sweep logic.

    This model handles the actual measurement strategy - how voltage sweeps
    are performed and data is collected. It uses the Keithley controller
    for device communication but contains all the sweep logic.
    """

    def __init__(
        self,
        controller: Keithley2450Controller,
        config: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize the measurement model.

        Args:
            controller: Keithley 2450 controller for device communication
            config: Optional configuration override (uses JV_MEASUREMENT_CONFIG by default)
        """
        self.controller = controller
        self.config = config or JV_MEASUREMENT_CONFIG.copy()

        # Measurement state
        self._is_measuring = False
        self._stop_requested = threading.Event()
        self._measurement_thread: Optional[threading.Thread] = None

        # Results
        self.result = JVMeasurementResult()

        # Callbacks
        self._progress_callback: Optional[Callable] = None
        self._completion_callback: Optional[Callable] = None
        self._point_callback: Optional[Callable] = None

    def set_progress_callback(
        self,
        callback: Callable[[str, int, int, float, float], None]
    ) -> None:
        """
        Set callback for measurement progress.

        Args:
            callback: Function(direction, current_point, total_points, voltage, current)
        """
        self._progress_callback = callback

    def set_completion_callback(
        self,
        callback: Callable[[bool, JVMeasurementResult], None]
    ) -> None:
        """
        Set callback for measurement completion.

        Args:
            callback: Function(success, result)
        """
        self._completion_callback = callback

    def set_point_callback(
        self,
        callback: Callable[[str, float, float], None]
    ) -> None:
        """
        Set callback for each measurement point (for real-time plotting).

        Args:
            callback: Function(direction, voltage, current)
        """
        self._point_callback = callback

    def is_measuring(self) -> bool:
        """Check if measurement is in progress."""
        return self._is_measuring

    def generate_voltage_array(
        self,
        start: float,
        stop: float,
        step: float,
    ) -> np.ndarray:
        """
        Generate voltage array for sweep, ensuring stop voltage is inclusive.

        Args:
            start: Start voltage in Volts
            stop: Stop voltage in Volts
            step: Step size in Volts

        Returns:
            np.ndarray: Array of voltage points
        """
        # Ensure stop_voltage is inclusive
        total_range = stop - start
        steps_needed = total_range / step
        if not float(steps_needed).is_integer():
            # Adjust stop to include it in the sweep
            stop += (step - (total_range % step))

        # Generate array with half-step tolerance for endpoint inclusion
        voltages = np.arange(start, stop + (step / 2), step)
        decimals = JV_MEASUREMENT_CONFIG.get("voltage_decimals", 2)
        return np.round(voltages, decimals=decimals)

    def start_measurement(
        self,
        start_voltage: float,
        stop_voltage: float,
        step_voltage: float,
        pixel_number: int,
    ) -> bool:
        """
        Start J-V measurement in a background thread.

        Args:
            start_voltage: Start voltage in Volts
            stop_voltage: Stop voltage in Volts
            step_voltage: Step size in Volts
            pixel_number: Pixel being measured

        Returns:
            bool: True if measurement started successfully
        """
        if self._is_measuring:
            return False

        # Clear previous results
        self.result.clear()
        self.result.pixel_number = pixel_number

        # Clear stop flag
        self._stop_requested.clear()
        self._is_measuring = True

        # Start measurement thread
        self._measurement_thread = threading.Thread(
            target=self._measurement_worker,
            args=(start_voltage, stop_voltage, step_voltage),
            daemon=True,
        )
        self._measurement_thread.start()

        return True

    def stop_measurement(self) -> None:
        """Request measurement to stop."""
        self._stop_requested.set()

    def wait_for_completion(self, timeout: Optional[float] = None) -> bool:
        """
        Wait for measurement to complete.

        Args:
            timeout: Maximum time to wait in seconds

        Returns:
            bool: True if measurement completed, False if timeout
        """
        if self._measurement_thread:
            self._measurement_thread.join(timeout=timeout)
            return not self._measurement_thread.is_alive()
        return True

    def _measurement_worker(
        self,
        start_voltage: float,
        stop_voltage: float,
        step_voltage: float,
    ) -> None:
        """
        Worker thread for performing measurement.

        Performs forward sweep (start -> stop) then reverse sweep (stop -> start).
        """
        success = False
        try:
            # Generate voltage arrays
            forward_voltages = self.generate_voltage_array(
                start_voltage, stop_voltage, step_voltage
            )
            reverse_voltages = self.generate_voltage_array(
                stop_voltage, start_voltage, -step_voltage
            )

            # Configure device for measurement
            self.controller.configure_for_jv_measurement(
                voltage_range=self.config.get("voltage_range", 2),
                current_range=self.config.get("current_range", 10),
                current_limit=self.config.get("current_compliance", 1),
                remote_sensing=self.config.get("remote_sensing", True),
            )

            # Initial stabilization at start voltage
            self.controller.set_voltage(start_voltage)
            time.sleep(self.config.get("initial_stabilization_s", 2.0))

            # Check for stop before starting
            if self._stop_requested.is_set():
                return

            # Forward sweep
            if not self._perform_sweep(
                forward_voltages, "forward", len(forward_voltages) + len(reverse_voltages)
            ):
                return

            # Inter-sweep delay
            time.sleep(self.config.get("inter_sweep_delay_s", 2.0))

            # Check for stop before reverse sweep
            if self._stop_requested.is_set():
                return

            # Reverse sweep
            offset = len(forward_voltages)
            if not self._perform_sweep(
                reverse_voltages, "reverse",
                len(forward_voltages) + len(reverse_voltages),
                point_offset=offset
            ):
                return

            self.result.measurement_complete = True
            success = True

        except Keithley2450Error as e:
            error = get_error("measurement_error", "jv")
            if error:
                _logger.student_error(error.title, error.message, error.causes, error.actions)
            _logger.error(f"Keithley error: {e}")
        except Exception as e:
            _logger.error(f"Unexpected error during measurement: {e}")
        finally:
            # Turn off output
            try:
                self.controller.output_off()
            except Exception:
                pass

            self._is_measuring = False

            # Notify completion
            if self._completion_callback:
                self._completion_callback(success, self.result)

    def _perform_sweep(
        self,
        voltages: np.ndarray,
        direction: str,
        total_points: int,
        point_offset: int = 0,
    ) -> bool:
        """
        Perform a single voltage sweep.

        Args:
            voltages: Array of voltage points
            direction: "forward" or "reverse"
            total_points: Total points in complete measurement (for progress)
            point_offset: Offset for progress calculation

        Returns:
            bool: True if sweep completed, False if stopped or error
        """
        sweep_data = self.result.forward if direction == "forward" else self.result.reverse
        dwell_time_s = self.config.get("dwell_time_ms", 500) / 1000.0
        update_interval = self.config.get("plot_update_interval", 10)

        for i, voltage in enumerate(voltages):
            # Check for stop request
            if self._stop_requested.is_set():
                return False

            try:
                # Set voltage and wait for stabilization
                self.controller.set_voltage(float(voltage))
                time.sleep(dwell_time_s)

                # Measure current with high precision
                current_reading = self.controller.measure_current_precise()

                # Convert to mA with proper rounding
                precision = JV_MEASUREMENT_CONFIG.get("current_precision", "0.00001")
                current_mA = (current_reading * Decimal(10**3)).quantize(
                    Decimal(precision), rounding=ROUND_HALF_UP
                )
                current_mA = float(current_mA)

                # Store data
                sweep_data.add_point(float(voltage), current_mA)

                # Notify point callback (for real-time plotting)
                if self._point_callback:
                    self._point_callback(direction, float(voltage), current_mA)

                # Notify progress periodically
                if self._progress_callback and (i % update_interval == 0 or i == len(voltages) - 1):
                    self._progress_callback(
                        direction,
                        point_offset + i + 1,
                        total_points,
                        float(voltage),
                        current_mA,
                    )

            except Keithley2450Error as e:
                _logger.warning(f"Error during {direction} sweep at {voltage}V: {e}")
                return False

        return True

    def get_measurement_data(self) -> JVMeasurementResult:
        """Get the current measurement result."""
        return self.result
