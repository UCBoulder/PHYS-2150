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
from .control_widgets import ParameterInputWidget, StatusDisplayWidget


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
    
    def __init__(self):
        """Initialize the measurement tab."""
        super().__init__()
        
        # Create UI components
        self.parameter_input = ParameterInputWidget()
        self.status_display = StatusDisplayWidget()
        self.plot_widget = MultiPlotWidget()
        
        # Set up layout
        self._setup_layout()
        
        # Connect internal signals
        self._connect_signals()
    
    def _setup_layout(self) -> None:
        """Set up the tab layout."""
        main_layout = QVBoxLayout()
        main_layout.setSpacing(10)
        
        # Top row: Parameter input and Device Status side by side
        top_row = QHBoxLayout()
        top_row.addWidget(self.parameter_input)
        top_row.addWidget(self.status_display)
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
        
        # Forward status display alignment button signal
        self.status_display.alignment_requested.connect(
            self.alignment_requested.emit)
    
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
