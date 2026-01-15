"""
J-V Stability Test Model

This module provides the model for voltage stability testing.
It runs current measurements at a fixed voltage over time,
providing real-time updates via callbacks (similar to EQE StabilityTestModel pattern).
"""

import time
import threading
import numpy as np
from typing import List, Optional, Callable
import logging

from ..controllers.keithley_2450 import Keithley2450Controller
from ..config.settings import JV_STABILITY_TEST_CONFIG
from common.utils import get_logger

_logger = get_logger("jv")


class JVStabilityTestModel:
    """
    Model for voltage stability testing.

    Runs current measurements at a fixed voltage over time,
    providing real-time updates via callbacks (not Qt signals).

    Test flow:
    1. Start at typical voltage (sweep_start_voltage)
    2. Sweep to target voltage
    3. Take repeated measurements at target voltage
    """

    def __init__(self,
                 controller: Keithley2450Controller,
                 config: Optional[dict] = None,
                 logger: Optional[logging.Logger] = None):
        """
        Initialize the stability test model.

        Args:
            controller: Keithley 2450 controller
            config: Optional configuration override
            logger: Logger instance
        """
        self.controller = controller
        self.config = config or JV_STABILITY_TEST_CONFIG.copy()
        self.logger = logger or _logger

        # Test state
        self._is_running = False
        self._stop_requested = False
        self._test_thread: Optional[threading.Thread] = None

        # Test data
        self.timestamps: List[float] = []
        self.voltages: List[float] = []
        self.currents: List[float] = []
        self.pixel_number: int = 0

        # Callbacks for updates
        self.measurement_callback: Optional[Callable[[float, float, float], None]] = None  # (timestamp, voltage, current)
        self.completion_callback: Optional[Callable[[bool], None]] = None  # (success)
        self.error_callback: Optional[Callable[[str], None]] = None  # (error_message)
        self.status_callback: Optional[Callable[[str], None]] = None  # (status_message)

    def is_running(self) -> bool:
        """Check if a test is currently running."""
        return self._is_running

    def set_measurement_callback(self, callback: Callable[[float, float, float], None]) -> None:
        """Set callback for measurement updates (timestamp, voltage, current)."""
        self.measurement_callback = callback

    def set_completion_callback(self, callback: Callable[[bool], None]) -> None:
        """Set callback for test completion (success)."""
        self.completion_callback = callback

    def set_error_callback(self, callback: Callable[[str], None]) -> None:
        """Set callback for errors (error_message)."""
        self.error_callback = callback

    def set_status_callback(self, callback: Callable[[str], None]) -> None:
        """Set callback for status updates (status_message)."""
        self.status_callback = callback

    def start_test(self, target_voltage: float, duration_min: float,
                   interval_sec: float, pixel_number: int = 1) -> None:
        """
        Start a voltage stability test.

        Args:
            target_voltage: Target voltage to test at (V)
            duration_min: Test duration in minutes
            interval_sec: Interval between measurements in seconds
            pixel_number: Pixel number (for documentation)
        """
        if self._is_running:
            if self.error_callback:
                self.error_callback("Test already running")
            return

        if not self.controller or not self.controller.is_connected():
            if self.error_callback:
                self.error_callback("Keithley 2450 not connected")
            return

        self._is_running = True
        self._stop_requested = False
        self.pixel_number = pixel_number

        # Clear previous data
        self.timestamps.clear()
        self.voltages.clear()
        self.currents.clear()

        # Start test in background thread
        self._test_thread = threading.Thread(
            target=self._run_stability_test,
            args=(target_voltage, duration_min, interval_sec),
            daemon=True
        )
        self._test_thread.start()

    def stop_test(self) -> None:
        """Stop the current test."""
        if self._is_running:
            self._stop_requested = True
            if self.status_callback:
                self.status_callback("Stopping test...")

    def _run_stability_test(self, target_voltage: float, duration_min: float,
                           interval_sec: float) -> None:
        """
        Run voltage stability test (worker function).

        Test flow:
        1. Start at typical voltage (e.g., -0.2V)
        2. Sweep to target voltage
        3. Take repeated measurements at target voltage

        Args:
            target_voltage: Target voltage in V
            duration_min: Duration in minutes
            interval_sec: Interval in seconds
        """
        timestamps = []
        voltages = []
        currents = []

        try:
            # Configure device for stability testing
            if self.status_callback:
                self.status_callback("Configuring device...")

            self.controller.configure_for_jv_measurement(
                voltage_range=self.config.get("voltage_range", 2),
                current_range=self.config.get("current_range", 10),
                current_limit=self.config.get("current_compliance", 1),
                remote_sensing=self.config.get("remote_sensing", True),
                nplc=self.config.get("nplc", 1.0),
                averaging_count=self.config.get("averaging_count", 1),
                averaging_filter=self.config.get("averaging_filter", "REPEAT"),
                source_delay_s=self.config.get("source_delay_s", 0.05),
            )

            # Step 1: Start at typical voltage
            start_voltage = self.config.get("sweep_start_voltage", -0.2)
            if self.status_callback:
                self.status_callback(f"Setting initial voltage to {start_voltage}V...")

            self.controller.set_voltage(start_voltage)
            time.sleep(self.config.get("initial_stabilization_s", 2.0))

            if self._stop_requested:
                return

            # Step 2: Sweep to target voltage
            if self.status_callback:
                self.status_callback(f"Sweeping to target voltage {target_voltage}V...")

            sweep_step = self.config.get("sweep_step_voltage", 0.05)
            sweep_voltages = self._generate_sweep_array(start_voltage, target_voltage, sweep_step)

            for v in sweep_voltages:
                if self._stop_requested:
                    return
                self.controller.set_voltage(float(v))
                time.sleep(self.config.get("sweep_delay_s", 0.1))

            # Final voltage settling
            time.sleep(self.config.get("target_stabilization_s", 2.0))

            if self._stop_requested:
                return

            # Step 3: Start stability measurements at target voltage
            start_time = time.time()
            end_time = start_time + (duration_min * 60)
            measurement_count = 0

            if self.status_callback:
                self.status_callback(f"Running stability test at {target_voltage}V...")

            while time.time() < end_time and not self._stop_requested:
                current_time = time.time() - start_time

                # Read current using configured averaging
                num_measurements = self.config.get("num_measurements", 5)
                current_readings_A = self.controller.measure_current_multiple(num_measurements)

                # Convert to mA and calculate mean
                current_readings_mA = [reading * 1e3 for reading in current_readings_A]
                mean_current_mA = float(np.mean(current_readings_mA))

                # Store data
                timestamps.append(current_time)
                voltages.append(target_voltage)
                currents.append(mean_current_mA)
                measurement_count += 1

                # Call measurement callback
                if self.measurement_callback:
                    try:
                        self.measurement_callback(current_time, target_voltage, mean_current_mA)
                    except Exception as e:
                        self.logger.warning(f"Measurement callback error: {e}")

                # Wait for next measurement
                time.sleep(interval_sec)

            # Store results
            self.timestamps = timestamps
            self.voltages = voltages
            self.currents = currents

            # Call completion callback
            success = not self._stop_requested
            if self.status_callback:
                if success:
                    self.status_callback(f"Test complete ({measurement_count} measurements)")
                else:
                    self.status_callback(f"Test stopped ({measurement_count} measurements)")

            if self.completion_callback:
                try:
                    self.completion_callback(success)
                except Exception as e:
                    self.logger.warning(f"Completion callback error: {e}")

        except Exception as e:
            self.logger.error(f"Stability test error: {e}", exc_info=True)
            if self.error_callback:
                try:
                    self.error_callback(f"Test failed: {str(e)}")
                except:
                    pass

        finally:
            # Turn off output
            try:
                self.controller.output_off()
            except:
                pass

            self._is_running = False

    def _generate_sweep_array(self, start: float, stop: float, step: float) -> np.ndarray:
        """
        Generate voltage sweep array from start to stop.

        Args:
            start: Starting voltage (V)
            stop: Stopping voltage (V)
            step: Step size (V)

        Returns:
            Array of voltages
        """
        if abs(stop - start) < abs(step):
            return np.array([stop])

        direction = 1 if stop > start else -1
        step_signed = abs(step) * direction

        # Generate array with half-step tolerance
        voltages = np.arange(start, stop + (step_signed / 2), step_signed)
        return np.round(voltages, decimals=2)

    @staticmethod
    def calculate_statistics(values: List[float]) -> dict:
        """
        Calculate statistics for a list of values.

        Args:
            values: List of measurement values

        Returns:
            dict: Statistics including mean, std, cv, min, max, range
        """
        if not values:
            return {
                'mean': 0.0,
                'std': 0.0,
                'cv_percent': 0.0,
                'min': 0.0,
                'max': 0.0,
                'range': 0.0,
                'count': 0
            }

        values_array = np.array(values)
        mean = np.mean(values_array)
        std = np.std(values_array, ddof=1) if len(values) > 1 else 0.0
        cv_percent = (std / abs(mean) * 100) if mean != 0 else 0.0

        return {
            'mean': float(mean),
            'std': float(std),
            'cv_percent': float(cv_percent),
            'min': float(np.min(values_array)),
            'max': float(np.max(values_array)),
            'range': float(np.max(values_array) - np.min(values_array)),
            'count': len(values)
        }
