"""
JV Measurement Application Entry Point

This module contains the main application class that coordinates the
Model-View-Controller components and handles application lifecycle.
"""

import sys
import os
import logging
from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import QTimer, Qt

# When running the module directly (python main.py) the package imports
# using relative paths fail because there's no parent package. Add the
# repository root to sys.path so absolute imports work in both modes.
if __package__ is None or __package__ == "":
    _this_file = os.path.abspath(__file__)
    _package_dir = os.path.dirname(_this_file)
    _repo_root = os.path.dirname(_package_dir)
    if _repo_root not in sys.path:
        sys.path.insert(0, _repo_root)

from jv.models.jv_experiment import JVExperimentModel, JVExperimentError
from jv.views.main_window import JVMainWindow
from jv.config import settings


def create_application() -> QApplication:
    """
    Create and configure the Qt application.

    Returns:
        QApplication: Configured Qt application instance
    """
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


class JVApplication:
    """
    Main application class that coordinates the MVC components.

    This class represents the highest level of the application architecture,
    coordinating the experiment model (M), main view (V), and handling
    the application lifecycle.
    """

    def __init__(self):
        """Initialize the JV application."""
        # Set up logging
        self._setup_logging()

        # Create QApplication
        self.qt_app = create_application()

        # Create model and view
        self.experiment_model = JVExperimentModel()
        self.main_window = JVMainWindow()

        # Connect model and view
        self.main_window.set_experiment_model(self.experiment_model)

        logging.info("JV Application initialized")

    def _setup_logging(self) -> None:
        """Set up application logging."""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('jv_application.log'),
                logging.StreamHandler()
            ]
        )

    def initialize_device(self) -> bool:
        """
        Initialize the measurement device.

        Returns:
            bool: True if successful
        """
        try:
            return self.experiment_model.initialize_device()
        except JVExperimentError as e:
            logging.error(f"Device initialization failed: {e}")
            QMessageBox.critical(
                self.main_window,
                "Device Error",
                str(e)
            )
            return False

    def run(self) -> int:
        """
        Run the application.

        Returns:
            int: Application exit code
        """
        try:
            # Show main window
            self.main_window.showMaximized()
            logging.info("Main window displayed")

            # Initialize device after window is shown
            # Use QTimer to allow event loop to start first
            QTimer.singleShot(100, self._delayed_init)

            # Run Qt event loop
            logging.info("Starting Qt event loop")
            exit_code = self.qt_app.exec()

            logging.info(f"Application exiting with code {exit_code}")
            return exit_code

        except Exception as e:
            logging.error(f"Application error: {e}")

            try:
                QMessageBox.critical(
                    None,
                    "Application Error",
                    f"An unexpected error occurred:\n\n{e}\n\n"
                    "The application will now exit."
                )
            except:
                pass

            return 1

        finally:
            self._cleanup()

    def _delayed_init(self) -> None:
        """Perform delayed initialization after window is shown."""
        # Initialize device
        if self.initialize_device():
            # Show cell number popup after successful init
            QTimer.singleShot(500, self.main_window.show_cell_number_popup)
        else:
            # Device failed - still show window but disabled
            pass

    def _cleanup(self) -> None:
        """Clean up application resources."""
        try:
            logging.info("Starting application cleanup")

            if self.experiment_model:
                self.experiment_model.cleanup()

            logging.info("Application cleanup completed")

        except Exception as e:
            logging.error(f"Cleanup error: {e}")


def main():
    """Main entry point for the JV application."""
    import argparse

    # Parse command line arguments
    parser = argparse.ArgumentParser(description='JV Measurement Application')
    parser.add_argument(
        '--offline',
        action='store_true',
        help='Run in offline mode without hardware (for GUI testing)'
    )
    args = parser.parse_args()

    # Set offline mode
    if args.offline:
        print("Running in OFFLINE mode - hardware initialization disabled")
        settings.OFFLINE_MODE = True

    try:
        app = JVApplication()
        exit_code = app.run()
        sys.exit(exit_code)

    except KeyboardInterrupt:
        print("\nApplication interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
