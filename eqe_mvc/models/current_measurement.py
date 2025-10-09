"""
Current Measurement Model

This model implements the logic for current measurements using the PicoScope
software lock-in amplifier and monochromator. It coordinates device operations
and handles the photocurrent measurement workflow.
"""

import time
from typing import List, Tuple, Optional, Callable
import threading

from ..controllers.picoscope_lockin import PicoScopeController, PicoScopeError
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
    across a wavelength range using the PicoScope software lock-in amplifier
    and monochromator.
    """
    
    def __init__(self, lockin: PicoScopeController,
                 monochromator: MonochromatorController,
                 logger: Optional[MeasurementDataLogger] = None):
        """
        Initialize the current measurement model.
        
        Args:
            lockin: PicoScope software lock-in controller
            monochromator: Monochromator controller
            logger: Optional logger for measurement progress
        """
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
        
        NOTE: Previously returned 0.45 for SR510 analog lock-in harmonic loss.
        With PicoScope software lock-in, no correction needed (returns 1.0).
        Method kept for API compatibility but effectively does nothing.
        
        Returns:
            float: Correction factor (always 1.0 with PicoScope)
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
    
    def _read_lockin_current(self) -> float:
        """
        Read current using PicoScope software lock-in amplifier.
        
        Returns:
            float: Measured current in Amps
            
        Raises:
            CurrentMeasurementError: If measurement fails
        """
        try:
            # Read current using PicoScope software lock-in with robust averaging
            current = self.lockin.read_current(num_measurements=5)
            
            if current is None:
                raise CurrentMeasurementError("Failed to read current from PicoScope")
            
            return current
                    
        except PicoScopeError as e:
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
            
            # Read current using software lock-in
            current = self._read_lockin_current()
            
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
            
            # Set initial filter based on starting wavelength and track current filter
            # Filter positions: 1 = 400 nm filter, 2 = 780 nm filter, 3 = no filter
            if start_wavelength <= 420:
                current_filter = 3  # No filter
                self.monochromator.set_filter(current_filter)
                self.logger.log("Set filter to 3 (no filter)")
            elif start_wavelength <= 800:
                current_filter = 1  # 400 nm filter
                self.monochromator.set_filter(current_filter)
                self.logger.log("Set filter to 1 (400 nm)")
            else:
                current_filter = 2  # 780 nm filter
                self.monochromator.set_filter(current_filter)
                self.logger.log("Set filter to 2 (780 nm)")
            
            # PicoScope doesn't need parameter configuration (it's software-based)
            
            # Calculate total number of measurements for progress
            total_measurements = int((end_wavelength - start_wavelength) / step_size) + 1
            measurement_count = 0
            
            current_wavelength = start_wavelength
            
            # Set initial wavelength and wait for stabilization
            self.monochromator.set_wavelength(current_wavelength)
            time.sleep(1)
            
            while current_wavelength <= end_wavelength and not self._stop_requested:
                try:
                    # Update filter only when crossing thresholds
                    if current_wavelength > 420 and current_filter == 3:
                        current_filter = 1  # Switch to 400 nm filter
                        self.monochromator.set_filter(current_filter)
                        self.logger.log("Set filter to 1 (400 nm)")
                    elif current_wavelength > 800 and current_filter == 1:
                        current_filter = 2  # Switch to 780 nm filter
                        self.monochromator.set_filter(current_filter)
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
            
            # Notify completion first (triggers save dialog)
            if self.completion_callback:
                self.completion_callback(success)
            
            # Set monochromator to green alignment dot position (happens during/after save dialog)
            try:
                self.logger.log("Setting monochromator to green alignment position (532 nm)")
                self.monochromator.set_filter(1)
                self.monochromator.set_grating(1)
                self.monochromator.set_wavelength(532.0)
                self.monochromator.open_shutter()
            except MonochromatorError as e:
                self.logger.log(f"Warning: Failed to set alignment position: {e}", "WARNING")
                
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
            pixel_number: Pixel number (1-8)
            
        Returns:
            bool: True if measurement started successfully
            
        Raises:
            CurrentMeasurementError: If measurement cannot be started
        """
        if self._is_measuring:
            raise CurrentMeasurementError("Measurement already in progress")
        
        if not (self.lockin.is_connected() and self.monochromator.is_connected()):
            raise CurrentMeasurementError("Devices not connected")
        
        if start_wavelength >= end_wavelength:
            raise CurrentMeasurementError("Start wavelength must be less than end wavelength")
        
        if step_size <= 0:
            raise CurrentMeasurementError("Step size must be positive")
        
        if not (1 <= pixel_number <= 8):
            raise CurrentMeasurementError("Pixel number must be between 1 and 8")
        
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