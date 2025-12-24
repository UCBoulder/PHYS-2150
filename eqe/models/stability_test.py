"""
Stability Test Model

This module provides the model for stability testing of power and current measurements.
It runs measurements at a fixed wavelength over time and provides real-time updates
via callbacks (similar to CurrentMeasurementModel pattern).
"""

import time
import threading
import numpy as np
from typing import List, Tuple, Optional, Callable
import logging

from ..controllers.monochromator import MonochromatorController
from ..controllers.thorlabs_power_meter import ThorlabsPowerMeterController
from ..controllers.picoscope_lockin import PicoScopeController
from ..config.settings import POWER_MEASUREMENT_CONFIG, CURRENT_MEASUREMENT_CONFIG, STABILITY_TEST_CONFIG
from common.utils import TieredLogger


class StabilityTestModel:
    """
    Model for stability testing.
    
    Runs power or current measurements at a fixed wavelength over time,
    providing real-time updates via callbacks (not Qt signals).
    """
    
    def __init__(self, 
                 power_meter: Optional[ThorlabsPowerMeterController] = None,
                 monochromator: Optional[MonochromatorController] = None,
                 lockin: Optional[PicoScopeController] = None,
                 logger: Optional[logging.Logger] = None):
        """
        Initialize the stability test model.
        
        Args:
            power_meter: Power meter controller (required for power tests)
            monochromator: Monochromator controller (required for all tests)
            lockin: PicoScope lock-in controller (required for current tests)
            logger: Logger instance
        """
        self.power_meter = power_meter
        self.monochromator = monochromator
        self.lockin = lockin
        self.logger = logger or logging.getLogger(__name__)
        
        # Test state
        self._is_running = False
        self._stop_requested = False
        self._test_thread: Optional[threading.Thread] = None
        
        # Test data
        self.timestamps: List[float] = []
        self.values: List[float] = []
        self.test_type: Optional[str] = None
        
        # Callbacks for updates
        self.measurement_callback: Optional[Callable[[float, float], None]] = None
        self.completion_callback: Optional[Callable[[List[float], List[float]], None]] = None
        self.error_callback: Optional[Callable[[str], None]] = None
        self.status_callback: Optional[Callable[[str], None]] = None
        self.monochromator_callback: Optional[Callable[[float, bool], None]] = None  # (wavelength, shutter_open)
    
    def is_running(self) -> bool:
        """Check if a test is currently running."""
        return self._is_running
    
    def set_measurement_callback(self, callback: Callable[[float, float], None]) -> None:
        """Set callback for measurement updates (timestamp, value)."""
        self.measurement_callback = callback
    
    def set_completion_callback(self, callback: Callable[[List[float], List[float]], None]) -> None:
        """Set callback for test completion (timestamps, values)."""
        self.completion_callback = callback
    
    def set_error_callback(self, callback: Callable[[str], None]) -> None:
        """Set callback for errors (error_message)."""
        self.error_callback = callback
    
    def set_status_callback(self, callback: Callable[[str], None]) -> None:
        """Set callback for status updates (status_message)."""
        self.status_callback = callback

    def set_monochromator_callback(self, callback: Callable[[float, bool], None]) -> None:
        """Set callback for monochromator state updates (wavelength, shutter_open)."""
        self.monochromator_callback = callback
    
    def start_power_test(self, wavelength: float, duration_min: float, 
                        interval_sec: float) -> None:
        """
        Start a power stability test.
        
        Args:
            wavelength: Wavelength to test at (nm)
            duration_min: Test duration in minutes
            interval_sec: Interval between measurements in seconds
        """
        if self._is_running:
            if self.error_callback:
                self.error_callback("Test already running")
            return

        if not self.power_meter or not self.monochromator:
            if self.error_callback:
                self.error_callback("Power meter or monochromator not available")
            return

        self._is_running = True
        self._stop_requested = False
        self.test_type = "power"

        # Start test in background thread
        self._test_thread = threading.Thread(
            target=self._run_power_test,
            args=(wavelength, duration_min, interval_sec),
            daemon=True
        )
        self._test_thread.start()
    
    def start_current_test(self, wavelength: float, duration_min: float,
                          interval_sec: float, pixel_number: int = 1) -> None:
        """
        Start a current stability test.

        Args:
            wavelength: Wavelength to test at (nm)
            duration_min: Test duration in minutes
            interval_sec: Interval between measurements in seconds
            pixel_number: Pixel number (for documentation)
        """
        if self._is_running:
            if self.error_callback:
                self.error_callback("Test already running")
            return

        if not self.lockin or not self.monochromator:
            if self.error_callback:
                self.error_callback("Lock-in or monochromator not available")
            return

        # Check if lock-in is actually connected
        if not self.lockin.is_connected():
            if self.error_callback:
                self.error_callback("Lock-in amplifier not connected")
            return
        
        self._is_running = True
        self._stop_requested = False
        self.test_type = "current"
        
        # Start test in background thread
        self._test_thread = threading.Thread(
            target=self._run_current_test,
            args=(wavelength, duration_min, interval_sec, pixel_number),
            daemon=True
        )
        self._test_thread.start()
    
    def stop_test(self) -> None:
        """Stop the current test."""
        if self._is_running:
            self._stop_requested = True
            if self.status_callback:
                self.status_callback("Stopping test...")
    
    def _run_power_test(self, wavelength: float, duration_min: float, interval_sec: float) -> None:
        """
        Run power stability test (worker function).

        Args:
            wavelength: Wavelength in nm
            duration_min: Duration in minutes
            interval_sec: Interval in seconds
        """
        timestamps = []
        power_values = []

        try:
            # Configure monochromator
            if self.status_callback:
                self.status_callback(f"Configuring monochromator to {wavelength} nm...")

            confirmed_wavelength = self.monochromator.configure_for_wavelength(wavelength)

            if self.status_callback:
                self.status_callback(f"Monochromator at {confirmed_wavelength} nm")

            # Set power meter wavelength for correct calibration
            self.power_meter.set_wavelength(confirmed_wavelength)

            # Notify monochromator state (wavelength set, shutter still closed)
            if self.monochromator_callback:
                try:
                    self.monochromator_callback(confirmed_wavelength, False)
                except Exception as e:
                    self.logger.warning(f"Monochromator callback error: {e}")

            # Open shutter
            self.monochromator.open_shutter()

            # Notify shutter opened
            if self.monochromator_callback:
                try:
                    self.monochromator_callback(confirmed_wavelength, True)
                except Exception as e:
                    self.logger.warning(f"Monochromator callback error: {e}")

            # Wait for stabilization
            if self.status_callback:
                self.status_callback("Stabilizing...")
            stabilization_time = STABILITY_TEST_CONFIG["initial_stabilization_time"]
            time.sleep(stabilization_time)
            
            # Start test
            start_time = time.time()
            end_time = start_time + (duration_min * 60)
            measurement_count = 0
            
            if self.status_callback:
                self.status_callback("Running measurements...")
            
            while time.time() < end_time and not self._stop_requested:
                current_time = time.time() - start_time
                
                # Read power using configured averaging
                num_measurements = POWER_MEASUREMENT_CONFIG["num_measurements"]
                correction_factor = POWER_MEASUREMENT_CONFIG["correction_factor"]
                
                power = self.power_meter.measure_power_average(
                    num_measurements=num_measurements,
                    correction_factor=correction_factor
                )
                
                timestamps.append(current_time)
                power_values.append(power)
                measurement_count += 1
                
                # Call measurement callback
                if self.measurement_callback:
                    self.measurement_callback(current_time, power)
                
                # Wait for next measurement
                time.sleep(interval_sec)
            
            # Close shutter
            self.monochromator.close_shutter()

            # Notify shutter closed
            if self.monochromator_callback:
                try:
                    self.monochromator_callback(confirmed_wavelength, False)
                except Exception as e:
                    self.logger.warning(f"Monochromator callback error: {e}")

            # Store results
            self.timestamps = timestamps
            self.values = power_values

            # Call completion callback
            success = not self._stop_requested
            if self.status_callback:
                if success:
                    self.status_callback(f"Test complete ({measurement_count} measurements)")
                else:
                    self.status_callback(f"Test stopped ({measurement_count} measurements)")

            if self.completion_callback:
                try:
                    self.completion_callback(timestamps, power_values)
                except Exception as e:
                    self.logger.warning(f"Completion callback error: {e}")

        except Exception as e:
            self.logger.error(f"Power test error: {e}", exc_info=True)
            if self.error_callback:
                try:
                    self.error_callback(f"Test failed: {str(e)}")
                except:
                    pass

            # Ensure shutter is closed
            try:
                if self.monochromator:
                    self.monochromator.close_shutter()
                    if self.monochromator_callback:
                        self.monochromator_callback(wavelength, False)
            except:
                pass

        finally:
            self._is_running = False

    def _run_current_test(self, wavelength: float, duration_min: float, 
                         interval_sec: float, pixel_number: int) -> None:
        """
        Run current stability test (worker function).
        
        Args:
            wavelength: Wavelength in nm
            duration_min: Duration in minutes
            interval_sec: Interval in seconds
            pixel_number: Pixel number
        """
        timestamps = []
        current_values = []

        TieredLogger.debug_output(f"[STAB] Starting CURRENT stability test: {wavelength}nm, {duration_min}min, {interval_sec}s interval")

        try:
            # Configure monochromator
            TieredLogger.debug_output(f"[STAB] Configuring monochromator...")
            if self.status_callback:
                self.status_callback(f"Configuring monochromator to {wavelength} nm...")

            confirmed_wavelength = self.monochromator.configure_for_wavelength(wavelength)
            TieredLogger.debug_output(f"[STAB] Monochromator configured to {confirmed_wavelength} nm")

            if self.status_callback:
                self.status_callback(f"Monochromator at {confirmed_wavelength} nm")

            # Notify monochromator state (wavelength set, shutter still closed)
            if self.monochromator_callback:
                TieredLogger.debug_output(f"[STAB] Calling monochromator callback (shutter closed)...")
                try:
                    self.monochromator_callback(confirmed_wavelength, False)
                    TieredLogger.debug_output(f"[STAB] Monochromator callback completed")
                except Exception as e:
                    self.logger.warning(f"Monochromator callback error: {e}")
                    TieredLogger.debug_output(f"[STAB] Monochromator callback FAILED: {e}")

            # Open shutter
            TieredLogger.debug_output(f"[STAB] Opening shutter...")
            self.monochromator.open_shutter()
            TieredLogger.debug_output(f"[STAB] Shutter opened")

            # Notify shutter opened
            if self.monochromator_callback:
                TieredLogger.debug_output(f"[STAB] Calling monochromator callback (shutter open)...")
                try:
                    self.monochromator_callback(confirmed_wavelength, True)
                    TieredLogger.debug_output(f"[STAB] Monochromator callback completed")
                except Exception as e:
                    self.logger.warning(f"Monochromator callback error: {e}")
                    TieredLogger.debug_output(f"[STAB] Monochromator callback FAILED: {e}")

            # Wait for stabilization
            stabilization_time = CURRENT_MEASUREMENT_CONFIG.get("stabilization_time", 0.2)
            TieredLogger.debug_output(f"[STAB] Waiting {stabilization_time}s for stabilization...")
            if self.status_callback:
                self.status_callback(f"Stabilizing ({stabilization_time}s)...")
            time.sleep(stabilization_time)
            TieredLogger.debug_output(f"[STAB] Stabilization complete")

            # Start test
            start_time = time.time()
            end_time = start_time + (duration_min * 60)
            measurement_count = 0
            TieredLogger.debug_output(f"[STAB] Test started, will run until {duration_min} minutes elapsed")

            if self.status_callback:
                self.status_callback("Running measurements...")

            # Get lock-in configuration
            num_measurements = CURRENT_MEASUREMENT_CONFIG["num_measurements"]
            TieredLogger.debug_output(f"[STAB] Will take {num_measurements} samples per measurement")
            
            while time.time() < end_time and not self._stop_requested:
                current_time = time.time() - start_time
                TieredLogger.debug_output(f"[STAB] Loop iteration {measurement_count+1}, t={current_time:.1f}s")

                # Read current using lock-in with configured averaging
                current_readings = []
                TieredLogger.debug_output(f"[STAB] Reading {num_measurements} lock-in samples...")
                for i in range(num_measurements):
                    try:
                        current = self.lockin.read_lockin_current()
                        if current is not None:
                            current_readings.append(current)
                            TieredLogger.debug_output(f"[STAB] Sample {i+1}: {current:.3e} A")
                    except Exception as e:
                        self.logger.warning(f"Lock-in read failed: {e}")
                        TieredLogger.debug_output(f"[STAB] Sample {i+1} FAILED: {e}")

                TieredLogger.debug_output(f"[STAB] Got {len(current_readings)} valid readings")

                if current_readings:
                    # Calculate mean and filter outliers (same as CurrentMeasurementModel)
                    mean_current = np.mean(current_readings)
                    std_current = np.std(current_readings)
                    TieredLogger.debug_output(f"[STAB] Mean={mean_current:.3e}, Std={std_current:.3e}")

                    # Filter outliers
                    outlier_std = STABILITY_TEST_CONFIG["outlier_rejection_std"]
                    filtered = [c for c in current_readings
                               if abs(c - mean_current) <= outlier_std * std_current]

                    if filtered:
                        final_current = np.mean(filtered)
                    else:
                        final_current = mean_current

                    timestamps.append(current_time)
                    current_values.append(final_current)
                    measurement_count += 1
                    TieredLogger.debug_output(f"[STAB] Final current: {final_current:.3e} A (measurement #{measurement_count})")

                    # Call measurement callback
                    if self.measurement_callback:
                        TieredLogger.debug_output(f"[STAB] Calling measurement callback...")
                        try:
                            self.measurement_callback(current_time, final_current)
                            TieredLogger.debug_output(f"[STAB] Callback completed successfully")
                        except Exception as cb_err:
                            self.logger.warning(f"Measurement callback error: {cb_err}")
                            TieredLogger.debug_output(f"[STAB] Callback FAILED: {cb_err}")
                else:
                    self.logger.warning("No valid current readings in this interval")
                    TieredLogger.debug_output(f"[STAB] WARNING: No valid readings!")

                # Wait for next measurement
                TieredLogger.debug_output(f"[STAB] Sleeping {interval_sec}s before next measurement...")
                time.sleep(interval_sec)
                TieredLogger.debug_output(f"[STAB] Sleep complete, continuing loop")
            
            # Close shutter
            self.monochromator.close_shutter()

            # Notify shutter closed
            if self.monochromator_callback:
                try:
                    self.monochromator_callback(confirmed_wavelength, False)
                except Exception as e:
                    self.logger.warning(f"Monochromator callback error: {e}")

            # Store results
            self.timestamps = timestamps
            self.values = current_values

            # Call completion callback
            success = not self._stop_requested
            if self.status_callback:
                if success:
                    self.status_callback(f"Test complete ({measurement_count} measurements)")
                else:
                    self.status_callback(f"Test stopped ({measurement_count} measurements)")

            if self.completion_callback:
                try:
                    self.completion_callback(timestamps, current_values)
                except Exception as e:
                    self.logger.warning(f"Completion callback error: {e}")

        except Exception as e:
            TieredLogger.debug_output(f"[STAB] EXCEPTION in current test: {type(e).__name__}: {e}")
            self.logger.error(f"Current test error: {e}", exc_info=True)
            if self.error_callback:
                try:
                    self.error_callback(f"Test failed: {str(e)}")
                except:
                    pass

            # Ensure shutter is closed
            try:
                if self.monochromator:
                    self.monochromator.close_shutter()
                    if self.monochromator_callback:
                        self.monochromator_callback(wavelength, False)
            except:
                pass

        finally:
            TieredLogger.debug_output(f"[STAB] Current test finished (finally block)")
            self._is_running = False
    
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
        std = np.std(values_array)
        cv_percent = (std / mean * 100) if mean != 0 else 0.0
        
        return {
            'mean': float(mean),
            'std': float(std),
            'cv_percent': float(cv_percent),
            'min': float(np.min(values_array)),
            'max': float(np.max(values_array)),
            'range': float(np.max(values_array) - np.min(values_array)),
            'count': len(values)
        }
