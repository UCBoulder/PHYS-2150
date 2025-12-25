"""
Shared UI components for PHYS 2150 measurement applications.

Provides base classes for Qt WebEngine windows and APIs to reduce
code duplication across EQE, JV, and launcher applications.
"""

from .web_window import BaseWebWindow
from .web_api import BaseWebApi

__all__ = [
    'BaseWebWindow',
    'BaseWebApi',
]
