"""
Stdout capture utility for redirecting print statements to web console.

When enabled, all print() statements are forwarded to the web terminal
in addition to the original stdout.
"""

import sys
from typing import Callable, Optional


class StdoutCapture:
    """
    Captures stdout and forwards to a callback while preserving original output.

    Usage:
        capture = StdoutCapture(lambda level, msg: send_to_web(level, msg))
        capture.enable()   # Start capturing
        print("Hello")     # Goes to both stdout AND web console
        capture.disable()  # Stop capturing

    The callback receives (level: str, message: str) where level is 'debug'.
    """

    _instance: Optional['StdoutCapture'] = None

    def __init__(self, callback: Callable[[str, str], None]):
        """
        Initialize the capture.

        Args:
            callback: Function to call with (level, message) for each print
        """
        self._callback = callback
        self._original_stdout = None
        self._enabled = False
        self._buffer = ""

    @classmethod
    def get_instance(cls) -> Optional['StdoutCapture']:
        """Get the current capture instance if any."""
        return cls._instance

    def enable(self) -> None:
        """Start capturing stdout."""
        if self._enabled:
            return

        self._original_stdout = sys.stdout
        self._enabled = True
        StdoutCapture._instance = self
        sys.stdout = self

    def disable(self) -> None:
        """Stop capturing stdout and restore original."""
        if not self._enabled:
            return

        # Flush any remaining buffer
        if self._buffer:
            self._forward_to_callback(self._buffer)
            self._buffer = ""

        sys.stdout = self._original_stdout
        self._enabled = False
        StdoutCapture._instance = None

    def is_enabled(self) -> bool:
        """Check if capture is currently enabled."""
        return self._enabled

    def write(self, text: str) -> int:
        """
        Write to stdout and forward to callback.

        Handles line buffering - only forwards complete lines to callback.
        """
        # Always write to original stdout
        if self._original_stdout:
            self._original_stdout.write(text)

        # Buffer text and forward complete lines
        self._buffer += text

        # Process complete lines
        while '\n' in self._buffer:
            line, self._buffer = self._buffer.split('\n', 1)
            if line.strip():  # Skip empty lines
                self._forward_to_callback(line)

        return len(text)

    def _forward_to_callback(self, message: str) -> None:
        """Forward a message to the callback."""
        try:
            self._callback('debug', message)
        except Exception:
            pass  # Don't let callback errors break stdout

    def flush(self) -> None:
        """Flush the stdout buffer."""
        if self._original_stdout:
            self._original_stdout.flush()

    # Support other stdout attributes
    def fileno(self):
        if self._original_stdout:
            return self._original_stdout.fileno()
        return -1

    def isatty(self) -> bool:
        if self._original_stdout:
            return self._original_stdout.isatty()
        return False

    @property
    def encoding(self):
        if self._original_stdout:
            return self._original_stdout.encoding
        return 'utf-8'
