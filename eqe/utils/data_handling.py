"""
Data handling utilities for the EQE measurement application.
"""

import csv
import os
import datetime
import logging
import pandas as pd
from typing import List, Tuple, Dict, Any, Optional
from pathlib import Path
import re

from ..config.settings import (
    FILE_NAMING, DATA_EXPORT_CONFIG, VALIDATION_PATTERNS, ERROR_MESSAGES
)


class DataValidationError(Exception):
    """Exception raised for data validation errors."""
    pass


def _get_pixel_list() -> List[int]:
    """Get list of valid pixel numbers from settings."""
    pixel_range = VALIDATION_PATTERNS["pixel_range"]
    return list(range(pixel_range[0], pixel_range[1] + 1))


class DataHandler:
    """Handles data saving, loading, and validation operations."""
    
    @staticmethod
    def validate_cell_number(cell_number: str) -> bool:
        """
        Validate cell number format.
        
        Args:
            cell_number: Cell number string to validate
            
        Returns:
            bool: True if valid, False otherwise
        """
        pattern = VALIDATION_PATTERNS["cell_number"]
        return bool(re.match(pattern, cell_number))
    
    @staticmethod
    def validate_pixel_number(pixel_number: int) -> bool:
        """
        Validate pixel number range.
        
        Args:
            pixel_number: Pixel number to validate
            
        Returns:
            bool: True if valid, False otherwise
        """
        min_pixel, max_pixel = VALIDATION_PATTERNS["pixel_range"]
        return min_pixel <= pixel_number <= max_pixel
    
    @staticmethod
    def generate_filename(measurement_type: str, cell_number: str, 
                         pixel_number: Optional[int] = None) -> str:
        """
        Generate filename based on measurement type and parameters.
        
        Args:
            measurement_type: Type of measurement ("power", "current", "phase")
            cell_number: Cell number string
            pixel_number: Pixel number (optional, for current measurements)
            
        Returns:
            str: Generated filename
            
        Raises:
            DataValidationError: If parameters are invalid
        """
        if not DataHandler.validate_cell_number(cell_number):
            raise DataValidationError(ERROR_MESSAGES["invalid_cell_number"])
        
        if pixel_number is not None and not DataHandler.validate_pixel_number(pixel_number):
            raise DataValidationError(ERROR_MESSAGES["invalid_pixel_number"])
        
        date = datetime.datetime.now().strftime(FILE_NAMING["date_format"])
        
        if measurement_type == "power":
            template = FILE_NAMING["power_file_template"]
            return template.format(date=date, cell_number=cell_number)
        elif measurement_type == "current":
            if pixel_number is None:
                raise DataValidationError("Pixel number required for current measurements")
            template = FILE_NAMING["current_file_template"]
            return template.format(date=date, cell_number=cell_number, pixel_number=pixel_number)
        elif measurement_type == "phase":
            template = FILE_NAMING["phase_file_template"]
            return template.format(date=date, cell_number=cell_number)
        else:
            raise DataValidationError(f"Unknown measurement type: {measurement_type}")
    
    @staticmethod
    def save_measurement_data(file_path: str, wavelengths: List[float],
                            measurements: List[float], measurement_type: str,
                            measurement_stats: Optional[List[Dict[str, Any]]] = None) -> None:
        """
        Save measurement data to CSV file.

        Args:
            file_path: Path to save the file
            wavelengths: List of wavelength values
            measurements: List of measurement values
            measurement_type: Type of measurement for header selection
            measurement_stats: Optional list of stat dicts per wavelength
                              Each dict: {std_dev: float, n: int}

        Raises:
            DataValidationError: If save operation fails
        """
        try:
            # Check if stats export is enabled and we have stats data
            include_stats = (
                DATA_EXPORT_CONFIG.get("include_measurement_stats", False)
                and measurement_type == "current"
                and measurement_stats is not None
                and len(measurement_stats) == len(measurements)
            )

            if include_stats:
                headers = DATA_EXPORT_CONFIG["headers"].get("current_with_stats",
                    ["Wavelength (nm)", "Current_mean (nA)", "Current_std (nA)", "n"])
            else:
                headers = DATA_EXPORT_CONFIG["headers"].get(measurement_type,
                    ["Wavelength (nm)", "Measurement"])

            with open(file_path, mode='w', newline='') as file:
                writer = csv.writer(file, delimiter=DATA_EXPORT_CONFIG["csv_delimiter"])
                writer.writerow(headers)

                precision = DATA_EXPORT_CONFIG["precision"]

                for i, (wavelength, measurement) in enumerate(zip(wavelengths, measurements)):
                    if include_stats:
                        # Convert from Amps to nanoamps for readability
                        # Students can immediately interpret "4.24 nA" vs "4.24E-09 A"
                        current_nA = measurement * 1e9
                        stats = measurement_stats[i]
                        std_nA = stats['std_dev'] * 1e9
                        row = [
                            wavelength,
                            f"{current_nA:.2f}",
                            f"{std_nA:.2f}",
                            stats['n']
                        ]
                    else:
                        if measurement_type == "current":
                            # Convert to nanoamps for readability
                            current_nA = measurement * 1e9
                            row = [wavelength, f"{current_nA:.2f}"]
                        else:
                            # Power stays in Watts with scientific notation
                            formatted_measurement = f"{measurement:.{precision}e}"
                            row = [wavelength, formatted_measurement]

                    writer.writerow(row)

        except Exception as e:
            raise DataValidationError(f"{ERROR_MESSAGES['file_save_failed']}: {e}")
    
    @staticmethod
    def save_phase_data(file_path: str, pixel_number: int, phase_angle: float,
                       signal: float, r_squared: float) -> None:
        """
        Save phase adjustment data to CSV file.
        
        Args:
            file_path: Path to save the file
            pixel_number: Pixel number
            phase_angle: Optimal phase angle
            signal: Signal value at optimal phase
            r_squared: R-squared value of the fit
            
        Raises:
            DataValidationError: If save operation fails
        """
        try:
            # Create or load existing phase data file
            if os.path.exists(file_path):
                try:
                    df = pd.read_csv(file_path)
                    # Handle legacy format
                    if "Pixel #" not in df.columns:
                        # Convert from legacy format (6 pixels)
                        legacy_data = df[["set angle", "signal", "r-value"]].values
                        pixels = _get_pixel_list()
                        df = pd.DataFrame({
                            "Pixel #": pixels,
                            "Set Angle": [None] * len(pixels),
                            "Signal": [None] * len(pixels),
                            "R^2 Value": [None] * len(pixels)
                        })
                        # Fill in legacy data (only first 6 pixels)
                        for i, row in enumerate(legacy_data[:6]):
                            df.at[i, "Set Angle"] = row[0]
                            df.at[i, "Signal"] = row[1]
                            df.at[i, "R^2 Value"] = row[2]
                    else:
                        # Ensure all pixels from settings are present
                        pixels = _get_pixel_list()
                        existing_pixels = df["Pixel #"].tolist()
                        for i in pixels:
                            if i not in existing_pixels:
                                df = pd.concat([df, pd.DataFrame({
                                    "Pixel #": [i],
                                    "Set Angle": [None],
                                    "Signal": [None],
                                    "R^2 Value": [None]
                                })], ignore_index=True)
                        df = df[df["Pixel #"].isin(pixels)].sort_values("Pixel #").reset_index(drop=True)
                except Exception:
                    # Create new dataframe if reading fails
                    pixels = _get_pixel_list()
                    df = pd.DataFrame({
                        "Pixel #": pixels,
                        "Set Angle": [None] * len(pixels),
                        "Signal": [None] * len(pixels),
                        "R^2 Value": [None] * len(pixels)
                    })
            else:
                # Create new dataframe
                pixels = _get_pixel_list()
                df = pd.DataFrame({
                    "Pixel #": pixels,
                    "Set Angle": [None] * len(pixels),
                    "Signal": [None] * len(pixels),
                    "R^2 Value": [None] * len(pixels)
                })
            
            # Update data for the specific pixel
            pixel_index = pixel_number - 1
            df.at[pixel_index, "Set Angle"] = f"{phase_angle:.2f}"
            df.at[pixel_index, "Signal"] = signal
            df.at[pixel_index, "R^2 Value"] = f"{r_squared:.4f}"
            
            # Save the file
            df.to_csv(file_path, index=False)
            
        except Exception as e:
            raise DataValidationError(f"{ERROR_MESSAGES['file_save_failed']}: {e}")
    
    @staticmethod
    def load_measurement_data(file_path: str) -> Tuple[List[float], List[float]]:
        """
        Load measurement data from CSV file.
        
        Args:
            file_path: Path to the CSV file
            
        Returns:
            Tuple[List[float], List[float]]: (wavelengths, measurements)
            
        Raises:
            DataValidationError: If load operation fails
        """
        try:
            df = pd.read_csv(file_path)
            wavelengths = df.iloc[:, 0].tolist()
            measurements = df.iloc[:, 1].tolist()
            return wavelengths, measurements
        except Exception as e:
            raise DataValidationError(f"Failed to load data: {e}")
    
    @staticmethod
    def create_data_directory(base_path: str = "data") -> Path:
        """
        Create data directory if it doesn't exist.
        
        Args:
            base_path: Base directory path for data
            
        Returns:
            Path: Path object for the data directory
        """
        data_dir = Path(base_path)
        data_dir.mkdir(parents=True, exist_ok=True)
        return data_dir


class MeasurementDataLogger:
    """Handles logging of measurement progress and status."""

    def __init__(self, log_file: Optional[str] = None):
        """
        Initialize the logger.

        Args:
            log_file: Optional log file path
        """
        self.log_file = log_file
        self.log_entries = []
        # Get Python logger for forwarding to web console
        self._python_logger = logging.getLogger("phys2150.eqe")

    def log(self, message: str, level: str = "INFO") -> None:
        """
        Log a message with timestamp.

        Args:
            message: Message to log
            level: Log level (INFO, WARNING, ERROR)
        """
        timestamp = datetime.datetime.now().isoformat()
        entry = f"{timestamp} [{level}] {message}"
        self.log_entries.append(entry)

        if self.log_file:
            try:
                with open(self.log_file, 'a') as f:
                    f.write(entry + '\n')
            except Exception:
                pass  # Silently ignore log file errors

        # Forward to Python logging system (for web console)
        log_level = getattr(logging, level.upper(), logging.INFO)
        self._python_logger.log(log_level, message)

    def debug(self, message: str) -> None:
        """Debug-level log (file and Python logger for web console)."""
        if self.log_file:
            timestamp = datetime.datetime.now().isoformat()
            entry = f"{timestamp} [DEBUG] {message}"
            try:
                with open(self.log_file, 'a') as f:
                    f.write(entry + '\n')
            except Exception:
                pass
        # Forward to Python logging system (for web console in debug mode)
        self._python_logger.debug(message)
    
    def get_log_entries(self) -> List[str]:
        """Get all log entries."""
        return self.log_entries.copy()
    
    def clear_log(self) -> None:
        """Clear log entries."""
        self.log_entries.clear()