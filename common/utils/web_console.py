"""
Web console logging handler for Qt WebEngine applications.

Provides a logging.Handler that forwards log messages to the web UI
console panel via Qt signals for thread-safe cross-thread communication.
"""

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PySide6.QtCore import SignalInstance


class WebConsoleHandler(logging.Handler):
    """
    Custom logging handler that forwards log messages to the web UI console.

    Uses Qt signals to safely forward messages from background threads
    to the main thread for JavaScript execution.

    Args:
        log_signal: A Qt Signal(str, str) that accepts (level, message) pairs.
                    The signal should be connected to a method that calls
                    JavaScript to display the log in the web console.

    Example:
        class MyWindow(QMainWindow):
            _log_signal = Signal(str, str)

            def __init__(self):
                self._log_signal.connect(self._on_log_message)
                handler = WebConsoleHandler(self._log_signal)
                handler.setLevel(logging.INFO)
                logging.getLogger('myapp').addHandler(handler)

            def _on_log_message(self, level: str, message: str):
                self.run_js(f"onLogMessage('{level}', '{message}')")
    """

    # Map Python log levels to web console levels
    LEVEL_MAP = {
        logging.DEBUG: 'debug',
        logging.INFO: 'info',
        logging.WARNING: 'warn',
        logging.ERROR: 'error',
        logging.CRITICAL: 'error',
    }

    def __init__(self, log_signal: 'SignalInstance'):
        super().__init__()
        self._log_signal = log_signal

    def emit(self, record: logging.LogRecord) -> None:
        """Forward log record to web console via Qt signal."""
        try:
            level = self.LEVEL_MAP.get(record.levelno, 'info')
            message = self.format(record)
            self._log_signal.emit(level, message)
        except Exception:
            self.handleError(record)
