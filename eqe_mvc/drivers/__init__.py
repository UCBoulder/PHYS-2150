"""
Hardware Drivers Package

This package contains low-level hardware drivers for laboratory instruments.
These drivers provide direct interfaces to device firmware and should be used
by the controller classes in the controllers/ package.

Available drivers:
- TLPMX: Thorlabs Power Meter driver
- cornerstone_mono: Oriel Cornerstone Monochromator driver
"""

# Import drivers for easy access
try:
    from .TLPMX import TLPMX, TLPM_DEFAULT_CHANNEL
except ImportError:
    # Driver not available
    TLPMX = None
    TLPM_DEFAULT_CHANNEL = None

try:
    from .cornerstone_mono import Cornerstone_Mono
except ImportError:
    # Driver not available
    Cornerstone_Mono = None

__all__ = ['TLPMX', 'TLPM_DEFAULT_CHANNEL', 'Cornerstone_Mono']