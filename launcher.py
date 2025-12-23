"""
PHYS 2150 Measurement Suite Launcher

Unified launcher for the EQE and J-V measurement applications.
Provides a simple interface to select which measurement to perform.
"""

import sys
import os
import subprocess
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QFrame,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont


class LauncherWindow(QMainWindow):
    """
    Main launcher window for selecting measurement application.
    """

    def __init__(self):
        super().__init__()

        self.setWindowTitle("PHYS 2150 Measurement Suite")
        self.setFixedSize(500, 350)

        # Center window on screen
        self._center_window()

        # Create UI
        self._setup_ui()

    def _center_window(self):
        """Center the window on the screen."""
        screen = QApplication.primaryScreen()
        screen_geometry = screen.availableGeometry()
        window_geometry = self.frameGeometry()
        center_point = screen_geometry.center()
        window_geometry.moveCenter(center_point)
        self.move(window_geometry.topLeft())

    def _setup_ui(self):
        """Set up the user interface."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        layout = QVBoxLayout(central_widget)
        layout.setSpacing(20)
        layout.setContentsMargins(30, 30, 30, 30)

        # Title
        title_label = QLabel("PHYS 2150 Measurement Suite")
        title_font = QFont()
        title_font.setPointSize(18)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)

        # Subtitle
        subtitle_label = QLabel("Select a measurement application:")
        subtitle_font = QFont()
        subtitle_font.setPointSize(11)
        subtitle_label.setFont(subtitle_font)
        subtitle_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(subtitle_label)

        layout.addSpacing(10)

        # Buttons container
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(20)

        # EQE Button with description
        eqe_frame = self._create_measurement_button(
            "EQE Measurement",
            "External Quantum Efficiency\n\nMeasure spectral response\nof solar cell pixels",
            "#4A90D9",  # Blue
            self._launch_eqe
        )
        buttons_layout.addWidget(eqe_frame)

        # JV Button with description
        jv_frame = self._create_measurement_button(
            "J-V Measurement",
            "Current-Voltage Characterization\n\nMeasure J-V curves\nfor solar cell analysis",
            "#5DAE5D",  # Green
            self._launch_jv
        )
        buttons_layout.addWidget(jv_frame)

        layout.addLayout(buttons_layout)

        layout.addStretch()

        # Footer
        footer_label = QLabel("CU Boulder Physics Undergraduate Labs")
        footer_label.setAlignment(Qt.AlignCenter)
        footer_label.setStyleSheet("color: gray;")
        layout.addWidget(footer_label)

    def _create_measurement_button(
        self,
        title: str,
        description: str,
        color: str,
        callback,
    ) -> QFrame:
        """
        Create a measurement button with description.

        Args:
            title: Button title
            description: Description text
            color: Background color for the button
            callback: Function to call when clicked

        Returns:
            QFrame containing the button and description
        """
        frame = QFrame()
        frame.setFrameStyle(QFrame.NoFrame)
        frame_layout = QVBoxLayout(frame)
        frame_layout.setSpacing(10)
        frame_layout.setContentsMargins(10, 10, 10, 10)

        # Main button
        button = QPushButton(title)
        button.setMinimumSize(180, 80)
        button_font = QFont()
        button_font.setPointSize(12)
        button_font.setBold(True)
        button.setFont(button_font)
        button.setStyleSheet(f"""
            QPushButton {{
                background-color: {color};
                color: white;
                border: none;
                border-radius: 8px;
                padding: 15px;
            }}
            QPushButton:hover {{
                background-color: {self._darken_color(color)};
            }}
            QPushButton:pressed {{
                background-color: {self._darken_color(color, 0.7)};
            }}
        """)
        button.clicked.connect(callback)
        frame_layout.addWidget(button)

        return frame

    def _darken_color(self, hex_color: str, factor: float = 0.85) -> str:
        """Darken a hex color by a factor."""
        hex_color = hex_color.lstrip('#')
        r = int(int(hex_color[0:2], 16) * factor)
        g = int(int(hex_color[2:4], 16) * factor)
        b = int(int(hex_color[4:6], 16) * factor)
        return f"#{r:02x}{g:02x}{b:02x}"

    def _launch_eqe(self):
        """Launch the EQE measurement application."""
        self._launch_application("eqe")

    def _launch_jv(self):
        """Launch the J-V measurement application."""
        self._launch_application("jv")

    def _launch_application(self, app_name: str):
        """
        Launch a measurement application.

        Args:
            app_name: Name of the application module ("eqe" or "jv")
        """
        # Hide the launcher
        self.hide()

        # Get the directory containing the launcher
        launcher_dir = os.path.dirname(os.path.abspath(__file__))

        # Launch as a subprocess so the launcher can close cleanly
        # Use sys.executable to ensure we use the same Python interpreter
        try:
            if sys.platform == 'win32':
                # On Windows, create a new console for the subprocess
                # This prevents the parent terminal from waiting for subprocess I/O
                subprocess.Popen(
                    [sys.executable, "-m", app_name],
                    cwd=launcher_dir,
                    creationflags=subprocess.CREATE_NEW_CONSOLE,
                )
            else:
                subprocess.Popen(
                    [sys.executable, "-m", app_name],
                    cwd=launcher_dir,
                    start_new_session=True,
                )
        except Exception as e:
            print(f"Failed to launch {app_name}: {e}")
            self.show()
            return

        # Close the launcher
        QApplication.quit()


def main():
    """Main entry point for the launcher."""
    app = QApplication(sys.argv)

    window = LauncherWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
