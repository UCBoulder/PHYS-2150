"""
EQE Experiment Model

This model coordinates the complete EQE measurement experiment, managing all devices
and measurement models. It represents the highest level of experiment logic.
"""

import time
import threading
from contextlib import contextmanager
from typing import Optional, Dict, Any, Callable, Tuple, List

import pyvisa as visa
from PySide6.QtCore import QObject, Signal

from ..controllers.thorlabs_power_meter import ThorlabsPowerMeterController, ThorlabsPowerMeterError
from ..controllers.monochromator import MonochromatorController, MonochromatorError
from ..controllers.picoscope_lockin import PicoScopeController, PicoScopeError
from ..models.power_measurement import PowerMeasurementModel, PowerMeasurementError
from ..models.current_measurement import CurrentMeasurementModel, CurrentMeasurementError
from ..models.phase_adjustment import PhaseAdjustmentModel, PhaseAdjustmentError
from ..config.settings import (
    DEFAULT_MEASUREMENT_PARAMS,
    DEVICE_CONFIGS,
    DeviceType,
    GUI_CONFIG,
    PHASE_ADJUSTMENT_CONFIG,
)
from ..utils.data_handling import DataHandler, MeasurementDataLogger, DataValidationError
from ..config import settings


class EQEExperimentError(Exception):
    """Exception raised for EQE experiment specific errors."""
    pass


class EQEExperimentModel(QObject):
    """
    High-level model for the complete EQE measurement experiment.
    
    This model coordinates all devices and measurement operations, providing
    a unified interface for the complete experimental workflow.
    """
    
    # Qt Signals for thread-safe GUI updates
    device_status_changed = Signal(str, bool, str)  # device_name, is_connected, message
    measurement_progress = Signal(str, dict)  # measurement_type, progress_data
    experiment_complete = Signal(bool, str)  # success, message
    live_signal_update = Signal(float)  # current in nanoamps
    monochromator_state_changed = Signal(float, bool, int)  # wavelength, shutter_open, filter
    phase_adjustment_complete = Signal(dict)  # phase_data, signal_data, fit_phases, fit_signals
    
    def __init__(self, logger: Optional[MeasurementDataLogger] = None):
        """
        Initialize the EQE experiment model.
        
        Args:
            logger: Optional logger for experiment progress
        """
        super().__init__()
        
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

        # Flag to skip auto-starting current measurement after phase adjustment
        # (used when running stability test - caller will start stability test instead)
        self._skip_auto_current_after_phase = False

        # Live signal monitor
        self._live_monitor_thread: Optional[threading.Thread] = None
        self._live_monitor_active = False

        # Monochromator state tracking (shutter state not queryable from hardware)
        self._shutter_open = False

        # Experiment parameters
        self.measurement_params = DEFAULT_MEASUREMENT_PARAMS.copy()
        
        # Legacy callbacks for backwards compatibility (will use signals instead)
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
        """Notify device status change using Qt signal for thread safety."""
        # Emit Qt signal (thread-safe)
        self.device_status_changed.emit(device_name, is_connected, message)
        
        # Keep legacy callback for backwards compatibility
        if self.device_status_callback:
            self.device_status_callback(device_name, is_connected, message)
    
    def _notify_measurement_progress(self, measurement_type: str, progress_data: Dict) -> None:
        """Notify measurement progress using Qt signal for thread safety."""
        # Emit Qt signal (thread-safe)
        self.measurement_progress.emit(measurement_type, progress_data)
        
        # Keep legacy callback for backwards compatibility
        if self.measurement_progress_callback:
            self.measurement_progress_callback(measurement_type, progress_data)
    
    def _notify_experiment_complete(self, success: bool, message: str) -> None:
        """Notify experiment completion using Qt signal for thread safety."""
        # Emit Qt signal (thread-safe)
        self.experiment_complete.emit(success, message)
        
        # Keep legacy callback for backwards compatibility
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
        # Check if running in offline mode
        if settings.OFFLINE_MODE:
            self.logger.log("Running in OFFLINE mode - skipping hardware initialization")
            self._notify_device_status("Thorlabs Power Meter", True, "OFFLINE MODE")
            self._notify_device_status("Monochromator", True, "OFFLINE MODE")
            self._notify_device_status("PicoScope Lock-in", True, "OFFLINE MODE")
            self._devices_initialized = True
            self.logger.log("Offline mode - devices simulated successfully")
            return True
        
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
            # Don't log here - device_status_changed signal already logged per-device failures
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
            self.lockin = PicoScopeController()

            # Connect to PicoScope (controller loads config in __init__)
            if not self.lockin.connect():
                raise PicoScopeError("Failed to connect to PicoScope")

            self._notify_device_status("PicoScope Lock-in", True, "Connected")
            self.logger.log("PicoScope lock-in initialized")
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

        # Update monochromator state display (shutter is open during measurement)
        self._shutter_open = True
        filter_number = self.monochromator._current_filter if self.monochromator else 0
        self.monochromator_state_changed.emit(wavelength, True, filter_number)
    
    def _on_power_complete(self, success: bool) -> None:
        """Handle power measurement completion."""
        message = "Power measurement completed" if success else "Power measurement failed"
        self.logger.log(message)
        self._notify_experiment_complete(success, message)

        # Update monochromator state (shutter is closed after measurement)
        self._shutter_open = False
        if self.monochromator:
            try:
                wavelength = self.monochromator.get_wavelength()
                filter_number = self.monochromator._current_filter or 0
                self.monochromator_state_changed.emit(wavelength, False, filter_number)
            except Exception:
                pass  # Ignore errors getting state after measurement
    
    def _on_current_progress(self, wavelength: float, current: float, progress: float) -> None:
        """Handle current measurement progress."""
        progress_data = {
            'wavelength': wavelength,
            'current': current,
            'progress_percent': progress
        }
        self._notify_measurement_progress('current', progress_data)

        # Update monochromator state display (shutter is open during measurement)
        self._shutter_open = True
        filter_number = self.monochromator._current_filter if self.monochromator else 0
        self.monochromator_state_changed.emit(wavelength, True, filter_number)
    
    def _on_current_complete(self, success: bool) -> None:
        """Handle current measurement completion."""
        message = "Current measurement completed" if success else "Current measurement failed"
        self.logger.log(message)
        self._notify_experiment_complete(success, message)

        # Update monochromator state (shutter is closed after measurement)
        self._shutter_open = False
        if self.monochromator:
            try:
                wavelength = self.monochromator.get_wavelength()
                filter_number = self.monochromator._current_filter or 0
                self.monochromator_state_changed.emit(wavelength, False, filter_number)
            except Exception:
                pass  # Ignore errors getting state after measurement
    
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
            optimal_phase = results.get('optimal_phase', 0)
            message = f"Phase adjustment: {optimal_phase:.1f}° (R² = {r_squared:.4f})"
            self.logger.log(message)

            # Emit phase adjustment data for plotting (measured data + sine fit)
            phase_data = {
                'phase_data': results.get('phase_data', []),
                'signal_data': results.get('signal_data', []),
                'fit_phases': results.get('fit_phases', []),
                'fit_signals': results.get('fit_signals', []),
                'optimal_phase': optimal_phase,
                'r_squared': r_squared
            }
            self.phase_adjustment_complete.emit(phase_data)

            # Automatically start current measurement after successful phase adjustment
            # (unless skip flag is set - used for stability tests)
            if self._skip_auto_current_after_phase:
                self._skip_auto_current_after_phase = False
                self.logger.log("Phase adjustment complete (skipping auto-start of current measurement)")
            else:
                try:
                    self.start_current_measurement()
                except EQEExperimentError as e:
                    self.logger.log(f"Failed to start current measurement: {e}", "ERROR")
                    self._notify_experiment_complete(False, f"Failed to start current measurement: {e}")
        else:
            message = "Phase adjustment failed"
            self.logger.log(message)
            # Notify UI that the experiment failed so it doesn't hang
            self._notify_experiment_complete(False,
                "Phase adjustment failed. Check that:\n\n"
                "   • Chopper and light source are on\n"
                "   • Light is aligned to the correct pixel\n"
                "   • Banana cables are connected correctly\n"
                "   • Transimpedance amplifier is powered on")
    
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
                'monochromator': False,
                'lockin': False
            }
        
        return {
            'power_meter': self.power_meter.is_connected() if self.power_meter else False,
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
            pixel_number = self.measurement_params.get('pixel_number', DEFAULT_MEASUREMENT_PARAMS['pixel_number'])
            if not self.data_handler.validate_pixel_number(pixel_number):
                raise EQEExperimentError("Invalid pixel number")
            
            # Validate wavelength range
            start_wl = self.measurement_params.get('start_wavelength', DEFAULT_MEASUREMENT_PARAMS['start_wavelength'])
            end_wl = self.measurement_params.get('end_wavelength', DEFAULT_MEASUREMENT_PARAMS['end_wavelength'])
            step_size = self.measurement_params.get('step_size', DEFAULT_MEASUREMENT_PARAMS['step_size'])
            
            if start_wl >= end_wl:
                raise EQEExperimentError("Start wavelength must be less than end wavelength")
            
            if step_size <= 0:
                raise EQEExperimentError("Step size must be positive")
            
            return True
            
        except Exception as e:
            raise EQEExperimentError(f"Parameter validation failed: {e}")
    
    def align_monochromator(self) -> None:
        """Align monochromator for visual alignment."""
        if settings.OFFLINE_MODE:
            raise EQEExperimentError("Cannot control hardware in OFFLINE mode")

        if not self._devices_initialized:
            raise EQEExperimentError("Devices not initialized")

        try:
            self.power_model.align_monochromator()
            self._shutter_open = True  # Alignment opens shutter
            # Update UI with current monochromator state
            wavelength = self.monochromator.get_wavelength()
            filter_number = self.monochromator._current_filter or 0
            self.monochromator_state_changed.emit(wavelength, self._shutter_open, filter_number)
            self.logger.log("Monochromator aligned for visual check")
        except PowerMeasurementError as e:
            raise EQEExperimentError(f"Failed to align monochromator: {e}")

    def start_live_signal_monitor(self) -> None:
        """
        Start live signal monitoring at 532 nm (green).

        Sets monochromator to 532 nm, opens shutter, and starts periodic
        fast lock-in measurements to help with cell alignment.
        Measurements run in a background thread to avoid blocking the UI.
        """
        if settings.OFFLINE_MODE:
            raise EQEExperimentError("Cannot perform measurements in OFFLINE mode")

        if not self._devices_initialized:
            raise EQEExperimentError("Devices not initialized")

        if self._live_monitor_active:
            return  # Already running

        try:
            # Set monochromator to alignment wavelength (green) and open shutter
            alignment_wl = PHASE_ADJUSTMENT_CONFIG["alignment_wavelength"]
            self.monochromator.set_wavelength(alignment_wl)
            self.monochromator.open_shutter()
            self._shutter_open = True
            self.logger.log(f"Live signal monitor: Set to {alignment_wl} nm, shutter open")

            # Update UI with current monochromator state
            wavelength = self.monochromator.get_wavelength()
            filter_number = self.monochromator._current_filter or 0
            self.monochromator_state_changed.emit(wavelength, self._shutter_open, filter_number)

            # Start measurements in background thread (doesn't block UI)
            self._live_monitor_active = True
            self._live_monitor_thread = threading.Thread(
                target=self._live_monitor_worker,
                daemon=True
            )
            self._live_monitor_thread.start()

        except (MonochromatorError, PicoScopeError) as e:
            self._live_monitor_active = False
            raise EQEExperimentError(f"Failed to start live monitor: {e}")

    def stop_live_signal_monitor(self) -> None:
        """Stop live signal monitoring."""
        self._live_monitor_active = False

        # Thread will exit on next iteration when it checks _live_monitor_active
        if self._live_monitor_thread and self._live_monitor_thread.is_alive():
            self._live_monitor_thread.join(timeout=1.0)
        self._live_monitor_thread = None

        self.logger.log("Live signal monitor stopped")

    def set_wavelength_manual(self, wavelength: float) -> None:
        """
        Manually set monochromator wavelength with auto grating/filter selection.

        Args:
            wavelength: Target wavelength in nm (200-1200)

        Raises:
            EQEExperimentError: If operation fails
        """
        if settings.OFFLINE_MODE:
            raise EQEExperimentError("Cannot control hardware in OFFLINE mode")

        if not self._devices_initialized:
            raise EQEExperimentError("Devices not initialized")

        try:
            # Use configure_for_wavelength which handles grating + filter + wavelength
            confirmed_wavelength = self.monochromator.configure_for_wavelength(wavelength)
            filter_number = self.monochromator._current_filter or 0
            self.monochromator_state_changed.emit(
                confirmed_wavelength, self._shutter_open, filter_number
            )
            self.logger.log(f"Wavelength set to {confirmed_wavelength:.1f} nm (filter {filter_number})")
        except MonochromatorError as e:
            raise EQEExperimentError(f"Failed to set wavelength: {e}")

    def open_shutter_manual(self) -> None:
        """
        Manually open the monochromator shutter.

        Raises:
            EQEExperimentError: If operation fails
        """
        if settings.OFFLINE_MODE:
            raise EQEExperimentError("Cannot control hardware in OFFLINE mode")

        if not self._devices_initialized:
            raise EQEExperimentError("Devices not initialized")

        try:
            self.monochromator.open_shutter()
            self._shutter_open = True
            wavelength = self.monochromator.get_wavelength()
            filter_number = self.monochromator._current_filter or 0
            self.monochromator_state_changed.emit(wavelength, self._shutter_open, filter_number)
            self.logger.log("Shutter opened")
        except MonochromatorError as e:
            raise EQEExperimentError(f"Failed to open shutter: {e}")

    def close_shutter_manual(self) -> None:
        """
        Manually close the monochromator shutter.

        Raises:
            EQEExperimentError: If operation fails
        """
        if settings.OFFLINE_MODE:
            raise EQEExperimentError("Cannot control hardware in OFFLINE mode")

        if not self._devices_initialized:
            raise EQEExperimentError("Devices not initialized")

        try:
            self.monochromator.close_shutter()
            self._shutter_open = False
            wavelength = self.monochromator.get_wavelength()
            filter_number = self.monochromator._current_filter or 0
            self.monochromator_state_changed.emit(wavelength, self._shutter_open, filter_number)
            self.logger.log("Shutter closed")
        except MonochromatorError as e:
            raise EQEExperimentError(f"Failed to close shutter: {e}")

    def get_monochromator_state(self) -> Dict[str, Any]:
        """
        Get current monochromator state.

        Returns:
            Dict with 'wavelength', 'shutter_open', and 'filter' keys
        """
        if not self._devices_initialized or not self.monochromator:
            return {'wavelength': 0.0, 'shutter_open': False, 'filter': 0}

        try:
            wavelength = self.monochromator.get_wavelength()
        except MonochromatorError:
            wavelength = 0.0

        return {
            'wavelength': wavelength,
            'shutter_open': self._shutter_open,
            'filter': self.monochromator._current_filter or 0
        }

    def _live_monitor_worker(self) -> None:
        """
        Worker function for live monitoring thread.

        Runs measurements in a loop until _live_monitor_active is set to False.
        Emits signals to update UI without blocking the main thread.
        """
        interval_s = GUI_CONFIG["live_monitor_interval_ms"] / 1000.0

        while self._live_monitor_active:
            try:
                # Use fast measurement with fewer cycles
                current = self.lockin.read_current_fast(num_cycles=20)

                if current is not None:
                    # Convert to nanoamps for display
                    current_nA = current * 1e9
                    self.live_signal_update.emit(current_nA)

            except PicoScopeError as e:
                self.logger.log(f"Live measurement error: {e}", "WARNING")

            # Sleep to maintain update interval (measurement time + sleep = interval)
            time.sleep(interval_s)
    
    def start_power_measurement(self) -> bool:
        """
        Start power measurement with current parameters.
        
        Returns:
            bool: True if measurement started successfully
        """
        if settings.OFFLINE_MODE:
            raise EQEExperimentError("Cannot perform measurements in OFFLINE mode")
        
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
        if settings.OFFLINE_MODE:
            raise EQEExperimentError("Cannot perform measurements in OFFLINE mode")
        
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
        if settings.OFFLINE_MODE:
            raise EQEExperimentError("Cannot perform measurements in OFFLINE mode")
        
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

        wavelengths, currents, pixel_number, measurement_stats = self.current_model.get_measurement_data()
        if not wavelengths:
            raise EQEExperimentError("No current data to save")

        try:
            # Pass measurement stats to save function (will export if enabled in settings)
            self.data_handler.save_measurement_data(
                file_path, wavelengths, currents, "current",
                measurement_stats=measurement_stats if measurement_stats else None
            )
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