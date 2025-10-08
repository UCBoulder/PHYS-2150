"""
Plot Widget Components

This module contains reusable plotting widgets for the EQE measurement application.
Each widget handles a specific type of plot and is designed to be embedded in larger views.
"""

import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout
from PySide6.QtCore import Qt, Signal, QObject
from typing import List, Optional, Tuple
import numpy as np

from ..config.settings import GUI_CONFIG


class PlotSignals(QObject):
    """Signals for plot widgets."""
    data_updated = Signal()
    plot_cleared = Signal()


class BasePlotWidget(QWidget):
    """
    Base class for plot widgets.
    
    Provides common functionality for all plot types including
    matplotlib integration, navigation toolbar, and consistent styling.
    """
    
    def __init__(self, title: str = "", xlabel: str = "", ylabel: str = "", parent=None):
        """
        Initialize the base plot widget.
        
        Args:
            title: Plot title
            xlabel: X-axis label
            ylabel: Y-axis label
            parent: Parent widget
        """
        super().__init__(parent)
        
        self.signals = PlotSignals()
        
        # Create matplotlib figure and axes
        self.figure = Figure(figsize=(8, 8), dpi=100)
        self.axes = self.figure.add_subplot(111)
        self.canvas = FigureCanvas(self.figure)
        
        # Set size constraints
        plot_size = GUI_CONFIG["plot_size"]
        plot_max_size = GUI_CONFIG["plot_max_size"]
        self.canvas.setMinimumSize(*plot_size)
        self.canvas.setMaximumSize(*plot_max_size)
        
        # Create navigation toolbar
        self.toolbar = NavigationToolbar(self.canvas, self)
        
        # Set up layout
        layout = QVBoxLayout()
        layout.addWidget(self.canvas, alignment=Qt.AlignHCenter)
        layout.addWidget(self.toolbar, alignment=Qt.AlignHCenter)
        self.setLayout(layout)
        
        # Configure plot
        self._configure_plot(title, xlabel, ylabel)
        
        # Data storage
        self.x_data: List[float] = []
        self.y_data: List[float] = []
    
    def _configure_plot(self, title: str, xlabel: str, ylabel: str) -> None:
        """Configure plot appearance."""
        font_sizes = GUI_CONFIG["font_sizes"]
        
        self.axes.set_xlabel(xlabel, fontsize=font_sizes["plot_axis"])
        self.axes.set_ylabel(ylabel, fontsize=font_sizes["plot_title"])
        self.axes.set_title(title, fontsize=font_sizes["plot_title"])
        self.axes.tick_params(axis='both', which='major', labelsize=font_sizes["plot_tick"])
        
        # Set consistent margins
        self.figure.subplots_adjust(left=0.15, right=0.85, top=0.85, bottom=0.15)
        
        self.axes.grid(True, alpha=0.3)
    
    def update_plot(self, x_data: List[float], y_data: List[float], 
                   append: bool = False) -> None:
        """
        Update plot data.
        
        Args:
            x_data: X-axis data
            y_data: Y-axis data
            append: Whether to append to existing data or replace
        """
        if append:
            self.x_data.extend(x_data)
            self.y_data.extend(y_data)
        else:
            self.x_data = list(x_data)
            self.y_data = list(y_data)
        
        self._redraw_plot()
        self.signals.data_updated.emit()
    
    def clear_plot(self) -> None:
        """Clear all plot data."""
        self.x_data.clear()
        self.y_data.clear()
        self.axes.clear()
        self._configure_plot(
            self.axes.get_title(),
            self.axes.get_xlabel(),
            self.axes.get_ylabel()
        )
        self.canvas.draw()
        self.signals.plot_cleared.emit()
    
    def _redraw_plot(self) -> None:
        """Redraw the plot with current data."""
        # To be implemented by subclasses
        pass
    
    def get_data(self) -> Tuple[List[float], List[float]]:
        """Get current plot data."""
        return self.x_data.copy(), self.y_data.copy()
    
    def set_title(self, title: str) -> None:
        """Update plot title."""
        self.axes.set_title(title, fontsize=GUI_CONFIG["font_sizes"]["plot_title"])
        self.canvas.draw()
    
    def save_plot(self, filename: str, dpi: int = 300) -> None:
        """Save plot to file."""
        self.figure.savefig(filename, dpi=dpi, bbox_inches='tight')


class PowerPlotWidget(BasePlotWidget):
    """Widget for displaying power measurement plots."""
    
    def __init__(self, parent=None):
        """Initialize the power plot widget."""
        super().__init__(
            title="Incident Light Power Measurements",
            xlabel="Wavelength (nm)",
            ylabel=r"Power ($\mu$W)",
            parent=parent
        )
        
        # Configure for power-specific display
        self.power_line = None
    
    def _redraw_plot(self) -> None:
        """Redraw the power plot."""
        self.axes.clear()
        self._configure_plot(
            "Incident Light Power Measurements",
            "Wavelength (nm)",
            r"Power ($\mu$W)"
        )
        
        if self.x_data and self.y_data:
            # Convert power to microwatts for display
            y_microwatts = [p * 1e6 for p in self.y_data]
            
            self.power_line, = self.axes.plot(
                self.x_data, y_microwatts, '.-', 
                color=GUI_CONFIG["colors"]["plot_line"],
                label='Power Measurement'
            )
            self.axes.legend()
        
        self.canvas.draw()
    
    def add_power_point(self, wavelength: float, power: float) -> None:
        """
        Add a single power measurement point.
        
        Args:
            wavelength: Wavelength in nm
            power: Power in watts
        """
        self.update_plot([wavelength], [power], append=True)


class CurrentPlotWidget(BasePlotWidget):
    """Widget for displaying current measurement plots."""
    
    def __init__(self, parent=None):
        """Initialize the current plot widget."""
        super().__init__(
            title="PV Current Measurements",
            xlabel="Wavelength (nm)",
            ylabel="Current (nA)",
            parent=parent
        )
        
        # Configure for current-specific display
        self.current_line = None
        self.pixel_number: Optional[int] = None
    
    def set_pixel_number(self, pixel_number: int) -> None:
        """Set the pixel number for the plot title."""
        self.pixel_number = pixel_number
        title = f"PV Current Measurements for Pixel {pixel_number}"
        self.set_title(title)
    
    def _redraw_plot(self) -> None:
        """Redraw the current plot."""
        self.axes.clear()
        title = f"PV Current Measurements for Pixel {self.pixel_number}" if self.pixel_number else "PV Current Measurements"
        self._configure_plot(
            title,
            "Wavelength (nm)",
            "Current (nA)"
        )
        
        if self.x_data and self.y_data:
            # Convert current to nanoamps for display
            y_nanoamps = [c * 1e9 for c in self.y_data]
            
            self.current_line, = self.axes.plot(
                self.x_data, y_nanoamps, '.-', 
                color=GUI_CONFIG["colors"]["plot_line"]
            )
        
        self.canvas.draw()
    
    def add_current_point(self, wavelength: float, current: float) -> None:
        """
        Add a single current measurement point.
        
        Args:
            wavelength: Wavelength in nm
            current: Current in amperes
        """
        self.update_plot([wavelength], [current], append=True)


class PhasePlotWidget(BasePlotWidget):
    """Widget for displaying phase adjustment plots."""
    
    def __init__(self, parent=None):
        """Initialize the phase plot widget."""
        super().__init__(
            title="Phase Response and Sine Fit",
            xlabel="Phase (degrees)",
            ylabel="Signal (V)",
            parent=parent
        )
        
        # Configure for phase-specific display
        self.measured_line = None
        self.fitted_line = None
        self.pixel_number: Optional[int] = None
        
        # Store fit data separately
        self.fit_x_data: List[float] = []
        self.fit_y_data: List[float] = []
    
    def set_pixel_number(self, pixel_number: int) -> None:
        """Set the pixel number for the plot title."""
        self.pixel_number = pixel_number
        title = f"Phase Response and Sine Fit for Pixel {pixel_number}"
        self.set_title(title)
    
    def update_phase_data(self, phase_data: List[float], signal_data: List[float],
                         fit_phases: Optional[List[float]] = None,
                         fit_signals: Optional[List[float]] = None) -> None:
        """
        Update phase plot with measured and fitted data.
        
        Args:
            phase_data: Measured phase values
            signal_data: Measured signal values
            fit_phases: Fitted phase values (optional)
            fit_signals: Fitted signal values (optional)
        """
        # Update measured data
        self.x_data = list(phase_data)
        self.y_data = list(signal_data)
        
        # Update fit data if provided
        if fit_phases is not None and fit_signals is not None:
            self.fit_x_data = list(fit_phases)
            self.fit_y_data = list(fit_signals)
        
        self._redraw_plot()
        self.signals.data_updated.emit()
    
    def _redraw_plot(self) -> None:
        """Redraw the phase plot."""
        self.axes.clear()
        title = f"Phase Response and Sine Fit for Pixel {self.pixel_number}" if self.pixel_number else "Phase Response and Sine Fit"
        self._configure_plot(
            title,
            "Phase (degrees)",
            "Signal (V)"
        )
        
        # Plot measured data
        if self.x_data and self.y_data:
            self.measured_line, = self.axes.plot(
                self.x_data, self.y_data, 'o',
                color=GUI_CONFIG["colors"]["plot_line"],
                label='Measured'
            )
        
        # Plot fitted data
        if self.fit_x_data and self.fit_y_data:
            self.fitted_line, = self.axes.plot(
                self.fit_x_data, self.fit_y_data, '-',
                color='red', alpha=0.7,
                label='Fitted Sine'
            )
        
        if (self.x_data and self.y_data) or (self.fit_x_data and self.fit_y_data):
            self.axes.legend()
        
        self.canvas.draw()
    
    def clear_plot(self) -> None:
        """Clear all phase plot data."""
        super().clear_plot()
        self.fit_x_data.clear()
        self.fit_y_data.clear()
    
    def add_phase_point(self, phase: float, signal: float) -> None:
        """
        Add a single phase measurement point.
        
        Args:
            phase: Phase in degrees
            signal: Signal in volts
        """
        self.update_plot([phase], [signal], append=True)


class MultiPlotWidget(QWidget):
    """
    Widget containing multiple plots in a horizontal layout.
    
    This is useful for the main application window that displays
    power, current, and phase plots side by side.
    """
    
    def __init__(self, parent=None):
        """Initialize the multi-plot widget."""
        super().__init__(parent)
        
        # Create individual plot widgets
        self.power_plot = PowerPlotWidget()
        self.current_plot = CurrentPlotWidget()
        self.phase_plot = PhasePlotWidget()
        
        # Set up horizontal layout
        layout = QHBoxLayout()
        layout.addWidget(self.power_plot)
        layout.addWidget(self.current_plot)
        layout.addWidget(self.phase_plot)
        self.setLayout(layout)
        
        # Connect signals for coordinated updates
        self._connect_plot_signals()
    
    def _connect_plot_signals(self) -> None:
        """Connect plot signals for coordinated behavior."""
        # You can add cross-plot coordination here if needed
        pass
    
    def get_power_plot(self) -> PowerPlotWidget:
        """Get the power plot widget."""
        return self.power_plot
    
    def get_current_plot(self) -> CurrentPlotWidget:
        """Get the current plot widget."""
        return self.current_plot
    
    def get_phase_plot(self) -> PhasePlotWidget:
        """Get the phase plot widget."""
        return self.phase_plot
    
    def clear_all_plots(self) -> None:
        """Clear all plots."""
        self.power_plot.clear_plot()
        self.current_plot.clear_plot()
        self.phase_plot.clear_plot()
    
    def set_pixel_number(self, pixel_number: int) -> None:
        """Set pixel number for current and phase plots."""
        self.current_plot.set_pixel_number(pixel_number)
        self.phase_plot.set_pixel_number(pixel_number)