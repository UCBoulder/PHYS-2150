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
from ..config.settings import POWER_MEASUREMENT_CONFIG, CURRENT_MEASUREMENT_CONFIG


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
            
            # Open shutter
            self.monochromator.open_shutter()
            
            # Wait for stabilization
            if self.status_callback:
                self.status_callback("Stabilizing...")
            time.sleep(2)
            
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
                self.completion_callback(timestamps, power_values)
            
        except Exception as e:
            self.logger.error(f"Power test error: {e}", exc_info=True)
            if self.error_callback:
                self.error_callback(f"Test failed: {str(e)}")
            
            # Ensure shutter is closed
            try:
                if self.monochromator:
                    self.monochromator.close_shutter()
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
        
        try:
            # Configure monochromator
            if self.status_callback:
                self.status_callback(f"Configuring monochromator to {wavelength} nm...")
            
            confirmed_wavelength = self.monochromator.configure_for_wavelength(wavelength)
            
            if self.status_callback:
                self.status_callback(f"Monochromator at {confirmed_wavelength} nm")
            
            # Open shutter
            self.monochromator.open_shutter()
            
            # Wait for stabilization
            stabilization_time = CURRENT_MEASUREMENT_CONFIG.get("stabilization_time", 0.2)
            if self.status_callback:
                self.status_callback(f"Stabilizing ({stabilization_time}s)...")
            time.sleep(stabilization_time)
            
            # Start test
            start_time = time.time()
            end_time = start_time + (duration_min * 60)
            measurement_count = 0
            
            if self.status_callback:
                self.status_callback("Running measurements...")
            
            # Get lock-in configuration
            num_measurements = CURRENT_MEASUREMENT_CONFIG["num_measurements"]
            
            while time.time() < end_time and not self._stop_requested:
                current_time = time.time() - start_time
                
                # Read current using lock-in with configured averaging
                current_readings = []
                for _ in range(num_measurements):
                    try:
                        current = self.lockin.read_lockin_current()
                        if current is not None:
                            current_readings.append(current)
                    except Exception as e:
                        self.logger.warning(f"Lock-in read failed: {e}")
                
                if current_readings:
                    # Calculate mean and filter outliers (same as CurrentMeasurementModel)
                    mean_current = np.mean(current_readings)
                    std_current = np.std(current_readings)
                    
                    # Filter outliers (> 2 std dev)
                    filtered = [c for c in current_readings 
                               if abs(c - mean_current) <= 2 * std_current]
                    
                    if filtered:
                        final_current = np.mean(filtered)
                    else:
                        final_current = mean_current
                    
                    timestamps.append(current_time)
                    current_values.append(final_current)
                    measurement_count += 1
                    
                    # Call measurement callback
                    if self.measurement_callback:
                        self.measurement_callback(current_time, final_current)
                
                # Wait for next measurement
                time.sleep(interval_sec)
            
            # Close shutter
            self.monochromator.close_shutter()
            
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
                self.completion_callback(timestamps, current_values)
            
        except Exception as e:
            self.logger.error(f"Current test error: {e}", exc_info=True)
            if self.error_callback:
                self.error_callback(f"Test failed: {str(e)}")
            
            # Ensure shutter is closed
            try:
                if self.monochromator:
                    self.monochromator.close_shutter()
            except:
                pass
        
        finally:
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
