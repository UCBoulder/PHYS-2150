"""
Main Application Entry Point

This module contains the main application class that coordinates the
Model-View-Controller components and handles application lifecycle.
"""

import sys
import logging
import os
from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import QThread, QObject, Signal, QMetaObject, Qt

# When running the module directly (python main.py) the package imports
# using relative paths fail because there's no parent package. Add the
# repository root to sys.path so absolute imports work in both modes.
if __package__ is None or __package__ == "":
    # When running as a script, add the parent directory of this package
    # (the repository root) to sys.path so the package `eqe` can be
    # imported as a top-level package. This allows modules inside the
    # package to use their existing relative imports.
    _this_file = os.path.abspath(__file__)
    _package_dir = os.path.dirname(_this_file)  # .../eqe
    _repo_root = os.path.dirname(_package_dir)
    if _repo_root not in sys.path:
        sys.path.insert(0, _repo_root)

# Import using the package-qualified names so internal relative imports
# (like those in models.eqe_experiment) work correctly.
from eqe.models.eqe_experiment import EQEExperimentModel, EQEExperimentError
from eqe.views.main_view import MainApplicationView, create_application
from common.utils import get_logger

# Module-level logger for EQE application
_logger = get_logger("eqe")


class DeviceInitializationWorker(QObject):
    """Worker for device initialization in separate thread."""

    # Signals
    initialization_complete = Signal(bool, str)  # success, message
    progress_update = Signal(str)  # status message

    def __init__(self, experiment_model: EQEExperimentModel):
        """
        Initialize the worker.

        Args:
            experiment_model: Experiment model to initialize
        """
        super().__init__()
        self.experiment_model = experiment_model

    def run(self) -> None:
        """Run device initialization."""
        try:
            self.progress_update.emit("Initializing devices...")
            _logger.info("Starting device initialization in worker thread")

            # Temporarily replace the model's logger and callbacks with
            # thread-safe adapters that emit Qt signals instead of touching
            # GUI objects directly from this worker thread.
            original_logger = self.experiment_model.logger
            original_device_cb = self.experiment_model.device_status_callback
            original_progress_cb = self.experiment_model.measurement_progress_callback
            original_complete_cb = self.experiment_model.experiment_complete_callback

            # Create a thread-safe logger adapter that emits signals
            class ThreadSafeLoggerAdapter:
                def __init__(self, worker):
                    self._worker = worker

                def log(self, message: str, level: str = "INFO"):
                    _logger.info(message) if level == "INFO" else _logger.debug(message)
                    try:
                        self._worker.progress_update.emit(message)
                    except Exception:
                        pass

                def debug(self, message: str):
                    """Debug-level log (no GUI output)."""
                    _logger.debug(message)

            logger_adapter = ThreadSafeLoggerAdapter(self)

            # Replace callbacks with wrappers that emit signals
            def device_status_wrapper(device_name, is_connected, message=""):
                status = "OK" if is_connected else "FAIL"
                try:
                    self.progress_update.emit(f"{device_name}: {status}")
                except Exception:
                    pass

            def measurement_progress_wrapper(measurement_type, progress_data):
                pass  # Not needed during initialization

            def experiment_complete_wrapper(success, message=""):
                pass  # Handled by initialization_complete signal

            # Apply temporary replacements
            self.experiment_model.logger = logger_adapter
            self.experiment_model.device_status_callback = device_status_wrapper
            self.experiment_model.measurement_progress_callback = measurement_progress_wrapper
            self.experiment_model.experiment_complete_callback = experiment_complete_wrapper

            try:
                success = self.experiment_model.initialize_devices()
            finally:
                # Restore the original logger and callbacks
                self.experiment_model.logger = original_logger
                self.experiment_model.device_status_callback = original_device_cb
                self.experiment_model.measurement_progress_callback = original_progress_cb
                self.experiment_model.experiment_complete_callback = original_complete_cb

            if success:
                _logger.info("Device initialization successful")
                self.initialization_complete.emit(True, "All devices initialized")
            else:
                _logger.warning("Device initialization failed")
                self.initialization_complete.emit(False, "Device initialization failed")

        except EQEExperimentError as e:
            _logger.error(f"EQE initialization error: {e}")
            self.initialization_complete.emit(False, f"Initialization error: {e}")
        except Exception as e:
            _logger.error(f"Unexpected initialization error: {e}")
            self.initialization_complete.emit(False, f"Unexpected error: {e}")


class EQEApplication:
    """
    Main application class that coordinates the MVC components.

    This class represents the highest level of the application architecture,
    coordinating the experiment model (M), main view (V), and acting as the
    primary controller (C) for the application lifecycle.
    """

    def __init__(self):
        """Initialize the EQE application."""
        # Create QApplication
        self.qt_app = create_application()

        # Create model and view
        # Logger is shared via the module-level get_logger("eqe")
        self.experiment_model = EQEExperimentModel(_logger)
        self.main_view = MainApplicationView()

        # Device initialization components
        self.init_thread: QThread = None
        self.init_worker: DeviceInitializationWorker = None

        # Connect model and view
        self._connect_components()

        _logger.info("EQE Application initialized")
    
    def _connect_components(self) -> None:
        """Connect the model and view components."""
        # Set experiment model in view
        self.main_view.set_experiment_model(self.experiment_model)

        _logger.debug("Model and view components connected")
    
    def initialize_devices_async(self) -> None:
        """Initialize devices asynchronously in a separate thread."""
        if self.init_thread and self.init_thread.isRunning():
            _logger.warning("Device initialization already in progress")
            return

        # Create thread and worker
        self.init_thread = QThread()
        self.init_worker = DeviceInitializationWorker(self.experiment_model)

        # Move worker to thread
        self.init_worker.moveToThread(self.init_thread)

        # Connect signals with Qt.QueuedConnection to ensure thread-safe GUI updates
        self.init_thread.started.connect(self.init_worker.run)
        self.init_worker.initialization_complete.connect(
            self._on_initialization_complete, Qt.QueuedConnection)
        self.init_worker.progress_update.connect(
            self._on_initialization_progress, Qt.QueuedConnection)
        self.init_worker.initialization_complete.connect(self.init_thread.quit)
        self.init_worker.initialization_complete.connect(self.init_worker.deleteLater)
        self.init_thread.finished.connect(self.init_thread.deleteLater)

        # Start initialization
        self.init_thread.start()
        _logger.info("Starting device initialization in background thread")

        # Update view status - this is safe since we're on the main thread
        try:
            status_display = self.main_view.measurement_tab.get_status_display()
            status_display.set_status_message("Initializing devices...")
        except Exception as e:
            _logger.debug(f"Could not update status display: {e}")
    
    def _on_initialization_progress(self, message: str) -> None:
        """
        Handle initialization progress updates.

        Args:
            message: Progress message
        """
        try:
            status_display = self.main_view.measurement_tab.get_status_display()
            status_display.set_status_message(message)
            _logger.debug(f"Init progress: {message}")
        except Exception as e:
            _logger.debug(f"Could not update progress: {e}")
    
    def _on_initialization_complete(self, success: bool, message: str) -> None:
        """
        Handle initialization completion.

        Args:
            success: Whether initialization was successful
            message: Completion message
        """
        try:
            status_display = self.main_view.measurement_tab.get_status_display()
            plot_widget = self.main_view.measurement_tab.get_plot_widget()
            monochromator_control = self.main_view.measurement_tab.get_monochromator_control()

            if success:
                status_display.set_status_message("Ready for measurements")
                _logger.info("Device initialization completed successfully")

                # Initialize stability test model now that devices are connected
                self.main_view.initialize_stability_model()

                # Enable controls
                plot_widget.set_buttons_enabled(True)
                status_display.live_monitor_button.setEnabled(True)
                monochromator_control.set_enabled(True)

            else:
                status_display.set_status_message("Initialization failed")
                _logger.warning(f"Device initialization failed: {message}")

                # Show error dialog with actionable guidance
                _logger.student_error(
                    "Device Initialization Failed",
                    "Could not connect to all required instruments.",
                    [
                        "One or more devices are not powered on",
                        "USB cables are disconnected",
                        "Another program is using the devices",
                    ],
                    [
                        "Check that all devices are powered on",
                        "Verify USB cable connections",
                        "Close PicoScope 6 or Thorlabs software if open",
                        "Restart the application",
                    ]
                )

                # Disable controls
                plot_widget.set_buttons_enabled(False)
                status_display.live_monitor_button.setEnabled(False)
                monochromator_control.set_enabled(False)
        except Exception as e:
            _logger.error(f"Error in initialization completion handler: {e}")
    
    def run(self) -> int:
        """
        Run the application.

        Returns:
            int: Application exit code
        """
        try:
            # Show main window
            self.main_view.show()
            _logger.debug("Main window displayed")

            # Start device initialization
            self.initialize_devices_async()

            # Run the Qt event loop
            _logger.debug("Starting Qt application event loop")
            exit_code = self.qt_app.exec()

            _logger.info(f"Application exiting with code {exit_code}")
            return exit_code

        except Exception as e:
            _logger.error(f"Application error: {e}")

            # Show error dialog if possible
            try:
                QMessageBox.critical(
                    None, "Application Error",
                    f"An unexpected error occurred:\n\n{e}\n\n"
                    "The application will now exit."
                )
            except:
                pass  # GUI might not be available

            return 1

        finally:
            # Cleanup
            self._cleanup()
    
    def _cleanup(self) -> None:
        """Clean up application resources."""
        import os
        import sys
        try:
            _logger.debug("Starting application cleanup")

            # Stop any running initialization
            # Wrap in try-except since Qt may have already deleted the thread
            try:
                if self.init_thread and self.init_thread.isRunning():
                    self.init_thread.quit()
                    self.init_thread.wait(5000)  # Wait up to 5 seconds
            except RuntimeError:
                # Thread already deleted by Qt, ignore
                pass

            # Cleanup experiment model
            if self.experiment_model:
                self.experiment_model.cleanup()

            _logger.debug("Application cleanup completed")

        except Exception as e:
            _logger.error(f"Error during cleanup: {e}")
        finally:
            # Flush all output streams before exit
            sys.stdout.flush()
            sys.stderr.flush()
            # Force terminate the process immediately
            os._exit(0)


def main():
    """Main entry point for the EQE application."""
    import argparse

    # Parse command line arguments
    parser = argparse.ArgumentParser(description='EQE Measurement Application')
    parser.add_argument('--offline', action='store_true',
                       help='Run in offline mode without hardware (for GUI testing)')
    args = parser.parse_args()

    # Set offline mode in config
    if args.offline:
        _logger.info("Running in OFFLINE mode - hardware initialization disabled")
        from eqe.config import settings
        settings.OFFLINE_MODE = True

    try:
        # Create and run application
        # Note: app.run() calls _cleanup() which calls os._exit()
        # so this function will not return normally
        app = EQEApplication()
        app.run()

    except KeyboardInterrupt:
        _logger.info("Application interrupted by user")
        sys.exit(1)
    except Exception as e:
        _logger.error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()