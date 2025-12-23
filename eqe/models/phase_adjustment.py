"""
Phase Adjustment Model

This model implements the logic for phase adjustment using the PicoScope software lock-in
and monochromator. It handles automatic phase optimization through signal measurement.
"""

import time
import numpy as np
from typing import List, Tuple, Optional, Callable, Dict, Any
import threading

from ..controllers.picoscope_lockin import PicoScopeController, PicoScopeError
from ..controllers.monochromator import MonochromatorController, MonochromatorError
from ..config.settings import PHASE_ADJUSTMENT_CONFIG
from ..utils.data_handling import MeasurementDataLogger
from ..utils.math_utils import MathUtils


class PhaseAdjustmentError(Exception):
    """Exception raised for phase adjustment specific errors."""
    pass


class PhaseAdjustmentModel:
    """
    Model for phase adjustment operations.
    
    This model implements the experiment logic for optimizing the software lock-in
    phase measurement and visualizing phase response using the PicoScope.
    """
    
    def __init__(self, lockin: PicoScopeController, monochromator: MonochromatorController,
                 logger: Optional[MeasurementDataLogger] = None):
        """
        Initialize the phase adjustment model.
        
        Args:
            lockin: PicoScope software lock-in controller
            monochromator: Monochromator controller
            logger: Optional logger for measurement progress
        """
        self.lockin = lockin
        self.monochromator = monochromator
        self.logger = logger or MeasurementDataLogger()
        
        # Adjustment state
        self._is_adjusting = False
        self._stop_requested = False
        self._adjustment_thread: Optional[threading.Thread] = None
        
        # Phase adjustment data
        self.phase_data: List[float] = []
        self.signal_data: List[float] = []
        self.fit_phases: List[float] = []
        self.fit_signals: List[float] = []
        
        # Results
        self.optimal_phase: Optional[float] = None
        self.optimal_signal: Optional[float] = None
        self.r_squared: Optional[float] = None
        
        # Callbacks
        self.progress_callback: Optional[Callable[[float, float], None]] = None
        self.completion_callback: Optional[Callable[[bool, Dict[str, Any]], None]] = None
    
    def is_adjusting(self) -> bool:
        """Check if phase adjustment is in progress."""
        return self._is_adjusting
    
    def set_progress_callback(self, callback: Callable[[float, float], None]) -> None:
        """
        Set callback for phase adjustment progress updates.
        
        Args:
            callback: Function(phase, signal)
        """
        self.progress_callback = callback
    
    def set_completion_callback(self, callback: Callable[[bool, Dict[str, Any]], None]) -> None:
        """
        Set callback for phase adjustment completion.
        
        Args:
            callback: Function(success, results_dict)
        """
        self.completion_callback = callback
    
    def _prepare_for_adjustment(self, pixel_number: int) -> None:
        """
        Prepare devices for phase adjustment.
        
        Args:
            pixel_number: Pixel number being measured
        """
        alignment_wavelength = PHASE_ADJUSTMENT_CONFIG["alignment_wavelength"]
        
        # Configure monochromator
        self.monochromator.send_command("grating 1")
        self.monochromator.send_command(f"gowave {alignment_wavelength}")
        self.monochromator.send_command("shutter o")
        
        # Wait for light to stabilize
        time.sleep(1.0)
        
        self.logger.log(f"Prepared for phase adjustment on pixel {pixel_number}")
    
    def _sample_phase_response(self) -> Tuple[np.ndarray, np.ndarray]:
        """
        Sample phase response using software lock-in.
        
        Uses PicoScope software lock-in to measure signal and determine optimal phase.
        The software lock-in calculates X, Y components and finds the phase that
        maximizes the signal magnitude.
        
        Returns:
            Tuple[np.ndarray, np.ndarray]: (phases, signals) for visualization
            
        Raises:
            PhaseAdjustmentError: If sampling fails
        """
        try:
            self.logger.log("Performing software lock-in measurement for phase optimization")
            
            # Perform software lock-in measurement
            result = self.lockin.perform_lockin_measurement()
            
            if result is None:
                raise PhaseAdjustmentError("Failed to perform lock-in measurement")
            
            # Extract results
            X = result['X']
            Y = result['Y']
            R = result['R']
            theta_deg = result['theta']
            measured_freq = result['freq']
            
            self.logger.log(f"Lock-in results:")
            self.logger.log(f"  X (in-phase):    {X:+.6f} V")
            self.logger.log(f"  Y (quadrature):  {Y:+.6f} V")
            self.logger.log(f"  R (magnitude):   {R:+.6f} V")
            self.logger.log(f"  Phase:           {theta_deg:+.1f}°")
            self.logger.log(f"  Measured freq:   {measured_freq:.2f} Hz")
            
            # Create visualization of projected signal vs phase
            # This shows how signal varies with assumed phase
            test_phases = np.linspace(0, 360, 37)
            signals = []
            
            for test_phase in test_phases:
                # Calculate what the signal would be if we rotated by this phase
                phase_rad = np.deg2rad(test_phase)
                rotated_signal = X * np.cos(phase_rad) + Y * np.sin(phase_rad)
                signals.append(rotated_signal)
            
            return test_phases, np.array(signals)
            
        except PicoScopeError as e:
            raise PhaseAdjustmentError(f"Failed to sample phase response: {e}")
    
    def _fit_sine_wave(self, phases: np.ndarray, signals: np.ndarray) -> Tuple[float, float, float]:
        """
        Fit sine wave to phase response data and extract optimal phase.
        
        For PicoScope software lock-in, we also directly compute the optimal phase
        from the X and Y components measured earlier.
        
        Args:
            phases: Phase values in degrees
            signals: Signal values
            
        Returns:
            Tuple[float, float, float]: (optimal_phase, signal_magnitude, quality_metric)
            
        Raises:
            PhaseAdjustmentError: If fitting fails
        """
        try:
            # Fit sine wave for visualization
            fit_params = MathUtils.fit_sine_wave(phases, signals)
            if fit_params is None:
                raise PhaseAdjustmentError("Failed to fit sine wave to phase response")
            
            # Calculate R-squared
            r_squared = MathUtils.calculate_r_squared(phases, signals, fit_params)
            if r_squared is None:
                raise PhaseAdjustmentError("Failed to calculate R-squared")
            
            # Find optimal phase from fit
            optimal_phase = MathUtils.find_optimal_phase(fit_params, prefer_positive=True)
            
            # Generate fit curve for visualization
            fit_phases, fit_signals = MathUtils.generate_sine_fit_curve(phases, fit_params)
            self.fit_phases = fit_phases.tolist()
            self.fit_signals = fit_signals.tolist()
            
            # Get the actual signal magnitude from the software lock-in
            # (this is more accurate than the fit baseline)
            result = self.lockin.perform_lockin_measurement()
            if result:
                signal_magnitude = result['R']
                actual_phase = result['theta'] % 360
                # Use the actual measured phase instead of fit phase
                optimal_phase = actual_phase
            else:
                signal_magnitude = np.max(np.abs(signals))
            
            self.logger.log(f"Phase analysis: Optimal phase = {optimal_phase:.1f}°, R² = {r_squared:.4f}")
            
            return optimal_phase, signal_magnitude, r_squared
            
        except Exception as e:
            raise PhaseAdjustmentError(f"Failed to fit sine wave: {e}")
    
    def _set_optimal_phase(self, optimal_phase: float) -> float:
        """
        Measure final signal at optimal phase.
        
        For PicoScope software lock-in, the phase is already determined by the measurement.
        This function is kept for API compatibility and returns the magnitude.
        
        Args:
            optimal_phase: Optimal phase angle in degrees
            
        Returns:
            float: Final signal magnitude
        """
        try:
            # Perform another lock-in measurement to confirm signal
            result = self.lockin.perform_lockin_measurement()
            
            if result is None:
                raise PhaseAdjustmentError("Failed to measure final signal")
            
            final_signal = result['R']  # Use magnitude
            
            self.logger.log(f"Optimal phase: {optimal_phase:.1f}°, signal magnitude: {final_signal:.6f} V")
            
            return final_signal
            
        except PicoScopeError as e:
            raise PhaseAdjustmentError(f"Failed to measure final signal: {e}")
    
    def _adjustment_worker(self, pixel_number: int) -> None:
        """
        Worker function for phase adjustment thread.
        
        Args:
            pixel_number: Pixel number being adjusted
        """
        try:
            self.logger.log(f"Starting phase adjustment for pixel {pixel_number}")
            
            # Clear previous data
            self.phase_data.clear()
            self.signal_data.clear()
            self.fit_phases.clear()
            self.fit_signals.clear()
            self.optimal_phase = None
            self.optimal_signal = None
            self.r_squared = None
            
            # Prepare devices
            self._prepare_for_adjustment(pixel_number)
            
            # Sample phase response
            phases, signals = self._sample_phase_response()
            
            if self._stop_requested:
                self.logger.log("Phase adjustment stopped by user")
                if self.completion_callback:
                    self.completion_callback(False, {})
                return
            
            # Store sampled data
            self.phase_data = phases.tolist()
            self.signal_data = signals.tolist()
            
            # Fit sine wave and find optimal phase
            optimal_phase, _, r_squared = self._fit_sine_wave(phases, signals)
            
            # Set optimal phase and measure final signal
            final_signal = self._set_optimal_phase(optimal_phase)
            
            # Store results
            self.optimal_phase = optimal_phase
            self.optimal_signal = final_signal
            self.r_squared = r_squared
            
            # Check R-squared quality
            min_r_squared = PHASE_ADJUSTMENT_CONFIG["min_r_squared"]
            success = r_squared >= min_r_squared
            
            if not success:
                self.logger.log(f"Warning: R² = {r_squared:.4f} is below threshold {min_r_squared}", "WARNING")
            
            results = {
                'pixel_number': pixel_number,
                'optimal_phase': optimal_phase,
                'optimal_signal': final_signal,
                'r_squared': r_squared,
                'phase_data': self.phase_data.copy(),
                'signal_data': self.signal_data.copy(),
                'fit_phases': self.fit_phases.copy(),
                'fit_signals': self.fit_signals.copy()
            }
            
            self.logger.log(f"Phase adjustment completed for pixel {pixel_number}")
            
            if self.completion_callback:
                self.completion_callback(True, results)
                
        except Exception as e:
            self.logger.log(f"Phase adjustment failed: {e}", "ERROR")
            if self.completion_callback:
                self.completion_callback(False, {})
        finally:
            self._is_adjusting = False
    
    def start_adjustment(self, pixel_number: int) -> bool:
        """
        Start phase adjustment in a separate thread.
        
        Args:
            pixel_number: Pixel number to adjust phase for
            
        Returns:
            bool: True if adjustment started successfully
            
        Raises:
            PhaseAdjustmentError: If adjustment cannot be started
        """
        if self._is_adjusting:
            raise PhaseAdjustmentError("Phase adjustment already in progress")
        
        if not self.lockin.is_connected() or not self.monochromator.is_connected():
            raise PhaseAdjustmentError("Devices not connected")
        
        if not (1 <= pixel_number <= 8):
            raise PhaseAdjustmentError("Pixel number must be between 1 and 8")
        
        # Start adjustment thread
        self._is_adjusting = True
        self._stop_requested = False
        self._adjustment_thread = threading.Thread(
            target=self._adjustment_worker,
            args=(pixel_number,),
            daemon=True
        )
        self._adjustment_thread.start()
        
        return True
    
    def stop_adjustment(self) -> None:
        """Stop the current phase adjustment."""
        if self._is_adjusting:
            self._stop_requested = True
            self.logger.log("Stop requested for phase adjustment")
    
    def wait_for_completion(self, timeout: Optional[float] = None) -> bool:
        """
        Wait for phase adjustment to complete.
        
        Args:
            timeout: Maximum time to wait in seconds
            
        Returns:
            bool: True if adjustment completed, False if timeout
        """
        if self._adjustment_thread:
            self._adjustment_thread.join(timeout)
            return not self._adjustment_thread.is_alive()
        return True
    
    def get_adjustment_data(self) -> Dict[str, Any]:
        """
        Get the current phase adjustment data.
        
        Returns:
            Dict[str, Any]: Adjustment data and results
        """
        return {
            'phase_data': self.phase_data.copy(),
            'signal_data': self.signal_data.copy(),
            'fit_phases': self.fit_phases.copy(),
            'fit_signals': self.fit_signals.copy(),
            'optimal_phase': self.optimal_phase,
            'optimal_signal': self.optimal_signal,
            'r_squared': self.r_squared
        }
    
    def clear_data(self) -> None:
        """Clear adjustment data."""
        self.phase_data.clear()
        self.signal_data.clear()
        self.fit_phases.clear()
        self.fit_signals.clear()
        self.optimal_phase = None
        self.optimal_signal = None
        self.r_squared = None
    
    def is_r_squared_acceptable(self) -> bool:
        """
        Check if the R-squared value meets the minimum threshold.
        
        Returns:
            bool: True if R-squared is acceptable
        """
        if self.r_squared is None:
            return False
        min_r_squared = PHASE_ADJUSTMENT_CONFIG["min_r_squared"]
        return self.r_squared >= min_r_squared