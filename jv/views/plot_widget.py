"""
JV Plot Widget

This view component handles the J-V curve visualization using matplotlib
embedded in a PySide6 widget.
"""

import matplotlib
matplotlib.use('QtAgg')  # Explicitly set Qt6 backend for PySide6
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
from typing import Optional, List, Tuple

from PySide6.QtWidgets import QWidget, QVBoxLayout
from PySide6.QtCore import Qt

from ..config.settings import GUI_CONFIG


class JVPlotWidget(QWidget):
    """
    Widget for displaying J-V characteristic curves.

    Shows forward and reverse voltage sweeps with real-time updates
    during measurement.
    """

    def __init__(self, parent: Optional[QWidget] = None):
        """
        Initialize the plot widget.

        Args:
            parent: Parent widget
        """
        super().__init__(parent)

        # Get config values
        self.colors = GUI_CONFIG["colors"]
        self.font_sizes = GUI_CONFIG["font_sizes"]

        # Create matplotlib figure and axes
        figsize = GUI_CONFIG.get("plot_figsize", (14, 14))
        dpi = GUI_CONFIG.get("plot_dpi", 100)
        self.figure = Figure(figsize=figsize, dpi=dpi)
        self.axes = self.figure.add_subplot(111)

        # Create canvas
        self.canvas = FigureCanvas(self.figure)

        # Apply size constraints
        min_size = GUI_CONFIG.get("plot_min_size", (525, 525))
        max_size = GUI_CONFIG.get("plot_max_size", (700, 700))
        self.canvas.setMinimumSize(*min_size)
        self.canvas.setMaximumSize(*max_size)

        # Create navigation toolbar
        self.toolbar = NavigationToolbar(self.canvas, self)

        # Layout
        layout = QVBoxLayout(self)
        layout.addWidget(self.canvas, alignment=Qt.AlignHCenter)
        layout.addWidget(self.toolbar, alignment=Qt.AlignHCenter)
        layout.addStretch(1)

        # Plot line references
        self.forward_line: Optional[Line2D] = None
        self.reverse_line: Optional[Line2D] = None

        # Data storage for real-time updates
        self.forward_voltages: List[float] = []
        self.forward_currents: List[float] = []
        self.reverse_voltages: List[float] = []
        self.reverse_currents: List[float] = []

        # Current pixel number for title
        self._pixel_number = 1

        # Configure initial plot
        self._configure_plot()

    def _configure_plot(self) -> None:
        """Configure plot appearance."""
        self.axes.set_xlabel('Voltage (V)', fontsize=self.font_sizes["plot_axis"])
        self.axes.set_ylabel('Current (mA)', fontsize=self.font_sizes["plot_axis"])
        self.axes.set_title(
            f'J-V Characterization of Pixel {self._pixel_number}',
            fontsize=self.font_sizes["plot_title"]
        )
        self.axes.tick_params(
            axis='both',
            which='major',
            labelsize=self.font_sizes["plot_tick"]
        )
        self.figure.tight_layout()
        self.figure.subplots_adjust(bottom=0.2, left=0.15, right=0.85, top=0.85)

    def clear_plot(self, pixel_number: int = 1) -> None:
        """
        Clear the plot and reset for new measurement.

        Args:
            pixel_number: Pixel number for plot title
        """
        self._pixel_number = pixel_number

        # Clear data
        self.forward_voltages.clear()
        self.forward_currents.clear()
        self.reverse_voltages.clear()
        self.reverse_currents.clear()

        # Clear line references
        self.forward_line = None
        self.reverse_line = None

        # Clear and reconfigure axes
        self.axes.clear()
        self._configure_plot()

        # Redraw
        self.canvas.draw()

    def initialize_forward_line(self) -> None:
        """Initialize the forward scan plot line."""
        self.forward_line, = self.axes.plot(
            [], [],
            '.',
            label="Forward Scan",
            color=self.colors["forward_scan"]
        )
        self.axes.legend(fontsize=self.font_sizes["plot_legend"])

    def initialize_reverse_line(self) -> None:
        """Initialize the reverse scan plot line."""
        self.reverse_line, = self.axes.plot(
            [], [],
            '.',
            label="Reverse Scan",
            color=self.colors["reverse_scan"]
        )
        self.axes.legend(fontsize=self.font_sizes["plot_legend"])

    def add_forward_point(self, voltage: float, current: float) -> None:
        """
        Add a point to the forward scan.

        Args:
            voltage: Voltage in V
            current: Current in mA
        """
        self.forward_voltages.append(voltage)
        self.forward_currents.append(current)

    def add_reverse_point(self, voltage: float, current: float) -> None:
        """
        Add a point to the reverse scan.

        Args:
            voltage: Voltage in V
            current: Current in mA
        """
        self.reverse_voltages.append(voltage)
        self.reverse_currents.append(current)

    def update_plot(self) -> None:
        """Update the plot with current data."""
        # Update forward line if it exists
        if self.forward_line is not None:
            self.forward_line.set_data(
                self.forward_voltages,
                self.forward_currents
            )

        # Update reverse line if it exists
        if self.reverse_line is not None:
            self.reverse_line.set_data(
                self.reverse_voltages,
                self.reverse_currents
            )

        # Rescale axes
        self.axes.relim()
        self.axes.autoscale_view()

        # Tight layout and redraw
        self.figure.tight_layout()
        self.canvas.draw()

    def set_data(
        self,
        forward_voltages: List[float],
        forward_currents: List[float],
        reverse_voltages: List[float],
        reverse_currents: List[float],
    ) -> None:
        """
        Set complete data for both sweeps.

        Args:
            forward_voltages: Forward sweep voltages
            forward_currents: Forward sweep currents
            reverse_voltages: Reverse sweep voltages
            reverse_currents: Reverse sweep currents
        """
        self.forward_voltages = list(forward_voltages)
        self.forward_currents = list(forward_currents)
        self.reverse_voltages = list(reverse_voltages)
        self.reverse_currents = list(reverse_currents)

        # Ensure lines exist
        if self.forward_line is None:
            self.initialize_forward_line()
        if self.reverse_line is None:
            self.initialize_reverse_line()

        self.update_plot()

    def get_figure(self) -> Figure:
        """Get the matplotlib figure for saving."""
        return self.figure
