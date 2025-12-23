"""
J-V Measurement Application (Web UI)

Qt WebEngine-based interface for J-V characterization.
Uses the same models and controllers as the Qt widget version,
but with a web-based frontend for full HTML/CSS/JS flexibility.
"""

import os
import sys
import json
from typing import Optional

from PySide6.QtCore import Qt, QObject, Slot, QUrl, QThread, Signal
from PySide6.QtWidgets import QApplication, QMainWindow, QFileDialog
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebChannel import QWebChannel

from .models.jv_experiment import JVExperimentModel, JVExperimentError
from .models.jv_measurement import JVMeasurementResult
from .utils.data_export import JVDataExporter
from .config.settings import GUI_CONFIG, VALIDATION_PATTERNS, DEFAULT_MEASUREMENT_PARAMS
from common.utils import get_logger

_logger = get_logger("jv")


class JVApi(QObject):
    """
    Python API exposed to JavaScript via QWebChannel.

    Handles device communication, measurement control, and data export.
    """

    def __init__(self, window: 'JVWebWindow'):
        super().__init__()
        self._window = window
        self._experiment: Optional[JVExperimentModel] = None
        self._exporter = JVDataExporter()
        self._current_result: Optional[JVMeasurementResult] = None

    def set_experiment(self, experiment: JVExperimentModel) -> None:
        """Set the experiment model and connect signals."""
        self._experiment = experiment

        # Connect model signals to push data to JS
        self._experiment.measurement_point.connect(self._on_measurement_point)
        self._experiment.measurement_complete.connect(self._on_measurement_complete)
        self._experiment.device_status_changed.connect(self._on_device_status_changed)

    @Slot(result=str)
    def get_device_status(self) -> str:
        """Get current device connection status."""
        from .config import settings
        offline_mode = getattr(settings, 'OFFLINE_MODE', False)

        if self._experiment:
            connected = self._experiment.is_initialized()
            if connected:
                message = "Keithley 2450"
            elif offline_mode:
                message = "Offline mode"
            else:
                message = "Not connected"
            return json.dumps({
                "connected": connected,
                "message": message,
                "offline_mode": offline_mode
            })
        return json.dumps({
            "connected": False,
            "message": "No experiment model",
            "offline_mode": offline_mode
        })

    @Slot(str, result=str)
    def start_measurement(self, params_json: str) -> str:
        """
        Start a J-V measurement.

        Args:
            params_json: JSON string with measurement parameters

        Returns:
            JSON string with success status
        """
        if not self._experiment:
            return json.dumps({"success": False, "message": "No experiment model"})

        try:
            params = json.loads(params_json)

            # Set parameters
            self._experiment.set_parameters(
                start_voltage=params["start_voltage"],
                stop_voltage=params["stop_voltage"],
                step_voltage=params["step_voltage"],
                cell_number=params["cell_number"],
            )

            # Start measurement
            self._experiment.start_measurement(params["pixel"])
            return json.dumps({"success": True})

        except JVExperimentError as e:
            return json.dumps({"success": False, "message": str(e)})
        except Exception as e:
            _logger.error(f"Measurement start failed: {e}")
            return json.dumps({"success": False, "message": str(e)})

    @Slot(result=str)
    def stop_measurement(self) -> str:
        """Stop the current measurement."""
        if self._experiment:
            self._experiment.stop_measurement()
        return json.dumps({"success": True})

    @Slot(str, result=str)
    def save_data(self, cell_number: str) -> str:
        """
        Save measurement data to file.

        Args:
            cell_number: Cell number for filename

        Returns:
            JSON string with success status and file path
        """
        if not self._current_result:
            return json.dumps({"success": False, "message": "No data to save"})

        # Generate default filename
        default_filename = self._exporter.generate_filename(
            cell_number,
            self._current_result.pixel_number
        )

        # Show save dialog
        file_path, _ = QFileDialog.getSaveFileName(
            self._window,
            "Save J-V Data",
            default_filename,
            "CSV files (*.csv)"
        )

        if file_path:
            try:
                self._exporter.save_measurement(self._current_result, file_path)
                return json.dumps({"success": True, "path": file_path})
            except Exception as e:
                return json.dumps({"success": False, "message": str(e)})

        return json.dumps({"success": False, "message": "Cancelled"})

    @Slot(str, str, int, result=str)
    def save_csv_data(self, csv_content: str, cell_number: str, pixel: int) -> str:
        """
        Save CSV data directly (for mock/offline mode).

        Args:
            csv_content: CSV string to save
            cell_number: Cell number for filename
            pixel: Pixel number for filename

        Returns:
            JSON string with success status and file path
        """
        from datetime import datetime

        # Generate default filename
        timestamp = datetime.now().strftime("%Y%m%d")
        default_filename = f"JV_Cell{cell_number}_Pixel{pixel}_{timestamp}.csv"

        # Show save dialog
        file_path, _ = QFileDialog.getSaveFileName(
            self._window,
            "Save J-V Data",
            default_filename,
            "CSV files (*.csv)"
        )

        if file_path:
            try:
                with open(file_path, 'w', newline='') as f:
                    f.write(csv_content)
                return json.dumps({"success": True, "path": file_path})
            except Exception as e:
                return json.dumps({"success": False, "message": str(e)})

        return json.dumps({"success": False, "message": "Cancelled"})

    def _on_measurement_point(self, direction: str, voltage: float, current: float) -> None:
        """Forward measurement point to JS."""
        js = f"onMeasurementPoint('{direction}', {voltage}, {current})"
        self._window.run_js(js)

    def _on_measurement_complete(self, success: bool, result: JVMeasurementResult) -> None:
        """Forward measurement completion to JS."""
        self._current_result = result if success else None
        js = f"onMeasurementComplete({str(success).lower()})"
        self._window.run_js(js)

    def _on_device_status_changed(self, connected: bool, message: str) -> None:
        """Forward device status change to JS."""
        js = f"updateDeviceStatus({str(connected).lower()}, '{message}')"
        self._window.run_js(js)


class JVWebWindow(QMainWindow):
    """Main window for J-V measurement with web UI."""

    def __init__(self):
        super().__init__()

        self.setWindowTitle("J-V Measurement - PHYS 2150")
        # Start with reasonable size, allow resizing
        self.resize(1200, 800)
        self.setMinimumSize(800, 600)

        # Track if page is ready for JS calls
        self._page_ready = False
        self._pending_js: list[str] = []

        # Create web view with dev tools enabled
        self.web_view = QWebEngineView()
        self.web_view.page().settings().setAttribute(
            self.web_view.page().settings().WebAttribute.LocalContentCanAccessRemoteUrls, True
        )
        self.web_view.page().settings().setAttribute(
            self.web_view.page().settings().WebAttribute.LocalContentCanAccessFileUrls, True
        )
        self.setCentralWidget(self.web_view)

        # Set up web channel
        self.channel = QWebChannel()
        self.api = JVApi(self)
        self.channel.registerObject("api", self.api)
        self.web_view.page().setWebChannel(self.channel)

        # Connect load finished signal
        self.web_view.loadFinished.connect(self._on_page_loaded)

        # Load HTML
        html_path = self._get_html_path()
        self.web_view.setUrl(QUrl.fromLocalFile(html_path))

        # Experiment model (initialized later)
        self._experiment: Optional[JVExperimentModel] = None

    def _on_page_loaded(self, success: bool) -> None:
        """Handle page load completion."""
        if success:
            self._page_ready = True
            # Execute any pending JS calls
            for js in self._pending_js:
                self.web_view.page().runJavaScript(js)
            self._pending_js.clear()

    def _get_html_path(self) -> str:
        """Get path to J-V HTML file."""
        if getattr(sys, 'frozen', False):
            base_path = sys._MEIPASS
        else:
            # Go up from jv/ to project root, then into ui/
            base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        return os.path.join(base_path, 'ui', 'jv.html')

    def run_js(self, script: str) -> None:
        """Execute JavaScript in the web view (queues if page not ready)."""
        if self._page_ready:
            self.web_view.page().runJavaScript(script)
        else:
            self._pending_js.append(script)

    def set_experiment(self, experiment: JVExperimentModel) -> None:
        """Set the experiment model."""
        self._experiment = experiment
        self.api.set_experiment(experiment)

    def closeEvent(self, event) -> None:
        """Handle window close."""
        if self._experiment:
            if self._experiment.is_measuring():
                self._experiment.stop_measurement()
            self._experiment.cleanup()
        event.accept()


class JVWebApplication:
    """
    Main application class for J-V measurement with web UI.

    Manages the application lifecycle, device initialization,
    and coordination between model and view.
    """

    def __init__(self):
        self.app = QApplication.instance() or QApplication(sys.argv)
        self.window = JVWebWindow()
        self.experiment = JVExperimentModel()

        # Connect experiment to window
        self.window.set_experiment(self.experiment)

    def run(self) -> int:
        """Run the application."""
        # Initialize experiment (connects to hardware)
        try:
            self.experiment.initialize_device()
        except JVExperimentError as e:
            _logger.warning(f"Device initialization failed: {e}")
            # Continue anyway - UI will show disconnected status

        self.window.show()
        return self.app.exec()


def main():
    """Entry point for J-V web application."""
    import argparse

    # Parse command line arguments
    parser = argparse.ArgumentParser(description='J-V Measurement Application')
    parser.add_argument(
        '--offline',
        action='store_true',
        help='Run in offline mode without hardware (for GUI testing)'
    )
    args = parser.parse_args()

    # Set offline mode in settings
    from .config import settings
    if args.offline:
        print("Running in OFFLINE mode - mock measurements enabled")
        settings.OFFLINE_MODE = True
    else:
        settings.OFFLINE_MODE = False

    try:
        app = JVWebApplication()
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
