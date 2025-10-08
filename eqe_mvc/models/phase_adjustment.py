"""
Phase Adjustment Model

This model implements the logic for phase adjustment using the SR510 lock-in amplifier
and monochromator. It handles automatic phase optimization through signal measurement.
"""

import time
import numpy as np
from typing import List, Tuple, Optional, Callable, Dict, Any
import threading

from ..controllers.sr510_lockin import SR510Controller, SR510Error
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
    
    This model implements the experiment logic for optimizing the lock-in amplifier
    phase by sampling phase response and fitting a sine wave.
    """
    
    def __init__(self, lockin: SR510Controller, monochromator: MonochromatorController,
                 logger: Optional[MeasurementDataLogger] = None):
        """
        Initialize the phase adjustment model.
        
        Args:
            lockin: SR510 lock-in amplifier controller
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
        
        # Configure lock-in amplifier
        self.lockin.configure_standard_parameters()
        
        self.logger.log(f"Prepared for phase adjustment on pixel {pixel_number}")
    
    def _sample_phase_response(self) -> Tuple[np.ndarray, np.ndarray]:
        """
        Sample phase response at multiple phase points.
        
        Returns:
            Tuple[np.ndarray, np.ndarray]: (phases, signals)
            
        Raises:
            PhaseAdjustmentError: If sampling fails
        """
        try:
            num_points = PHASE_ADJUSTMENT_CONFIG["num_phase_points"]
            phase_range = PHASE_ADJUSTMENT_CONFIG["phase_range"]
            
            phases = np.linspace(phase_range[0], phase_range[1], num_points)
            signals = []
            
            self.logger.log(f"Sampling phase response at {num_points} points")
            
            for i, phase in enumerate(phases):
                if self._stop_requested:
                    raise PhaseAdjustmentError("Phase adjustment stopped by user")
                
                # Set phase
                self.lockin.set_phase(phase)
                
                # Read signal
                signal = self.lockin.read_output()
                signals.append(signal)
                
                self.logger.log(f"Phase: {phase:.1f}°, Signal: {signal:.6f}")
                
                if self.progress_callback:
                    self.progress_callback(phase, signal)
            
            return phases, np.array(signals)
            
        except SR510Error as e:
            raise PhaseAdjustmentError(f"Failed to sample phase response: {e}")
    
    def _fit_sine_wave(self, phases: np.ndarray, signals: np.ndarray) -> Tuple[float, float, float]:
        """
        Fit sine wave to phase response data.
        
        Args:
            phases: Phase values in degrees
            signals: Signal values
            
        Returns:
            Tuple[float, float, float]: (optimal_phase, optimal_signal, r_squared)
            
        Raises:
            PhaseAdjustmentError: If fitting fails
        """
        try:
            # Fit sine wave
            fit_params = MathUtils.fit_sine_wave(phases, signals)
            if fit_params is None:
                raise PhaseAdjustmentError("Failed to fit sine wave to phase response")
            
            # Calculate R-squared
            r_squared = MathUtils.calculate_r_squared(phases, signals, fit_params)
            if r_squared is None:
                raise PhaseAdjustmentError("Failed to calculate R-squared")
            
            # Find optimal phase
            optimal_phase = MathUtils.find_optimal_phase(fit_params, prefer_positive=True)
            
            # Generate fit curve for visualization
            fit_phases, fit_signals = MathUtils.generate_sine_fit_curve(phases, fit_params)
            self.fit_phases = fit_phases.tolist()
            self.fit_signals = fit_signals.tolist()
            
            self.logger.log(f"Sine wave fit completed: R² = {r_squared:.4f}")
            
            return optimal_phase, fit_params[2], r_squared  # Return phase, offset (baseline), R²
            
        except Exception as e:
            raise PhaseAdjustmentError(f"Failed to fit sine wave: {e}")
    
    def _set_optimal_phase(self, optimal_phase: float) -> float:
        """
        Set the optimal phase and measure final signal.
        
        Args:
            optimal_phase: Optimal phase angle in degrees
            
        Returns:
            float: Final signal at optimal phase
        """
        try:
            # Set optimal phase
            self.lockin.set_phase(optimal_phase)
            
            # Read final signal
            final_signal = self.lockin.read_output()
            
            # If signal is negative, try adding 180 degrees
            if final_signal < 0:
                adjusted_phase = (optimal_phase + 180) % 360
                self.logger.log(f"Signal negative, adjusting phase to {adjusted_phase:.1f}°")
                self.lockin.set_phase(adjusted_phase)
                final_signal = self.lockin.read_output()
                optimal_phase = adjusted_phase
            
            self.logger.log(f"Set optimal phase to {optimal_phase:.1f}°, final signal: {final_signal:.6f}")
            
            return final_signal
            
        except SR510Error as e:
            raise PhaseAdjustmentError(f"Failed to set optimal phase: {e}")
    
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
        
        if not (1 <= pixel_number <= 6):
            raise PhaseAdjustmentError("Pixel number must be between 1 and 6")
        
        # Start adjustment thread
        self._is_adjusting = True
        self._stop_requested = False
        self._adjustment_thread = threading.Thread(
            target=self._adjustment_worker,
            args=(pixel_number,)
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