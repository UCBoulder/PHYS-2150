"""
Mathematical and signal processing utilities for the EQE measurement application.
"""

import warnings
import numpy as np
from scipy.optimize import curve_fit, OptimizeWarning
from typing import Tuple, Optional, Dict, Any


class MathUtils:
    """Mathematical utilities for data processing and analysis."""
    
    @staticmethod
    def fit_sine_wave(phases: np.ndarray, signals: np.ndarray) -> Optional[Tuple[float, float, float]]:
        """
        Fit a sine wave to phase response data.
        
        Args:
            phases: Phase values in degrees
            signals: Signal values
            
        Returns:
            Optional[Tuple[float, float, float]]: (amplitude, phase_shift, offset) or None if fit fails
        """
        try:
            x = np.radians(phases)
            
            def sine_func(x, amplitude, phase_shift, offset):
                return amplitude * np.sin(x + phase_shift) + offset
            
            # Initial guess
            p0 = [
                (np.max(signals) - np.min(signals)) / 2,  # amplitude
                0,  # phase_shift
                np.mean(signals)  # offset
            ]

            # Suppress OptimizeWarning when fit fails (e.g., no signal)
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", OptimizeWarning)
                popt, _ = curve_fit(sine_func, x, signals, p0=p0)
            return tuple(popt)
            
        except Exception:
            return None
    
    @staticmethod
    def calculate_r_squared(phases: np.ndarray, signals: np.ndarray, 
                           fit_params: Tuple[float, float, float]) -> Optional[float]:
        """
        Calculate R-squared value for sine wave fit.
        
        Args:
            phases: Phase values in degrees
            signals: Signal values
            fit_params: Sine wave fit parameters (amplitude, phase_shift, offset)
            
        Returns:
            Optional[float]: R-squared value or None if calculation fails
        """
        try:
            amplitude, phase_shift, offset = fit_params
            x = np.radians(phases)
            fitted = amplitude * np.sin(x + phase_shift) + offset
            
            ss_tot = np.sum((signals - np.mean(signals))**2)
            ss_res = np.sum((signals - fitted)**2)
            
            if ss_tot == 0:  # Avoid division by zero
                return None
                
            r_squared = 1 - ss_res / ss_tot
            return r_squared
            
        except Exception:
            return None
    
    @staticmethod
    def find_optimal_phase(fit_params: Tuple[float, float, float], 
                          prefer_positive: bool = True) -> float:
        """
        Find optimal phase angle from sine wave fit.
        
        Args:
            fit_params: Sine wave fit parameters (amplitude, phase_shift, offset)
            prefer_positive: Whether to prefer positive signal
            
        Returns:
            float: Optimal phase angle in degrees
        """
        amplitude, phase_shift, offset = fit_params
        
        # Calculate phase for maximum signal
        optimal_phase = (np.degrees(-phase_shift) + 90) % 360
        
        if not prefer_positive:
            # For minimum signal, add 180 degrees
            optimal_phase = (optimal_phase + 180) % 360
        
        return optimal_phase
    
    @staticmethod
    def generate_sine_fit_curve(phases: np.ndarray, fit_params: Tuple[float, float, float],
                               num_points: int = 1000) -> Tuple[np.ndarray, np.ndarray]:
        """
        Generate smooth sine curve from fit parameters.
        
        Args:
            phases: Original phase values in degrees
            fit_params: Sine wave fit parameters
            num_points: Number of points for smooth curve
            
        Returns:
            Tuple[np.ndarray, np.ndarray]: (smooth_phases, smooth_signals)
        """
        amplitude, phase_shift, offset = fit_params
        
        phase_min, phase_max = np.min(phases), np.max(phases)
        smooth_phases = np.linspace(phase_min, phase_max, num_points)
        x = np.radians(smooth_phases)
        smooth_signals = amplitude * np.sin(x + phase_shift) + offset
        
        return smooth_phases, smooth_signals
    
    @staticmethod
    def calculate_statistics(data: np.ndarray) -> Dict[str, float]:
        """
        Calculate basic statistics for a dataset.
        
        Args:
            data: Input data array
            
        Returns:
            Dict[str, float]: Statistics dictionary
        """
        return {
            'mean': np.mean(data),
            'std': np.std(data, ddof=1) if len(data) > 1 else 0.0,
            'min': np.min(data),
            'max': np.max(data),
            'median': np.median(data),
            'count': len(data)
        }
    
    @staticmethod
    def moving_average(data: np.ndarray, window_size: int) -> np.ndarray:
        """
        Calculate moving average of data.
        
        Args:
            data: Input data
            window_size: Size of the moving window
            
        Returns:
            np.ndarray: Smoothed data
        """
        if window_size >= len(data):
            return np.full_like(data, np.mean(data))
        
        return np.convolve(data, np.ones(window_size) / window_size, mode='same')
    
    @staticmethod
    def normalize_data(data: np.ndarray, method: str = 'minmax') -> np.ndarray:
        """
        Normalize data using specified method.
        
        Args:
            data: Input data
            method: Normalization method ('minmax', 'zscore')
            
        Returns:
            np.ndarray: Normalized data
        """
        if method == 'minmax':
            data_min, data_max = np.min(data), np.max(data)
            if data_max == data_min:
                return np.zeros_like(data)
            return (data - data_min) / (data_max - data_min)
        elif method == 'zscore':
            mean, std = np.mean(data), np.std(data)
            if std == 0:
                return np.zeros_like(data)
            return (data - mean) / std
        else:
            raise ValueError(f"Unknown normalization method: {method}")


class SignalProcessing:
    """Signal processing utilities for measurement data."""
    
    @staticmethod
    def remove_outliers(data: np.ndarray, method: str = 'iqr', 
                       factor: float = 1.5) -> Tuple[np.ndarray, np.ndarray]:
        """
        Remove outliers from data.
        
        Args:
            data: Input data
            method: Outlier detection method ('iqr', 'zscore')
            factor: Factor for outlier threshold
            
        Returns:
            Tuple[np.ndarray, np.ndarray]: (cleaned_data, outlier_mask)
        """
        if method == 'iqr':
            q1, q3 = np.percentile(data, [25, 75])
            iqr = q3 - q1
            lower_bound = q1 - factor * iqr
            upper_bound = q3 + factor * iqr
            outlier_mask = (data < lower_bound) | (data > upper_bound)
        elif method == 'zscore':
            z_scores = np.abs((data - np.mean(data)) / np.std(data))
            outlier_mask = z_scores > factor
        else:
            raise ValueError(f"Unknown outlier detection method: {method}")
        
        cleaned_data = data[~outlier_mask]
        return cleaned_data, outlier_mask
    
    @staticmethod
    def detect_peaks(data: np.ndarray, height: Optional[float] = None,
                    distance: Optional[int] = None) -> np.ndarray:
        """
        Detect peaks in data.
        
        Args:
            data: Input data
            height: Minimum peak height
            distance: Minimum distance between peaks
            
        Returns:
            np.ndarray: Peak indices
        """
        # Simple peak detection - can be enhanced with scipy.signal.find_peaks
        peaks = []
        
        for i in range(1, len(data) - 1):
            if data[i] > data[i-1] and data[i] > data[i+1]:
                if height is None or data[i] >= height:
                    peaks.append(i)
        
        peaks = np.array(peaks)
        
        # Apply distance constraint
        if distance is not None and len(peaks) > 1:
            filtered_peaks = [peaks[0]]
            for peak in peaks[1:]:
                if peak - filtered_peaks[-1] >= distance:
                    filtered_peaks.append(peak)
            peaks = np.array(filtered_peaks)
        
        return peaks
    
    @staticmethod
    def interpolate_data(x_old: np.ndarray, y_old: np.ndarray, 
                        x_new: np.ndarray, method: str = 'linear') -> np.ndarray:
        """
        Interpolate data to new x values.
        
        Args:
            x_old: Original x values
            y_old: Original y values
            x_new: New x values for interpolation
            method: Interpolation method ('linear', 'cubic')
            
        Returns:
            np.ndarray: Interpolated y values
        """
        return np.interp(x_new, x_old, y_old)


class CalibrationUtils:
    """Utilities for instrument calibration and correction."""
    
    @staticmethod
    def apply_correction_factor(data: np.ndarray, factor: float) -> np.ndarray:
        """
        Apply a correction factor to data.
        
        Args:
            data: Input data
            factor: Correction factor
            
        Returns:
            np.ndarray: Corrected data
        """
        return data * factor
    
    @staticmethod
    def wavelength_to_energy(wavelength_nm: np.ndarray) -> np.ndarray:
        """
        Convert wavelength in nm to energy in eV.
        
        Args:
            wavelength_nm: Wavelength in nanometers
            
        Returns:
            np.ndarray: Energy in electron volts
        """
        # E(eV) = hc / λ = 1239.84 / λ(nm)
        return 1239.84 / wavelength_nm
    
    @staticmethod
    def energy_to_wavelength(energy_ev: np.ndarray) -> np.ndarray:
        """
        Convert energy in eV to wavelength in nm.
        
        Args:
            energy_ev: Energy in electron volts
            
        Returns:
            np.ndarray: Wavelength in nanometers
        """
        # λ(nm) = hc / E = 1239.84 / E(eV)
        return 1239.84 / energy_ev