"""
JV Main Window

This view is the main application window that coordinates the controls panel
and plot widget, and connects to the experiment model.
"""

import re
from typing import Optional

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout,
    QMessageBox, QInputDialog, QFileDialog,
    QApplication,
)
from PySide6.QtCore import Qt, QTimer

from .plot_widget import JVPlotWidget
from .controls_panel import JVControlsPanel
from ..models.jv_experiment import JVExperimentModel, JVExperimentError
from ..models.jv_measurement import JVMeasurementResult
from ..utils.data_export import JVDataExporter
from ..config.settings import GUI_CONFIG, VALIDATION_PATTERNS


class JVMainWindow(QMainWindow):
    """
    Main application window for J-V characterization.

    Coordinates the controls panel, plot widget, and experiment model.
    """

    def __init__(self, parent: Optional[QWidget] = None):
        """
        Initialize the main window.

        Args:
            parent: Parent widget
        """
        super().__init__(parent)

        # Window configuration
        self.setWindowTitle(GUI_CONFIG["window_title"])
        geometry = GUI_CONFIG["window_geometry"]
        self.setGeometry(*geometry)

        # Experiment model (to be set externally)
        self.experiment_model: Optional[JVExperimentModel] = None

        # Data exporter
        self.data_exporter = JVDataExporter()

        # Create UI components
        self._setup_ui()

        # Connect view signals
        self._connect_signals()

    def _setup_ui(self) -> None:
        """Set up the UI layout."""
        # Main widget
        main_widget = QWidget()
        self.setCentralWidget(main_widget)

        # Horizontal layout: controls on left, plot on right
        main_layout = QHBoxLayout(main_widget)

        # Controls panel (left column)
        self.controls_panel = JVControlsPanel()

        # Calculate width based on screen size
        screen = QApplication.primaryScreen()
        screen_width = screen.size().width()
        input_width = int(
            screen_width * GUI_CONFIG.get("input_panel_width_fraction", 0.1)
        )
        self.controls_panel.setFixedWidth(input_width)

        # Plot widget (right column)
        self.plot_widget = JVPlotWidget()

        # Add to layout
        main_layout.addWidget(self.controls_panel)
        main_layout.addWidget(self.plot_widget)

        # Set stretch factors
        main_layout.setStretch(0, 1)  # Controls - minimal stretch
        main_layout.setStretch(1, 9)  # Plot - expands

    def _connect_signals(self) -> None:
        """Connect view signals to handlers."""
        self.controls_panel.start_requested.connect(self._on_start_requested)
        self.controls_panel.stop_requested.connect(self._on_stop_requested)

    def set_experiment_model(self, model: JVExperimentModel) -> None:
        """
        Set the experiment model and connect its signals.

        Args:
            model: JV experiment model
        """
        self.experiment_model = model

        # Connect model signals
        self.experiment_model.device_status_changed.connect(
            self._on_device_status_changed,
            Qt.QueuedConnection
        )
        self.experiment_model.measurement_progress.connect(
            self._on_measurement_progress,
            Qt.QueuedConnection
        )
        self.experiment_model.measurement_point.connect(
            self._on_measurement_point,
            Qt.QueuedConnection
        )
        self.experiment_model.measurement_complete.connect(
            self._on_measurement_complete,
            Qt.QueuedConnection
        )

    def show_cell_number_popup(self) -> bool:
        """
        Show popup to enter cell number.

        Returns:
            bool: True if cell number was set, False if cancelled
        """
        cell_pattern = VALIDATION_PATTERNS["cell_number"]

        while True:
            cell_number, ok = QInputDialog.getText(
                self,
                "Enter Cell Number",
                "Enter Cell Number (e.g., 195):"
            )

            if not ok:
                # User cancelled - allow them to explore the interface
                return False

            if cell_number and re.match(cell_pattern, cell_number):
                self.controls_panel.set_cell_number(cell_number)
                if self.experiment_model:
                    self.experiment_model.set_parameter("cell_number", cell_number)
                return True
            else:
                QMessageBox.warning(
                    self,
                    "Invalid Input",
                    "Cell number must be a 3-digit number (e.g., 195)."
                )

    def _on_start_requested(self) -> None:
        """Handle start measurement request from controls."""
        if not self.experiment_model:
            QMessageBox.critical(self, "Error", "Experiment model not initialized")
            return

        # Ensure cell number is set before measurement
        cell_number = self.controls_panel.get_cell_number()
        if not cell_number:
            if not self.show_cell_number_popup():
                return  # User cancelled

        # Prompt for pixel number
        pixel_range = VALIDATION_PATTERNS["pixel_range"]
        pixel_input, ok = QInputDialog.getText(
            self,
            "Pixel Selection",
            f"Enter pixel number ({pixel_range[0]}-{pixel_range[1]}):"
        )

        if not ok or not pixel_input:
            return

        try:
            pixel_number = int(pixel_input)
            if not (pixel_range[0] <= pixel_number <= pixel_range[1]):
                raise ValueError("Out of range")
        except ValueError:
            QMessageBox.critical(
                self,
                "Input Error",
                f"Pixel number must be between {pixel_range[0]} and {pixel_range[1]}."
            )
            return

        # Update parameters from controls
        params = self.controls_panel.get_parameters()
        try:
            self.experiment_model.set_parameters(
                start_voltage=float(params["start_voltage"]),
                stop_voltage=float(params["stop_voltage"]),
                step_voltage=float(params["step_voltage"]),
                cell_number=params["cell_number"],
            )
        except ValueError:
            QMessageBox.critical(
                self,
                "Input Error",
                "Please enter valid numerical values for voltages."
            )
            return

        # Clear plot and start measurement
        self.plot_widget.clear_plot(pixel_number)

        try:
            self.experiment_model.start_measurement(pixel_number)
            self.controls_panel.set_measuring_state(True)

            # Initialize forward line
            self.plot_widget.initialize_forward_line()

        except JVExperimentError as e:
            QMessageBox.critical(self, "Measurement Error", str(e))
            self.controls_panel.set_measuring_state(False)

    def _on_stop_requested(self) -> None:
        """Handle stop measurement request from controls."""
        if self.experiment_model:
            self.experiment_model.stop_measurement()
        self.controls_panel.set_measuring_state(False)

    def _on_device_status_changed(self, connected: bool, message: str) -> None:
        """Handle device status change."""
        if connected:
            self.controls_panel.set_enabled(True)
            print(f"Device connected: {message}")
        else:
            self.controls_panel.set_enabled(False)
            QMessageBox.critical(
                self,
                "Device Error",
                f"Device connection failed: {message}"
            )

    def _on_measurement_progress(
        self,
        direction: str,
        current_point: int,
        total_points: int,
        voltage: float,
        current: float,
    ) -> None:
        """Handle measurement progress update."""
        # Update plot periodically
        self.plot_widget.update_plot()
        QApplication.processEvents()

    def _on_measurement_point(
        self,
        direction: str,
        voltage: float,
        current: float,
    ) -> None:
        """Handle individual measurement point."""
        if direction == "forward":
            self.plot_widget.add_forward_point(voltage, current)
        else:
            # Initialize reverse line if needed
            if self.plot_widget.reverse_line is None:
                self.plot_widget.initialize_reverse_line()
            self.plot_widget.add_reverse_point(voltage, current)

    def _on_measurement_complete(
        self,
        success: bool,
        result: JVMeasurementResult,
    ) -> None:
        """Handle measurement completion."""
        # Update button state
        self.controls_panel.set_measuring_state(False)

        # Final plot update
        self.plot_widget.update_plot()

        if success and result.measurement_complete:
            print("Measurement complete.")

            # Prompt to save data
            cell_number = self.controls_panel.get_cell_number()
            if cell_number:
                self._prompt_save_data(result, cell_number)
        else:
            print("Measurement stopped or failed.")

    def _prompt_save_data(
        self,
        result: JVMeasurementResult,
        cell_number: str,
    ) -> None:
        """Prompt user to save measurement data."""
        # Generate default filename
        default_filename = self.data_exporter.generate_filename(
            cell_number,
            result.pixel_number
        )

        # Show save dialog
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save J-V Data",
            default_filename,
            "CSV files (*.csv)"
        )

        if file_path:
            try:
                self.data_exporter.save_measurement(result, file_path)
                print(f"Data saved to {file_path}")
            except Exception as e:
                QMessageBox.critical(
                    self,
                    "Save Error",
                    f"Failed to save file: {e}"
                )

    def closeEvent(self, event) -> None:
        """Handle window close event."""
        # Stop any running measurement
        if self.experiment_model:
            if self.experiment_model.is_measuring():
                self.experiment_model.stop_measurement()
            self.experiment_model.cleanup()

        event.accept()
