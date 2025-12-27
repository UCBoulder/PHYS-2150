"""
Current Measurement Model

This model implements the logic for current measurements using the PicoScope
software lock-in amplifier and monochromator. It coordinates device operations
and handles the photocurrent measurement workflow.
"""

import gc
import threading
import time
from typing import Callable, List, Optional, Tuple

from common.utils import get_error, get_logger

from ..config.settings import (
    CURRENT_MEASUREMENT_CONFIG,
    DATA_EXPORT_CONFIG,
    DEVICE_CONFIGS,
    PHASE_ADJUSTMENT_CONFIG,
    DeviceType,
)
from ..controllers.monochromator import MonochromatorController, MonochromatorError
from ..controllers.picoscope_lockin import PicoScopeController, PicoScopeError
from ..utils.data_handling import MeasurementDataLogger

# Module-level logger for current measurement
_logger = get_logger("eqe")


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
        self.measurement_stats: List[dict] = []  # Stats per wavelength: {std_dev, n, cv_percent}
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

    def _read_lockin_current(self, wavelength_nm: float = None, return_stats: bool = False):
        """
        Read current using PicoScope software lock-in amplifier.

        Args:
            wavelength_nm: Optional wavelength for logging context
            return_stats: If True, return (current, stats_dict); if False, return just current

        Returns:
            If return_stats=False: float - Measured current in Amps
            If return_stats=True: Tuple[float, dict] - (current, {std_dev, n, cv_percent})

        Raises:
            CurrentMeasurementError: If measurement fails
        """
        try:
            # Read current using PicoScope software lock-in with robust averaging
            # Use configured number of measurements for stability
            num_measurements = CURRENT_MEASUREMENT_CONFIG.get("num_measurements", 5)
            result = self.lockin.read_current(
                num_measurements=num_measurements,
                wavelength_nm=wavelength_nm,
                return_stats=return_stats
            )

            if result is None:
                raise CurrentMeasurementError("Failed to read current from PicoScope")

            if return_stats:
                # Result is dict: {current, std_dev, n, cv_percent}
                return result['current'], {
                    'std_dev': result['std_dev'],
                    'n': result['n'],
                    'cv_percent': result['cv_percent']
                }
            return result

        except PicoScopeError as e:
            raise CurrentMeasurementError(f"Failed to read current: {e}")

    def _validate_chopper(self) -> None:
        """
        Validate that the chopper is running before starting measurement.

        Performs a lock-in measurement and checks both frequency and amplitude
        of the reference signal to ensure the chopper is operational.

        Raises:
            CurrentMeasurementError: If chopper validation fails
        """
        self.logger.log("Validating chopper signal...")

        try:
            result = self.lockin.perform_lockin_measurement()

            if result is None:
                raise CurrentMeasurementError("Failed to perform lock-in measurement for chopper validation")

            measured_freq = result['freq']
            ref_amplitude = result['ref_amplitude']

            # Get validation thresholds from config
            config = DEVICE_CONFIGS[DeviceType.PICOSCOPE_LOCKIN]
            expected_freq = config["default_chopper_freq"]
            freq_tolerance = config["chopper_freq_tolerance"]
            min_amplitude = config["min_reference_amplitude"]

            freq_error = abs(measured_freq - expected_freq) / expected_freq
            amplitude_ok = ref_amplitude >= min_amplitude
            freq_ok = freq_error <= freq_tolerance

            if not amplitude_ok or not freq_ok:
                error = get_error("chopper_not_running", "eqe")
                if error:
                    _logger.student_error(error.title, error.message, error.causes, error.actions)

                if not amplitude_ok and not freq_ok:
                    raise CurrentMeasurementError(
                        f"No chopper signal detected: amplitude {ref_amplitude:.2f} Vpp < {min_amplitude} Vpp, "
                        f"frequency {measured_freq:.1f} Hz not near {expected_freq} Hz. Is the chopper running?"
                    )
                elif not amplitude_ok:
                    raise CurrentMeasurementError(
                        f"Reference signal too weak: {ref_amplitude:.2f} Vpp < {min_amplitude} Vpp minimum. "
                        f"Check chopper is running and reference cable is connected."
                    )
                else:
                    raise CurrentMeasurementError(
                        f"Chopper frequency mismatch: measured {measured_freq:.1f} Hz, "
                        f"expected {expected_freq} Hz. Is the chopper running?"
                    )

            self.logger.log(f"Chopper validated: {measured_freq:.1f} Hz, {ref_amplitude:.2f} Vpp")

        except PicoScopeError as e:
            raise CurrentMeasurementError(f"Failed to validate chopper: {e}")

    def measure_current_at_wavelength(self, wavelength: float, return_stats: bool = False):
        """
        Measure current at a specific wavelength.

        Args:
            wavelength: Wavelength in nm
            return_stats: If True, also return measurement statistics

        Returns:
            If return_stats=False: Tuple[float, float] - (confirmed_wavelength, current)
            If return_stats=True: Tuple[float, float, dict] - (confirmed_wavelength, current, stats)

        Raises:
            CurrentMeasurementError: If measurement fails
        """
        try:
            # Configure devices
            confirmed_wavelength = self._configure_for_wavelength(wavelength)

            # Wait for photocell to stabilize after wavelength change
            stabilization_time = CURRENT_MEASUREMENT_CONFIG.get("stabilization_time", 0.2)
            time.sleep(stabilization_time)

            # Read current using software lock-in (wavelength passed for logging context)
            if return_stats:
                current, stats = self._read_lockin_current(
                    wavelength_nm=confirmed_wavelength,
                    return_stats=True
                )
                self.logger.debug(f"Current at {confirmed_wavelength:.1f} nm: {current:.6e} A")
                return confirmed_wavelength, current, stats
            else:
                current = self._read_lockin_current(wavelength_nm=confirmed_wavelength)
                self.logger.debug(f"Current at {confirmed_wavelength:.1f} nm: {current:.6e} A")
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
            self.measurement_stats.clear()
            self.pixel_number = pixel_number

            # Check if we should collect stats for export
            collect_stats = DATA_EXPORT_CONFIG.get("include_measurement_stats", False)

            # Prepare monochromator
            self.monochromator.open_shutter()

            # Validate chopper is running before starting measurement
            # This catches common errors like chopper not turned on
            alignment_wavelength = PHASE_ADJUSTMENT_CONFIG["alignment_wavelength"]
            self.monochromator.set_wavelength(alignment_wavelength)
            stabilization_time = PHASE_ADJUSTMENT_CONFIG["stabilization_time"]
            time.sleep(stabilization_time)
            self._validate_chopper()

            # Set initial filter based on starting wavelength
            self.monochromator.set_filter_for_wavelength(start_wavelength)
            initial_filter = self.monochromator.get_filter_for_wavelength(start_wavelength)
            self.logger.debug(f"Set filter to {initial_filter}")

            # PicoScope doesn't need parameter configuration (it's software-based)

            # Calculate total number of measurements for progress
            total_measurements = int((end_wavelength - start_wavelength) / step_size) + 1
            measurement_count = 0

            current_wavelength = start_wavelength

            # Set initial wavelength and wait for stabilization
            self.monochromator.set_wavelength(current_wavelength)
            initial_stabilization = CURRENT_MEASUREMENT_CONFIG["initial_stabilization_time"]
            time.sleep(initial_stabilization)

            # Disable garbage collection during measurement loop to prevent
            # ctypes buffer crashes when switching between USB devices
            gc.disable()

            while current_wavelength <= end_wavelength and not self._stop_requested:
                try:
                    # Update filter if wavelength crossed a threshold
                    if self.monochromator.set_filter_for_wavelength(current_wavelength):
                        new_filter = self.monochromator.get_filter_for_wavelength(current_wavelength)
                        self.logger.debug(f"Set filter to {new_filter}")

                    # Measure current (with stats if enabled for export)
                    if collect_stats:
                        confirmed_wavelength, current, stats = self.measure_current_at_wavelength(
                            current_wavelength, return_stats=True
                        )
                        self.measurement_stats.append(stats)
                    else:
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

                # Small delay between measurements to let USB devices settle
                # This helps prevent crashes when switching between PicoScope and monochromator
                time.sleep(0.05)

                current_wavelength += step_size

            # Re-enable garbage collection after measurement loop
            gc.enable()

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
                alignment_wl = PHASE_ADJUSTMENT_CONFIG["alignment_wavelength"]
                self.logger.log(f"Setting monochromator to green alignment position ({alignment_wl} nm)")
                self.monochromator.align_for_measurement(alignment_wl)
            except MonochromatorError as e:
                self.logger.log(f"Warning: Failed to set alignment position: {e}", "WARNING")

        except Exception as e:
            self.logger.log(f"Current measurement failed: {e}", "ERROR")
            if self.completion_callback:
                self.completion_callback(False)
        finally:
            # Always re-enable garbage collection
            gc.enable()
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
            args=(start_wavelength, end_wavelength, step_size, pixel_number),
            daemon=True
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

    def get_measurement_data(self) -> Tuple[List[float], List[float], Optional[int], List[dict]]:
        """
        Get the current measurement data.

        Returns:
            Tuple containing:
                - wavelengths: List of wavelengths in nm
                - currents: List of currents in A
                - pixel_number: Pixel number (1-8)
                - measurement_stats: List of stat dicts {std_dev, n, cv_percent} per wavelength
        """
        return (
            self.wavelengths.copy(),
            self.currents.copy(),
            self.pixel_number,
            self.measurement_stats.copy()
        )

    def clear_data(self) -> None:
        """Clear measurement data."""
        self.wavelengths.clear()
        self.currents.clear()
        self.measurement_stats.clear()
        self.pixel_number = None

    def align_monochromator(self, alignment_wavelength: float = None) -> None:
        """
        Align monochromator for visual alignment.

        Args:
            alignment_wavelength: Wavelength for alignment in nm (defaults to config value)
        """
        try:
            if alignment_wavelength is None:
                alignment_wavelength = PHASE_ADJUSTMENT_CONFIG["alignment_wavelength"]
            self.logger.log(f"Aligning monochromator to {alignment_wavelength} nm")
            self.monochromator.align_for_measurement(alignment_wavelength)
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
