"""
EQE Measurement Application (Web UI)

Qt WebEngine-based interface for EQE characterization.
Uses the same models and controllers as the Qt widget version,
but with a web-based frontend for full HTML/CSS/JS flexibility.
"""

import os
import sys
import json
from typing import Optional, Dict, Any

from PySide6.QtCore import Qt, QObject, Slot, QUrl, QThread, Signal
from PySide6.QtWidgets import QApplication, QMainWindow, QFileDialog
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebChannel import QWebChannel

from .models.eqe_experiment import EQEExperimentModel, EQEExperimentError
from .config.settings import GUI_CONFIG, DEFAULT_MEASUREMENT_PARAMS
from .config import settings
from common.utils import get_logger

_logger = get_logger("eqe")


class EQEApi(QObject):
    """
    Python API exposed to JavaScript via QWebChannel.

    Handles device communication, measurement control, and data export.
    """

    def __init__(self, window: 'EQEWebWindow'):
        super().__init__()
        self._window = window
        self._experiment: Optional[EQEExperimentModel] = None

    def set_experiment(self, experiment: EQEExperimentModel) -> None:
        """Set the experiment model and connect signals."""
        self._experiment = experiment

        # Connect model signals to push data to JS
        self._experiment.device_status_changed.connect(self._on_device_status_changed)
        self._experiment.measurement_progress.connect(self._on_measurement_progress)
        self._experiment.experiment_complete.connect(self._on_experiment_complete)
        self._experiment.live_signal_update.connect(self._on_live_signal_update)
        self._experiment.monochromator_state_changed.connect(self._on_monochromator_state_changed)

    # ==================== Device Status ====================

    @Slot(result=str)
    def get_device_status(self) -> str:
        """Get current device connection status."""
        offline_mode = getattr(settings, 'OFFLINE_MODE', False)

        if offline_mode:
            return json.dumps({
                "picoscope": {"connected": False, "message": "Offline mode"},
                "monochromator": {"connected": False, "message": "Offline mode"},
                "power_meter": {"connected": False, "message": "Offline mode"},
                "offline_mode": True
            })

        if self._experiment:
            status = self._experiment.get_device_status()
            return json.dumps({
                "picoscope": {
                    "connected": status.get('lockin', False),
                    "message": "PicoScope 5000" if status.get('lockin') else "Not connected"
                },
                "monochromator": {
                    "connected": status.get('monochromator', False),
                    "message": "Cornerstone 130" if status.get('monochromator') else "Not connected"
                },
                "power_meter": {
                    "connected": status.get('power_meter', False),
                    "message": "Thorlabs PM" if status.get('power_meter') else "Not connected"
                },
                "offline_mode": False
            })

        return json.dumps({
            "picoscope": {"connected": False, "message": "No experiment model"},
            "monochromator": {"connected": False, "message": "No experiment model"},
            "power_meter": {"connected": False, "message": "No experiment model"},
            "offline_mode": False
        })

    @Slot(result=str)
    def get_monochromator_state(self) -> str:
        """Get current monochromator state."""
        if self._experiment:
            state = self._experiment.get_monochromator_state()
            return json.dumps(state)
        return json.dumps({"wavelength": 0.0, "shutter_open": False, "filter": 0})

    # ==================== Measurements ====================

    @Slot(str, result=str)
    def start_power_measurement(self, params_json: str) -> str:
        """Start a power measurement."""
        if not self._experiment:
            return json.dumps({"success": False, "message": "No experiment model"})

        try:
            params = json.loads(params_json)

            # Set parameters
            self._experiment.set_measurement_parameters(
                start_wavelength=params["start_wavelength"],
                end_wavelength=params["end_wavelength"],
                step_size=params["step_size"],
                cell_number=params["cell_number"],
            )

            # Start measurement
            self._experiment.start_power_measurement()
            return json.dumps({"success": True})

        except EQEExperimentError as e:
            return json.dumps({"success": False, "message": str(e)})
        except Exception as e:
            _logger.error(f"Power measurement start failed: {e}")
            return json.dumps({"success": False, "message": str(e)})

    @Slot(str, result=str)
    def start_current_measurement(self, params_json: str) -> str:
        """Start a current measurement (includes phase adjustment first)."""
        if not self._experiment:
            return json.dumps({"success": False, "message": "No experiment model"})

        try:
            params = json.loads(params_json)

            # Set parameters
            self._experiment.set_measurement_parameters(
                start_wavelength=params["start_wavelength"],
                end_wavelength=params["end_wavelength"],
                step_size=params["step_size"],
                cell_number=params["cell_number"],
                pixel_number=params["pixel"],
            )

            # Start phase adjustment first (current measurement follows automatically)
            self._experiment.start_phase_adjustment(params["pixel"])
            return json.dumps({"success": True, "phase": "adjusting"})

        except EQEExperimentError as e:
            return json.dumps({"success": False, "message": str(e)})
        except Exception as e:
            _logger.error(f"Current measurement start failed: {e}")
            return json.dumps({"success": False, "message": str(e)})

    @Slot(result=str)
    def stop_measurement(self) -> str:
        """Stop any running measurement."""
        if self._experiment:
            self._experiment.stop_all_measurements()
        return json.dumps({"success": True})

    # ==================== Monochromator Control ====================

    @Slot(float, result=str)
    def set_wavelength(self, wavelength: float) -> str:
        """Set monochromator wavelength."""
        if not self._experiment:
            return json.dumps({"success": False, "message": "No experiment model"})

        try:
            self._experiment.set_wavelength_manual(wavelength)
            return json.dumps({"success": True})
        except EQEExperimentError as e:
            return json.dumps({"success": False, "message": str(e)})

    @Slot(result=str)
    def open_shutter(self) -> str:
        """Open monochromator shutter."""
        if not self._experiment:
            return json.dumps({"success": False, "message": "No experiment model"})

        try:
            self._experiment.open_shutter_manual()
            return json.dumps({"success": True})
        except EQEExperimentError as e:
            return json.dumps({"success": False, "message": str(e)})

    @Slot(result=str)
    def close_shutter(self) -> str:
        """Close monochromator shutter."""
        if not self._experiment:
            return json.dumps({"success": False, "message": "No experiment model"})

        try:
            self._experiment.close_shutter_manual()
            return json.dumps({"success": True})
        except EQEExperimentError as e:
            return json.dumps({"success": False, "message": str(e)})

    @Slot(result=str)
    def align_monochromator(self) -> str:
        """Align monochromator (set to green 532nm with shutter open)."""
        if not self._experiment:
            return json.dumps({"success": False, "message": "No experiment model"})

        try:
            self._experiment.align_monochromator()
            return json.dumps({"success": True})
        except EQEExperimentError as e:
            return json.dumps({"success": False, "message": str(e)})

    # ==================== Live Monitor ====================

    @Slot(result=str)
    def start_live_monitor(self) -> str:
        """Start live signal monitoring."""
        if not self._experiment:
            return json.dumps({"success": False, "message": "No experiment model"})

        try:
            self._experiment.start_live_signal_monitor()
            return json.dumps({"success": True})
        except EQEExperimentError as e:
            return json.dumps({"success": False, "message": str(e)})

    @Slot(result=str)
    def stop_live_monitor(self) -> str:
        """Stop live signal monitoring."""
        if self._experiment:
            self._experiment.stop_live_signal_monitor()
        return json.dumps({"success": True})

    # ==================== Data Export ====================

    @Slot(str, str, result=str)
    def save_power_data(self, csv_content: str, cell_number: str) -> str:
        """Save power measurement data to file."""
        from datetime import datetime

        timestamp = datetime.now().strftime("%Y%m%d")
        default_filename = f"power_cell{cell_number}_{timestamp}.csv"

        file_path, _ = QFileDialog.getSaveFileName(
            self._window,
            "Save Power Data",
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

    @Slot(str, str, int, result=str)
    def save_current_data(self, csv_content: str, cell_number: str, pixel: int) -> str:
        """Save current measurement data to file."""
        from datetime import datetime

        timestamp = datetime.now().strftime("%Y%m%d")
        default_filename = f"current_cell{cell_number}_pixel{pixel}_{timestamp}.csv"

        file_path, _ = QFileDialog.getSaveFileName(
            self._window,
            "Save Current Data",
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

    # ==================== Signal Handlers ====================

    def _on_device_status_changed(self, device_name: str, is_connected: bool, message: str) -> None:
        """Forward device status change to JS."""
        js = f"onDeviceStatusChanged('{device_name}', {str(is_connected).lower()}, '{message}')"
        self._window.run_js(js)

    def _on_measurement_progress(self, measurement_type: str, progress_data: Dict) -> None:
        """Forward measurement progress to JS."""
        if measurement_type == "power":
            js = f"onPowerProgress({progress_data['wavelength']}, {progress_data['power']}, {progress_data['progress_percent']})"
        elif measurement_type == "current":
            js = f"onCurrentProgress({progress_data['wavelength']}, {progress_data['current']}, {progress_data['progress_percent']})"
        elif measurement_type == "phase":
            js = f"onPhaseProgress({progress_data['phase']}, {progress_data['signal']})"
        else:
            return
        self._window.run_js(js)

    def _on_experiment_complete(self, success: bool, message: str) -> None:
        """Forward experiment completion to JS."""
        # Escape message for JS string
        escaped_message = message.replace("'", "\\'")
        js = f"onMeasurementComplete({str(success).lower()}, '{escaped_message}')"
        self._window.run_js(js)

    def _on_live_signal_update(self, current_nA: float) -> None:
        """Forward live signal update to JS."""
        js = f"onLiveSignalUpdate({current_nA})"
        self._window.run_js(js)

    def _on_monochromator_state_changed(self, wavelength: float, shutter_open: bool, filter_number: int) -> None:
        """Forward monochromator state change to JS."""
        js = f"onMonochromatorStateChanged({wavelength}, {str(shutter_open).lower()}, {filter_number})"
        self._window.run_js(js)


class EQEWebWindow(QMainWindow):
    """Main window for EQE measurement with web UI."""

    def __init__(self):
        super().__init__()

        self.setWindowTitle("EQE Measurement - PHYS 2150")
        # Match existing GUI_CONFIG window size
        self.resize(1400, 950)
        self.setMinimumSize(1000, 700)

        # Track if page is ready for JS calls
        self._page_ready = False
        self._pending_js: list[str] = []

        # Create web view
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
        self.api = EQEApi(self)
        self.channel.registerObject("api", self.api)
        self.web_view.page().setWebChannel(self.channel)

        # Connect load finished signal
        self.web_view.loadFinished.connect(self._on_page_loaded)

        # Load HTML
        html_path = self._get_html_path()
        self.web_view.setUrl(QUrl.fromLocalFile(html_path))

        # Experiment model (initialized later)
        self._experiment: Optional[EQEExperimentModel] = None

    def _on_page_loaded(self, success: bool) -> None:
        """Handle page load completion."""
        if success:
            self._page_ready = True
            # Execute any pending JS calls
            for js in self._pending_js:
                self.web_view.page().runJavaScript(js)
            self._pending_js.clear()

    def _get_html_path(self) -> str:
        """Get path to EQE HTML file."""
        if getattr(sys, 'frozen', False):
            base_path = sys._MEIPASS
        else:
            # Go up from eqe/ to project root, then into ui/
            base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        return os.path.join(base_path, 'ui', 'eqe.html')

    def run_js(self, script: str) -> None:
        """Execute JavaScript in the web view (queues if page not ready)."""
        if self._page_ready:
            self.web_view.page().runJavaScript(script)
        else:
            self._pending_js.append(script)

    def set_experiment(self, experiment: EQEExperimentModel) -> None:
        """Set the experiment model."""
        self._experiment = experiment
        self.api.set_experiment(experiment)

    def closeEvent(self, event) -> None:
        """Handle window close."""
        if self._experiment:
            self._experiment.stop_all_measurements()
            self._experiment.cleanup()
        event.accept()


class EQEWebApplication:
    """
    Main application class for EQE measurement with web UI.

    Manages the application lifecycle, device initialization,
    and coordination between model and view.
    """

    def __init__(self):
        self.app = QApplication.instance() or QApplication(sys.argv)
        self.window = EQEWebWindow()
        self.experiment = EQEExperimentModel()

        # Connect experiment to window
        self.window.set_experiment(self.experiment)

    def run(self) -> int:
        """Run the application."""
        # Initialize experiment (connects to hardware)
        try:
            self.experiment.initialize_devices()
        except EQEExperimentError as e:
            _logger.warning(f"Device initialization failed: {e}")
            # Continue anyway - UI will show disconnected status

        self.window.show()
        return self.app.exec()


def main():
    """Entry point for EQE web application."""
    import argparse

    # Parse command line arguments
    parser = argparse.ArgumentParser(description='EQE Measurement Application')
    parser.add_argument(
        '--offline',
        action='store_true',
        help='Run in offline mode without hardware (for GUI testing)'
    )
    args = parser.parse_args()

    # Set offline mode in settings
    if args.offline:
        print("Running in OFFLINE mode - mock measurements enabled")
        settings.OFFLINE_MODE = True
    else:
        settings.OFFLINE_MODE = False

    try:
        app = EQEWebApplication()
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
