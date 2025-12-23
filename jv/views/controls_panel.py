"""
JV Controls Panel

This view component provides the input fields and control buttons for
J-V measurement parameters.
"""

from typing import Optional, Dict, Any
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QGridLayout,
    QPushButton, QLineEdit, QLabel,
    QSpacerItem, QSizePolicy,
)
from PySide6.QtCore import Qt, Signal

from ..config.settings import GUI_CONFIG, DEFAULT_MEASUREMENT_PARAMS


class JVControlsPanel(QWidget):
    """
    Panel containing measurement parameter inputs and control buttons.

    Signals:
        start_requested: Emitted when start button clicked
        stop_requested: Emitted when stop button clicked
    """

    start_requested = Signal()
    stop_requested = Signal()

    def __init__(self, parent: Optional[QWidget] = None):
        """
        Initialize the controls panel.

        Args:
            parent: Parent widget
        """
        super().__init__(parent)

        self.font_sizes = GUI_CONFIG["font_sizes"]
        self.colors = GUI_CONFIG["colors"]

        # Track button state
        self._is_measuring = False

        # Create UI
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the UI components."""
        layout = QVBoxLayout(self)

        # Grid for input fields
        grid = QGridLayout()
        grid.setVerticalSpacing(10)
        grid.setHorizontalSpacing(10)

        # Font style for labels and inputs
        label_style = f"font-size: {self.font_sizes['label']}px;"
        input_style = f"font-size: {self.font_sizes['input']}px;"

        # Row counter
        row = 0

        # Start Voltage
        start_voltage_label = QLabel("Start Voltage:")
        start_voltage_label.setStyleSheet(label_style)
        self.start_voltage_input = QLineEdit(
            str(DEFAULT_MEASUREMENT_PARAMS["start_voltage"])
        )
        self.start_voltage_input.setStyleSheet(input_style)
        self.start_voltage_input.setFixedHeight(30)
        grid.addWidget(start_voltage_label, row, 0)
        row += 1
        grid.addWidget(self.start_voltage_input, row, 0)
        row += 1

        # Stop Voltage
        stop_voltage_label = QLabel("Stop Voltage:")
        stop_voltage_label.setStyleSheet(label_style)
        self.stop_voltage_input = QLineEdit(
            str(DEFAULT_MEASUREMENT_PARAMS["stop_voltage"])
        )
        self.stop_voltage_input.setStyleSheet(input_style)
        self.stop_voltage_input.setFixedHeight(30)
        grid.addWidget(stop_voltage_label, row, 0)
        row += 1
        grid.addWidget(self.stop_voltage_input, row, 0)
        row += 1

        # Step Voltage
        step_voltage_label = QLabel("Step Voltage:")
        step_voltage_label.setStyleSheet(label_style)
        self.step_voltage_input = QLineEdit(
            str(DEFAULT_MEASUREMENT_PARAMS["step_voltage"])
        )
        self.step_voltage_input.setStyleSheet(input_style)
        self.step_voltage_input.setFixedHeight(30)
        grid.addWidget(step_voltage_label, row, 0)
        row += 1
        grid.addWidget(self.step_voltage_input, row, 0)
        row += 1

        # Spacer
        spacer1 = QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Fixed)
        grid.addItem(spacer1, row, 0)
        row += 1

        # Cell Number
        cell_number_label = QLabel("Cell Number:")
        cell_number_label.setStyleSheet(label_style)
        self.cell_number_input = QLineEdit("")
        self.cell_number_input.setStyleSheet(input_style)
        self.cell_number_input.setFixedHeight(30)
        self.cell_number_input.setReadOnly(True)  # Set via popup
        grid.addWidget(cell_number_label, row, 0)
        row += 1
        grid.addWidget(self.cell_number_input, row, 0)
        row += 1

        # Spacer
        spacer2 = QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Fixed)
        grid.addItem(spacer2, row, 0)
        row += 1

        # Start/Stop Measurement Button
        self.measure_button = QPushButton("Start Measurement")
        button_style = (
            f"font-size: {self.font_sizes['button']}px; "
            f"background-color: {self.colors['start_button']}; "
            "color: black;"
        )
        self.measure_button.setStyleSheet(button_style)
        self.measure_button.setFixedHeight(30)
        self.measure_button.clicked.connect(self._on_button_clicked)
        grid.addWidget(self.measure_button, row, 0, alignment=Qt.AlignHCenter)

        layout.addLayout(grid)
        layout.addStretch(1)  # Push controls to top

    def _on_button_clicked(self) -> None:
        """Handle measure button click."""
        if self._is_measuring:
            self.stop_requested.emit()
        else:
            self.start_requested.emit()

    def set_measuring_state(self, is_measuring: bool) -> None:
        """
        Update button state based on measurement status.

        Args:
            is_measuring: True if measurement in progress
        """
        self._is_measuring = is_measuring

        if is_measuring:
            self.measure_button.setText("Stop Measurement")
            self.measure_button.setStyleSheet(
                f"font-size: {self.font_sizes['button']}px; "
                f"background-color: {self.colors['stop_button']}; "
                "color: black;"
            )
            # Disable input fields during measurement
            self._set_inputs_enabled(False)
        else:
            self.measure_button.setText("Start Measurement")
            self.measure_button.setStyleSheet(
                f"font-size: {self.font_sizes['button']}px; "
                f"background-color: {self.colors['start_button']}; "
                "color: black;"
            )
            # Re-enable input fields
            self._set_inputs_enabled(True)

    def _set_inputs_enabled(self, enabled: bool) -> None:
        """Enable or disable input fields."""
        self.start_voltage_input.setEnabled(enabled)
        self.stop_voltage_input.setEnabled(enabled)
        self.step_voltage_input.setEnabled(enabled)
        # Cell number is always read-only but can be visually disabled
        # self.cell_number_input.setEnabled(enabled)

    def get_parameters(self) -> Dict[str, Any]:
        """
        Get current parameter values from inputs.

        Returns:
            Dict with parameter values
        """
        return {
            "start_voltage": self.start_voltage_input.text(),
            "stop_voltage": self.stop_voltage_input.text(),
            "step_voltage": self.step_voltage_input.text(),
            "cell_number": self.cell_number_input.text(),
        }

    def set_cell_number(self, cell_number: str) -> None:
        """
        Set the cell number display.

        Args:
            cell_number: Cell number string
        """
        self.cell_number_input.setText(cell_number)

    def get_cell_number(self) -> str:
        """Get the cell number."""
        return self.cell_number_input.text()

    def set_enabled(self, enabled: bool) -> None:
        """
        Enable or disable the entire panel.

        Args:
            enabled: True to enable, False to disable
        """
        self.measure_button.setEnabled(enabled)
        self._set_inputs_enabled(enabled)
