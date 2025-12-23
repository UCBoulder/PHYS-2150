"""
Base Plot Widget Components

Provides reusable matplotlib-PySide6 plotting widgets for measurement applications.
"""

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
from PySide6.QtWidgets import QWidget, QVBoxLayout, QSizePolicy
from PySide6.QtCore import Signal, QObject
from typing import List, Tuple, Optional, Dict, Any


# Default plot configuration
DEFAULT_PLOT_CONFIG = {
    "font_sizes": {
        "title": 10,
        "axis": 10,
        "tick": 8,
    },
    "colors": {
        "primary": "#0077BB",
        "secondary": "#EE7733",
        "tertiary": "#009988",
    },
    "figure": {
        "dpi": 100,
        "figsize": (8, 6),
    },
    "margins": {
        "left": 0.15,
        "right": 0.85,
        "top": 0.85,
        "bottom": 0.15,
    }
}


class PlotSignals(QObject):
    """Signals for plot widgets."""
    data_updated = Signal()
    plot_cleared = Signal()


class BasePlotWidget(QWidget):
    """
    Base class for matplotlib plot widgets in PySide6.

    Provides common functionality for all plot types including
    matplotlib integration, navigation toolbar, and consistent styling.
    """

    def __init__(self, title: str = "", xlabel: str = "", ylabel: str = "",
                 config: Optional[Dict[str, Any]] = None, parent=None):
        """
        Initialize the base plot widget.

        Args:
            title: Plot title
            xlabel: X-axis label
            ylabel: Y-axis label
            config: Optional configuration dictionary (overrides defaults)
            parent: Parent widget
        """
        super().__init__(parent)

        self.config = {**DEFAULT_PLOT_CONFIG, **(config or {})}
        self.signals = PlotSignals()

        # Store labels
        self._title = title
        self._xlabel = xlabel
        self._ylabel = ylabel

        # Create matplotlib figure and axes
        fig_config = self.config["figure"]
        self.figure = Figure(figsize=fig_config["figsize"], dpi=fig_config["dpi"])
        self.axes = self.figure.add_subplot(111)
        self.canvas = FigureCanvas(self.figure)

        # Allow canvas to expand and fill available space
        self.canvas.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding
        )

        # Create navigation toolbar
        self.toolbar = NavigationToolbar(self.canvas, self)

        # Set up layout
        layout = QVBoxLayout()
        layout.addWidget(self.canvas)
        layout.addWidget(self.toolbar)
        self.setLayout(layout)

        # Configure plot
        self._configure_plot()

        # Data storage
        self.x_data: List[float] = []
        self.y_data: List[float] = []

    def _configure_plot(self) -> None:
        """Configure plot appearance."""
        font_sizes = self.config["font_sizes"]
        margins = self.config["margins"]

        self.axes.set_xlabel(self._xlabel, fontsize=font_sizes["axis"])
        self.axes.set_ylabel(self._ylabel, fontsize=font_sizes["axis"])
        self.axes.set_title(self._title, fontsize=font_sizes["title"])
        self.axes.tick_params(axis='both', which='major', labelsize=font_sizes["tick"])

        # Set consistent margins
        self.figure.subplots_adjust(**margins)

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

    def add_point(self, x: float, y: float) -> None:
        """
        Add a single data point.

        Args:
            x: X-axis value
            y: Y-axis value
        """
        self.update_plot([x], [y], append=True)

    def clear_plot(self) -> None:
        """Clear all plot data."""
        self.x_data.clear()
        self.y_data.clear()
        self.axes.clear()
        self._configure_plot()
        self.canvas.draw()
        self.signals.plot_cleared.emit()

    def _redraw_plot(self) -> None:
        """
        Redraw the plot with current data.
        Override in subclasses for custom plotting behavior.
        """
        self.axes.clear()
        self._configure_plot()

        if self.x_data and self.y_data:
            self.axes.plot(
                self.x_data, self.y_data, '.-',
                color=self.config["colors"]["primary"]
            )

        self.canvas.draw()

    def get_data(self) -> Tuple[List[float], List[float]]:
        """Get current plot data."""
        return self.x_data.copy(), self.y_data.copy()

    def set_title(self, title: str) -> None:
        """Update plot title."""
        self._title = title
        self.axes.set_title(title, fontsize=self.config["font_sizes"]["title"])
        self.canvas.draw()

    def set_xlabel(self, label: str) -> None:
        """Update X-axis label."""
        self._xlabel = label
        self.axes.set_xlabel(label, fontsize=self.config["font_sizes"]["axis"])
        self.canvas.draw()

    def set_ylabel(self, label: str) -> None:
        """Update Y-axis label."""
        self._ylabel = label
        self.axes.set_ylabel(label, fontsize=self.config["font_sizes"]["axis"])
        self.canvas.draw()

    def save_plot(self, filename: str, dpi: int = 300) -> None:
        """Save plot to file."""
        self.figure.savefig(filename, dpi=dpi, bbox_inches='tight')

    def set_config(self, config: Dict[str, Any]) -> None:
        """
        Update plot configuration.

        Args:
            config: Configuration dictionary to merge with existing config
        """
        self.config = {**self.config, **config}
        self._configure_plot()
        self.canvas.draw()
