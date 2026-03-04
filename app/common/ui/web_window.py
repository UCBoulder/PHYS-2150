"""
Base web window class for Qt WebEngine applications.

Provides common functionality for web-based UI windows including
GPU acceleration, JavaScript execution queuing, theme management,
and logging integration.
"""

import json
import os
import sys
from typing import Optional

from PySide6.QtCore import Signal, QUrl
from PySide6.QtWidgets import QMainWindow
from PySide6.QtGui import QIcon
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebChannel import QWebChannel


class BaseWebWindow(QMainWindow):
    """
    Base class for Qt WebEngine-based application windows.

    Provides common functionality:
    - GPU acceleration setup
    - Page ready tracking with JS queuing
    - Theme initialization
    - Log message forwarding to web console
    - Window icon setup

    Subclasses should:
    - Call super().__init__() with appropriate parameters
    - Override closeEvent() for app-specific cleanup
    - Set up their own API class and web channel registration

    Example:
        class MyWindow(BaseWebWindow):
            def __init__(self):
                super().__init__(
                    title="My App",
                    html_filename="my_app.html",
                    size=(1200, 800),
                    min_size=(800, 600)
                )
                # Set up app-specific API
                self.api = MyApi(self)
                self.channel.registerObject("api", self.api)
    """

    # Signal for thread-safe log forwarding from background threads
    _log_signal = Signal(str, str)  # level, message

    def __init__(
        self,
        title: str,
        html_filename: str,
        size: tuple[int, int] = (1200, 800),
        min_size: Optional[tuple[int, int]] = None,
        allow_local_file_access: bool = True,
        app_name: Optional[str] = None
    ):
        """
        Initialize the base web window.

        Args:
            title: Window title
            html_filename: Name of HTML file in ui/ directory (e.g., "jv.html")
            size: Initial window size as (width, height)
            min_size: Minimum window size as (width, height), or None for no minimum
            allow_local_file_access: Whether to enable LocalContentCanAccessFileUrls
            app_name: Application name for log file lookup (e.g., "eqe", "jv")
        """
        super().__init__()

        # Store app name for log file lookup
        self._app_name = app_name or html_filename.replace('.html', '')

        # Connect log signal to handler
        self._log_signal.connect(self._on_log_message)

        self.setWindowTitle(title)
        self.resize(*size)
        if min_size:
            self.setMinimumSize(*min_size)

        # Set window icon
        self._setup_window_icon()

        # Track if page is ready for JS calls
        self._page_ready = False
        self._pending_js: list[str] = []

        # Create web view with GPU acceleration
        self._setup_web_view(allow_local_file_access)

        # Set up web channel (subclasses register their own API objects)
        self.channel = QWebChannel()
        self.web_view.page().setWebChannel(self.channel)

        # Connect load finished signal
        self.web_view.loadFinished.connect(self._on_page_loaded)

        # Load HTML
        html_path = self._get_html_path(html_filename)
        self.web_view.setUrl(QUrl.fromLocalFile(html_path))

    def _setup_window_icon(self) -> None:
        """Set up the window icon from assets directory."""
        # Look for icon in project root assets folder
        if getattr(sys, 'frozen', False):
            base_path = sys._MEIPASS
        else:
            # Go up from common/ui to project root
            base_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

        icon_path = os.path.join(base_path, "assets", "icon.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

    def _setup_web_view(self, allow_local_file_access: bool) -> None:
        """Set up the web view with GPU acceleration and settings."""
        self.web_view = QWebEngineView()
        settings = self.web_view.page().settings()

        # Enable GPU acceleration
        settings.setAttribute(settings.WebAttribute.Accelerated2dCanvasEnabled, True)
        settings.setAttribute(settings.WebAttribute.WebGLEnabled, True)

        # Enable local file access if requested (needed for loading local resources)
        if allow_local_file_access:
            settings.setAttribute(settings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
            settings.setAttribute(settings.WebAttribute.LocalContentCanAccessFileUrls, True)

        self.setCentralWidget(self.web_view)

    def _get_html_path(self, html_filename: str) -> str:
        """Get the full path to an HTML file in the ui/ directory."""
        if getattr(sys, 'frozen', False):
            base_path = sys._MEIPASS
        else:
            # Go up from common/ui to project root
            base_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

        return os.path.join(base_path, 'ui', html_filename)

    def _on_page_loaded(self, success: bool) -> None:
        """Handle page load completion."""
        if success:
            self._page_ready = True
            # Execute any pending JS calls
            for js in self._pending_js:
                self.web_view.page().runJavaScript(js)
            self._pending_js.clear()

    def run_js(self, script: str) -> None:
        """
        Execute JavaScript in the web view.

        If the page is not yet loaded, the script is queued and
        executed once the page is ready.

        Args:
            script: JavaScript code to execute
        """
        if self._page_ready:
            self.web_view.page().runJavaScript(script)
        else:
            self._pending_js.append(script)

    def send_log(self, level: str, message: str) -> None:
        """
        Send a log message to the JS console panel.

        Args:
            level: Log level ('debug', 'info', 'warn', 'error')
            message: Log message text
        """
        # Use json.dumps for safe JavaScript string serialization
        js = f"onLogMessage({json.dumps(level)}, {json.dumps(message)})"
        self.run_js(js)

    def _on_log_message(self, level: str, message: str) -> None:
        """Handle log message signal (runs on main thread)."""
        self.send_log(level, message)

    def set_initial_theme(self, theme: str) -> None:
        """
        Set the initial theme via JavaScript after page loads.

        Args:
            theme: Theme name ('dark' or 'light')
        """
        # Set localStorage and apply theme directly (no reload to avoid disrupting device status)
        # LabTheme.apply takes a boolean (true=dark, false=light)
        is_dark = 'true' if theme == 'dark' else 'false'
        js = f"""
            localStorage.setItem('theme', '{theme}');
            if (typeof LabTheme !== 'undefined' && LabTheme.apply) {{
                LabTheme.apply({is_dark});
            }} else {{
                document.body.classList.toggle('dark-mode', {is_dark});
                document.body.classList.toggle('light-mode', !{is_dark});
            }}
        """
        self.run_js(js)
