"""
Current Measurement Model

This model implements the logic for current measurements using the Keithley multimeter,
SR510 lock-in amplifier, and monochromator. It coordinates device operations and handles
the photocurrent measurement workflow.
"""

import time
from typing import List, Tuple, Optional, Callable
import threading

from ..controllers.keithley_2110 import Keithley2110Controller, Keithley2110Error
from ..controllers.sr510_lockin import SR510Controller, SR510Error
from ..controllers.monochromator import MonochromatorController, MonochromatorError
from ..config.settings import CURRENT_MEASUREMENT_CONFIG, MONOCHROMATOR_CORRECTION_FACTORS
from ..utils.data_handling import MeasurementDataLogger


class CurrentMeasurementError(Exception):
    """Exception raised for current measurement specific errors."""
    pass


class CurrentMeasurementModel:
    """
    Model for current measurement operations.
    
    This model implements the experiment logic for measuring photocurrent
    across a wavelength range using the Keithley multimeter, lock-in amplifier,
    and monochromator.
    """
    
    def __init__(self, keithley: Keithley2110Controller, lockin: SR510Controller,
                 monochromator: MonochromatorController,
                 logger: Optional[MeasurementDataLogger] = None):
        """
        Initialize the current measurement model.
        
        Args:
            keithley: Keithley 2110 multimeter controller
            lockin: SR510 lock-in amplifier controller
            monochromator: Monochromator controller
            logger: Optional logger for measurement progress
        """
        self.keithley = keithley
        self.lockin = lockin
        self.monochromator = monochromator
        self.logger = logger or MeasurementDataLogger()
        
        # Measurement state
        self._is_measuring = False
        self._stop_requested = False
        self._measurement_thread: Optional[threading.Thread] = None
        
        # Measurement data
        self.wavelengths: List[float] = []
        self.currents: List[float] = []
        self.pixel_number: Optional[int] = None
        
        # Callbacks for progress updates
        self.progress_callback: Optional[Callable[[float, float, float], None]] = None
        self.completion_callback: Optional[Callable[[bool], None]] = None
    
    def is_measuring(self) -> bool:
        """Check if measurement is in progress."""
        return self._is_measuring
    
    def set_progress_callback(self, callback: Callable[[float, float, float], None]) -> None:
        """
        Set callback for measurement progress updates.
        
        Args:
            callback: Function(wavelength, current, progress_percent)
        """
        self.progress_callback = callback
    
    def set_completion_callback(self, callback: Callable[[bool], None]) -> None:
        """
        Set callback for measurement completion.
        
        Args:
            callback: Function(success)
        """
        self.completion_callback = callback
    
    def get_correction_factor(self) -> float:
        """
        Get correction factor based on monochromator serial number.
        
        Returns:
            float: Correction factor
        """
        serial_number = self.monochromator.serial_number
        return MONOCHROMATOR_CORRECTION_FACTORS.get(serial_number, 1.0)
    
    def _configure_for_wavelength(self, wavelength: float) -> float:
        """
        Configure devices for specific wavelength.
        
        Args:
            wavelength: Target wavelength in nm
            
        Returns:
            float: Confirmed wavelength from monochromator
        """
        # Configure monochromator
        confirmed_wavelength = self.monochromator.configure_for_wavelength(wavelength)
        
        return confirmed_wavelength
    
    def _read_lock_in_with_keithley_check(self) -> float:
        """
        Read lock-in amplifier output with Keithley voltage monitoring.
        
        Returns:
            float: Processed current value
            
        Raises:
            CurrentMeasurementError: If measurement fails
        """
        try:
            # Check lock-in status
            while True:
                # Flush input and check status
                self.lockin.flush_input()
                status = self.lockin.get_status()
                
                if status['locked'] and status['has_reference'] and not status['overloaded']:
                    # Get sensitivity
                    sensitivity_code, sensitivity_value = self.lockin.get_sensitivity()
                    
                    # Read Keithley voltage
                    num_readings = CURRENT_MEASUREMENT_CONFIG["num_voltage_readings"]
                    average_voltage = self.keithley.measure_voltage_average(num_readings)
                    
                    # Check if voltage is too high and adjust sensitivity
                    voltage_threshold = CURRENT_MEASUREMENT_CONFIG["voltage_threshold"]
                    if average_voltage > voltage_threshold:
                        self.logger.log(f"Voltage {average_voltage:.2f}V > threshold, increasing sensitivity")
                        self.lockin.increase_sensitivity()
                        continue
                    
                    # Calculate adjusted current
                    correction_factor = self.get_correction_factor()
                    adjusted_voltage = (average_voltage * sensitivity_value / 10) / correction_factor
                    
                    # Convert to current (accounts for transimpedance amplifier gain)
                    transimpedance_gain = CURRENT_MEASUREMENT_CONFIG["transimpedance_gain"]
                    current = adjusted_voltage * transimpedance_gain
                    
                    return current
                else:
                    self.logger.log("Lock-in not ready or overloaded, retrying...")
                    time.sleep(1)
                    continue
                    
        except (Keithley2110Error, SR510Error) as e:
            raise CurrentMeasurementError(f"Failed to read current: {e}")
    
    def measure_current_at_wavelength(self, wavelength: float) -> Tuple[float, float]:
        """
        Measure current at a specific wavelength.
        
        Args:
            wavelength: Wavelength in nm
            
        Returns:
            Tuple[float, float]: (confirmed_wavelength, current)
            
        Raises:
            CurrentMeasurementError: If measurement fails
        """
        try:
            # Configure devices
            confirmed_wavelength = self._configure_for_wavelength(wavelength)
            
            # Read current with lock-in and Keithley
            current = self._read_lock_in_with_keithley_check()
            
            self.logger.log(f"Current at {confirmed_wavelength:.1f} nm: {current:.6e} A")
            
            return confirmed_wavelength, current
            
        except (CurrentMeasurementError, MonochromatorError) as e:
            raise CurrentMeasurementError(f"Failed to measure current at {wavelength} nm: {e}")
    
    def _measurement_worker(self, start_wavelength: float, end_wavelength: float,
                           step_size: float, pixel_number: int) -> None:
        """
        Worker function for measurement thread.
        
        Args:
            start_wavelength: Starting wavelength in nm
            end_wavelength: Ending wavelength in nm
            step_size: Step size in nm
            pixel_number: Pixel number being measured
        """
        try:
            self.logger.log(f"Starting current measurement for pixel {pixel_number}")
            self.wavelengths.clear()
            self.currents.clear()
            self.pixel_number = pixel_number
            
            # Prepare monochromator
            self.monochromator.open_shutter()
            
            # Set initial filter based on starting wavelength
            if start_wavelength <= 400:
                self.monochromator.set_filter(3)  # No filter
                self.logger.log("Set filter to 3 (no filter)")
            
            # Configure lock-in parameters
            self.lockin.configure_standard_parameters()
            
            # Calculate total number of measurements for progress
            total_measurements = int((end_wavelength - start_wavelength) / step_size) + 1
            measurement_count = 0
            
            current_wavelength = start_wavelength
            
            # Set initial wavelength and wait for stabilization
            self.monochromator.set_wavelength(current_wavelength)
            time.sleep(1)
            
            while current_wavelength <= end_wavelength and not self._stop_requested:
                try:
                    # Update filter if needed
                    if current_wavelength > 420 and len(self.wavelengths) == 0:
                        self.monochromator.set_filter(1)  # 400 nm filter
                        self.logger.log("Set filter to 1 (400 nm)")
                    elif current_wavelength > 800 and all(w <= 800 for w in self.wavelengths):
                        self.monochromator.set_filter(2)  # 780 nm filter
                        self.logger.log("Set filter to 2 (780 nm)")
                    
                    # Measure current
                    confirmed_wavelength, current = self.measure_current_at_wavelength(current_wavelength)
                    
                    # Store data
                    self.wavelengths.append(confirmed_wavelength)
                    self.currents.append(current)
                    
                    # Update progress
                    measurement_count += 1
                    progress_percent = (measurement_count / total_measurements) * 100
                    
                    if self.progress_callback:
                        self.progress_callback(confirmed_wavelength, current, progress_percent)
                    
                except CurrentMeasurementError as e:
                    self.logger.log(f"Error at wavelength {current_wavelength}: {e}", "ERROR")
                
                current_wavelength += step_size
            
            # Close shutter
            self.monochromator.close_shutter()
            
            success = not self._stop_requested
            if success:
                self.logger.log(f"Current measurement completed for pixel {pixel_number}")
            else:
                self.logger.log(f"Current measurement stopped for pixel {pixel_number}")
            
            if self.completion_callback:
                self.completion_callback(success)
                
        except Exception as e:
            self.logger.log(f"Current measurement failed: {e}", "ERROR")
            if self.completion_callback:
                self.completion_callback(False)
        finally:
            self._is_measuring = False
    
    def start_measurement(self, start_wavelength: float, end_wavelength: float,
                         step_size: float, pixel_number: int) -> bool:
        """
        Start current measurement in a separate thread.
        
        Args:
            start_wavelength: Starting wavelength in nm
            end_wavelength: Ending wavelength in nm
            step_size: Step size in nm
            pixel_number: Pixel number (1-6)
            
        Returns:
            bool: True if measurement started successfully
            
        Raises:
            CurrentMeasurementError: If measurement cannot be started
        """
        if self._is_measuring:
            raise CurrentMeasurementError("Measurement already in progress")
        
        if not (self.keithley.is_connected() and self.lockin.is_connected() 
                and self.monochromator.is_connected()):
            raise CurrentMeasurementError("Devices not connected")
        
        if start_wavelength >= end_wavelength:
            raise CurrentMeasurementError("Start wavelength must be less than end wavelength")
        
        if step_size <= 0:
            raise CurrentMeasurementError("Step size must be positive")
        
        if not (1 <= pixel_number <= 6):
            raise CurrentMeasurementError("Pixel number must be between 1 and 6")
        
        # Start measurement thread
        self._is_measuring = True
        self._stop_requested = False
        self._measurement_thread = threading.Thread(
            target=self._measurement_worker,
            args=(start_wavelength, end_wavelength, step_size, pixel_number)
        )
        self._measurement_thread.start()
        
        return True
    
    def stop_measurement(self) -> None:
        """Stop the current measurement."""
        if self._is_measuring:
            self._stop_requested = True
            self.logger.log("Stop requested for current measurement")
    
    def wait_for_completion(self, timeout: Optional[float] = None) -> bool:
        """
        Wait for measurement to complete.
        
        Args:
            timeout: Maximum time to wait in seconds
            
        Returns:
            bool: True if measurement completed, False if timeout
        """
        if self._measurement_thread:
            self._measurement_thread.join(timeout)
            return not self._measurement_thread.is_alive()
        return True
    
    def get_measurement_data(self) -> Tuple[List[float], List[float], Optional[int]]:
        """
        Get the current measurement data.
        
        Returns:
            Tuple[List[float], List[float], Optional[int]]: (wavelengths, currents, pixel_number)
        """
        return self.wavelengths.copy(), self.currents.copy(), self.pixel_number
    
    def clear_data(self) -> None:
        """Clear measurement data."""
        self.wavelengths.clear()
        self.currents.clear()
        self.pixel_number = None
    
    def align_monochromator(self, alignment_wavelength: float = 532.0) -> None:
        """
        Align monochromator for visual alignment.
        
        Args:
            alignment_wavelength: Wavelength for alignment in nm
        """
        try:
            self.logger.log(f"Aligning monochromator to {alignment_wavelength} nm")
            self.monochromator.set_filter(1)
            self.monochromator.set_grating(1)
            self.monochromator.set_wavelength(alignment_wavelength)
            self.monochromator.open_shutter()
        except MonochromatorError as e:
            raise CurrentMeasurementError(f"Failed to align monochromator: {e}")
    
    def get_measurement_progress(self) -> dict:
        """
        Get current measurement progress information.
        
        Returns:
            dict: Progress information
        """
        return {
            'is_measuring': self._is_measuring,
            'pixel_number': self.pixel_number,
            'num_points_collected': len(self.wavelengths),
            'current_wavelength': self.wavelengths[-1] if self.wavelengths else None,
            'latest_current': self.currents[-1] if self.currents else None
        }