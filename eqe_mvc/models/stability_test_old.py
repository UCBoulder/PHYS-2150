"""
Stability Test Model

This module provides the model for stability testing of power and current measurements.
It runs measurements at a fixed wavelength over time and provides real-time updates
via Qt signals.
"""

import time
import numpy as np
from typing import List, Tuple, Optional
from PySide6.QtCore import QObject, Signal, QThread, Qt
import logging

from ..controllers.monochromator import MonochromatorController
from ..controllers.thorlabs_power_meter import ThorlabsPowerMeterController
from ..controllers.picoscope_lockin import PicoScopeController
from ..config.settings import POWER_MEASUREMENT_CONFIG, CURRENT_MEASUREMENT_CONFIG


class StabilityTestWorker(QObject):
    """Worker for running stability tests in a separate thread."""
    
    # Signals (note: list types can't cross threads in PySide6, so we use no-parameter signal)
    measurement_update = Signal(float, float)  # timestamp, value
    test_complete = Signal()  # completion signal (access data via get_results())
    test_error = Signal(str)  # error message
    status_update = Signal(str)  # status message
    
    def __init__(self, test_type: str, wavelength: float, duration_min: float,
                 interval_sec: float, pixel_number: int,
                 power_meter: Optional[ThorlabsPowerMeterController],
                 monochromator: Optional[MonochromatorController],
                 lockin: Optional[PicoScopeController],
                 logger: Optional[logging.Logger]):
        """
        Initialize the worker.
        
        Args:
            test_type: 'power' or 'current'
            wavelength: Wavelength in nm
            duration_min: Duration in minutes
            interval_sec: Interval in seconds
            pixel_number: Pixel number (for current tests)
            power_meter: Power meter controller
            monochromator: Monochromator controller
            lockin: Lock-in controller
            logger: Logger instance
        """
        super().__init__()
        
        # Store results for retrieval after completion
        self.result_timestamps: List[float] = []
        self.result_values: List[float] = []
        self.test_type = test_type
        self.wavelength = wavelength
        self.duration_min = duration_min
        self.interval_sec = interval_sec
        self.pixel_number = pixel_number
        self.power_meter = power_meter
        self.monochromator = monochromator
        self.lockin = lockin
        self.logger = logger or logging.getLogger(__name__)
        self._should_stop = False
    
    def stop(self):
        """Signal the worker to stop."""
        self._should_stop = True
    
    def run(self):
        """Run the stability test."""
        if self.test_type == "power":
            self._run_power_test()
        else:
            self._run_current_test()
    
    def _run_power_test(self):
        """Run power stability test."""
        timestamps = []
        power_values = []
        
        try:
            # Configure monochromator
            self.status_update.emit(f"Configuring monochromator to {self.wavelength} nm...")
            confirmed_wavelength = self.monochromator.configure_for_wavelength(self.wavelength)
            self.status_update.emit(f"Monochromator at {confirmed_wavelength} nm")
            
            # Open shutter
            self.monochromator.open_shutter()
            
            # Wait for stabilization
            self.status_update.emit("Stabilizing...")
            time.sleep(2)
            
            # Start test
            start_time = time.time()
            end_time = start_time + (self.duration_min * 60)
            measurement_count = 0
            
            self.status_update.emit("Running measurements...")
            
            while time.time() < end_time and not self._should_stop:
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
                
                # Emit update
                self.measurement_update.emit(current_time, power)
                
                # Wait for next measurement
                time.sleep(self.interval_sec)
            
            print(f"DEBUG: Loop ended, closing shutter (measurements: {measurement_count})")
            
            # Close shutter
            self.monochromator.close_shutter()
            
            print(f"DEBUG: Shutter closed, emitting completion signal")
            
            # Store results for retrieval
            self.result_timestamps = timestamps
            self.result_values = power_values
            
            # Emit completion
            if self._should_stop:
                self.status_update.emit(f"Test stopped ({measurement_count} measurements)")
            else:
                self.status_update.emit(f"Test complete ({measurement_count} measurements)")
            
            print(f"DEBUG: About to emit test_complete signal")
            self.test_complete.emit()
            print(f"DEBUG: test_complete signal emitted")
            
        except Exception as e:
            self.logger.error(f"Power test error: {e}", exc_info=True)
            self.test_error.emit(f"Test failed: {str(e)}")
            
            # Ensure shutter is closed
            try:
                if self.monochromator:
                    self.monochromator.close_shutter()
            except:
                pass
    
    def _run_current_test(self):
        """Run current stability test."""
        timestamps = []
        current_values = []
        
        try:
            # Configure monochromator
            self.status_update.emit(f"Configuring monochromator to {self.wavelength} nm...")
            confirmed_wavelength = self.monochromator.configure_for_wavelength(self.wavelength)
            self.status_update.emit(f"Monochromator at {confirmed_wavelength} nm")
            
            # Open shutter
            self.monochromator.open_shutter()
            
            # Wait for stabilization
            stabilization_time = CURRENT_MEASUREMENT_CONFIG.get("stabilization_time", 0.2)
            self.status_update.emit(f"Stabilizing ({stabilization_time}s)...")
            time.sleep(stabilization_time)
            
            # Start test
            start_time = time.time()
            end_time = start_time + (self.duration_min * 60)
            measurement_count = 0
            
            self.status_update.emit("Running measurements...")
            
            # Get lock-in configuration
            num_measurements = CURRENT_MEASUREMENT_CONFIG["num_measurements"]
            
            while time.time() < end_time and not self._should_stop:
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
                    
                    # Emit update
                    self.measurement_update.emit(current_time, final_current)
                
                # Wait for next measurement
                time.sleep(self.interval_sec)
            
            # Close shutter
            self.monochromator.close_shutter()
            
            # Store results for retrieval
            self.result_timestamps = timestamps
            self.result_values = current_values
            
            # Emit completion
            if self._should_stop:
                self.status_update.emit(f"Test stopped ({measurement_count} measurements)")
            else:
                self.status_update.emit(f"Test complete ({measurement_count} measurements)")
            
            self.test_complete.emit()
            
        except Exception as e:
            self.logger.error(f"Current test error: {e}", exc_info=True)
            self.test_error.emit(f"Test failed: {str(e)}")
            
            # Ensure shutter is closed
            try:
                if self.monochromator:
                    self.monochromator.close_shutter()
            except:
                pass


class StabilityTestModel(QObject):
    """
    Model for stability testing.
    
    Runs power or current measurements at a fixed wavelength over time,
    providing real-time updates via signals.
    """
    
    # Signals for real-time updates
    measurement_update = Signal(float, float)  # timestamp, value
    test_complete = Signal(list, list)  # timestamps, values
    test_error = Signal(str)  # error message
    status_update = Signal(str)  # status message
    
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
        super().__init__()
        
        self.power_meter = power_meter
        self.monochromator = monochromator
        self.lockin = lockin
        self.logger = logger or logging.getLogger(__name__)
        
        self._is_running = False
        self._worker: Optional[StabilityTestWorker] = None
        self._thread: Optional[QThread] = None
        
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
            self.test_error.emit("Test already running")
            return
            
        if not self.power_meter or not self.monochromator:
            self.test_error.emit("Power meter or monochromator not available")
            return
        
        self._is_running = True
        
        # Create worker and thread
        self._thread = QThread()
        self._worker = StabilityTestWorker(
            test_type="power",
            wavelength=wavelength,
            duration_min=duration_min,
            interval_sec=interval_sec,
            pixel_number=0,  # Not used for power tests
            power_meter=self.power_meter,
            monochromator=self.monochromator,
            lockin=None,
            logger=self.logger
        )
        
        # Move worker to thread
        self._worker.moveToThread(self._thread)
        
        # Connect signals - use AutoConnection for real-time updates, QueuedConnection for completion
        self._thread.started.connect(self._worker.run)
        self._worker.measurement_update.connect(self.measurement_update.emit)
        self._worker.test_complete.connect(self._on_test_complete, Qt.QueuedConnection)
        self._worker.test_error.connect(self._on_test_error, Qt.QueuedConnection)
        self._worker.status_update.connect(self.status_update.emit)
        
        # IMPORTANT: Thread must quit when worker finishes, otherwise it keeps running
        # Connect AFTER moveToThread so the quit() call goes to the correct thread
        self._worker.test_complete.connect(self._thread.quit, Qt.QueuedConnection)
        self._worker.test_error.connect(self._thread.quit, Qt.QueuedConnection)
        
        # Cleanup on completion
        self._thread.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        
        # Start thread
        self._thread.start()
    
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
            self.test_error.emit("Test already running")
            return
            
        if not self.lockin or not self.monochromator:
            self.test_error.emit("Lock-in or monochromator not available")
            return
        
        self._is_running = True
        
        # Create worker and thread
        self._thread = QThread()
        self._worker = StabilityTestWorker(
            test_type="current",
            wavelength=wavelength,
            duration_min=duration_min,
            interval_sec=interval_sec,
            pixel_number=pixel_number,
            power_meter=None,
            monochromator=self.monochromator,
            lockin=self.lockin,
            logger=self.logger
        )
        
        # Move worker to thread
        self._worker.moveToThread(self._thread)
        
        # Connect signals - use AutoConnection for real-time updates, QueuedConnection for completion
        self._thread.started.connect(self._worker.run)
        self._worker.measurement_update.connect(self.measurement_update.emit)
        self._worker.test_complete.connect(self._on_test_complete, Qt.QueuedConnection)
        self._worker.test_error.connect(self._on_test_error, Qt.QueuedConnection)
        self._worker.status_update.connect(self.status_update.emit)
        
        # IMPORTANT: Thread must quit when worker finishes, otherwise it keeps running
        # Connect AFTER moveToThread so the quit() call goes to the correct thread
        self._worker.test_complete.connect(self._thread.quit, Qt.QueuedConnection)
        self._worker.test_error.connect(self._thread.quit, Qt.QueuedConnection)
        
        # Cleanup on completion
        self._thread.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        
        # Start thread
        self._thread.start()
    
    def stop_test(self) -> None:
        """Stop the current test."""
        if self._is_running and self._worker:
            self._worker.stop()
            self.status_update.emit("Stopping test...")
    
    def _on_test_complete(self) -> None:
        """Handle test completion."""
        # Retrieve results from worker
        timestamps = self._worker.result_timestamps if self._worker else []
        values = self._worker.result_values if self._worker else []
        
        print(f"DEBUG: Model _on_test_complete called with {len(timestamps)} points")
        self._is_running = False
        print(f"DEBUG: Model emitting test_complete signal to tab")
        self.test_complete.emit(timestamps, values)
        print(f"DEBUG: Model test_complete signal emitted")
    
    def _on_test_error(self, error_message: str) -> None:
        """Handle test error."""
        self._is_running = False
        self.test_error.emit(error_message)
    
    @staticmethod
    def calculate_statistics(values: List[float]) -> dict:
        """
        Calculate statistics for measurement values.
        
        Args:
            values: List of measurement values
            
        Returns:
            Dictionary with mean, std, cv, min, max, range
        """
        if not values:
            return {}
        
        values_array = np.array(values)
        mean = np.mean(values_array)
        std = np.std(values_array)
        cv = (std / mean * 100) if mean > 0 else 0
        
        return {
            "mean": mean,
            "std": std,
            "cv": cv,
            "min": np.min(values_array),
            "max": np.max(values_array),
            "range": np.max(values_array) - np.min(values_array),
            "count": len(values)
        }
