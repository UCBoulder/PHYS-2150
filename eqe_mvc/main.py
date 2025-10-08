"""
Main Application Entry Point

This module contains the main application class that coordinates the
Model-View-Controller components and handles application lifecycle.
"""

import sys
import logging
from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import QThread, QObject, Signal, QMetaObject, Qt

from .models.eqe_experiment import EQEExperimentModel, EQEExperimentError
from .views.main_view import MainApplicationView, create_application
from .utils.data_handling import MeasurementDataLogger


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
        # Use standard Python logging instead of MeasurementDataLogger in worker
        self.logger = logging.getLogger(__name__)
    
    def run(self) -> None:
        """Run device initialization."""
        try:
            self.progress_update.emit("Initializing devices...")
            self.logger.info("Starting device initialization in worker thread")
            
            # Temporarily replace the model's logger with a thread-safe one
            original_logger = self.experiment_model.logger
            thread_safe_logger = logging.getLogger("device_init_worker")
            
            # Create a simple logging adapter that doesn't use Qt components
            class ThreadSafeLoggerAdapter:
                def __init__(self, logger):
                    self._logger = logger
                
                def log(self, message: str, level: str = "INFO"):
                    if level.upper() == "ERROR":
                        self._logger.error(message)
                    elif level.upper() == "WARNING":
                        self._logger.warning(message)
                    else:
                        self._logger.info(message)
            
            # Replace the logger temporarily
            self.experiment_model.logger = ThreadSafeLoggerAdapter(thread_safe_logger)
            
            try:
                success = self.experiment_model.initialize_devices()
            finally:
                # Restore the original logger
                self.experiment_model.logger = original_logger
            
            if success:
                self.logger.info("Device initialization successful")
                self.initialization_complete.emit(True, "All devices initialized successfully")
            else:
                self.logger.warning("Device initialization failed")
                self.initialization_complete.emit(False, "Device initialization failed")
                
        except EQEExperimentError as e:
            self.logger.error(f"EQE initialization error: {e}")
            self.initialization_complete.emit(False, f"Initialization error: {e}")
        except Exception as e:
            self.logger.error(f"Unexpected initialization error: {e}")
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
        # Set up logging
        self._setup_logging()
        
        # Create QApplication
        self.qt_app = create_application()
        
        # Create logger
        self.logger = MeasurementDataLogger("eqe_application.log")
        
        # Create model and view
        self.experiment_model = EQEExperimentModel(self.logger)
        self.main_view = MainApplicationView()
        
        # Device initialization components
        self.init_thread: QThread = None
        self.init_worker: DeviceInitializationWorker = None
        
        # Connect model and view
        self._connect_components()
        
        self.logger.log("EQE Application initialized")
    
    def _setup_logging(self) -> None:
        """Set up application logging."""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('eqe_application.log'),
                logging.StreamHandler()
            ]
        )
    
    def _connect_components(self) -> None:
        """Connect the model and view components."""
        # Set experiment model in view
        self.main_view.set_experiment_model(self.experiment_model)
        
        self.logger.log("Model and view components connected")
    
    def initialize_devices_async(self) -> None:
        """Initialize devices asynchronously in a separate thread."""
        if self.init_thread and self.init_thread.isRunning():
            self.logger.log("Device initialization already in progress", "WARNING")
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
        self.logger.log("Starting device initialization in background thread")
        
        # Update view status - this is safe since we're on the main thread
        try:
            status_display = self.main_view.control_panel.get_status_display()
            status_display.set_status_message("Initializing devices...")
        except Exception as e:
            print(f"Warning: Could not update status display: {e}")
    
    def _on_initialization_progress(self, message: str) -> None:
        """
        Handle initialization progress updates.
        
        Args:
            message: Progress message
        """
        try:
            status_display = self.main_view.control_panel.get_status_display()
            status_display.set_status_message(message)
            # Use print instead of logger to avoid thread issues
            print(f"Initialization progress: {message}")
        except Exception as e:
            print(f"Warning: Could not update progress: {e}")
    
    def _on_initialization_complete(self, success: bool, message: str) -> None:
        """
        Handle initialization completion.
        
        Args:
            success: Whether initialization was successful
            message: Completion message
        """
        try:
            status_display = self.main_view.control_panel.get_status_display()
            
            if success:
                status_display.set_status_message("Ready for measurements")
                print("Device initialization completed successfully")
                
                # Enable controls
                control_buttons = self.main_view.control_panel.get_control_buttons()
                control_buttons.setEnabled(True)
                
            else:
                status_display.set_status_message("Initialization failed")
                print(f"Device initialization failed: {message}")
                
                # Show error dialog
                QMessageBox.critical(
                    self.main_view,
                    "Initialization Failed",
                    f"Failed to initialize devices:\n\n{message}\n\n"
                    "Please check device connections and try restarting the application."
                )
                
                # Disable controls
                control_buttons = self.main_view.control_panel.get_control_buttons()
                control_buttons.setEnabled(False)
        except Exception as e:
            print(f"Error in initialization completion handler: {e}")
    
    def run(self) -> int:
        """
        Run the application.
        
        Returns:
            int: Application exit code
        """
        try:
            # Show main window
            self.main_view.show()
            self.logger.log("Main window displayed")
            
            # Start device initialization
            self.initialize_devices_async()
            
            # Run the Qt event loop
            self.logger.log("Starting Qt application event loop")
            exit_code = self.qt_app.exec()
            
            self.logger.log(f"Application exiting with code {exit_code}")
            return exit_code
            
        except Exception as e:
            self.logger.log(f"Application error: {e}", "ERROR")
            
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
        try:
            self.logger.log("Starting application cleanup")
            
            # Stop any running initialization
            if self.init_thread and self.init_thread.isRunning():
                self.init_thread.quit()
                self.init_thread.wait(5000)  # Wait up to 5 seconds
            
            # Cleanup experiment model
            if self.experiment_model:
                self.experiment_model.cleanup()
            
            self.logger.log("Application cleanup completed")
            
        except Exception as e:
            self.logger.log(f"Error during cleanup: {e}", "ERROR")


def main():
    """Main entry point for the EQE application."""
    try:
        # Create and run application
        app = EQEApplication()
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