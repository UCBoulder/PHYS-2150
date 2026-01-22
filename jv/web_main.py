"""
J-V Measurement Application (Web UI)

Qt WebEngine-based interface for J-V characterization.
Uses the same models and controllers as the Qt widget version,
but with a web-based frontend for full HTML/CSS/JS flexibility.
"""

import os
import sys
import json
import logging
import ctypes
from typing import Optional

from PySide6.QtCore import Qt, QObject, Slot, QUrl, QThread, Signal, Slot as QtSlot
from PySide6.QtWidgets import QApplication, QFileDialog
from PySide6.QtWebChannel import QWebChannel

from .models.jv_experiment import JVExperimentModel, JVExperimentError
from .models.jv_measurement import JVMeasurementResult
from .utils.data_export import JVDataExporter
from .config.settings import (
    GUI_CONFIG, VALIDATION_PATTERNS, DEFAULT_MEASUREMENT_PARAMS,
    JV_STABILITY_TEST_CONFIG, DATA_EXPORT_CONFIG
)
from common.utils import get_logger, TieredLogger, WebConsoleHandler
from common.utils.remote_config import get_remote_config, deep_merge
from common.ui import BaseWebWindow, BaseWebApi

_logger = get_logger("jv")


class JVApi(BaseWebApi):
    """
    Python API exposed to JavaScript via QWebChannel.

    Handles device communication, measurement control, and data export.
    """

    # Internal signals for thread-safe marshaling of callbacks from worker thread
    # When measurement callbacks emit signals from the worker thread, Qt needs to
    # marshal them to the main thread before calling run_js()
    _measurement_point_signal = Signal(str, float, float)  # direction, voltage, current
    _measurement_progress_signal = Signal(str, int, int, float, float)  # direction, current, total, V, I
    _measurement_stats_signal = Signal(str, float, object)  # direction, voltage, stats
    _measurement_complete_signal = Signal(bool, object)  # success, result
    _device_status_signal = Signal(bool, str)  # connected, message

    # Stability test signals
    _stability_measurement_signal = Signal(float, float, float)  # timestamp, voltage, current
    _stability_complete_signal = Signal(bool)  # success
    _stability_error_signal = Signal(str)  # error_message
    _stability_status_signal = Signal(str)  # status_message

    def __init__(self, window: 'JVWebWindow'):
        super().__init__(window)
        self._experiment: Optional[JVExperimentModel] = None
        self._exporter = JVDataExporter()
        self._current_result: Optional[JVMeasurementResult] = None

        # Connect internal signals to slots for thread-safe JavaScript calls
        self._measurement_point_signal.connect(self._emit_measurement_point)
        self._measurement_progress_signal.connect(self._emit_measurement_progress)
        self._measurement_stats_signal.connect(self._emit_measurement_stats)
        self._measurement_complete_signal.connect(self._emit_measurement_complete)
        self._device_status_signal.connect(self._emit_device_status)

        # Connect stability test signals
        self._stability_measurement_signal.connect(self._emit_stability_measurement)
        self._stability_complete_signal.connect(self._emit_stability_complete)
        self._stability_error_signal.connect(self._emit_stability_error)
        self._stability_status_signal.connect(self._emit_stability_status)

    def set_experiment(self, experiment: JVExperimentModel) -> None:
        """Set the experiment model and connect signals."""
        self._experiment = experiment

        # Connect model signals to push data to JS
        self._experiment.measurement_point.connect(self._on_measurement_point)
        self._experiment.measurement_progress.connect(self._on_measurement_progress)
        self._experiment.measurement_stats.connect(self._on_measurement_stats)
        self._experiment.measurement_complete.connect(self._on_measurement_complete)
        self._experiment.device_status_changed.connect(self._on_device_status_changed)

        # Connect stability test signals
        self._experiment.stability_measurement_point.connect(self._on_stability_measurement)
        self._experiment.stability_complete.connect(self._on_stability_complete)
        self._experiment.stability_error.connect(self._on_stability_error)
        self._experiment.stability_status.connect(self._on_stability_status)

    @Slot(result=str)
    def get_device_status(self) -> str:
        """Get current device connection status."""
        from .config import settings
        offline_mode = getattr(settings, 'OFFLINE_MODE', False)

        # In offline mode, we're never "really" connected to hardware
        if offline_mode:
            return json.dumps({
                "connected": False,
                "message": "Offline mode",
                "offline_mode": True
            })

        # Check real hardware connection
        if self._experiment:
            connected = self._experiment.is_initialized()
            message = "Keithley 2450" if connected else "Not connected"
            return json.dumps({
                "connected": connected,
                "message": message,
                "offline_mode": False
            })

        return json.dumps({
            "connected": False,
            "message": "No experiment model",
            "offline_mode": False
        })

    @Slot(result=str)
    def get_ui_config(self) -> str:
        """
        Get UI configuration values for the frontend.

        Remote config (from GitHub) is the primary source for UI defaults.
        Built-in settings.py values serve as fallbacks only.

        Note: Hardware/measurement params (NPLC, source_delay, etc.) are NOT
        exposed to the frontend - those stay in settings.py for Python use only.
        """
        # Remote config is the primary source for UI defaults
        remote = get_remote_config('jv')

        # Extract stability UI defaults from settings.py (for fallback only)
        stability_ui_defaults = {
            "default_target_voltage": JV_STABILITY_TEST_CONFIG["default_target_voltage"],
            "default_duration_min": JV_STABILITY_TEST_CONFIG["default_duration_min"],
            "duration_range": list(JV_STABILITY_TEST_CONFIG["duration_range"]),
            "default_interval_sec": JV_STABILITY_TEST_CONFIG["default_interval_sec"],
            "interval_range": list(JV_STABILITY_TEST_CONFIG["interval_range"]),
        }

        # Build config with remote values, falling back to settings.py
        config = {
            "defaults": remote.get("defaults", dict(DEFAULT_MEASUREMENT_PARAMS)),
            "validation": remote.get("validation", dict(VALIDATION_PATTERNS)),
            "stability": remote.get("stability", stability_ui_defaults),
            "export": dict(DATA_EXPORT_CONFIG),  # Not remotely configurable
        }

        return json.dumps(config)

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

            # Log to console
            self._window.send_log('info', f"Starting I-V measurement: {params['start_voltage']}V to {params['stop_voltage']}V, step {params['step_voltage']}V")

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
            self._window.send_log('error', f"Measurement failed: {e}")
            return json.dumps({"success": False, "message": str(e)})
        except Exception as e:
            _logger.error(f"Measurement start failed: {e}")
            self._window.send_log('error', f"Measurement failed: {e}")
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

        # Show save dialog with smart directory default
        default_path = self._build_save_path(default_filename)
        file_path, _ = QFileDialog.getSaveFileName(
            self._window,
            "Save J-V Data",
            default_path,
            "CSV files (*.csv)"
        )

        if file_path:
            try:
                self._exporter.save_measurement(self._current_result, file_path)
                self._save_last_directory(file_path)
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
        # Generate default filename using settings template
        default_filename = self._exporter.generate_filename(cell_number, pixel)

        # Show save dialog with smart directory default
        default_path = self._build_save_path(default_filename)
        file_path, _ = QFileDialog.getSaveFileName(
            self._window,
            "Save J-V Data",
            default_path,
            "CSV files (*.csv)"
        )

        if file_path:
            try:
                with open(file_path, 'w', newline='') as f:
                    f.write(csv_content)
                self._save_last_directory(file_path)
                return json.dumps({"success": True, "path": file_path})
            except Exception as e:
                return json.dumps({"success": False, "message": str(e)})

        return json.dumps({"success": False, "message": "Cancelled"})

    @Slot(str, result=str)
    def save_analysis_data(self, csv_content: str) -> str:
        """
        Save I-V analysis results to file.

        Args:
            csv_content: CSV string with analysis results

        Returns:
            JSON string with success status and file path
        """
        from datetime import datetime

        # Generate default filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_filename = f"iv_analysis_{timestamp}.csv"

        # Show save dialog with smart directory default
        default_path = self._build_save_path(default_filename)
        file_path, _ = QFileDialog.getSaveFileName(
            self._window,
            "Save I-V Analysis",
            default_path,
            "CSV files (*.csv)"
        )

        if file_path:
            try:
                with open(file_path, 'w', newline='') as f:
                    f.write(csv_content)
                self._save_last_directory(file_path)
                return json.dumps({"success": True, "path": file_path})
            except Exception as e:
                return json.dumps({"success": False, "message": str(e)})

        return json.dumps({"success": False, "message": "Cancelled"})

    # ========================================================================
    # Stability Test API Methods
    # ========================================================================

    @Slot(str, result=str)
    def start_stability_test(self, params_json: str) -> str:
        """
        Start a voltage stability test.

        Args:
            params_json: JSON with {target_voltage, duration, interval, pixel, cell_number}

        Returns:
            JSON string with success status
        """
        if not self._experiment:
            return json.dumps({"success": False, "message": "No experiment model"})

        try:
            params = json.loads(params_json)

            # Log to console
            self._window.send_log(
                'info',
                f"Starting stability test at {params['target_voltage']}V for {params['duration']} min"
            )

            # Start test
            self._experiment.start_stability_test(
                target_voltage=params["target_voltage"],
                duration_min=params["duration"],
                interval_sec=params["interval"],
                pixel_number=params["pixel"]
            )
            return json.dumps({"success": True})

        except JVExperimentError as e:
            self._window.send_log('error', f"Stability test failed: {e}")
            return json.dumps({"success": False, "message": str(e)})
        except Exception as e:
            _logger.error(f"Stability test start failed: {e}")
            self._window.send_log('error', f"Stability test failed: {e}")
            return json.dumps({"success": False, "message": str(e)})

    @Slot(result=str)
    def stop_stability_test(self) -> str:
        """Stop the running stability test."""
        if self._experiment:
            self._experiment.stop_stability_test()
        return json.dumps({"success": True})

    @Slot(str, str, int, result=str)
    def save_stability_data(self, csv_content: str, cell_number: str, pixel: int) -> str:
        """
        Save stability test data to file.

        Args:
            csv_content: CSV string to save
            cell_number: Cell number for filename
            pixel: Pixel number for filename

        Returns:
            JSON string with success status and file path
        """
        # Generate default filename using settings template
        default_filename = self._exporter.generate_stability_filename(cell_number, pixel)

        # Show save dialog with smart directory default
        default_path = self._build_save_path(default_filename)
        file_path, _ = QFileDialog.getSaveFileName(
            self._window,
            "Save Stability Test Data",
            default_path,
            "CSV files (*.csv)"
        )

        if file_path:
            try:
                with open(file_path, 'w', newline='') as f:
                    f.write(csv_content)
                self._save_last_directory(file_path)
                return json.dumps({"success": True, "path": file_path})
            except Exception as e:
                return json.dumps({"success": False, "message": str(e)})

        return json.dumps({"success": False, "message": "Cancelled"})

    # ========================================================================
    # Measurement Forwarder Methods (worker thread → main thread marshaling)
    # ========================================================================

    def _on_measurement_point(self, direction: str, voltage: float, current: float) -> None:
        """Forward measurement point to JS (called from worker thread via Qt signal)."""
        # Emit internal signal to marshal to main thread
        self._measurement_point_signal.emit(direction, voltage, current)

    def _on_measurement_progress(
        self, direction: str, current_point: int, total_points: int, voltage: float, current: float
    ) -> None:
        """Forward measurement progress to JS (called from worker thread via Qt signal)."""
        # Emit internal signal to marshal to main thread
        self._measurement_progress_signal.emit(direction, current_point, total_points, voltage, current)

    def _on_measurement_stats(self, direction: str, voltage: float, stats) -> None:
        """Forward measurement statistics to JS (called from worker thread via Qt signal)."""
        # Emit internal signal to marshal to main thread
        self._measurement_stats_signal.emit(direction, voltage, stats)

    def _on_measurement_complete(self, success: bool, result: JVMeasurementResult) -> None:
        """Forward measurement completion to JS (called from worker thread via Qt signal)."""
        # Store result before emitting signal (thread-safe since Python GIL)
        self._current_result = result if success else None
        # Emit internal signal to marshal to main thread
        self._measurement_complete_signal.emit(success, result)

    def _on_device_status_changed(self, connected: bool, message: str) -> None:
        """Forward device status change to JS (may be called from worker thread)."""
        # Emit internal signal to marshal to main thread
        self._device_status_signal.emit(connected, message)

    # Stability test forwarder methods

    def _on_stability_measurement(self, timestamp: float, voltage: float, current: float) -> None:
        """Forward stability measurement to JS (called from worker thread via Qt signal)."""
        self._stability_measurement_signal.emit(timestamp, voltage, current)

    def _on_stability_complete(self, success: bool) -> None:
        """Forward stability completion to JS (called from worker thread via Qt signal)."""
        self._stability_complete_signal.emit(success)

    def _on_stability_error(self, error_message: str) -> None:
        """Forward stability error to JS (called from worker thread via Qt signal)."""
        self._stability_error_signal.emit(error_message)

    def _on_stability_status(self, status_message: str) -> None:
        """Forward stability status to JS (called from worker thread via Qt signal)."""
        self._stability_status_signal.emit(status_message)

    # ========================================================================
    # Emitter Methods (main thread → JavaScript)
    # ========================================================================

    @QtSlot(str, float, float)
    def _emit_measurement_point(self, direction: str, voltage: float, current: float) -> None:
        """Emit measurement point to JS (runs on main thread)."""
        js = f"onMeasurementPoint({json.dumps(direction)}, {voltage}, {current})"
        self._window.run_js(js)

    @QtSlot(str, int, int, float, float)
    def _emit_measurement_progress(
        self, direction: str, current_point: int, total_points: int, voltage: float, current: float
    ) -> None:
        """Emit measurement progress to JS (runs on main thread)."""
        # Calculate percentage and format status message
        percent = (current_point / total_points * 100) if total_points > 0 else 0
        direction_label = "Forward" if direction == "forward" else "Reverse"
        message = f"{direction_label}: {voltage:.2f} V"
        js = f"onMeasurementProgress({percent}, {json.dumps(message)})"
        self._window.run_js(js)

    @QtSlot(str, float, object)
    def _emit_measurement_stats(self, direction: str, voltage: float, stats) -> None:
        """Emit measurement statistics to JS (runs on main thread)."""
        # Convert MeasurementStats to dict for JSON serialization
        stats_dict = {
            'direction': direction,
            'voltage': voltage,
            'mean': stats.mean,
            'std_dev': stats.std_dev,
            'std_error': stats.std_error,
            'sem_percent': stats.sem_percent,
            'n': stats.n_measurements,
            'quality': stats.quality,
            'unit': stats.unit
        }
        js = f"onMeasurementStats({json.dumps(stats_dict)})"
        self._window.run_js(js)

    @QtSlot(bool, object)
    def _emit_measurement_complete(self, success: bool, result: JVMeasurementResult) -> None:
        """Emit measurement completion to JS (runs on main thread)."""
        if success and result:
            num_points = len(result.forward) + len(result.reverse)
            self._window.send_log('info', f"Measurement complete: {num_points} data points collected")
        else:
            self._window.send_log('warn', "Measurement stopped or failed")
        js = f"onMeasurementComplete({str(success).lower()})"
        self._window.run_js(js)

    @QtSlot(bool, str)
    def _emit_device_status(self, connected: bool, message: str) -> None:
        """Emit device status to JS (runs on main thread)."""
        # Log via Python logger (WebConsoleHandler forwards to terminal panel)
        if connected:
            _logger.info(f"Device: {message}")
        else:
            _logger.warning(f"Device: {message}")
        js = f"updateDeviceStatus({str(connected).lower()}, {json.dumps(message)})"
        self._window.run_js(js)

    # Stability test emitter methods

    @QtSlot(float, float, float)
    def _emit_stability_measurement(self, timestamp: float, voltage: float, current: float) -> None:
        """Emit stability measurement to JS (runs on main thread)."""
        js = f"onStabilityMeasurement({timestamp}, {voltage}, {current})"
        self._window.run_js(js)

    @QtSlot(bool)
    def _emit_stability_complete(self, success: bool) -> None:
        """Emit stability completion to JS (runs on main thread)."""
        js = f"onStabilityComplete({str(success).lower()})"
        self._window.run_js(js)

    @QtSlot(str)
    def _emit_stability_error(self, error_message: str) -> None:
        """Emit stability error to JS (runs on main thread)."""
        # Escape for JSON
        error_escaped = error_message.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')
        js = f'onStabilityError("{error_escaped}")'
        self._window.run_js(js)

    @QtSlot(str)
    def _emit_stability_status(self, status_message: str) -> None:
        """Emit stability status to JS (runs on main thread)."""
        status_escaped = status_message.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')
        js = f'onStabilityStatus("{status_escaped}")'
        self._window.run_js(js)


class JVWebWindow(BaseWebWindow):
    """Main window for J-V measurement with web UI."""

    def __init__(self):
        super().__init__(
            title="I-V Measurement - PHYS 2150",
            html_filename="jv.html",
            size=GUI_CONFIG["window_size"],
            min_size=GUI_CONFIG["window_min_size"]
        )

        # Set up app-specific API
        self.api = JVApi(self)
        self.channel.registerObject("api", self.api)

        # Experiment model (initialized later)
        self._experiment: Optional[JVExperimentModel] = None

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

        # Install log handler to forward all log messages to web console
        self._install_log_handler()

    def _install_log_handler(self) -> None:
        """Install custom handler to forward log messages to web UI."""
        # TieredLogger uses "phys2150.{name}" for the actual Python logger
        jv_logger = logging.getLogger("phys2150.jv")

        # Create and configure handler (pass signal for thread-safe forwarding)
        handler = WebConsoleHandler(self.window._log_signal)
        handler.setFormatter(logging.Formatter('%(message)s'))
        handler.setLevel(logging.INFO)  # Default to INFO, debug mode enables DEBUG

        # Store reference so we can update level when debug mode toggles
        self.window._web_console_handler = handler

        # Add to logger
        jv_logger.addHandler(handler)

    def run(self) -> int:
        """Run the application."""
        # Initialize experiment (connects to hardware)
        try:
            self.experiment.initialize_device()
        except JVExperimentError:
            # Continue anyway - device_status_changed signal already notified UI
            pass

        self.window.show()
        return self.app.exec()


def _set_windows_app_id():
    """Set Windows AppUserModelID so taskbar shows correct icon instead of Python's."""
    if sys.platform == 'win32':
        app_id = 'CUBoulder.PHYS2150.JV'
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)


def main():
    """Entry point for J-V web application."""
    import argparse

    # Set AppUserModelID before QApplication so Windows shows correct taskbar icon
    _set_windows_app_id()

    # Parse command line arguments
    parser = argparse.ArgumentParser(description='J-V Measurement Application')
    parser.add_argument(
        '--offline',
        action='store_true',
        help='Run in offline mode without hardware (for GUI testing)'
    )
    parser.add_argument(
        '--theme',
        choices=['dark', 'light'],
        default=None,
        help='Set initial color theme'
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

        # Apply theme from command line if specified
        if args.theme:
            app.window.set_initial_theme(args.theme)

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
