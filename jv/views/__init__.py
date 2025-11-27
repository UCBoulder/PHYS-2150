"""
JV Views Package

Views handle GUI components - visualization and user input.
Views interact with models, never directly with controllers.
"""

from .main_window import JVMainWindow
from .plot_widget import JVPlotWidget
from .controls_panel import JVControlsPanel

__all__ = ["JVMainWindow", "JVPlotWidget", "JVControlsPanel"]
