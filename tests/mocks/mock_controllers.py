"""
Mock Controllers for Testing

Provides mock implementations of hardware controllers for testing
without physical devices. These mocks track state and can generate
physics-based mock data.
"""

import numpy as np
from decimal import Decimal
from typing import Optional, Dict, Any, List
from unittest.mock import Mock


class MockKeithley2450Controller:
    """
    Mock Keithley 2450 Source Measure Unit.

    Simulates basic SMU operations and can generate
    realistic I-V curve data using diode equation.
    """

    def __init__(self):
        self._connected = False
        self._output_enabled = False
        self._voltage = 0.0
        self._current_compliance = 1.0

        # Solar cell parameters for mock data
        self._jsc = 0.035  # Short-circuit current (A)
        self._voc = 1.1    # Open-circuit voltage (V)
        self._n = 1.5      # Ideality factor
        self._vt = 0.026   # Thermal voltage at 300K

    def connect(self) -> bool:
        self._connected = True
        return True

    def disconnect(self) -> None:
        self._connected = False
        self._output_enabled = False

    def is_connected(self) -> bool:
        return self._connected

    def output_on(self) -> None:
        self._output_enabled = True

    def output_off(self) -> None:
        self._output_enabled = False

    def set_voltage(self, voltage: float) -> None:
        self._voltage = voltage

    def measure_current(self) -> float:
        """Generate mock current using simplified diode equation."""
        v = self._voltage
        # Simplified single-diode model: I = Isc - I0*(exp(V/(n*Vt)) - 1)
        i0 = self._jsc / (np.exp(self._voc / (self._n * self._vt)) - 1)
        current = self._jsc - i0 * (np.exp(v / (self._n * self._vt)) - 1)
        # Add small noise
        current += np.random.normal(0, abs(current) * 0.001)
        return float(current)

    def measure_current_precise(self) -> Decimal:
        """Generate mock current with high precision (returns Decimal for math compatibility)."""
        return Decimal(str(self.measure_current()))

    def measure_current_multiple(self, count: int = 10) -> List[float]:
        """Take multiple current measurements and return all individual readings."""
        import time
        count = max(10, min(100, count))  # Clamp to valid range
        # Small delay to simulate real I/O latency (allows stop tests to work)
        time.sleep(0.001)
        return [self.measure_current() for _ in range(count)]

    def configure_source_voltage(self) -> None:
        pass

    def configure_for_jv_measurement(self, voltage_range: float = 2,
                                      current_range: float = 10,
                                      current_limit: float = 1,
                                      remote_sensing: bool = True,
                                      nplc: float = 1.0,
                                      averaging_count: int = 1,
                                      averaging_filter: str = "REPEAT",
                                      source_delay_s: float = 0.0) -> None:
        """Configure device for J-V measurement."""
        self._current_compliance = current_limit
        self.output_on()

    def set_current_compliance(self, compliance: float) -> None:
        self._current_compliance = compliance


class MockPicoScopeController:
    """
    Mock PicoScope software lock-in amplifier.

    Simulates lock-in measurement with configurable signal levels.
    """

    def __init__(self):
        self._connected = False
        self._reference_frequency = 81.0
        self._num_cycles = 100
        self._signal_amplitude = 1e-7  # 100 nA default
        self._phase = 45.0  # degrees

    def connect(self) -> bool:
        self._connected = True
        return True

    def disconnect(self) -> None:
        self._connected = False

    def is_connected(self) -> bool:
        return self._connected

    def set_reference_frequency(self, freq: float) -> None:
        self._reference_frequency = freq

    def set_num_cycles(self, cycles: int) -> None:
        self._num_cycles = cycles

    def set_signal_amplitude(self, amplitude: float) -> None:
        """Set the mock signal amplitude for testing."""
        self._signal_amplitude = amplitude

    def read_current(self, num_measurements: int = 5,
                     wavelength_nm: float = None,
                     return_stats: bool = False):
        """Generate mock current reading with optional stats."""
        # Generate measurements with noise
        noise_level = 0.01  # 1% CV
        measurements = np.random.normal(
            self._signal_amplitude,
            self._signal_amplitude * noise_level,
            num_measurements
        )

        mean_current = float(np.mean(measurements))

        if return_stats:
            std_dev = float(np.std(measurements))
            cv_percent = (std_dev / abs(mean_current) * 100) if mean_current != 0 else 0
            return {
                'current': mean_current,
                'std_dev': std_dev,
                'n': num_measurements,
                'cv_percent': cv_percent
            }
        return mean_current

    def read_lockin_current(self) -> float:
        """Single lock-in measurement for stability test."""
        return self.read_current(num_measurements=1)

    def perform_lockin_measurement(self) -> Dict[str, float]:
        """Perform full lock-in measurement."""
        r = self._signal_amplitude
        theta = np.radians(self._phase)
        return {
            'X': r * np.cos(theta),
            'Y': r * np.sin(theta),
            'R': r,
            'theta': self._phase,
            'freq': self._reference_frequency,
            'ref_amplitude': 2.0  # Mock reference amplitude in Vpp
        }

    def read_current_fast(self, num_cycles: int = 20) -> float:
        """Fast current read with fewer cycles (for live monitoring)."""
        return self.read_current(num_measurements=1)

    def measure_phase_response(self) -> tuple:
        """Measure phase response (phase, magnitude, quality)."""
        return (self._phase, self._signal_amplitude, 0.95)

    def get_status(self) -> Dict[str, Any]:
        return {
            'connected': self._connected,
            'locked': True,
            'has_reference': True,
            'overloaded': False
        }


class MockMonochromatorController:
    """
    Mock Newport CS130B monochromator.

    Tracks wavelength, grating, filter, and shutter state.
    Implements filter selection logic matching real controller.
    """

    # Filter thresholds matching eqe/config/settings.py
    FILTER_THRESHOLD_LOWER = 420  # nm
    FILTER_THRESHOLD_UPPER = 800  # nm

    def __init__(self):
        self._connected = False
        self._wavelength = 500.0
        self._grating = 1
        self._filter = 1
        self._current_filter = 1  # Alias used by experiment model
        self._shutter_open = False
        self.serial_number = "MOCK-CS130B-001"

    def connect(self, interface: str = None, timeout_msec: int = 1000) -> bool:
        self._connected = True
        return True

    def disconnect(self) -> None:
        self._connected = False
        self._shutter_open = False

    def is_connected(self) -> bool:
        return self._connected

    def get_wavelength(self) -> float:
        return self._wavelength

    def set_wavelength(self, wavelength: float) -> None:
        self._wavelength = wavelength

    def get_filter_for_wavelength(self, wavelength: float) -> int:
        """Get appropriate filter for wavelength (matching real logic)."""
        if wavelength <= self.FILTER_THRESHOLD_LOWER:
            return 3  # No filter
        elif wavelength <= self.FILTER_THRESHOLD_UPPER:
            return 1  # 400 nm filter
        else:
            return 2  # 780 nm filter

    def set_filter(self, position: int) -> None:
        self._filter = position
        self._current_filter = position

    def get_filter(self) -> int:
        return self._filter

    def set_filter_for_wavelength(self, wavelength: float) -> bool:
        """Set appropriate filter based on wavelength."""
        new_filter = self.get_filter_for_wavelength(wavelength)
        old_filter = self._filter
        self.set_filter(new_filter)
        return old_filter != new_filter

    def set_wavelength_with_grating_auto(self, wavelength: float) -> None:
        """Set wavelength with automatic grating selection."""
        self._wavelength = wavelength
        # Grating selection logic (simplified)
        self._grating = 1 if wavelength < 800 else 2

    def configure_for_wavelength(self, wavelength: float) -> float:
        """Configure for wavelength - sets grating, filter, wavelength."""
        self.set_wavelength_with_grating_auto(wavelength)
        self.set_filter_for_wavelength(wavelength)
        return self._wavelength

    def send_command(self, command: str) -> str:
        """Send command to monochromator (mock - parses and updates state)."""
        parts = command.lower().split()
        if parts[0] == "grating" and len(parts) > 1:
            self._grating = int(parts[1])
        elif parts[0] == "gowave" and len(parts) > 1:
            self._wavelength = float(parts[1])
        elif parts[0] == "shutter":
            if len(parts) > 1 and parts[1] == "o":
                self._shutter_open = True
            elif len(parts) > 1 and parts[1] == "c":
                self._shutter_open = False
        return "OK"

    def align_for_measurement(self, wavelength: float) -> None:
        """Align monochromator for visual alignment at specified wavelength."""
        self.configure_for_wavelength(wavelength)
        self.open_shutter()

    def open_shutter(self) -> None:
        self._shutter_open = True

    def close_shutter(self) -> None:
        self._shutter_open = False

    def is_shutter_open(self) -> bool:
        return self._shutter_open


class MockPowerMeterController:
    """
    Mock Thorlabs PM100USB power meter.

    Returns wavelength-dependent power based on simplified
    Xenon lamp spectrum model.
    """

    def __init__(self):
        self._connected = False
        self._wavelength = 550
        self._base_power = 1e-3  # 1 mW base

    def connect(self) -> bool:
        self._connected = True
        return True

    def disconnect(self) -> None:
        self._connected = False

    def is_connected(self) -> bool:
        return self._connected

    def set_wavelength(self, wavelength: int) -> None:
        self._wavelength = wavelength

    def measure_power(self) -> float:
        """Return wavelength-dependent mock power."""
        # Simple bell curve centered at 550nm
        wl = self._wavelength
        power = self._base_power * np.exp(-((wl - 550) / 200) ** 2)
        # Add noise
        power += np.random.normal(0, power * 0.01)
        return float(power)

    def measure_power_average(self, num_measurements: int = 200,
                              correction_factor: float = 1.0) -> float:
        """Average multiple power measurements."""
        powers = [self.measure_power() for _ in range(num_measurements)]
        return float(np.mean(powers) * correction_factor)

    def measure_power_with_stats(self, num_measurements: int = 200,
                                  correction_factor: float = 1.0) -> dict:
        """Measure power with statistics (mean and standard deviation)."""
        powers = [self.measure_power() for _ in range(num_measurements)]
        mean = float(np.mean(powers))
        std_dev = float(np.std(powers))
        return {
            'mean': mean * correction_factor,
            'std_dev': std_dev * correction_factor,
            'n': num_measurements
        }
