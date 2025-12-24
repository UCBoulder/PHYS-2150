"""
PHYS 2150 Measurement Suite Launcher (Qt WebEngine)

A web-based launcher using Qt WebEngine for full HTML/CSS/JS control
with Qt's mature accessibility support.

Usage:
    python qtwebengine_launcher.py
"""

import os
import sys
import subprocess

from PySide6.QtCore import Qt, QObject, Slot, QUrl
from PySide6.QtWidgets import QApplication, QMainWindow
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebChannel import QWebChannel


class LauncherApi(QObject):
    """
    Python API exposed to JavaScript via QWebChannel.

    All @Slot methods are callable from JS via:
        api.method_name(args, callback)
    """

    def __init__(self, window: QMainWindow):
        super().__init__()
        self._window = window
        self._project_root = os.path.dirname(os.path.abspath(__file__))

    @Slot(result=str)
    def launch_eqe(self) -> str:
        """Launch the EQE measurement application."""
        return self._launch_application("eqe")

    @Slot(result=str)
    def launch_jv(self) -> str:
        """Launch the J-V measurement application."""
        return self._launch_application("jv")

    def _launch_application(self, app_name: str) -> str:
        """
        Launch a measurement application as a subprocess.

        Args:
            app_name: Name of the application module ("eqe" or "jv")

        Returns:
            JSON string with success status
        """
        try:
            if sys.platform == 'win32':
                subprocess.Popen(
                    [sys.executable, "-m", app_name],
                    cwd=self._project_root,
                    creationflags=subprocess.CREATE_NEW_CONSOLE,
                )
            else:
                subprocess.Popen(
                    [sys.executable, "-m", app_name],
                    cwd=self._project_root,
                    start_new_session=True,
                )

            # Close the launcher after successful launch
            QApplication.quit()
            return '{"success": true}'

        except Exception as e:
            return f'{{"success": false, "message": "{str(e)}"}}'

    @Slot(result=str)
    def get_version(self) -> str:
        """Get the application version."""
        return "2.3.0"


class LauncherWindow(QMainWindow):
    """Main launcher window using Qt WebEngine."""

    def __init__(self):
        super().__init__()

        self.setWindowTitle("PHYS 2150 Measurement Suite")
        self.setFixedSize(500, 350)

        # Center on screen
        self._center_window()

        # Create web view with GPU acceleration
        self.web_view = QWebEngineView()
        settings = self.web_view.page().settings()
        settings.setAttribute(settings.WebAttribute.Accelerated2dCanvasEnabled, True)
        settings.setAttribute(settings.WebAttribute.WebGLEnabled, True)
        self.setCentralWidget(self.web_view)

        # Set up the web channel for Python <-> JS communication
        self.channel = QWebChannel()
        self.api = LauncherApi(self)
        self.channel.registerObject("api", self.api)
        self.web_view.page().setWebChannel(self.channel)

        # Load the HTML file
        html_path = self._get_html_path()
        self.web_view.setUrl(QUrl.fromLocalFile(html_path))

    def _center_window(self):
        """Center the window on the screen."""
        screen = QApplication.primaryScreen()
        screen_geometry = screen.availableGeometry()
        x = (screen_geometry.width() - self.width()) // 2
        y = (screen_geometry.height() - self.height()) // 2
        self.move(x, y)

    def _get_html_path(self) -> str:
        """Get the path to the launcher HTML file."""
        if getattr(sys, 'frozen', False):
            base_path = sys._MEIPASS
        else:
            base_path = os.path.dirname(os.path.abspath(__file__))

        return os.path.join(base_path, 'ui', 'launcher.html')


def main():
    """Main entry point for the Qt WebEngine launcher."""
    app = QApplication(sys.argv)

    window = LauncherWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
