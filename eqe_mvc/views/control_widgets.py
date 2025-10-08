"""
Control Panel Components

This module contains control widgets for user input and measurement control.
Includes parameter input forms, control buttons, and status displays.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QFormLayout,
    QPushButton, QLineEdit, QLabel, QGroupBox, QSpinBox, QDoubleSpinBox,
    QMessageBox, QProgressBar, QTextEdit, QSplitter
)
from PySide6.QtCore import Qt, Signal, QTimer
from typing import Dict, List, Optional, Tuple, Any  # Add Any to the import
import re

from ..config.settings import (
    DEFAULT_MEASUREMENT_PARAMS, GUI_CONFIG, VALIDATION_PATTERNS, ERROR_MESSAGES
)


class ParameterInputWidget(QGroupBox):
    """Widget for inputting measurement parameters."""
    
    # Signals
    parameters_changed = Signal(dict)  # Emitted when parameters change
    
    def __init__(self, parent=None):
        """Initialize the parameter input widget."""
        super().__init__("Measurement Parameters", parent)
        
        # Create input fields
        self.start_wavelength = QDoubleSpinBox()
        self.end_wavelength = QDoubleSpinBox()
        self.step_size = QDoubleSpinBox()
        self.cell_number = QLineEdit()
        
        self._setup_inputs()
        self._setup_layout()
        self._connect_signals()
        
        # Load default values
        self.load_parameters(DEFAULT_MEASUREMENT_PARAMS)
    
    def _setup_inputs(self) -> None:
        """Configure input field properties."""
        font_size = GUI_CONFIG["font_sizes"]["label"]
        
        # Wavelength inputs
        self.start_wavelength.setRange(200, 1200)
        self.start_wavelength.setSuffix(" nm")
        self.start_wavelength.setDecimals(1)
        self.start_wavelength.setStyleSheet(f"font-size: {font_size}px;")
        
        self.end_wavelength.setRange(200, 1200)
        self.end_wavelength.setSuffix(" nm")
        self.end_wavelength.setDecimals(1)
        self.end_wavelength.setStyleSheet(f"font-size: {font_size}px;")
        
        # Step size input
        self.step_size.setRange(0.1, 100)
        self.step_size.setSuffix(" nm")
        self.step_size.setDecimals(1)
        self.step_size.setStyleSheet(f"font-size: {font_size}px;")
        
        # Cell number input
        self.cell_number.setPlaceholderText("e.g., C60_01 or 2501-04")
        self.cell_number.setStyleSheet(f"font-size: {font_size}px;")
    
    def _setup_layout(self) -> None:
        """Set up the widget layout."""
        layout = QFormLayout()
        font_size = GUI_CONFIG["font_sizes"]["label"]
        
        # Create labels with consistent styling
        start_label = QLabel("Start Wavelength:")
        end_label = QLabel("End Wavelength:")
        step_label = QLabel("Step Size:")
        cell_label = QLabel("Cell Number:")
        
        for label in [start_label, end_label, step_label, cell_label]:
            label.setStyleSheet(f"font-size: {font_size}px;")
        
        # Add fields to layout
        layout.addRow(start_label, self.start_wavelength)
        layout.addRow(end_label, self.end_wavelength)
        layout.addRow(step_label, self.step_size)
        layout.addRow(cell_label, self.cell_number)
        
        self.setLayout(layout)
    
    def _connect_signals(self) -> None:
        """Connect input field signals."""
        self.start_wavelength.valueChanged.connect(self._on_parameter_changed)
        self.end_wavelength.valueChanged.connect(self._on_parameter_changed)
        self.step_size.valueChanged.connect(self._on_parameter_changed)
        self.cell_number.textChanged.connect(self._on_parameter_changed)
    
    def _on_parameter_changed(self) -> None:
        """Handle parameter change."""
        params = self.get_parameters()
        self.parameters_changed.emit(params)
    
    def get_parameters(self) -> Dict[str, Any]:
        """
        Get current parameter values.
        
        Returns:
            Dict[str, Any]: Current parameter values
        """
        return {
            'start_wavelength': self.start_wavelength.value(),
            'end_wavelength': self.end_wavelength.value(),
            'step_size': self.step_size.value(),
            'cell_number': self.cell_number.text().strip()
        }
    
    def load_parameters(self, params: Dict[str, Any]) -> None:
        """
        Load parameter values into the input fields.
        
        Args:
            params: Parameter dictionary to load
        """
        # Temporarily disconnect signals to avoid recursive updates
        self._disconnect_signals()
        
        try:
            if 'start_wavelength' in params:
                self.start_wavelength.setValue(params['start_wavelength'])
            if 'end_wavelength' in params:
                self.end_wavelength.setValue(params['end_wavelength'])
            if 'step_size' in params:
                self.step_size.setValue(params['step_size'])
            if 'cell_number' in params:
                self.cell_number.setText(str(params['cell_number']))
        finally:
            # Reconnect signals
            self._connect_signals()
    
    def _disconnect_signals(self) -> None:
        """Temporarily disconnect signals."""
        self.start_wavelength.valueChanged.disconnect()
        self.end_wavelength.valueChanged.disconnect()
        self.step_size.valueChanged.disconnect()
        self.cell_number.textChanged.disconnect()
    
    def validate_parameters(self) -> Tuple[bool, str]:
        """
        Validate current parameter values.
        
        Returns:
            Tuple[bool, str]: (is_valid, error_message)
        """
        params = self.get_parameters()
        
        # Validate cell number format
        cell_number = params['cell_number']
        if not cell_number:
            return False, "Cell number is required"
        
        pattern = VALIDATION_PATTERNS["cell_number"]
        if not re.match(pattern, cell_number):
            return False, ERROR_MESSAGES["invalid_cell_number"]
        
        # Validate wavelength range
        if params['start_wavelength'] >= params['end_wavelength']:
            return False, "Start wavelength must be less than end wavelength"
        
        # Validate step size
        if params['step_size'] <= 0:
            return False, "Step size must be positive"
        
        return True, ""


class ControlButtonWidget(QWidget):
    """Widget containing measurement control buttons."""
    
    # Signals
    power_measurement_requested = Signal()
    current_measurement_requested = Signal(int)  # pixel number
    phase_adjustment_requested = Signal(int)     # pixel number
    alignment_requested = Signal()
    stop_requested = Signal()
    
    def __init__(self, parent=None):
        """Initialize the control button widget."""
        super().__init__(parent)
        
        # Create buttons
        self.power_button = QPushButton("Start Power Measurement")
        self.current_button = QPushButton("Start Current Measurement")
        self.align_button = QPushButton("Enable Green Alignment Dot")
        
        self._setup_buttons()
        self._setup_layout()
        self._connect_signals()
        
        # Button states
        self._power_measuring = False
        self._current_measuring = False
        self._phase_adjusting = False
    
    def _setup_buttons(self) -> None:
        """Configure button properties."""
        font_size = GUI_CONFIG["font_sizes"]["button"]
        button_height = 30
        start_color = GUI_CONFIG["colors"]["start_button"]
        
        # Power measurement button
        self.power_button.setStyleSheet(f"font-size: {font_size}px; background-color: {start_color}; color: black;")
        self.power_button.setFixedHeight(button_height)
        
        # Current measurement button
        self.current_button.setStyleSheet(f"font-size: {font_size}px; background-color: {start_color}; color: black;")
        self.current_button.setFixedHeight(button_height)
        
        # Alignment button
        self.align_button.setStyleSheet(f"font-size: {font_size}px; background-color: {start_color}; color: black;")
        self.align_button.setFixedHeight(button_height)
    
    def _setup_layout(self) -> None:
        """Set up the widget layout."""
        layout = QVBoxLayout()
        layout.addWidget(self.power_button)
        layout.addWidget(self.current_button)
        layout.addWidget(self.align_button)
        layout.addStretch()
        self.setLayout(layout)
    
    def _connect_signals(self) -> None:
        """Connect button signals."""
        self.power_button.clicked.connect(self._on_power_button_clicked)
        self.current_button.clicked.connect(self._on_current_button_clicked)
        self.align_button.clicked.connect(self.alignment_requested.emit)
    
    def _on_power_button_clicked(self) -> None:
        """Handle power measurement button click."""
        if self._power_measuring:
            self.stop_requested.emit()
        else:
            self.power_measurement_requested.emit()
    
    def _on_current_button_clicked(self) -> None:
        """Handle current measurement button click."""
        if self._current_measuring:
            self.stop_requested.emit()
        else:
            # Get pixel number from user
            pixel_number = self._get_pixel_number()
            if pixel_number is not None:
                self.current_measurement_requested.emit(pixel_number)
    
    def _get_pixel_number(self) -> Optional[int]:
        """Get pixel number from user input."""
        from PySide6.QtWidgets import QInputDialog
        
        pixel_number, ok = QInputDialog.getInt(
            self, "Pixel Selection", "Enter pixel number (1-6):",
            value=1, min=1, max=6
        )
        
        if ok:
            return pixel_number
        return None
    
    def set_power_measuring(self, measuring: bool) -> None:
        """
        Update power measurement button state.
        
        Args:
            measuring: True if measurement is in progress
        """
        self._power_measuring = measuring
        
        if measuring:
            self.power_button.setText("Stop Power Measurement")
            self.power_button.setStyleSheet(
                f"font-size: {GUI_CONFIG['font_sizes']['button']}px; "
                f"background-color: {GUI_CONFIG['colors']['stop_button']}; color: black;"
            )
        else:
            self.power_button.setText("Start Power Measurement")
            self.power_button.setStyleSheet(
                f"font-size: {GUI_CONFIG['font_sizes']['button']}px; "
                f"background-color: {GUI_CONFIG['colors']['start_button']}; color: black;"
            )
    
    def set_current_measuring(self, measuring: bool) -> None:
        """
        Update current measurement button state.
        
        Args:
            measuring: True if measurement is in progress
        """
        self._current_measuring = measuring
        
        if measuring:
            self.current_button.setText("Stop Current Measurement")
            self.current_button.setStyleSheet(
                f"font-size: {GUI_CONFIG['font_sizes']['button']}px; "
                f"background-color: {GUI_CONFIG['colors']['stop_button']}; color: black;"
            )
        else:
            self.current_button.setText("Start Current Measurement")
            self.current_button.setStyleSheet(
                f"font-size: {GUI_CONFIG['font_sizes']['button']}px; "
                f"background-color: {GUI_CONFIG['colors']['start_button']}; color: black;"
            )
    
    def set_enabled(self, enabled: bool) -> None:
        """Enable or disable all buttons."""
        self.power_button.setEnabled(enabled)
        self.current_button.setEnabled(enabled)
        self.align_button.setEnabled(enabled)


class StatusDisplayWidget(QWidget):
    """Widget for displaying system status and progress."""
    
    def __init__(self, parent=None):
        """Initialize the status display widget."""
        super().__init__(parent)
        
        # Create status components
        self.device_status = QTextEdit()
        self.progress_bar = QProgressBar()
        self.status_label = QLabel("Ready")
        
        self._setup_components()
        self._setup_layout()
    
    def _setup_components(self) -> None:
        """Configure status display components."""
        # Device status text area
        self.device_status.setMaximumHeight(100)
        self.device_status.setReadOnly(True)
        self.device_status.setStyleSheet("font-family: monospace; font-size: 10px;")
        
        # Progress bar
        self.progress_bar.setVisible(False)
        self.progress_bar.setRange(0, 100)
        
        # Status label
        font_size = GUI_CONFIG["font_sizes"]["label"]
        self.status_label.setStyleSheet(f"font-size: {font_size}px; font-weight: bold;")
        self.status_label.setAlignment(Qt.AlignCenter)
    
    def _setup_layout(self) -> None:
        """Set up the widget layout."""
        layout = QVBoxLayout()
        
        # Device status group
        device_group = QGroupBox("Device Status")
        device_layout = QVBoxLayout()
        device_layout.addWidget(self.device_status)
        device_group.setLayout(device_layout)
        
        # Progress group
        progress_group = QGroupBox("Progress")
        progress_layout = QVBoxLayout()
        progress_layout.addWidget(self.status_label)
        progress_layout.addWidget(self.progress_bar)
        progress_group.setLayout(progress_layout)
        
        layout.addWidget(device_group)
        layout.addWidget(progress_group)
        layout.addStretch()
        
        self.setLayout(layout)
    
    def update_device_status(self, device_name: str, is_connected: bool, message: str = "") -> None:
        """
        Update device connection status.
        
        Args:
            device_name: Name of the device
            is_connected: Connection status
            message: Additional status message
        """
        status_text = "✓ Connected" if is_connected else "✗ Disconnected"
        full_message = f"{device_name}: {status_text}"
        if message:
            full_message += f" ({message})"
        
        # Update the device status display
        current_text = self.device_status.toPlainText()
        lines = current_text.split('\n') if current_text else []
        
        # Update or add device status line
        updated = False
        for i, line in enumerate(lines):
            if line.startswith(device_name + ":"):
                lines[i] = full_message
                updated = True
                break
        
        if not updated:
            lines.append(full_message)
        
        self.device_status.setPlainText('\n'.join(lines))
    
    def update_progress(self, value: int, message: str = "") -> None:
        """
        Update measurement progress.
        
        Args:
            value: Progress value (0-100)
            message: Progress message
        """
        self.progress_bar.setValue(value)
        
        if message:
            self.status_label.setText(message)
        
        # Show progress bar when measurement is active
        self.progress_bar.setVisible(value > 0 and value < 100)
    
    def set_status_message(self, message: str) -> None:
        """Set the main status message."""
        self.status_label.setText(message)
    
    def clear_progress(self) -> None:
        """Clear progress display."""
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
        self.status_label.setText("Ready")


class MainControlPanel(QWidget):
    """
    Main control panel containing all control widgets.
    
    Combines parameter input, control buttons, and status display
    into a unified control interface.
    """
    
    def __init__(self, parent=None):
        """Initialize the main control panel."""
        super().__init__(parent)
        
        # Create component widgets
        self.parameter_input = ParameterInputWidget()
        self.control_buttons = ControlButtonWidget()
        self.status_display = StatusDisplayWidget()
        
        self._setup_layout()
    
    def _setup_layout(self) -> None:
        """Set up the control panel layout."""
        # Create splitter for resizable sections
        splitter = QSplitter(Qt.Vertical)
        
        # Add widgets to splitter
        splitter.addWidget(self.parameter_input)
        splitter.addWidget(self.control_buttons)
        splitter.addWidget(self.status_display)
        
        # Set initial sizes (give more space to parameters and status)
        splitter.setSizes([300, 150, 200])
        
        # Main layout
        layout = QVBoxLayout()
        layout.addWidget(splitter)
        self.setLayout(layout)
    
    def get_parameter_input(self) -> ParameterInputWidget:
        """Get the parameter input widget."""
        return self.parameter_input
    
    def get_control_buttons(self) -> ControlButtonWidget:
        """Get the control buttons widget."""
        return self.control_buttons
    
    def get_status_display(self) -> StatusDisplayWidget:
        """Get the status display widget."""
        return self.status_display