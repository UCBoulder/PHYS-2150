"""
EQE Measurement Application (Web UI)

Qt WebEngine-based interface for EQE characterization.
Uses the same models and controllers as the Qt widget version,
but with a web-based frontend for full HTML/CSS/JS flexibility.
"""

import os
import sys
import json
import logging
import ctypes
from typing import Optional, Dict, Any

from PySide6.QtCore import Qt, QObject, Slot, QUrl, QThread, Signal, Slot as QtSlot
from PySide6.QtWidgets import QApplication, QFileDialog
from PySide6.QtWebChannel import QWebChannel

from .models.eqe_experiment import EQEExperimentModel, EQEExperimentError
from .models.stability_test import StabilityTestModel
from .config.settings import (
    GUI_CONFIG, DEFAULT_MEASUREMENT_PARAMS, VALIDATION_PATTERNS,
    DEVICE_CONFIGS, STABILITY_TEST_CONFIG, PHASE_ADJUSTMENT_CONFIG, DeviceType
)
from .config import settings
from common.utils import get_logger, TieredLogger, WebConsoleHandler
from common.utils.remote_config import get_remote_config, deep_merge
from common.ui import BaseWebWindow, BaseWebApi

_logger = get_logger("eqe")


class EQEApi(BaseWebApi):
    """
    Python API exposed to JavaScript via QWebChannel.

    Handles device communication, measurement control, and data export.
    """

    # Signals for thread-safe stability test callbacks
    _stability_progress_signal = Signal(float, float)
    _stability_complete_signal = Signal(bool, str)
    _stability_mono_signal = Signal(float, bool)  # wavelength, shutter_open

    def __init__(self, window: 'EQEWebWindow'):
        super().__init__(window)
        self._experiment: Optional[EQEExperimentModel] = None
        self._stability_model: Optional[StabilityTestModel] = None

        # Pending stability test (waiting for phase adjustment)
        self._pending_stability_params: Optional[Dict[str, Any]] = None

        # Connect signals to slots for thread-safe callbacks
        self._stability_progress_signal.connect(self._emit_stability_progress)
        self._stability_complete_signal.connect(self._emit_stability_complete)
        self._stability_mono_signal.connect(self._emit_stability_mono)

    def set_experiment(self, experiment: EQEExperimentModel) -> None:
        """Set the experiment model and connect signals."""
        self._experiment = experiment

        # Connect model signals to push data to JS
        self._experiment.device_status_changed.connect(self._on_device_status_changed)
        self._experiment.measurement_progress.connect(self._on_measurement_progress)
        self._experiment.experiment_complete.connect(self._on_experiment_complete)
        self._experiment.live_signal_update.connect(self._on_live_signal_update)
        self._experiment.monochromator_state_changed.connect(self._on_monochromator_state_changed)
        self._experiment.phase_adjustment_complete.connect(self._on_phase_adjustment_complete)

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

    @Slot(result=str)
    def get_ui_config(self) -> str:
        """
        Get UI configuration values, merging remote overrides.

        Returns config needed by JavaScript for form defaults and validation.
        Remote config from GitHub is merged over built-in defaults.
        """
        # Convert DeviceType enum keys to strings for JSON serialization
        devices_config = {
            "monochromator": dict(DEVICE_CONFIGS[DeviceType.MONOCHROMATOR]),
            "picoscope": dict(DEVICE_CONFIGS[DeviceType.PICOSCOPE_LOCKIN]),
            "power_meter": dict(DEVICE_CONFIGS[DeviceType.THORLABS_POWER_METER]),
        }

        # Built-in defaults
        config = {
            "defaults": dict(DEFAULT_MEASUREMENT_PARAMS),
            "validation": dict(VALIDATION_PATTERNS),
            "devices": devices_config,
            "stability": dict(STABILITY_TEST_CONFIG),
            "phase": dict(PHASE_ADJUSTMENT_CONFIG),
        }

        # Merge remote config (overrides built-in)
        remote = get_remote_config('eqe')
        if remote:
            config = deep_merge(config, remote)

        return json.dumps(config)

    # ==================== Measurements ====================

    @Slot(str, result=str)
    def start_power_measurement(self, params_json: str) -> str:
        """Start a power measurement."""
        if not self._experiment:
            return json.dumps({"success": False, "message": "No experiment model"})

        try:
            params = json.loads(params_json)

            # Log to console
            self._window.send_log('info', f"Starting power measurement: {params['start_wavelength']}-{params['end_wavelength']}nm, step {params['step_size']}nm")

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
            self._window.send_log('error', f"Power measurement failed: {e}")
            return json.dumps({"success": False, "message": str(e)})
        except Exception as e:
            _logger.error(f"Power measurement start failed: {e}")
            self._window.send_log('error', f"Power measurement failed: {e}")
            return json.dumps({"success": False, "message": str(e)})

    @Slot(str, result=str)
    def start_current_measurement(self, params_json: str) -> str:
        """Start a current measurement."""
        if not self._experiment:
            return json.dumps({"success": False, "message": "No experiment model"})

        try:
            params = json.loads(params_json)

            # Log to console
            self._window.send_log('info', f"Starting current measurement: {params['start_wavelength']}-{params['end_wavelength']}nm, pixel {params['pixel']}")

            # Set parameters
            self._experiment.set_measurement_parameters(
                start_wavelength=params["start_wavelength"],
                end_wavelength=params["end_wavelength"],
                step_size=params["step_size"],
                cell_number=params["cell_number"],
                pixel_number=params["pixel"],
            )

            # Start current measurement directly (chopper validation happens at start)
            self._experiment.start_current_measurement()
            return json.dumps({"success": True})

        except EQEExperimentError as e:
            self._window.send_log('error', f"Current measurement failed: {e}")
            return json.dumps({"success": False, "message": str(e)})
        except Exception as e:
            _logger.error(f"Current measurement start failed: {e}")
            self._window.send_log('error', f"Current measurement failed: {e}")
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

    # ==================== Lock-in Lab ====================

    @Slot(int, result=str)
    def lockinlab_measure(self, num_cycles: int) -> str:
        """
        Perform a Lock-in Lab measurement returning full data for visualization.

        Returns waveforms, FFT, and phasor data for educational display.
        """
        if not self._experiment or not self._experiment.lockin:
            return json.dumps({"success": False, "message": "Lock-in not available"})

        try:
            # Get full measurement data including waveforms
            result = self._experiment.lockin.perform_lockin_measurement_full(num_cycles)

            if result is None:
                return json.dumps({"success": False, "message": "Measurement failed"})

            # Process data for web display
            processed = self._process_lockinlab_data(result)
            processed["success"] = True

            return json.dumps(processed)

        except Exception as e:
            _logger.error(f"Lock-in Lab measurement failed: {e}")
            return json.dumps({"success": False, "message": str(e)})

    def _process_lockinlab_data(self, result: Dict) -> Dict:
        """
        Process raw lock-in data for web display.

        Decimates waveforms, computes FFT, and formats for Plotly.
        """
        import numpy as np

        # Extract raw data
        signal_data = result.get('signal_data')
        reference_data = result.get('reference_data')
        sample_rate = result.get('sample_rate', 8000)  # Default fallback

        # Phasor data (already computed by driver)
        X = result['X']
        Y = result['Y']
        R = result['R']
        theta = result['theta']

        # Initialize output
        output = {
            # Phasor diagram data
            'X': X,
            'Y': Y,
            'R': R,
            'theta': theta,
            'freq': result.get('freq', 81),
            'num_cycles': result.get('num_cycles', 100),

            # Verification: students can check R² = X² + Y²
            'R_squared': R * R,
            'X_squared_plus_Y_squared': X * X + Y * Y,
        }

        # Process waveforms if available
        if signal_data is not None and reference_data is not None:
            signal_data = np.array(signal_data)
            reference_data = np.array(reference_data)

            # Decimate to 500 points for web display
            signal_dec = self._decimate_waveform(signal_data, 500)
            reference_dec = self._decimate_waveform(reference_data, 500)

            # Compute product waveform (signal × reference)
            # Normalize reference for product display
            ref_normalized = reference_data - np.mean(reference_data)
            ref_normalized = ref_normalized / (np.std(ref_normalized) + 1e-10)
            signal_normalized = signal_data - np.mean(signal_data)
            product = signal_normalized * ref_normalized
            product_dec = self._decimate_waveform(product, 500)

            # Time axis in milliseconds
            duration_ms = len(signal_data) / sample_rate * 1000
            time_axis = [i * duration_ms / len(signal_dec) for i in range(len(signal_dec))]

            output['signal_waveform'] = signal_dec
            output['reference_waveform'] = reference_dec
            output['product_waveform'] = product_dec
            output['time_axis'] = time_axis
            output['sample_rate'] = sample_rate

            # Compute FFT for frequency display
            fft_freqs, fft_mag = self._compute_fft(signal_data, sample_rate)
            output['fft_frequencies'] = fft_freqs
            output['fft_magnitude'] = fft_mag

        return output

    def _decimate_waveform(self, data: 'np.ndarray', target_points: int = 500) -> list:
        """Reduce waveform to web-friendly size."""
        import numpy as np

        if len(data) <= target_points:
            return data.tolist()

        # Use linear interpolation indices for even sampling
        indices = np.linspace(0, len(data) - 1, target_points, dtype=int)
        return data[indices].tolist()

    def _compute_fft(self, signal: 'np.ndarray', sample_rate: float) -> tuple:
        """
        Compute magnitude spectrum for display.

        Returns frequencies up to 200 Hz (chopper is at ~81 Hz).
        """
        import numpy as np

        # Remove DC offset
        signal = signal - np.mean(signal)

        # Compute FFT
        fft = np.fft.rfft(signal)
        freqs = np.fft.rfftfreq(len(signal), 1 / sample_rate)
        magnitude = np.abs(fft)

        # Normalize for display
        magnitude = magnitude / len(signal)

        # Return only up to 200 Hz (captures chopper frequency and some harmonics)
        mask = freqs <= 200
        return freqs[mask].tolist(), magnitude[mask].tolist()

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

    # ==================== Stability Tests ====================

    def set_stability_model(self, model: StabilityTestModel) -> None:
        """Set the stability test model and connect callbacks."""
        self._stability_model = model

        # Connect callbacks to forward to JS
        model.set_measurement_callback(self._on_stability_progress)
        model.set_completion_callback(self._on_stability_complete)
        model.set_error_callback(self._on_stability_error)
        model.set_status_callback(self._on_stability_status)
        model.set_monochromator_callback(self._on_stability_mono)

    @Slot(str, result=str)
    def start_stability_test(self, params_json: str) -> str:
        """Start a stability test."""
        if not self._stability_model:
            return json.dumps({"success": False, "message": "Stability model not available"})

        try:
            params = json.loads(params_json)
            test_type = params.get("type", "power")
            wavelength = params.get("wavelength", 550)
            duration = params.get("duration", 5)  # minutes
            interval = params.get("interval", 2)  # seconds
            pixel = params.get("pixel", 1)

            if test_type == "power":
                # Power tests don't need phase adjustment
                self._stability_model.start_power_test(wavelength, duration, interval)
                return json.dumps({"success": True})
            else:
                # Current tests need phase adjustment first (to lock onto chopper)
                if not self._experiment or not self._experiment.phase_model:
                    return json.dumps({"success": False, "message": "Phase adjustment not available"})

                # Store params for after phase adjustment completes
                self._pending_stability_params = {
                    "wavelength": wavelength,
                    "duration": duration,
                    "interval": interval,
                    "pixel": pixel
                }

                # Tell experiment model NOT to auto-start current measurement after phase
                self._experiment._skip_auto_current_after_phase = True

                # Set pixel number in experiment parameters (needed for phase adjustment)
                self._experiment.set_measurement_parameters(pixel_number=pixel)

                # Start phase adjustment (stability test will start on completion)
                _logger.info(f"Starting phase adjustment for current stability test (pixel {pixel})")
                self._experiment.phase_model.start_adjustment(pixel_number=pixel)

                return json.dumps({"success": True, "phase": "adjusting"})

        except Exception as e:
            _logger.error(f"Stability test start failed: {e}")
            self._pending_stability_params = None
            return json.dumps({"success": False, "message": str(e)})

    @Slot(result=str)
    def stop_stability_test(self) -> str:
        """Stop the running stability test."""
        if self._stability_model:
            self._stability_model.stop_test()
        return json.dumps({"success": True})

    @Slot(str, float, str, result=str)
    def save_stability_data(self, csv_content: str, wavelength: float, test_type: str) -> str:
        """Save stability test data to file."""
        from datetime import datetime

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_filename = f"stability_{test_type}_{wavelength:.0f}nm_{timestamp}.csv"

        file_path, _ = QFileDialog.getSaveFileName(
            self._window,
            "Save Stability Test Data",
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

    @Slot(str, result=str)
    def save_analysis_data(self, csv_content: str) -> str:
        """Save EQE analysis results to file."""
        from datetime import datetime

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_filename = f"eqe_analysis_{timestamp}.csv"

        file_path, _ = QFileDialog.getSaveFileName(
            self._window,
            "Save EQE Analysis",
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

    def _on_stability_progress(self, timestamp: float, value: float) -> None:
        """Forward stability progress to JS (called from background thread)."""
        # Emit signal to marshal to main thread
        self._stability_progress_signal.emit(timestamp, value)

    def _on_stability_complete(self, timestamps: list, values: list) -> None:
        """Forward stability completion to JS (called from background thread)."""
        self._stability_complete_signal.emit(True, 'Complete')

    def _on_stability_error(self, message: str) -> None:
        """Forward stability error to JS (called from background thread)."""
        self._stability_complete_signal.emit(False, message)

    def _on_stability_status(self, message: str) -> None:
        """Forward stability status to JS (optional, for status bar)."""
        # Status updates are handled by progress callback for now
        pass

    def _on_stability_mono(self, wavelength: float, shutter_open: bool) -> None:
        """Forward monochromator state to JS (called from background thread)."""
        self._stability_mono_signal.emit(wavelength, shutter_open)

    @QtSlot(float, float)
    def _emit_stability_progress(self, timestamp: float, value: float) -> None:
        """Emit stability progress to JS (runs on main thread)."""
        js = f"onStabilityProgress({timestamp}, {value})"
        self._window.run_js(js)

    @QtSlot(bool, str)
    def _emit_stability_complete(self, success: bool, message: str) -> None:
        """Emit stability completion to JS (runs on main thread)."""
        js = f"onStabilityComplete({str(success).lower()}, {json.dumps(message)})"
        self._window.run_js(js)

    @QtSlot(float, bool)
    def _emit_stability_mono(self, wavelength: float, shutter_open: bool) -> None:
        """Emit monochromator state to JS (runs on main thread)."""
        # Reuse the existing onMonochromatorStateChanged JS function
        js = f"onMonochromatorStateChanged({wavelength}, {str(shutter_open).lower()}, 0)"
        self._window.run_js(js)

    # ==================== Signal Handlers ====================

    def _on_device_status_changed(self, device_name: str, is_connected: bool, message: str) -> None:
        """Forward device status change to JS."""
        # Log via Python logger (WebConsoleHandler forwards to terminal panel)
        if is_connected:
            _logger.info(f"{device_name}: {message}")
        else:
            _logger.warning(f"{device_name}: {message}")
        js = f"onDeviceStatusChanged({json.dumps(device_name)}, {str(is_connected).lower()}, {json.dumps(message)})"
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
        # Check if this is a phase adjustment failure for a pending stability test
        if not success and self._pending_stability_params:
            # Phase adjustment failed while trying to start stability test
            self._pending_stability_params = None
            # Also clear the skip flag if it was set
            if self._experiment:
                self._experiment._skip_auto_current_after_phase = False

            # Notify stability test completion with failure
            self._stability_complete_signal.emit(False, message)
            return  # Don't also send to measurement complete

        # Log to console
        if success:
            self._window.send_log('info', f"Measurement complete: {message}")
        else:
            self._window.send_log('warn', f"Measurement stopped: {message}")

        js = f"onMeasurementComplete({str(success).lower()}, {json.dumps(message)})"
        self._window.run_js(js)

    def _on_live_signal_update(self, current_nA: float) -> None:
        """Forward live signal update to JS."""
        js = f"onLiveSignalUpdate({current_nA})"
        self._window.run_js(js)

    def _on_monochromator_state_changed(self, wavelength: float, shutter_open: bool, filter_number: int) -> None:
        """Forward monochromator state change to JS."""
        js = f"onMonochromatorStateChanged({wavelength}, {str(shutter_open).lower()}, {filter_number})"
        self._window.run_js(js)

    def _on_phase_adjustment_complete(self, phase_data: Dict) -> None:
        """Forward phase adjustment data (including sine fit) to JS."""
        phase_json = json.dumps(phase_data)
        js = f"onPhaseAdjustmentComplete({phase_json})"
        self._window.run_js(js)

        # If we have pending stability test params, start the stability test now
        if self._pending_stability_params:
            params = self._pending_stability_params
            self._pending_stability_params = None  # Clear before starting

            _logger.info(f"Phase adjustment complete, starting current stability test")

            # Start the stability test
            try:
                self._stability_model.start_current_test(
                    wavelength=params["wavelength"],
                    duration=params["duration"],
                    interval=params["interval"],
                    pixel_number=params["pixel"]
                )
            except Exception as e:
                _logger.error(f"Failed to start stability test after phase adjustment: {e}")
                self._stability_complete_signal.emit(False, f"Failed to start: {str(e)}")


class EQEWebWindow(BaseWebWindow):
    """Main window for EQE measurement with web UI."""

    def __init__(self):
        super().__init__(
            title="EQE Measurement - PHYS 2150",
            html_filename="eqe.html",
            size=(1400, 750),
            min_size=(1000, 600)
        )

        # Set up app-specific API
        self.api = EQEApi(self)
        self.channel.registerObject("api", self.api)

        # Experiment model (initialized later)
        self._experiment: Optional[EQEExperimentModel] = None

    def set_experiment(self, experiment: EQEExperimentModel) -> None:
        """Set the experiment model."""
        self._experiment = experiment
        self.api.set_experiment(experiment)

    def closeEvent(self, event) -> None:
        """Handle window close."""
        # Stop stability test if running
        if self.api._stability_model and self.api._stability_model.is_running():
            self.api._stability_model.stop_test()

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
        self.stability_model: Optional[StabilityTestModel] = None

        # Connect experiment to window
        self.window.set_experiment(self.experiment)

        # Install log handler to forward all log messages to web console
        self._install_log_handler()

        # Connect logger stats callback to forward measurement stats to web UI
        eqe_logger = get_logger("eqe")
        eqe_logger.set_stats_callback(self._on_measurement_stats)

    def _install_log_handler(self) -> None:
        """Install custom handler to forward log messages to web UI."""
        # TieredLogger uses "phys2150.{name}" for the actual Python logger
        eqe_logger = logging.getLogger("phys2150.eqe")

        # Create and configure handler (pass signal for thread-safe forwarding)
        handler = WebConsoleHandler(self.window._log_signal)
        handler.setFormatter(logging.Formatter('%(message)s'))
        handler.setLevel(logging.INFO)  # Default to INFO, debug mode enables DEBUG

        # Store reference so we can update level when debug mode toggles
        self.window._web_console_handler = handler

        # Add to logger
        eqe_logger.addHandler(handler)

    def _on_measurement_stats(self, stats) -> None:
        """Forward measurement statistics to web UI."""
        # Convert MeasurementStats object to dict for JSON serialization
        stats_dict = {
            'mean': stats.mean,
            'std_dev': stats.std_dev,
            'std_error': stats.std_error,  # SE = σ/√n, uncertainty in the mean
            'n': stats.n_measurements,
            'total': stats.n_total,
            'outliers': stats.n_outliers,
            'cv_percent': stats.cv_percent,
            'quality': stats.quality
        }
        stats_json = json.dumps(stats_dict)
        self.window.run_js(f"onMeasurementStats({stats_json})")

    def run(self) -> int:
        """Run the application."""
        # Initialize experiment (connects to hardware)
        try:
            self.experiment.initialize_devices()
        except EQEExperimentError:
            # Continue anyway - device_status_changed signal already notified UI of failures
            pass

        # Initialize stability test model with shared hardware controllers
        self.stability_model = StabilityTestModel(
            power_meter=self.experiment.power_meter,
            monochromator=self.experiment.monochromator,
            lockin=self.experiment.lockin,
            logger=_logger
        )
        self.window.api.set_stability_model(self.stability_model)

        self.window.show()

        # Trigger cell modal after window is shown (ensures focus works after PicoScope splash)
        self.window.run_js("showStartupCellModal()")

        return self.app.exec()


def _set_windows_app_id():
    """Set Windows AppUserModelID so taskbar shows correct icon instead of Python's."""
    if sys.platform == 'win32':
        app_id = 'CUBoulder.PHYS2150.EQE'
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)


def main():
    """Entry point for EQE web application."""
    import argparse

    # Set AppUserModelID before QApplication so Windows shows correct taskbar icon
    _set_windows_app_id()

    # Parse command line arguments
    parser = argparse.ArgumentParser(description='EQE Measurement Application')
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
    if args.offline:
        print("Running in OFFLINE mode - mock measurements enabled")
        settings.OFFLINE_MODE = True
    else:
        settings.OFFLINE_MODE = False

    try:
        app = EQEWebApplication()

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
