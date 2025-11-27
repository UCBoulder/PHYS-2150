"""
JV Measurement Application Package

This package implements J-V (current-voltage) characterization for solar cells
using an MVC (Model-View-Controller) architecture.

Architecture:
- controllers/: Device drivers (Keithley 2450 SMU communication)
- models/: Experiment logic (measurement strategies, data analysis)
- views/: PySide6 GUI components
- config/: Settings and parameters
- utils/: Data export and utilities
"""

__version__ = "2.0.0"
