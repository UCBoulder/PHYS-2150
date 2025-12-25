"""
PHYS 2150 Measurement Suite Launcher

Web-based launcher for the EQE and I-V measurement applications.
Uses Qt WebEngine to provide a modern HTML/CSS/JS interface.
"""

import sys
import os
import json
import subprocess

from PySide6.QtCore import QObject, Slot, QUrl
from PySide6.QtWidgets import QApplication, QMainWindow
from PySide6.QtGui import QIcon
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebChannel import QWebChannel


class LauncherApi(QObject):
    """Python API exposed to JavaScript via QWebChannel."""

    def __init__(self, window: 'LauncherWindow'):
        super().__init__()
        self._window = window
        self._show_terminal = False

    @Slot(result=str)
    def toggle_terminal(self) -> str:
        """Toggle whether to show terminal window when launching apps."""
        self._show_terminal = not self._show_terminal
        return json.dumps({"show_terminal": self._show_terminal})

    @Slot(bool, str, result=str)
    def launch_eqe(self, offline: bool = False, theme: str = "dark") -> str:
        """Launch the EQE measurement application."""
        return self._launch_application("eqe", offline, theme)

    @Slot(bool, str, result=str)
    def launch_jv(self, offline: bool = False, theme: str = "dark") -> str:
        """Launch the I-V measurement application."""
        return self._launch_application("jv", offline, theme)

    def _launch_application(self, app_name: str, offline: bool = False, theme: str = "dark") -> str:
        """
        Launch a measurement application.

        Args:
            app_name: Name of the application module ("eqe" or "jv")
            offline: Whether to launch in offline mode (no hardware)
            theme: Color theme ("dark" or "light")

        Returns:
            JSON string with success status
        """
        # Get the directory containing the launcher
        launcher_dir = os.path.dirname(os.path.abspath(__file__))

        # Build command
        cmd = [sys.executable, "-m", app_name]
        if offline:
            cmd.append("--offline")
        if theme:
            cmd.extend(["--theme", theme])

        try:
            if sys.platform == 'win32':
                # Use CREATE_NO_WINDOW by default, CREATE_NEW_CONSOLE if terminal requested
                if self._show_terminal:
                    flags = subprocess.CREATE_NEW_CONSOLE
                else:
                    flags = subprocess.CREATE_NO_WINDOW
                subprocess.Popen(
                    cmd,
                    cwd=launcher_dir,
                    creationflags=flags,
                )
            else:
                subprocess.Popen(
                    cmd,
                    cwd=launcher_dir,
                    start_new_session=True,
                )

            # Close the launcher after successful launch
            QApplication.quit()
            return json.dumps({"success": True})

        except Exception as e:
            return json.dumps({"success": False, "message": str(e)})


class LauncherWindow(QMainWindow):
    """Main launcher window with web UI."""

    def __init__(self):
        super().__init__()

        self.setWindowTitle("PHYS 2150 Measurement Suite")
        self.setFixedSize(500, 350)

        # Set window icon
        icon_path = os.path.join(os.path.dirname(__file__), "assets", "icon.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        # Center window on screen
        self._center_window()

        # Create web view
        self.web_view = QWebEngineView()
        self.setCentralWidget(self.web_view)

        # Set up web channel for Python-JS communication
        self.channel = QWebChannel()
        self.api = LauncherApi(self)
        self.channel.registerObject("api", self.api)
        self.web_view.page().setWebChannel(self.channel)

        # Load the launcher HTML
        html_path = self._get_html_path()
        self.web_view.setUrl(QUrl.fromLocalFile(html_path))

    def _center_window(self):
        """Center the window on the screen."""
        screen = QApplication.primaryScreen()
        screen_geometry = screen.availableGeometry()
        window_geometry = self.frameGeometry()
        center_point = screen_geometry.center()
        window_geometry.moveCenter(center_point)
        self.move(window_geometry.topLeft())

    def _get_html_path(self) -> str:
        """Get path to launcher HTML file."""
        if getattr(sys, 'frozen', False):
            base_path = sys._MEIPASS
        else:
            base_path = os.path.dirname(os.path.abspath(__file__))

        return os.path.join(base_path, 'ui', 'launcher.html')


def main():
    """Main entry point for the launcher."""
    app = QApplication(sys.argv)

    window = LauncherWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
