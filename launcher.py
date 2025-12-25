"""
PHYS 2150 Measurement Suite Launcher

Web-based launcher for the EQE and I-V measurement applications.
Uses Qt WebEngine to provide a modern HTML/CSS/JS interface.
"""

import sys
import os
import json
import subprocess
from importlib.metadata import version, PackageNotFoundError

from PySide6.QtCore import QObject, Slot, QTimer
from PySide6.QtWidgets import QApplication

from common.ui import BaseWebWindow


def get_app_version() -> str:
    """Get the application version from pyproject.toml via importlib.metadata."""
    try:
        return version("phys2150")
    except PackageNotFoundError:
        # Fallback: read from pyproject.toml directly (for development)
        try:
            import tomllib
            pyproject_path = os.path.join(os.path.dirname(__file__), "pyproject.toml")
            with open(pyproject_path, "rb") as f:
                data = tomllib.load(f)
                return data.get("project", {}).get("version", "dev")
        except Exception:
            return "dev"


class LauncherApi(QObject):
    """Python API exposed to JavaScript via QWebChannel."""

    def __init__(self, window: 'LauncherWindow'):
        super().__init__()
        self._window = window
        self._show_terminal = False

    @Slot(result=str)
    def get_version(self) -> str:
        """Get the application version."""
        return json.dumps({"version": get_app_version()})

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

            # Close the launcher after a brief delay so user sees "Launching..." feedback
            QTimer.singleShot(800, QApplication.quit)
            return json.dumps({"success": True})

        except Exception as e:
            return json.dumps({"success": False, "message": str(e)})


class LauncherWindow(BaseWebWindow):
    """Main launcher window with web UI."""

    def __init__(self):
        super().__init__(
            title="PHYS 2150 Measurement Suite",
            html_filename="launcher.html",
            size=(500, 350),
            allow_local_file_access=False  # Launcher doesn't need file access
        )

        # Launcher uses fixed size (not resizable)
        self.setFixedSize(500, 350)

        # Center window on screen
        self._center_window()

        # Set up app-specific API
        self.api = LauncherApi(self)
        self.channel.registerObject("api", self.api)

    def _center_window(self):
        """Center the window on the screen."""
        screen = QApplication.primaryScreen()
        screen_geometry = screen.availableGeometry()
        window_geometry = self.frameGeometry()
        center_point = screen_geometry.center()
        window_geometry.moveCenter(center_point)
        self.move(window_geometry.topLeft())


def main():
    """Main entry point for the launcher."""
    app = QApplication(sys.argv)

    window = LauncherWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
