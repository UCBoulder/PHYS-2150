"""
Base API class for Qt WebEngine applications.

Provides common functionality for Python-JavaScript API classes including
debug mode toggling and file save dialogs.
"""

import json
import logging
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, Slot
from PySide6.QtWidgets import QFileDialog

from common.utils import TieredLogger

if TYPE_CHECKING:
    from .web_window import BaseWebWindow


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

    @Slot(result=str)
    def toggle_debug_mode(self) -> str:
        """
        Toggle staff debug mode for verbose console output.

        When enabled, DEBUG-level log messages are shown in the
        web console panel. When disabled, only INFO and above
        are shown.

        Returns:
            JSON string with {"enabled": bool}
        """
        current = TieredLogger._staff_debug_mode
        new_mode = not current
        TieredLogger.set_staff_debug_mode(new_mode)

        # Also update the web console handler level
        if hasattr(self._window, '_web_console_handler'):
            self._window._web_console_handler.setLevel(
                logging.DEBUG if new_mode else logging.INFO
            )

        # Log the mode change (this message will be visible in console)
        if new_mode:
            self._window.send_log('info', "Staff debug mode ENABLED (Ctrl+Shift+D) - technical output visible in console")
        else:
            self._window.send_log('info', "Staff debug mode DISABLED")

        return json.dumps({"enabled": new_mode})

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
