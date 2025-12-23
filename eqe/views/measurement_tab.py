"""
Measurement Tab View

This module contains the measurement tab for EQE measurements.
It encapsulates all the UI components for power and current measurements.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout
)
from PySide6.QtCore import Signal
from typing import Dict, Any

from .plot_widgets import MultiPlotWidget
from .control_widgets import ParameterInputWidget, StatusDisplayWidget, MonochromatorControlWidget


class MeasurementTab(QWidget):
    """
    Measurement tab containing all EQE measurement UI components.
    
    This tab includes parameter input, device status, and plot widgets.
    """
    
    # Signals for measurement control
    parameters_changed = Signal(dict)  # parameters
    power_measurement_requested = Signal()
    current_measurement_requested = Signal(int)  # pixel_number
    stop_requested = Signal()
    alignment_requested = Signal()
    live_monitor_requested = Signal(bool)  # True to start, False to stop

    # Signals for monochromator control
    wavelength_change_requested = Signal(float)  # wavelength in nm
    shutter_open_requested = Signal()
    shutter_close_requested = Signal()
    
    def __init__(self):
        """Initialize the measurement tab."""
        super().__init__()

        # Create UI components
        self.parameter_input = ParameterInputWidget()
        self.status_display = StatusDisplayWidget()
        self.monochromator_control = MonochromatorControlWidget()
        self.plot_widget = MultiPlotWidget()

        # Set up layout
        self._setup_layout()

        # Connect internal signals
        self._connect_signals()
    
    def _setup_layout(self) -> None:
        """Set up the tab layout."""
        main_layout = QVBoxLayout()
        main_layout.setSpacing(10)

        # Top row: Two columns
        top_row = QHBoxLayout()

        # Left column: Parameters + Device Status (stacked)
        left_column = QVBoxLayout()
        left_column.addWidget(self.parameter_input)
        left_column.addWidget(self.status_display.device_group)
        left_column.addStretch()

        # Right column: Progress + Monochromator Controls (stacked)
        right_column = QVBoxLayout()
        right_column.addWidget(self.status_display.progress_group)
        right_column.addWidget(self.monochromator_control)
        right_column.addStretch()

        top_row.addLayout(left_column)
        top_row.addLayout(right_column)
        main_layout.addLayout(top_row)

        # Middle section: Plots (takes most of the space, full width)
        main_layout.addWidget(self.plot_widget, stretch=3)

        self.setLayout(main_layout)
    
    def _connect_signals(self) -> None:
        """Connect internal signals."""
        # Forward parameter input signals
        self.parameter_input.parameters_changed.connect(
            self.parameters_changed.emit)

        # Forward plot widget button signals
        self.plot_widget.power_measurement_requested.connect(
            self.power_measurement_requested.emit)
        self.plot_widget.current_measurement_requested.connect(
            self.current_measurement_requested.emit)
        self.plot_widget.stop_requested.connect(
            self.stop_requested.emit)

        # Forward status display signals
        self.status_display.live_monitor_requested.connect(
            self.live_monitor_requested.emit)

        # Forward monochromator control signals
        self.monochromator_control.alignment_requested.connect(
            self.alignment_requested.emit)
        self.monochromator_control.wavelength_change_requested.connect(
            self.wavelength_change_requested.emit)
        self.monochromator_control.shutter_open_requested.connect(
            self.shutter_open_requested.emit)
        self.monochromator_control.shutter_close_requested.connect(
            self.shutter_close_requested.emit)
    
    # Public methods for external control
    
    def get_parameters(self) -> Dict[str, Any]:
        """Get current measurement parameters."""
        return self.parameter_input.get_parameters()
    
    def load_parameters(self, params: Dict[str, Any]) -> None:
        """Load measurement parameters."""
        self.parameter_input.load_parameters(params)
    
    def update_device_status(self, device_name: str, is_connected: bool, 
                            message: str = "") -> None:
        """Update device status display."""
        self.status_display.update_device_status(device_name, is_connected, message)
    
    def update_power_plot(self, wavelength: float, power: float) -> None:
        """Update power plot with new data point."""
        self.plot_widget.update_power_plot(wavelength, power)
    
    def update_current_plot(self, wavelength: float, current: float,
                           pixel_number: int) -> None:
        """Update current plot with new data point."""
        self.plot_widget.update_current_plot(wavelength, current, pixel_number)
    
    def clear_power_plot(self) -> None:
        """Clear power plot data."""
        self.plot_widget.clear_power_plot()
    
    def clear_current_plot(self) -> None:
        """Clear current plot data."""
        self.plot_widget.clear_current_plot()
    
    def set_measurement_active(self, active: bool, measurement_type: str = None) -> None:
        """
        Set measurement active state.
        
        Args:
            active: Whether measurement is active
            measurement_type: Type of measurement ('power', 'current', or None)
        """
        # Enable/disable buttons based on state
        if active:
            # Disable start buttons when measuring
            pass  # Handled by plot_widget
        else:
            # Enable buttons when not measuring
            pass  # Handled by plot_widget
    
    def get_plot_widget(self) -> MultiPlotWidget:
        """Get the plot widget (for direct access if needed)."""
        return self.plot_widget
    
    def get_status_display(self) -> StatusDisplayWidget:
        """Get the status display widget."""
        return self.status_display
    
    def get_parameter_input(self) -> ParameterInputWidget:
        """Get the parameter input widget."""
        return self.parameter_input

    def update_live_signal(self, current_nA: float) -> None:
        """Update the live signal display with current reading."""
        self.status_display.update_live_signal(current_nA)

    def stop_live_monitor(self) -> None:
        """Stop live monitoring UI state."""
        self.status_display.stop_live_monitor()

    def update_monochromator_state(self, wavelength: float, shutter_open: bool,
                                   filter_number: int) -> None:
        """Update monochromator state display."""
        self.monochromator_control.update_state(wavelength, shutter_open, filter_number)

    def get_monochromator_control(self) -> MonochromatorControlWidget:
        """Get the monochromator control widget."""
        return self.monochromator_control
