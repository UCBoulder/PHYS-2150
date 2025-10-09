"""
EQE Experiment Model

This model coordinates the complete EQE measurement experiment, managing all devices
and measurement models. It represents the highest level of experiment logic.
"""

import pyvisa as visa
from typing import Optional, Dict, Any, Callable, Tuple, List
import threading
from contextlib import contextmanager

from ..controllers.thorlabs_power_meter import ThorlabsPowerMeterController, ThorlabsPowerMeterError
from ..controllers.monochromator import MonochromatorController, MonochromatorError
from ..controllers.picoscope_lockin import PicoScopeController, PicoScopeError
from ..models.power_measurement import PowerMeasurementModel, PowerMeasurementError
from ..models.current_measurement import CurrentMeasurementModel, CurrentMeasurementError
from ..models.phase_adjustment import PhaseAdjustmentModel, PhaseAdjustmentError
from ..config.settings import DEFAULT_MEASUREMENT_PARAMS, DEVICE_CONFIGS, DeviceType
from ..utils.data_handling import DataHandler, MeasurementDataLogger, DataValidationError


class EQEExperimentError(Exception):
    """Exception raised for EQE experiment specific errors."""
    pass


class EQEExperimentModel:
    """
    High-level model for the complete EQE measurement experiment.
    
    This model coordinates all devices and measurement operations, providing
    a unified interface for the complete experimental workflow.
    """
    
    def __init__(self, logger: Optional[MeasurementDataLogger] = None):
        """
        Initialize the EQE experiment model.
        
        Args:
            logger: Optional logger for experiment progress
        """
        self.logger = logger or MeasurementDataLogger()
        
        # VISA resource manager
        self._rm: Optional[visa.ResourceManager] = None
        
        # Device controllers
        self.power_meter: Optional[ThorlabsPowerMeterController] = None
        self.monochromator: Optional[MonochromatorController] = None
        self.lockin: Optional[PicoScopeController] = None
        
        # Measurement models
        self.power_model: Optional[PowerMeasurementModel] = None
        self.current_model: Optional[CurrentMeasurementModel] = None
        self.phase_model: Optional[PhaseAdjustmentModel] = None
        
        # Data handler
        self.data_handler = DataHandler()
        
        # Experiment state
        self._devices_initialized = False
        self._experiment_running = False
        
        # Experiment parameters
        self.measurement_params = DEFAULT_MEASUREMENT_PARAMS.copy()
        
        # Callbacks
        self.device_status_callback: Optional[Callable[[str, bool, str], None]] = None
        self.measurement_progress_callback: Optional[Callable[[str, Dict], None]] = None
        self.experiment_complete_callback: Optional[Callable[[bool, str], None]] = None
    
    def set_device_status_callback(self, callback: Callable[[str, bool, str], None]) -> None:
        """
        Set callback for device status updates.
        
        Args:
            callback: Function(device_name, is_connected, message)
        """
        self.device_status_callback = callback
    
    def set_measurement_progress_callback(self, callback: Callable[[str, Dict], None]) -> None:
        """
        Set callback for measurement progress updates.
        
        Args:
            callback: Function(measurement_type, progress_data)
        """
        self.measurement_progress_callback = callback
    
    def set_experiment_complete_callback(self, callback: Callable[[bool, str], None]) -> None:
        """
        Set callback for experiment completion.
        
        Args:
            callback: Function(success, message)
        """
        self.experiment_complete_callback = callback
    
    def _notify_device_status(self, device_name: str, is_connected: bool, message: str = "") -> None:
        """Notify device status change."""
        if self.device_status_callback:
            self.device_status_callback(device_name, is_connected, message)
    
    def _notify_measurement_progress(self, measurement_type: str, progress_data: Dict) -> None:
        """Notify measurement progress."""
        if self.measurement_progress_callback:
            self.measurement_progress_callback(measurement_type, progress_data)
    
    def _notify_experiment_complete(self, success: bool, message: str) -> None:
        """Notify experiment completion."""
        if self.experiment_complete_callback:
            self.experiment_complete_callback(success, message)
    
    def initialize_devices(self) -> bool:
        """
        Initialize all devices and create measurement models.
        
        Returns:
            bool: True if all devices initialized successfully
            
        Raises:
            EQEExperimentError: If device initialization fails
        """
        try:
            self.logger.log("Initializing devices...")
            
            # Initialize VISA resource manager
            self._rm = visa.ResourceManager()
            
            # Initialize device controllers
            self._initialize_power_meter()
            self._initialize_monochromator()
            self._initialize_lockin()
            
            # Create measurement models
            self._create_measurement_models()
            
            self._devices_initialized = True
            self.logger.log("All devices initialized successfully")
            return True
            
        except Exception as e:
            self.logger.log(f"Device initialization failed: {e}", "ERROR")
            raise EQEExperimentError(f"Failed to initialize devices: {e}")
    
    def _initialize_power_meter(self) -> None:
        """Initialize Thorlabs power meter."""
        try:
            self.power_meter = ThorlabsPowerMeterController()
            self.power_meter.connect()
            self._notify_device_status("Thorlabs Power Meter", True, "Connected")
            self.logger.log("Thorlabs power meter initialized")
        except ThorlabsPowerMeterError as e:
            self._notify_device_status("Thorlabs Power Meter", False, str(e))
            raise EQEExperimentError(f"Failed to initialize power meter: {e}")
    

    
    def _initialize_monochromator(self) -> None:
        """Initialize monochromator."""
        try:
            config = DEVICE_CONFIGS[DeviceType.MONOCHROMATOR]
            self.monochromator = MonochromatorController(self._rm)
            self.monochromator.connect(
                interface=config["interface"],
                timeout_msec=config["timeout_msec"]
            )
            serial_number = self.monochromator.serial_number
            self._notify_device_status("Monochromator", True, f"Connected (S/N: {serial_number})")
            self.logger.log(f"Monochromator initialized (S/N: {serial_number})")
        except MonochromatorError as e:
            self._notify_device_status("Monochromator", False, str(e))
            raise EQEExperimentError(f"Failed to initialize monochromator: {e}")
    
    def _initialize_lockin(self) -> None:
        """Initialize PicoScope software lock-in amplifier."""
        try:
            config = DEVICE_CONFIGS[DeviceType.PICOSCOPE_LOCKIN]
            self.lockin = PicoScopeController()
            
            # Connect to PicoScope
            if not self.lockin.connect():
                raise PicoScopeError("Failed to connect to PicoScope")
            
            # Configure with default parameters
            chopper_freq = config.get("default_chopper_freq", 81)
            num_cycles = config.get("default_num_cycles", 100)
            correction_factor = config.get("correction_factor", 0.45)
            
            self.lockin.set_reference_frequency(chopper_freq)
            self.lockin.set_num_cycles(num_cycles)
            self.lockin.set_correction_factor(correction_factor)
            
            self._notify_device_status("PicoScope Lock-in", True, f"Connected (Freq: {chopper_freq} Hz)")
            self.logger.log(f"PicoScope lock-in initialized (Freq: {chopper_freq} Hz, Cycles: {num_cycles})")
        except PicoScopeError as e:
            self._notify_device_status("PicoScope Lock-in", False, str(e))
            raise EQEExperimentError(f"Failed to initialize lock-in: {e}")
    
    def _create_measurement_models(self) -> None:
        """Create measurement models."""
        # Power measurement model
        self.power_model = PowerMeasurementModel(
            power_meter=self.power_meter,
            monochromator=self.monochromator,
            logger=self.logger
        )
        self.power_model.set_progress_callback(self._on_power_progress)
        self.power_model.set_completion_callback(self._on_power_complete)
        
        # Current measurement model (uses PicoScope lock-in only)
        self.current_model = CurrentMeasurementModel(
            lockin=self.lockin,
            monochromator=self.monochromator,
            logger=self.logger
        )
        self.current_model.set_progress_callback(self._on_current_progress)
        self.current_model.set_completion_callback(self._on_current_complete)
        
        # Phase adjustment model
        self.phase_model = PhaseAdjustmentModel(
            lockin=self.lockin,
            monochromator=self.monochromator,
            logger=self.logger
        )
        self.phase_model.set_progress_callback(self._on_phase_progress)
        self.phase_model.set_completion_callback(self._on_phase_complete)
    
    def _on_power_progress(self, wavelength: float, power: float, progress: float) -> None:
        """Handle power measurement progress."""
        progress_data = {
            'wavelength': wavelength,
            'power': power,
            'progress_percent': progress
        }
        self._notify_measurement_progress('power', progress_data)
    
    def _on_power_complete(self, success: bool) -> None:
        """Handle power measurement completion."""
        message = "Power measurement completed" if success else "Power measurement failed"
        self.logger.log(message)
        self._notify_experiment_complete(success, message)
    
    def _on_current_progress(self, wavelength: float, current: float, progress: float) -> None:
        """Handle current measurement progress."""
        progress_data = {
            'wavelength': wavelength,
            'current': current,
            'progress_percent': progress
        }
        self._notify_measurement_progress('current', progress_data)
    
    def _on_current_complete(self, success: bool) -> None:
        """Handle current measurement completion."""
        message = "Current measurement completed" if success else "Current measurement failed"
        self.logger.log(message)
        self._notify_experiment_complete(success, message)
    
    def _on_phase_progress(self, phase: float, signal: float) -> None:
        """Handle phase adjustment progress."""
        progress_data = {
            'phase': phase,
            'signal': signal
        }
        self._notify_measurement_progress('phase', progress_data)
    
    def _on_phase_complete(self, success: bool, results: Dict[str, Any]) -> None:
        """Handle phase adjustment completion."""
        if success:
            r_squared = results.get('r_squared', 0)
            pixel_number = results.get('pixel_number', 0)
            message = f"Phase adjustment completed for pixel {pixel_number} (R² = {r_squared:.4f})"
        else:
            message = "Phase adjustment failed"
        self.logger.log(message)
        self._notify_experiment_complete(success, message)
    
    def is_initialized(self) -> bool:
        """Check if devices are initialized."""
        return self._devices_initialized
    
    def get_device_status(self) -> Dict[str, bool]:
        """
        Get status of all devices.
        
        Returns:
            Dict[str, bool]: Device status dictionary
        """
        if not self._devices_initialized:
            return {
                'power_meter': False,
                'keithley': False,
                'monochromator': False,
                'lockin': False
            }
        
        return {
            'power_meter': self.power_meter.is_connected() if self.power_meter else False,
            'keithley': self.keithley.is_connected() if self.keithley else False,
            'monochromator': self.monochromator.is_connected() if self.monochromator else False,
            'lockin': self.lockin.is_connected() if self.lockin else False
        }
    
    def set_measurement_parameters(self, **params) -> None:
        """
        Set measurement parameters.
        
        Args:
            **params: Measurement parameters to update
        """
        for key, value in params.items():
            if key in self.measurement_params:
                self.measurement_params[key] = value
                self.logger.log(f"Set {key} = {value}")
    
    def get_measurement_parameters(self) -> Dict[str, Any]:
        """Get current measurement parameters."""
        return self.measurement_params.copy()
    
    def validate_measurement_parameters(self) -> bool:
        """
        Validate current measurement parameters.
        
        Returns:
            bool: True if parameters are valid
            
        Raises:
            EQEExperimentError: If parameters are invalid
        """
        try:
            # Validate cell number
            cell_number = self.measurement_params.get('cell_number', '')
            if not self.data_handler.validate_cell_number(cell_number):
                raise EQEExperimentError("Invalid cell number format")
            
            # Validate pixel number
            pixel_number = self.measurement_params.get('pixel_number', 1)
            if not self.data_handler.validate_pixel_number(pixel_number):
                raise EQEExperimentError("Invalid pixel number")
            
            # Validate wavelength range
            start_wl = self.measurement_params.get('start_wavelength', 350)
            end_wl = self.measurement_params.get('end_wavelength', 850)
            step_size = self.measurement_params.get('step_size', 10)
            
            if start_wl >= end_wl:
                raise EQEExperimentError("Start wavelength must be less than end wavelength")
            
            if step_size <= 0:
                raise EQEExperimentError("Step size must be positive")
            
            return True
            
        except Exception as e:
            raise EQEExperimentError(f"Parameter validation failed: {e}")
    
    def align_monochromator(self) -> None:
        """Align monochromator for visual alignment."""
        if not self._devices_initialized:
            raise EQEExperimentError("Devices not initialized")
        
        try:
            self.power_model.align_monochromator()
            self.logger.log("Monochromator aligned for visual check")
        except PowerMeasurementError as e:
            raise EQEExperimentError(f"Failed to align monochromator: {e}")
    
    def start_power_measurement(self) -> bool:
        """
        Start power measurement with current parameters.
        
        Returns:
            bool: True if measurement started successfully
        """
        if not self._devices_initialized:
            raise EQEExperimentError("Devices not initialized")
        
        self.validate_measurement_parameters()
        
        try:
            return self.power_model.start_measurement(
                start_wavelength=self.measurement_params['start_wavelength'],
                end_wavelength=self.measurement_params['end_wavelength'],
                step_size=self.measurement_params['step_size']
            )
        except PowerMeasurementError as e:
            raise EQEExperimentError(f"Failed to start power measurement: {e}")
    
    def start_current_measurement(self, pixel_number: Optional[int] = None) -> bool:
        """
        Start current measurement with current parameters.
        
        Args:
            pixel_number: Optional pixel number (overrides parameter)
            
        Returns:
            bool: True if measurement started successfully
        """
        if not self._devices_initialized:
            raise EQEExperimentError("Devices not initialized")
        
        self.validate_measurement_parameters()
        
        if pixel_number is not None:
            self.set_measurement_parameters(pixel_number=pixel_number)
        
        try:
            return self.current_model.start_measurement(
                start_wavelength=self.measurement_params['start_wavelength'],
                end_wavelength=self.measurement_params['end_wavelength'],
                step_size=self.measurement_params['step_size'],
                pixel_number=self.measurement_params['pixel_number']
            )
        except CurrentMeasurementError as e:
            raise EQEExperimentError(f"Failed to start current measurement: {e}")
    
    def start_phase_adjustment(self, pixel_number: Optional[int] = None) -> bool:
        """
        Start phase adjustment with current parameters.
        
        Args:
            pixel_number: Optional pixel number (overrides parameter)
            
        Returns:
            bool: True if adjustment started successfully
        """
        if not self._devices_initialized:
            raise EQEExperimentError("Devices not initialized")
        
        if pixel_number is not None:
            self.set_measurement_parameters(pixel_number=pixel_number)
        
        try:
            return self.phase_model.start_adjustment(
                pixel_number=self.measurement_params['pixel_number']
            )
        except PhaseAdjustmentError as e:
            raise EQEExperimentError(f"Failed to start phase adjustment: {e}")
    
    def stop_all_measurements(self) -> None:
        """Stop all running measurements."""
        if self.power_model:
            self.power_model.stop_measurement()
        if self.current_model:
            self.current_model.stop_measurement()
        if self.phase_model:
            self.phase_model.stop_adjustment()
        self.logger.log("All measurements stopped")
    
    def get_measurement_status(self) -> Dict[str, bool]:
        """
        Get status of all measurements.
        
        Returns:
            Dict[str, bool]: Measurement status dictionary
        """
        return {
            'power_measuring': self.power_model.is_measuring() if self.power_model else False,
            'current_measuring': self.current_model.is_measuring() if self.current_model else False,
            'phase_adjusting': self.phase_model.is_adjusting() if self.phase_model else False
        }
    
    def save_power_data(self, file_path: str) -> None:
        """Save power measurement data."""
        if not self.power_model:
            raise EQEExperimentError("Power model not initialized")
        
        wavelengths, powers = self.power_model.get_measurement_data()
        if not wavelengths:
            raise EQEExperimentError("No power data to save")
        
        try:
            self.data_handler.save_measurement_data(file_path, wavelengths, powers, "power")
            self.logger.log(f"Power data saved to {file_path}")
        except DataValidationError as e:
            raise EQEExperimentError(f"Failed to save power data: {e}")
    
    def save_current_data(self, file_path: str) -> None:
        """Save current measurement data."""
        if not self.current_model:
            raise EQEExperimentError("Current model not initialized")
        
        wavelengths, currents, pixel_number = self.current_model.get_measurement_data()
        if not wavelengths:
            raise EQEExperimentError("No current data to save")
        
        try:
            self.data_handler.save_measurement_data(file_path, wavelengths, currents, "current")
            self.logger.log(f"Current data saved to {file_path} (pixel {pixel_number})")
        except DataValidationError as e:
            raise EQEExperimentError(f"Failed to save current data: {e}")
    
    def save_phase_data(self, file_path: str) -> None:
        """Save phase adjustment data."""
        if not self.phase_model:
            raise EQEExperimentError("Phase model not initialized")
        
        data = self.phase_model.get_adjustment_data()
        if data['optimal_phase'] is None:
            raise EQEExperimentError("No phase data to save")
        
        try:
            self.data_handler.save_phase_data(
                file_path=file_path,
                pixel_number=self.measurement_params['pixel_number'],
                phase_angle=data['optimal_phase'],
                signal=data['optimal_signal'],
                r_squared=data['r_squared']
            )
            self.logger.log(f"Phase data saved to {file_path}")
        except DataValidationError as e:
            raise EQEExperimentError(f"Failed to save phase data: {e}")
    
    @contextmanager
    def experiment_session(self):
        """
        Context manager for experiment session.
        Automatically initializes and cleans up resources.
        """
        try:
            if not self._devices_initialized:
                self.initialize_devices()
            yield self
        except Exception as e:
            self.logger.log(f"Experiment session error: {e}", "ERROR")
            raise
        finally:
            self.cleanup()
    
    def cleanup(self) -> None:
        """Clean up resources and disconnect devices."""
        try:
            self.stop_all_measurements()
            
            # Wait for measurements to stop
            if self.power_model:
                self.power_model.wait_for_completion(timeout=5)
            if self.current_model:
                self.current_model.wait_for_completion(timeout=5)
            if self.phase_model:
                self.phase_model.wait_for_completion(timeout=5)
            
            # Disconnect devices
            if self.power_meter:
                self.power_meter.disconnect()
            if self.keithley:
                self.keithley.disconnect()
            if self.monochromator:
                self.monochromator.disconnect()
            if self.lockin:
                self.lockin.disconnect()
            
            # Close VISA resource manager
            if self._rm:
                self._rm.close()
            
            self._devices_initialized = False
            self.logger.log("Experiment cleanup completed")
            
        except Exception as e:
            self.logger.log(f"Cleanup error: {e}", "ERROR")