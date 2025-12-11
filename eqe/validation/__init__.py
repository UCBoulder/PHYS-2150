"""
Lock-in Amplifier Validation Module

This module provides tools for testing and validating the software lock-in
amplifier implementation using the PicoScope's built-in AWG.

Components:
- lockin_simulator: Synthetic signal testing (no hardware required)
- lockin_tester: Hardware validation using AWG
- improved_lockin: Experimental algorithm improvements
"""

from .lockin_simulator import LockinSimulator
from .lockin_tester import LockinTester

__all__ = ['LockinSimulator', 'LockinTester']
