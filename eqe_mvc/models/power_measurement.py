"""
Power Measurement Model

This model implements the logic for power measurements using the Thorlabs power meter
and monochromator. It coordinates device operations and handles measurement workflows.
"""

import time
from typing import List, Tuple, Optional, Callable
import threading

from ..controllers.thorlabs_power_meter import ThorlabsPowerMeterController, ThorlabsPowerMeterError
from ..controllers.monochromator import MonochromatorController, MonochromatorError
from ..config.settings import POWER_MEASUREMENT_CONFIG, MONOCHROMATOR_CORRECTION_FACTORS
from ..utils.data_handling import MeasurementDataLogger


class PowerMeasurementError(Exception):
    """Exception raised for power measurement specific errors."""
    pass


class PowerMeasurementModel:
    """
    Model for power measurement operations.
    
    This model implements the experiment logic for measuring incident light power
    across a wavelength range using the power meter and monochromator.
    """
    
    def __init__(self, power_meter: ThorlabsPowerMeterController,
                 monochromator: MonochromatorController,
                 logger: Optional[MeasurementDataLogger] = None):
        """
        Initialize the power measurement model.
        
        Args:
            power_meter: Thorlabs power meter controller
            monochromator: Monochromator controller
            logger: Optional logger for measurement progress
        """
        self.power_meter = power_meter
        self.monochromator = monochromator
        self.logger = logger or MeasurementDataLogger()
        
        # Measurement state
        self._is_measuring = False
        self._stop_requested = False
        self._measurement_thread: Optional[threading.Thread] = None
        
        # Measurement data
        self.wavelengths: List[float] = []
        self.powers: List[float] = []
        
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
            callback: Function(wavelength, power, progress_percent)
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
        
        # Set power meter wavelength for calibration
        self.power_meter.set_wavelength(confirmed_wavelength)
        
        # Allow time for stabilization
        time.sleep(POWER_MEASUREMENT_CONFIG["stabilization_time"])
        
        return confirmed_wavelength
    
    def measure_power_at_wavelength(self, wavelength: float) -> Tuple[float, float]:
        """
        Measure power at a specific wavelength.
        
        Args:
            wavelength: Wavelength in nm
            
        Returns:
            Tuple[float, float]: (confirmed_wavelength, power)
            
        Raises:
            PowerMeasurementError: If measurement fails
        """
        try:
            # Configure devices
            confirmed_wavelength = self._configure_for_wavelength(wavelength)
            
            # Take power measurement
            num_measurements = POWER_MEASUREMENT_CONFIG["num_measurements"]
            correction_factor = POWER_MEASUREMENT_CONFIG["correction_factor"]
            
            power = self.power_meter.measure_power_average(
                num_measurements=num_measurements,
                correction_factor=correction_factor
            )
            
            self.logger.log(f"Power at {confirmed_wavelength:.1f} nm: {power:.6e} W")
            
            return confirmed_wavelength, power
            
        except (ThorlabsPowerMeterError, MonochromatorError) as e:
            raise PowerMeasurementError(f"Failed to measure power at {wavelength} nm: {e}")
    
    def _measurement_worker(self, start_wavelength: float, end_wavelength: float,
                           step_size: float) -> None:
        """
        Worker function for measurement thread.
        
        Args:
            start_wavelength: Starting wavelength in nm
            end_wavelength: Ending wavelength in nm
            step_size: Step size in nm
        """
        try:
            self.logger.log("Starting power measurement")
            self.wavelengths.clear()
            self.powers.clear()
            
            # Prepare monochromator
            self.monochromator.open_shutter()
            
            # Set initial filter based on starting wavelength
            if start_wavelength <= 420:
                self.monochromator.set_filter(3)  # No filter
                self.logger.log("Set filter to 3 (no filter)")
            
            # Calculate total number of measurements for progress
            total_measurements = int((end_wavelength - start_wavelength) / step_size) + 1
            measurement_count = 0
            
            current_wavelength = start_wavelength
            while current_wavelength <= end_wavelength and not self._stop_requested:
                try:
                    # Update filter if needed
                    if current_wavelength > 420 and len(self.wavelengths) == 0:
                        self.monochromator.set_filter(1)  # 400 nm filter
                        self.logger.log("Set filter to 1 (400 nm)")
                    elif current_wavelength > 800 and all(w <= 800 for w in self.wavelengths):
                        self.monochromator.set_filter(2)  # 780 nm filter
                        self.logger.log("Set filter to 2 (780 nm)")
                    
                    # Measure power
                    confirmed_wavelength, power = self.measure_power_at_wavelength(current_wavelength)
                    
                    # Store data
                    self.wavelengths.append(confirmed_wavelength)
                    self.powers.append(power)
                    
                    # Update progress
                    measurement_count += 1
                    progress_percent = (measurement_count / total_measurements) * 100
                    
                    if self.progress_callback:
                        self.progress_callback(confirmed_wavelength, power, progress_percent)
                    
                except PowerMeasurementError as e:
                    self.logger.log(f"Error at wavelength {current_wavelength}: {e}", "ERROR")
                
                current_wavelength += step_size
            
            # Close shutter
            self.monochromator.close_shutter()
            
            success = not self._stop_requested
            if success:
                self.logger.log("Power measurement completed successfully")
            else:
                self.logger.log("Power measurement stopped by user")
            
            if self.completion_callback:
                self.completion_callback(success)
                
        except Exception as e:
            self.logger.log(f"Power measurement failed: {e}", "ERROR")
            if self.completion_callback:
                self.completion_callback(False)
        finally:
            self._is_measuring = False
    
    def start_measurement(self, start_wavelength: float, end_wavelength: float,
                         step_size: float) -> bool:
        """
        Start power measurement in a separate thread.
        
        Args:
            start_wavelength: Starting wavelength in nm
            end_wavelength: Ending wavelength in nm
            step_size: Step size in nm
            
        Returns:
            bool: True if measurement started successfully
            
        Raises:
            PowerMeasurementError: If measurement cannot be started
        """
        if self._is_measuring:
            raise PowerMeasurementError("Measurement already in progress")
        
        if not self.power_meter.is_connected() or not self.monochromator.is_connected():
            raise PowerMeasurementError("Devices not connected")
        
        if start_wavelength >= end_wavelength:
            raise PowerMeasurementError("Start wavelength must be less than end wavelength")
        
        if step_size <= 0:
            raise PowerMeasurementError("Step size must be positive")
        
        # Start measurement thread
        self._is_measuring = True
        self._stop_requested = False
        self._measurement_thread = threading.Thread(
            target=self._measurement_worker,
            args=(start_wavelength, end_wavelength, step_size)
        )
        self._measurement_thread.start()
        
        return True
    
    def stop_measurement(self) -> None:
        """Stop the current measurement."""
        if self._is_measuring:
            self._stop_requested = True
            self.logger.log("Stop requested for power measurement")
    
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
    
    def get_measurement_data(self) -> Tuple[List[float], List[float]]:
        """
        Get the current measurement data.
        
        Returns:
            Tuple[List[float], List[float]]: (wavelengths, powers)
        """
        return self.wavelengths.copy(), self.powers.copy()
    
    def clear_data(self) -> None:
        """Clear measurement data."""
        self.wavelengths.clear()
        self.powers.clear()
    
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
            raise PowerMeasurementError(f"Failed to align monochromator: {e}")
    
    def get_measurement_progress(self) -> dict:
        """
        Get current measurement progress information.
        
        Returns:
            dict: Progress information
        """
        return {
            'is_measuring': self._is_measuring,
            'num_points_collected': len(self.wavelengths),
            'current_wavelength': self.wavelengths[-1] if self.wavelengths else None,
            'latest_power': self.powers[-1] if self.powers else None
        }