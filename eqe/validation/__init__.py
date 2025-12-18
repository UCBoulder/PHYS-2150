"""
Lock-in Amplifier Validation Module

This module provides tools for testing and validating the software lock-in
amplifier implementation using the PicoScope's built-in AWG.

Components:
- lockin_simulator: Synthetic signal testing (no hardware required)
- lockin_tester: Hardware validation using PicoScope AWG
- keysight_awg_test: External AWG validation (EDU33212A)
- tia_gain_test: Transimpedance amplifier gain verification
- lockin_live_test: Real-time lock-in testing with actual signals
- check_reference_signal: Reference signal frequency diagnostics
"""

from .lockin_simulator import LockinSimulator
from .lockin_tester import LockinTester

__all__ = ['LockinSimulator', 'LockinTester']
