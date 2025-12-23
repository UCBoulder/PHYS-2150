"""
Main Application View

This module contains the main window and application view that coordinates
all GUI components and provides the primary user interface.
"""

import sys
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QMessageBox,
    QFileDialog, QInputDialog, QApplication, QPushButton, QTabWidget
)
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QKeyEvent
from typing import Optional, Dict, Any
import logging

from ..models.eqe_experiment import EQEExperimentModel, EQEExperimentError
from ..models.stability_test import StabilityTestModel
from ..utils.data_handling import DataHandler, DataValidationError
from ..config.settings import GUI_CONFIG, ERROR_MESSAGES, FILE_NAMING, PHASE_ADJUSTMENT_CONFIG
from .measurement_tab import MeasurementTab
from .stability_test_tab import StabilityTestTab
from .eqe_analysis_tab import EQEAnalysisTab
from common.utils import TieredLogger, MeasurementStats
import datetime


class MainApplicationView(QMainWindow):
    """
    Main application window.
    
    This view coordinates all GUI components and serves as the primary
    interface between the user and the experiment model.
    """
    
    # Signals for experiment control
    experiment_start_requested = Signal(str, dict)  # measurement_type, parameters
    experiment_stop_requested = Signal()
    
    def __init__(self):
        """Initialize the main application view."""
        super().__init__()
        
        # Set up the main window
        self._setup_window()
        
        # Create main components
        self.experiment_model: Optional[EQEExperimentModel] = None
        self.stability_model: Optional[StabilityTestModel] = None
        self.data_handler = DataHandler()
        self.logger = logging.getLogger(__name__)
        
        # Create tab widget
        self.tab_widget = QTabWidget()
        
        # Create tabs
        self.measurement_tab = MeasurementTab()
        self.stability_tab = StabilityTestTab()
        
        # Add tabs
        self.tab_widget.addTab(self.measurement_tab, "Measurements")
        self.tab_widget.addTab(self.stability_tab, "Stability Tests")
        
        # Set up layouts and connections
        self._setup_layout()
        self._connect_signals()
        
        # Initialize timers for periodic updates
        self._setup_timers()

        # Track current measurement state
        self._current_measurement_type: Optional[str] = None
        self._current_pixel_number: Optional[int] = None

        # Track device initialization state
        self._devices_initialized = False

        # Staff mode (hidden EQE analysis tab)
        self._staff_mode_enabled = False
        self.eqe_analysis_tab = EQEAnalysisTab()

        # Staff debug mode (Ctrl+Shift+D to show technical debug output)
        self._staff_debug_mode = False

        # Connect tiered logger to measurement stats widget
        self._setup_logger_callbacks()

        # Disable all interactive buttons until device initialization completes
        # This prevents focus issues when native PicoScope splash screen is shown
        self._disable_buttons_during_init()

        # Show cell number input on startup
        QTimer.singleShot(1000, self._show_initial_cell_number_dialog)
    
    def _setup_window(self) -> None:
        """Configure the main window properties."""
        self.setWindowTitle(GUI_CONFIG["window_title"])
        self.setGeometry(100, 100, *GUI_CONFIG["window_size"])
    
    def _setup_layout(self) -> None:
        """Set up the main window layout."""
        # Set tab widget as central widget
        self.setCentralWidget(self.tab_widget)
    
    def _connect_signals(self) -> None:
        """Connect signals between GUI components."""
        # Measurement tab signals
        self.measurement_tab.parameters_changed.connect(self._on_parameters_changed)
        self.measurement_tab.power_measurement_requested.connect(self._start_power_measurement)
        self.measurement_tab.current_measurement_requested.connect(self._start_current_measurement)
        self.measurement_tab.stop_requested.connect(self._stop_measurement)
        self.measurement_tab.alignment_requested.connect(self._on_align_button_clicked)
        self.measurement_tab.live_monitor_requested.connect(self._on_live_monitor_requested)

        # Monochromator control signals
        self.measurement_tab.wavelength_change_requested.connect(self._on_wavelength_change_requested)
        self.measurement_tab.shutter_open_requested.connect(self._on_shutter_open_requested)
        self.measurement_tab.shutter_close_requested.connect(self._on_shutter_close_requested)

        # Stability tab signals (placeholder for future expansion)
        # Signals are handled internally by the stability tab and model
    
    def _setup_timers(self) -> None:
        """Set up periodic update timers."""
        # Status update timer
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self._update_status)
        self.status_timer.start(1000)  # Update every second

    def _setup_logger_callbacks(self) -> None:
        """
        Connect the tiered logger to GUI components.

        This routes measurement statistics to the stats widget and
        enables error dialogs for student-friendly error messages.
        """
        eqe_logger = TieredLogger.get_logger("eqe")

        # Connect stats callback to update measurement stats widget
        eqe_logger.set_stats_callback(self._on_measurement_stats)

        # Connect error callback for student-friendly error dialogs
        eqe_logger.set_error_callback(self._on_student_error)

        # Connect GUI status callback for status bar updates
        eqe_logger.set_gui_callback(self._on_logger_status)

    def _on_measurement_stats(self, stats: MeasurementStats) -> None:
        """
        Handle measurement statistics from the tiered logger.

        Routes statistics to the measurement stats widget for display.
        """
        self.measurement_tab.update_measurement_stats(stats)

    def _on_student_error(self, title: str, message: str,
                          causes: list, actions: list) -> None:
        """
        Handle student-friendly error messages from the tiered logger.

        Displays an error dialog with context and suggested actions.
        """
        # Build detailed message
        full_message = message

        if causes:
            full_message += "\n\nPossible causes:\n"
            for cause in causes:
                full_message += f"  - {cause}\n"

        if actions:
            full_message += "\nWhat to do:\n"
            for action in actions:
                full_message += f"  - {action}\n"

        QMessageBox.warning(self, title, full_message.strip())

    def _on_logger_status(self, message: str) -> None:
        """
        Handle status messages from the tiered logger.

        Updates the status display with student-facing messages.
        """
        # Update status in the progress group
        status_display = self.measurement_tab.get_status_display()
        status_display.status_label.setText(message)

    def _disable_buttons_during_init(self) -> None:
        """
        Disable all interactive buttons during device initialization.

        This prevents a bug where clicking on the application window while
        the PicoScope 2204A firmware upload splash screen is visible can
        cause buttons to become permanently unresponsive. The native Windows
        splash dialog interferes with Qt's event handling when clicked.

        Buttons are re-enabled in _on_device_status_update when all devices
        are connected (all_connected = True).
        """
        plot_widget = self.measurement_tab.get_plot_widget()
        status_display = self.measurement_tab.get_status_display()
        monochromator_control = self.measurement_tab.get_monochromator_control()
        plot_widget.set_buttons_enabled(False)
        status_display.live_monitor_button.setEnabled(False)
        monochromator_control.set_enabled(False)
    
    def set_experiment_model(self, model: EQEExperimentModel) -> None:
        """
        Set the experiment model and connect its signals.
        
        Args:
            model: EQE experiment model instance
        """
        self.experiment_model = model
        
        # Connect model Qt signals with QueuedConnection for thread safety
        # This ensures all GUI updates happen on the main thread
        model.device_status_changed.connect(
            self._on_device_status_update, Qt.QueuedConnection)
        model.measurement_progress.connect(
            self._on_measurement_progress, Qt.QueuedConnection)
        model.experiment_complete.connect(
            self._on_experiment_complete, Qt.QueuedConnection)
        model.live_signal_update.connect(
            self._on_live_signal_update, Qt.QueuedConnection)
        model.monochromator_state_changed.connect(
            self._on_monochromator_state_changed, Qt.QueuedConnection)

        # Update EQE analysis tab if staff mode is enabled
        if self._staff_mode_enabled:
            self.eqe_analysis_tab.set_experiment_model(model)

        # Note: StabilityTestModel will be created after device initialization completes
        # See initialize_stability_model() method
    
    def initialize_stability_model(self) -> None:
        """
        Initialize the stability test model after devices are connected.
        
        This must be called after device initialization is complete.
        """
        if not self.experiment_model:
            return
        
        # Create and set up stability test model using same hardware controllers
        self.stability_model = StabilityTestModel(
            power_meter=self.experiment_model.power_meter,
            monochromator=self.experiment_model.monochromator,
            lockin=self.experiment_model.lockin,
            logger=self.logger
        )
        self.stability_tab.set_stability_model(self.stability_model)
        self.logger.info("Stability test model initialized with shared hardware controllers")
    
    def _show_cell_number_dialog(self) -> bool:
        """
        Show cell number input dialog.

        Returns:
            bool: True if cell number was set, False if cancelled
        """
        while True:
            cell_number, ok = QInputDialog.getText(
                self, "Enter Cell Number",
                "Enter Cell Number (three digits, e.g., 167, 001):"
            )

            if not ok:
                # User cancelled - allow them to explore the interface
                return False

            if cell_number and self.data_handler.validate_cell_number(cell_number):
                current_params = self.measurement_tab.get_parameters()
                current_params['cell_number'] = cell_number
                self.measurement_tab.load_parameters(current_params)
                return True
            else:
                QMessageBox.warning(self, "Invalid Input", ERROR_MESSAGES["invalid_cell_number"])

    def _show_initial_cell_number_dialog(self) -> None:
        """Show cell number input dialog on application startup."""
        self._show_cell_number_dialog()

    def _ensure_cell_number(self) -> bool:
        """
        Ensure cell number is set before measurement.

        If cell number is not set, prompts the user to enter one.

        Returns:
            bool: True if cell number is set, False if user cancelled
        """
        params = self.measurement_tab.get_parameters()
        cell_number = params.get('cell_number', '')
        if not cell_number or not self.data_handler.validate_cell_number(cell_number):
            return self._show_cell_number_dialog()
        return True

    def _on_parameters_changed(self, params: Dict[str, Any]) -> None:
        """
        Handle parameter changes from the input widget.
        
        Args:
            params: Updated parameters
        """
        if self.experiment_model:
            try:
                self.experiment_model.set_measurement_parameters(**params)
            except EQEExperimentError as e:
                self._show_error(f"Parameter error: {e}")
    
    def _on_device_status_update(self, device_name: str, is_connected: bool, message: str) -> None:
        """
        Handle device status updates from the experiment model.

        Args:
            device_name: Name of the device
            is_connected: Connection status
            message: Status message
        """
        self.measurement_tab.update_device_status(device_name, is_connected, message)

        # Update control button states based on overall device status
        if self.experiment_model:
            device_status = self.experiment_model.get_device_status()
            all_connected = all(device_status.values())
            plot_widget = self.measurement_tab.get_plot_widget()
            monochromator_control = self.measurement_tab.get_monochromator_control()
            plot_widget.set_buttons_enabled(all_connected)
            monochromator_control.set_enabled(all_connected)

            # Track that devices are initialized (fixes button responsiveness)
            if all_connected:
                self._devices_initialized = True
    
    def _on_measurement_progress(self, measurement_type: str, progress_data: Dict) -> None:
        """
        Handle measurement progress updates.
        
        Args:
            measurement_type: Type of measurement ('power', 'current', 'phase')
            progress_data: Progress data dictionary
        """
        if measurement_type == "power":
            self._update_power_progress(progress_data)
        elif measurement_type == "current":
            self._update_current_progress(progress_data)
        elif measurement_type == "phase":
            self._update_phase_progress(progress_data)
    
    def _update_power_progress(self, progress_data: Dict) -> None:
        """Update power measurement progress."""
        wavelength = progress_data.get('wavelength', 0)
        power = progress_data.get('power', 0)
        progress_percent = progress_data.get('progress_percent', 0)
        
        # Update plot
        plot_widget = self.measurement_tab.get_plot_widget()
        power_plot = plot_widget.get_power_plot()
        power_plot.add_power_point(wavelength, power)
        
        # Update status
        status_display = self.measurement_tab.get_status_display()
        status_display.update_progress(
            int(progress_percent),
            f"Power measurement: {wavelength:.1f} nm"
        )
    
    def _update_current_progress(self, progress_data: Dict) -> None:
        """Update current measurement progress."""
        wavelength = progress_data.get('wavelength', 0)
        current = progress_data.get('current', 0)
        progress_percent = progress_data.get('progress_percent', 0)
        
        # Update plot
        plot_widget = self.measurement_tab.get_plot_widget()
        current_plot = plot_widget.get_current_plot()
        current_plot.add_current_point(wavelength, current)
        
        # Update status
        status_display = self.measurement_tab.get_status_display()
        status_display.update_progress(
            int(progress_percent),
            f"Current measurement: {wavelength:.1f} nm (Pixel {self._current_pixel_number})"
        )
    
    def _update_phase_progress(self, progress_data: Dict) -> None:
        """Update phase adjustment progress."""
        phase = progress_data.get('phase', 0)
        signal = progress_data.get('signal', 0)
        
        # Update plot
        plot_widget = self.measurement_tab.get_plot_widget()
        phase_plot = plot_widget.get_phase_plot()
        phase_plot.add_phase_point(phase, signal)
        
        # Update status
        status_display = self.measurement_tab.get_status_display()
        status_display.set_status_message(
            f"Phase adjustment: {phase:.1f}° (Pixel {self._current_pixel_number})"
        )
    
    def _on_experiment_complete(self, success: bool, message: str) -> None:
        """
        Handle experiment completion.
        
        Args:
            success: Whether the experiment completed successfully
            message: Completion message
        """
        # Update status
        status_display = self.measurement_tab.get_status_display()
        status_display.clear_progress()
        status_display.set_status_message(message)
        
        # Reset button states
        plot_widget = self.measurement_tab.get_plot_widget()
        plot_widget.set_power_measuring(False)
        plot_widget.set_current_measuring(False)

        # Re-enable controls
        monochromator_control = self.measurement_tab.get_monochromator_control()
        monochromator_control.set_enabled(True)
        status_display.set_live_monitor_enabled(True)
        
        # Show completion message
        if success:
            if self._current_measurement_type:
                self._offer_data_save()
        else:
            QMessageBox.warning(self, "Measurement Failed", message)
        
        # Reset measurement state
        self._current_measurement_type = None
        self._current_pixel_number = None
    
    def _offer_data_save(self) -> None:
        """Offer to save measurement data."""
        if not self.experiment_model or not self._current_measurement_type:
            return
        
        try:
            # Generate filename
            params = self.experiment_model.get_measurement_parameters()
            cell_number = params.get('cell_number', 'unknown')
            
            if self._current_measurement_type == "power":
                filename = self.data_handler.generate_filename("power", cell_number)
                filter_str = "CSV files (*.csv)"
                
                file_path, _ = QFileDialog.getSaveFileName(
                    self, "Save Power Data", filename, filter_str
                )
                
                if file_path:
                    self.experiment_model.save_power_data(file_path)
                    QMessageBox.information(self, "Data Saved", f"Power data saved to {file_path}")
            
            elif self._current_measurement_type == "current":
                filename = self.data_handler.generate_filename(
                    "current", cell_number, self._current_pixel_number
                )
                filter_str = "CSV files (*.csv)"
                
                file_path, _ = QFileDialog.getSaveFileName(
                    self, "Save Current Data", filename, filter_str
                )
                
                if file_path:
                    self.experiment_model.save_current_data(file_path)
                    QMessageBox.information(self, "Data Saved", f"Current data saved to {file_path}")
                    
                    # Offer to save phase data if enabled in config
                    from ..config.settings import GUI_CONFIG
                    if GUI_CONFIG.get("prompt_phase_data_save", False):
                        self._offer_phase_data_save(cell_number)
            
        except (EQEExperimentError, DataValidationError) as e:
            self._show_error(f"Failed to save data: {e}")
    
    def _offer_phase_data_save(self, cell_number: str) -> None:
        """Offer to save phase adjustment data."""
        if not self.experiment_model:
            return
        
        try:
            # Check if phase data exists
            phase_model = self.experiment_model.phase_model
            if phase_model and phase_model.optimal_phase is not None:
                filename = self.data_handler.generate_filename("phase", cell_number)
                filter_str = "CSV files (*.csv)"
                
                file_path, _ = QFileDialog.getSaveFileName(
                    self, "Save Phase Data", filename, filter_str
                )
                
                if file_path:
                    self.experiment_model.save_phase_data(file_path)
                    QMessageBox.information(self, "Data Saved", f"Phase data saved to {file_path}")
                    
                    # Check R-squared value and warn if low
                    min_r_squared = PHASE_ADJUSTMENT_CONFIG["min_r_squared"]
                    if phase_model.r_squared is not None and phase_model.r_squared < min_r_squared:
                        QMessageBox.warning(
                            self, "Low R² Value",
                            ERROR_MESSAGES["low_r_squared"].format(pixel=self._current_pixel_number)
                        )
        
        except (EQEExperimentError, DataValidationError) as e:
            self._show_error(f"Failed to save phase data: {e}")
    
    def _start_power_measurement(self) -> None:
        """Start power measurement."""
        if not self.experiment_model:
            self._show_error("Experiment model not initialized")
            return

        # Ensure cell number is set before measurement
        if not self._ensure_cell_number():
            return  # User cancelled

        try:
            # Validate parameters
            parameter_input = self.measurement_tab.get_parameter_input()
            is_valid, error_msg = parameter_input.validate_parameters()
            if not is_valid:
                self._show_error(error_msg)
                return
            
            # Clear power plot
            plot_widget = self.measurement_tab.get_plot_widget()
            plot_widget.get_power_plot().clear_plot()
            
            # Stop live signal monitor if running
            self.experiment_model.stop_live_signal_monitor()
            status_display = self.measurement_tab.get_status_display()
            status_display.stop_live_monitor()

            # Start measurement
            if self.experiment_model.start_power_measurement():
                self._current_measurement_type = "power"
                plot_widget.set_power_measuring(True)

                # Disable controls during measurement
                monochromator_control = self.measurement_tab.get_monochromator_control()
                monochromator_control.set_enabled(False)
                status_display.set_live_monitor_enabled(False)

                status_display.set_status_message("Starting power measurement...")
        
        except EQEExperimentError as e:
            self._show_error(f"Failed to start power measurement: {e}")
    
    def _start_current_measurement(self, pixel_number: int) -> None:
        """
        Start current measurement for specified pixel.

        Args:
            pixel_number: Pixel number to measure
        """
        if not self.experiment_model:
            self._show_error("Experiment model not initialized")
            return

        # Ensure cell number is set before measurement
        if not self._ensure_cell_number():
            return  # User cancelled

        try:
            # Validate parameters
            parameter_input = self.measurement_tab.get_parameter_input()
            is_valid, error_msg = parameter_input.validate_parameters()
            if not is_valid:
                self._show_error(error_msg)
                return
            
            # Set pixel number in plots
            plot_widget = self.measurement_tab.get_plot_widget()
            plot_widget.set_pixel_number(pixel_number)
            
            # Clear current and phase plots
            plot_widget.get_current_plot().clear_plot()
            plot_widget.get_phase_plot().clear_plot()
            
            # Stop live signal monitor if running
            self.experiment_model.stop_live_signal_monitor()
            status_display = self.measurement_tab.get_status_display()
            status_display.stop_live_monitor()

            # Start phase adjustment first
            self._current_pixel_number = pixel_number
            self._current_measurement_type = None  # Reset to ensure continuation logic works
            if self.experiment_model.start_phase_adjustment(pixel_number):
                # Disable controls during measurement
                monochromator_control = self.measurement_tab.get_monochromator_control()
                monochromator_control.set_enabled(False)
                status_display.set_live_monitor_enabled(False)

                status_display.set_status_message(f"Starting phase adjustment for pixel {pixel_number}...")

                # Phase adjustment will complete, then we'll start current measurement
                # This is handled in _update_status() which checks for phase completion
        
        except EQEExperimentError as e:
            self._show_error(f"Failed to start current measurement: {e}")
    
    def _continue_with_current_measurement(self) -> None:
        """Continue with current measurement after phase adjustment."""
        if not self.experiment_model or self._current_pixel_number is None:
            return
        
        # Check if we've already triggered continuation
        if self._current_measurement_type == "current":
            return
        
        # Mark that we're attempting to start current measurement
        # This prevents multiple calls to this function
        self._current_measurement_type = "current"
        
        try:
            # Update phase plot with results
            phase_model = self.experiment_model.phase_model
            plot_widget = self.measurement_tab.get_plot_widget()
            if phase_model:
                phase_data = phase_model.get_adjustment_data()
                phase_plot = plot_widget.get_phase_plot()
                phase_plot.update_phase_data(
                    phase_data['phase_data'],
                    phase_data['signal_data'],
                    phase_data['fit_phases'],
                    phase_data['fit_signals']
                )
            
            # Start current measurement
            if self.experiment_model.start_current_measurement(self._current_pixel_number):
                plot_widget.set_current_measuring(True)
                # Auto-switch to Current Measurement tab to show stats
                self.measurement_tab.show_current_measurement_tab()
                status_display = self.measurement_tab.get_status_display()
                status_display.set_status_message(f"Starting current measurement for pixel {self._current_pixel_number}...")
            else:
                # Failed to start - reset flag so it can be retried
                self._current_measurement_type = None
                self._show_error("Failed to start current measurement")
        
        except EQEExperimentError as e:
            # Failed to start - reset flag so it can be retried
            self._current_measurement_type = None
            self._show_error(f"Failed to continue with current measurement: {e}")
    
    def _on_align_button_clicked(self) -> None:
        """Handle alignment button click."""
        # Check if in offline mode
        from ..config import settings
        if settings.OFFLINE_MODE:
            QMessageBox.warning(
                self, 
                "Offline Mode",
                "Cannot control hardware in OFFLINE mode.\n\n"
                "Restart the application without the --offline flag to use hardware."
            )
            return
        
        self._align_monochromator()
    
    def _align_monochromator(self) -> None:
        """Align monochromator for visual check."""
        if not self.experiment_model:
            self._show_error("Experiment model not initialized")
            return
        
        try:
            self.experiment_model.align_monochromator()
            alignment_wl = PHASE_ADJUSTMENT_CONFIG["alignment_wavelength"]
            status_display = self.measurement_tab.get_status_display()
            status_display.set_status_message(f"Monochromator aligned at {alignment_wl} nm")

        except EQEExperimentError as e:
            self._show_error(f"Failed to align monochromator: {e}")
        except Exception as e:
            self._show_error(f"Unexpected error during alignment: {e}")

    def _on_live_monitor_requested(self, start: bool) -> None:
        """Handle live signal monitor toggle."""
        if not self.experiment_model:
            self._show_error("Experiment model not initialized")
            self.measurement_tab.stop_live_monitor()
            return

        try:
            if start:
                self.experiment_model.start_live_signal_monitor()
                status_display = self.measurement_tab.get_status_display()
                status_display.set_status_message("Live signal monitor active (523 nm)")
            else:
                self.experiment_model.stop_live_signal_monitor()
                status_display = self.measurement_tab.get_status_display()
                status_display.set_status_message("Ready")

        except EQEExperimentError as e:
            self._show_error(f"Live monitor error: {e}")
            self.measurement_tab.stop_live_monitor()

    def _on_live_signal_update(self, current_nA: float) -> None:
        """Handle live signal update from experiment model."""
        self.measurement_tab.update_live_signal(current_nA)

    def _on_wavelength_change_requested(self, wavelength: float) -> None:
        """Handle wavelength change request from UI."""
        if not self.experiment_model:
            self._show_error("Experiment model not initialized")
            return

        try:
            self.experiment_model.set_wavelength_manual(wavelength)
            status_display = self.measurement_tab.get_status_display()
            status_display.set_status_message(f"Wavelength set to {wavelength:.1f} nm")

        except EQEExperimentError as e:
            self._show_error(f"Failed to set wavelength: {e}")

    def _on_shutter_open_requested(self) -> None:
        """Handle shutter open request from UI."""
        if not self.experiment_model:
            self._show_error("Experiment model not initialized")
            return

        try:
            self.experiment_model.open_shutter_manual()
            status_display = self.measurement_tab.get_status_display()
            status_display.set_status_message("Shutter opened")

        except EQEExperimentError as e:
            self._show_error(f"Failed to open shutter: {e}")

    def _on_shutter_close_requested(self) -> None:
        """Handle shutter close request from UI."""
        if not self.experiment_model:
            self._show_error("Experiment model not initialized")
            return

        try:
            self.experiment_model.close_shutter_manual()
            status_display = self.measurement_tab.get_status_display()
            status_display.set_status_message("Shutter closed")

        except EQEExperimentError as e:
            self._show_error(f"Failed to close shutter: {e}")

    def _on_monochromator_state_changed(self, wavelength: float, shutter_open: bool,
                                        filter_number: int) -> None:
        """Handle monochromator state change from model."""
        self.measurement_tab.update_monochromator_state(wavelength, shutter_open, filter_number)

    def _stop_measurement(self) -> None:
        """Stop current measurement."""
        if self.experiment_model:
            self.experiment_model.stop_all_measurements()
            self.experiment_model.stop_live_signal_monitor()

            # Reset button states
            plot_widget = self.measurement_tab.get_plot_widget()
            plot_widget.set_power_measuring(False)
            plot_widget.set_current_measuring(False)

            # Stop live monitor UI
            self.measurement_tab.stop_live_monitor()

            status_display = self.measurement_tab.get_status_display()
            status_display.set_status_message("Measurement stopped")
    
    def _update_status(self) -> None:
        """Periodic status update."""
        if not self.experiment_model:
            return
        
        # Update measurement status in plot widget buttons
        measurement_status = self.experiment_model.get_measurement_status()
        
        plot_widget = self.measurement_tab.get_plot_widget()
        # Only update if states have changed to avoid flicker
        current_power_state = plot_widget._power_measuring
        current_current_state = plot_widget._current_measuring
        
        if current_power_state != measurement_status['power_measuring']:
            plot_widget.set_power_measuring(measurement_status['power_measuring'])
        
        if current_current_state != measurement_status['current_measuring']:
            plot_widget.set_current_measuring(measurement_status['current_measuring'])
        
        # Handle phase adjustment completion - automatically continue with current measurement
        if (self._current_pixel_number is not None and 
            not measurement_status['phase_adjusting'] and
            not measurement_status['current_measuring'] and
            self._current_measurement_type != "current"):
            # Phase adjustment completed, start current measurement
            self._continue_with_current_measurement()
    
    def _show_error(self, message: str) -> None:
        """
        Show error message to user.

        Args:
            message: Error message to display
        """
        QMessageBox.critical(self, "Error", message)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """
        Handle key press events.

        Ctrl+Shift+E toggles hidden staff mode (EQE Analysis tab).
        Ctrl+Shift+D toggles staff debug mode (technical debug output in console).
        """
        if event.modifiers() == (Qt.ControlModifier | Qt.ShiftModifier):
            if event.key() == Qt.Key_E:
                self._toggle_staff_mode()
            elif event.key() == Qt.Key_D:
                self._toggle_debug_mode()
            else:
                super().keyPressEvent(event)
        else:
            super().keyPressEvent(event)

    def _toggle_staff_mode(self) -> None:
        """Toggle hidden staff mode (EQE Analysis tab)."""
        if self._staff_mode_enabled:
            # Hide the EQE Analysis tab
            index = self.tab_widget.indexOf(self.eqe_analysis_tab)
            if index >= 0:
                self.tab_widget.removeTab(index)
            self._staff_mode_enabled = False
            self.logger.info("Staff mode disabled")
        else:
            # Show the EQE Analysis tab
            self.tab_widget.addTab(self.eqe_analysis_tab, "EQE Analysis")
            # Give it access to the experiment model for session data
            if self.experiment_model:
                self.eqe_analysis_tab.set_experiment_model(self.experiment_model)
            self._staff_mode_enabled = True
            # Switch to the new tab
            self.tab_widget.setCurrentWidget(self.eqe_analysis_tab)
            self.logger.info("Staff mode enabled (Ctrl+Shift+E)")

    def _toggle_debug_mode(self) -> None:
        """
        Toggle staff debug mode.

        When enabled, technical debug output (samples, timebases, SDK calls)
        appears in the console. When disabled, only INFO-level messages appear.

        This is for staff troubleshooting only - students should not need this.
        """
        self._staff_debug_mode = not self._staff_debug_mode
        TieredLogger.set_staff_debug_mode(self._staff_debug_mode)

        if self._staff_debug_mode:
            self.logger.info("Staff debug mode ENABLED (Ctrl+Shift+D) - technical output visible in console")
            QMessageBox.information(
                self,
                "Debug Mode Enabled",
                "Staff debug mode is now ON.\n\n"
                "Technical debug output (samples, timebases, SDK calls) "
                "will appear in the console.\n\n"
                "Press Ctrl+Shift+D again to disable."
            )
        else:
            self.logger.info("Staff debug mode disabled")
            QMessageBox.information(
                self,
                "Debug Mode Disabled",
                "Staff debug mode is now OFF.\n\n"
                "Technical output hidden from console."
            )

    def closeEvent(self, event) -> None:
        """Handle application close event."""
        # Stop the status timer first to prevent callbacks during cleanup
        if hasattr(self, 'status_timer') and self.status_timer:
            self.status_timer.stop()

        # Stop stability test if running
        if hasattr(self, 'stability_model') and self.stability_model:
            try:
                self.stability_model.stop_test()
            except Exception as e:
                print(f"Error stopping stability test: {e}")

        if self.experiment_model:
            try:
                # Stop live monitor if active
                self.experiment_model.stop_live_signal_monitor()

                # Stop all measurements
                self.experiment_model.stop_all_measurements()

                # Clean up resources
                self.experiment_model.cleanup()
            except Exception as e:
                print(f"Error during cleanup: {e}")

        event.accept()


def create_application() -> QApplication:
    """
    Create and configure the QApplication instance.
    
    Returns:
        QApplication: Configured application instance
    """
    app = QApplication(sys.argv)
    app.setApplicationName("EQE Measurement Application")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("PHYS 2150 Lab")
    
    return app