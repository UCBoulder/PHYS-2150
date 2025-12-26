"""
Base API class for Qt WebEngine applications.

Provides common functionality for Python-JavaScript API classes including
debug mode toggling, file save dialogs, and log viewing.
"""

import json
import logging
import os
from collections import deque
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, Slot
from PySide6.QtWidgets import QFileDialog

from common.utils import TieredLogger, StdoutCapture

if TYPE_CHECKING:
    from .web_window import BaseWebWindow


def _get_log_directory() -> Path:
    """Get the log directory (%LOCALAPPDATA%\\PHYS2150\\)."""
    local_app_data = os.environ.get('LOCALAPPDATA')
    if local_app_data:
        return Path(local_app_data) / 'PHYS2150'
    return Path.home() / 'PHYS2150'


class BaseWebApi(QObject):
    """
    Base class for Qt WebChannel API objects.

    Provides shared functionality:
    - Staff debug mode toggling
    - Generic file save dialogs

    Subclasses should:
    - Call super().__init__(window) with their window reference
    - Define app-specific @Slot methods

    Example:
        class MyApi(BaseWebApi):
            def __init__(self, window):
                super().__init__(window)
                self._experiment = None

            @Slot(str, result=str)
            def my_method(self, params: str) -> str:
                # App-specific implementation
                ...
    """

    def __init__(self, window: 'BaseWebWindow'):
        """
        Initialize the base API.

        Args:
            window: The parent window with logging support
        """
        super().__init__()
        self._window = window
        self._stdout_capture = None

    @Slot(result=str)
    def toggle_debug_mode(self) -> str:
        """
        Toggle stdout capture mode for viewing print statements.

        When enabled, all print() statements are forwarded to the
        web console panel in addition to stdout. This captures
        debug output from TieredLogger.debug_output() and any
        other print() calls.

        Returns:
            JSON string with {"enabled": bool}
        """
        # Check if capture is currently enabled
        current_capture = StdoutCapture.get_instance()
        is_enabled = current_capture is not None and current_capture.is_enabled()

        if is_enabled:
            # Disable capture
            if self._stdout_capture:
                self._stdout_capture.disable()
                self._stdout_capture = None
            self._window.send_log('info', "Print capture DISABLED")
            return json.dumps({"enabled": False})
        else:
            # Enable capture - forward prints to web console
            def forward_to_console(level: str, message: str) -> None:
                self._window.send_log(level, f"[print] {message}")

            self._stdout_capture = StdoutCapture(forward_to_console)
            self._stdout_capture.enable()
            self._window.send_log('info', "Print capture ENABLED - print() statements now visible in console")
            return json.dumps({"enabled": True})

    def save_file_with_dialog(
        self,
        content: str,
        title: str = "Save File",
        default_name: str = "data.csv",
        file_filter: str = "CSV files (*.csv)"
    ) -> dict:
        """
        Show a file save dialog and write content to the selected file.

        This is a helper method for subclasses to use when implementing
        file export functionality.

        Args:
            content: The content to write to the file
            title: Dialog window title
            default_name: Default filename
            file_filter: File type filter string

        Returns:
            Dict with {"success": bool, "path": str} or {"success": False, "message": str}
        """
        file_path, _ = QFileDialog.getSaveFileName(
            self._window,
            title,
            default_name,
            file_filter
        )

        if file_path:
            try:
                with open(file_path, 'w', newline='') as f:
                    f.write(content)
                return {"success": True, "path": file_path}
            except Exception as e:
                return {"success": False, "message": str(e)}

        return {"success": False, "message": "Cancelled"}

    @Slot(int, result=str)
    def get_recent_logs(self, num_lines: int = 50) -> str:
        """
        Get recent log entries from the debug log file.

        Reads the last N lines from the application's debug log file
        stored in %LOCALAPPDATA%\\PHYS2150\\{app}_debug.log.

        Args:
            num_lines: Number of recent lines to return (default 50)

        Returns:
            JSON string with {"success": bool, "logs": str, "path": str}
        """
        try:
            # Determine app name from window title or class name
            app_name = getattr(self._window, '_app_name', 'app')
            log_dir = _get_log_directory()
            log_file = log_dir / f"{app_name}_debug.log"

            if not log_file.exists():
                return json.dumps({
                    "success": True,
                    "logs": f"No log file found at:\n{log_file}\n\nLogs will appear here once the application generates them.",
                    "path": str(log_file)
                })

            # Read last N lines efficiently using deque
            with open(log_file, 'r', encoding='utf-8', errors='replace') as f:
                recent_lines = deque(f, maxlen=num_lines)

            logs = ''.join(recent_lines)

            return json.dumps({
                "success": True,
                "logs": logs,
                "path": str(log_file)
            })

        except Exception as e:
            return json.dumps({
                "success": False,
                "message": f"Failed to read logs: {str(e)}",
                "logs": "",
                "path": ""
            })

    @Slot(result=str)
    def open_log_file(self) -> str:
        """
        Open the log file in the default text editor (Notepad on Windows).

        Returns:
            JSON string with {"success": bool, "message": str}
        """
        import subprocess
        import sys

        try:
            app_name = getattr(self._window, '_app_name', 'app')
            log_dir = _get_log_directory()
            log_file = log_dir / f"{app_name}_debug.log"

            if not log_file.exists():
                return json.dumps({
                    "success": False,
                    "message": f"Log file not found: {log_file}"
                })

            # Open in Notepad on Windows (read-only by default for log files)
            if sys.platform == 'win32':
                subprocess.Popen(['notepad.exe', str(log_file)])
            else:
                # Fallback for other platforms
                subprocess.Popen(['xdg-open', str(log_file)])

            return json.dumps({"success": True})

        except Exception as e:
            return json.dumps({
                "success": False,
                "message": f"Failed to open log file: {str(e)}"
            })
