"""
EQE Measurement Application using MVC Pattern

This application provides a well-structured implementation of External Quantum Efficiency
measurements using the Model-View-Controller design pattern for laboratory instruments.

The MVC pattern separation allows for:
- Controllers: Device-specific drivers (Thorlabs, Monochromator, PicoScope Lock-in)
- Models: Measurement logic and experiment coordination
- Views: User interface components and data visualization
"""

__version__ = "1.0.0"
__author__ = "PHYS 2150 Lab"