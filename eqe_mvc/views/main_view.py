"""
Main Application View

This module contains the main window and application view that coordinates
all GUI components and provides the primary user interface.
"""

import sys
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QMessageBox, 
    QFileDialog, QInputDialog, QApplication, QPushButton
)
from PySide6.QtCore import Qt, QTimer, Signal
from typing import Optional, Dict, Any

from ..models.eqe_experiment import EQEExperimentModel, EQEExperimentError
from ..utils.data_handling import DataHandler, DataValidationError
from ..config.settings import GUI_CONFIG, ERROR_MESSAGES, FILE_NAMING
from .plot_widgets import MultiPlotWidget
from .control_widgets import ParameterInputWidget, StatusDisplayWidget
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
        self.data_handler = DataHandler()
        
        # Create GUI components
        self.parameter_input = ParameterInputWidget()
        self.status_display = StatusDisplayWidget()
        self.plot_widget = MultiPlotWidget()
        
        # Set up layouts and connections
        self._setup_layout()
        self._connect_signals()
        
        # Initialize timers for periodic updates
        self._setup_timers()
        
        # Track current measurement state
        self._current_measurement_type: Optional[str] = None
        self._current_pixel_number: Optional[int] = None
        
        # Show cell number input on startup
        QTimer.singleShot(1000, self._show_initial_cell_number_dialog)
    
    def _setup_window(self) -> None:
        """Configure the main window properties."""
        self.setWindowTitle(GUI_CONFIG["window_title"])
        self.setGeometry(100, 100, *GUI_CONFIG["window_size"])
        
        # Show maximized
        self.showMaximized()
    
    def _setup_layout(self) -> None:
        """Set up the main window layout."""
        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main vertical layout
        main_layout = QVBoxLayout()
        main_layout.setSpacing(10)
        
        # Top row: Parameter input and Device Status side by side
        top_row = QHBoxLayout()
        top_row.addWidget(self.parameter_input)
        top_row.addWidget(self.status_display)
        main_layout.addLayout(top_row)
        
        # Middle section: Plots (takes most of the space, full width)
        main_layout.addWidget(self.plot_widget, stretch=3)
        
        central_widget.setLayout(main_layout)
    
    def _connect_signals(self) -> None:
        """Connect signals between GUI components."""
        # Parameter input signals
        self.parameter_input.parameters_changed.connect(self._on_parameters_changed)
        
        # Plot widget button signals
        self.plot_widget.power_measurement_requested.connect(self._start_power_measurement)
        self.plot_widget.current_measurement_requested.connect(self._start_current_measurement)
        self.plot_widget.stop_requested.connect(self._stop_measurement)
        
        # Status display alignment button signal
        self.status_display.alignment_requested.connect(self._on_align_button_clicked)
    
    def _setup_timers(self) -> None:
        """Set up periodic update timers."""
        # Status update timer
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self._update_status)
        self.status_timer.start(1000)  # Update every second
    
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
    
    def _show_initial_cell_number_dialog(self) -> None:
        """Show cell number input dialog on application startup."""
        cell_number, ok = QInputDialog.getText(
            self, "Enter Cell Number",
            "Enter Cell Number (three digits, e.g., 167, 001):"
        )
        
        if ok and cell_number:
            if self.data_handler.validate_cell_number(cell_number):
                current_params = self.parameter_input.get_parameters()
                current_params['cell_number'] = cell_number
                self.parameter_input.load_parameters(current_params)
            else:
                QMessageBox.warning(self, "Invalid Input", ERROR_MESSAGES["invalid_cell_number"])
                self._show_initial_cell_number_dialog()
        else:
            # User cancelled, show again
            self._show_initial_cell_number_dialog()
    
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
        self.status_display.update_device_status(device_name, is_connected, message)
        
        # Update control button states based on overall device status
        if self.experiment_model:
            device_status = self.experiment_model.get_device_status()
            all_connected = all(device_status.values())
            self.plot_widget.set_buttons_enabled(all_connected)
            self.status_display.align_button.setEnabled(all_connected)
    
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
        power_plot = self.plot_widget.get_power_plot()
        power_plot.add_power_point(wavelength, power)
        
        # Update status
        self.status_display.update_progress(
            int(progress_percent),
            f"Power measurement: {wavelength:.1f} nm"
        )
    
    def _update_current_progress(self, progress_data: Dict) -> None:
        """Update current measurement progress."""
        wavelength = progress_data.get('wavelength', 0)
        current = progress_data.get('current', 0)
        progress_percent = progress_data.get('progress_percent', 0)
        
        # Update plot
        current_plot = self.plot_widget.get_current_plot()
        current_plot.add_current_point(wavelength, current)
        
        # Update status
        self.status_display.update_progress(
            int(progress_percent),
            f"Current measurement: {wavelength:.1f} nm (Pixel {self._current_pixel_number})"
        )
    
    def _update_phase_progress(self, progress_data: Dict) -> None:
        """Update phase adjustment progress."""
        phase = progress_data.get('phase', 0)
        signal = progress_data.get('signal', 0)
        
        # Update plot
        phase_plot = self.plot_widget.get_phase_plot()
        phase_plot.add_phase_point(phase, signal)
        
        # Update status
        self.status_display.set_status_message(
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
        self.status_display.clear_progress()
        self.status_display.set_status_message(message)
        
        # Reset button states
        self.plot_widget.set_power_measuring(False)
        self.plot_widget.set_current_measuring(False)
        
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
                    if phase_model.r_squared is not None and phase_model.r_squared < 0.90:
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
        
        try:
            # Validate parameters
            is_valid, error_msg = self.parameter_input.validate_parameters()
            if not is_valid:
                self._show_error(error_msg)
                return
            
            # Clear power plot
            self.plot_widget.get_power_plot().clear_plot()
            
            # Start measurement
            if self.experiment_model.start_power_measurement():
                self._current_measurement_type = "power"
                self.plot_widget.set_power_measuring(True)
                
                self.status_display.set_status_message("Starting power measurement...")
        
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
        
        try:
            # Validate parameters
            is_valid, error_msg = self.parameter_input.validate_parameters()
            if not is_valid:
                self._show_error(error_msg)
                return
            
            # Set pixel number in plots
            self.plot_widget.set_pixel_number(pixel_number)
            
            # Clear current and phase plots
            self.plot_widget.get_current_plot().clear_plot()
            self.plot_widget.get_phase_plot().clear_plot()
            
            # Start phase adjustment first
            self._current_pixel_number = pixel_number
            self._current_measurement_type = None  # Reset to ensure continuation logic works
            if self.experiment_model.start_phase_adjustment(pixel_number):
                self.status_display.set_status_message(f"Starting phase adjustment for pixel {pixel_number}...")
                
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
            if phase_model:
                phase_data = phase_model.get_adjustment_data()
                phase_plot = self.plot_widget.get_phase_plot()
                phase_plot.update_phase_data(
                    phase_data['phase_data'],
                    phase_data['signal_data'],
                    phase_data['fit_phases'],
                    phase_data['fit_signals']
                )
            
            # Start current measurement
            if self.experiment_model.start_current_measurement(self._current_pixel_number):
                self.plot_widget.set_current_measuring(True)
                self.status_display.set_status_message(f"Starting current measurement for pixel {self._current_pixel_number}...")
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
            self.status_display.set_status_message("Monochromator aligned at 532 nm")
        
        except EQEExperimentError as e:
            self._show_error(f"Failed to align monochromator: {e}")
    
    def _stop_measurement(self) -> None:
        """Stop current measurement."""
        if self.experiment_model:
            self.experiment_model.stop_all_measurements()
            
            # Reset button states
            self.plot_widget.set_power_measuring(False)
            self.plot_widget.set_current_measuring(False)
            
            self.status_display.set_status_message("Measurement stopped")
    
    def _update_status(self) -> None:
        """Periodic status update."""
        if not self.experiment_model:
            return
        
        # Update measurement status in plot widget buttons
        measurement_status = self.experiment_model.get_measurement_status()
        
        # Only update if states have changed to avoid flicker
        current_power_state = self.plot_widget._power_measuring
        current_current_state = self.plot_widget._current_measuring
        
        if current_power_state != measurement_status['power_measuring']:
            self.plot_widget.set_power_measuring(measurement_status['power_measuring'])
        
        if current_current_state != measurement_status['current_measuring']:
            self.plot_widget.set_current_measuring(measurement_status['current_measuring'])
        
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
    
    def closeEvent(self, event) -> None:
        """Handle application close event."""
        if self.experiment_model:
            try:
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