"""
Generic logging utilities for measurement applications.
"""

import datetime
from typing import List, Optional, Callable
from enum import Enum


class LogLevel(Enum):
    """Log levels for measurement logging."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


class MeasurementLogger:
    """
    Simple logger for measurement progress and status.

    Provides timestamped logging with optional file output
    and callback support for GUI integration.
    """

    def __init__(self, log_file: Optional[str] = None,
                 callback: Optional[Callable[[str, str], None]] = None):
        """
        Initialize the logger.

        Args:
            log_file: Optional path to log file
            callback: Optional callback function(message, level) for GUI updates
        """
        self.log_file = log_file
        self.callback = callback
        self.log_entries: List[str] = []

    def _format_entry(self, message: str, level: LogLevel) -> str:
        """Format a log entry with timestamp."""
        timestamp = datetime.datetime.now().isoformat()
        return f"{timestamp} [{level.value}] {message}"

    def log(self, message: str, level: LogLevel = LogLevel.INFO) -> None:
        """
        Log a message with timestamp.

        Args:
            message: Message to log
            level: Log level
        """
        entry = self._format_entry(message, level)
        self.log_entries.append(entry)

        # Write to file if configured
        if self.log_file:
            try:
                with open(self.log_file, 'a') as f:
                    f.write(entry + '\n')
            except Exception:
                pass  # Silently ignore log file errors

        # Call callback if configured
        if self.callback:
            try:
                self.callback(message, level.value)
            except Exception:
                pass  # Silently ignore callback errors

        print(entry)

    def debug(self, message: str) -> None:
        """Log a debug message."""
        self.log(message, LogLevel.DEBUG)

    def info(self, message: str) -> None:
        """Log an info message."""
        self.log(message, LogLevel.INFO)

    def warning(self, message: str) -> None:
        """Log a warning message."""
        self.log(message, LogLevel.WARNING)

    def error(self, message: str) -> None:
        """Log an error message."""
        self.log(message, LogLevel.ERROR)

    def get_entries(self) -> List[str]:
        """Get all log entries."""
        return self.log_entries.copy()

    def clear(self) -> None:
        """Clear log entries from memory."""
        self.log_entries.clear()

    def set_callback(self, callback: Optional[Callable[[str, str], None]]) -> None:
        """Set or update the callback function."""
        self.callback = callback
