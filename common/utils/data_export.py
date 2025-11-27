"""
Generic data export utilities for measurement applications.
"""

import csv
import datetime
from pathlib import Path
from typing import List, Tuple, Dict, Any, Optional
from abc import ABC, abstractmethod


class DataExportError(Exception):
    """Exception raised for data export errors."""
    pass


class DataExporter(ABC):
    """Abstract base class for data exporters."""

    @abstractmethod
    def export(self, file_path: str, data: Dict[str, List[Any]],
               headers: Optional[List[str]] = None) -> None:
        """Export data to file."""
        pass

    @staticmethod
    def generate_timestamp() -> str:
        """Generate timestamp string for filenames."""
        return datetime.datetime.now().strftime("%Y_%m_%d")

    @staticmethod
    def ensure_directory(file_path: str) -> Path:
        """Ensure the directory for a file path exists."""
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        return path


class CSVExporter(DataExporter):
    """CSV file exporter for measurement data."""

    def __init__(self, delimiter: str = ',', precision: int = 6):
        """
        Initialize CSV exporter.

        Args:
            delimiter: CSV field delimiter
            precision: Decimal places for floating point values
        """
        self.delimiter = delimiter
        self.precision = precision

    def export(self, file_path: str, data: Dict[str, List[Any]],
               headers: Optional[List[str]] = None) -> None:
        """
        Export data to CSV file.

        Args:
            file_path: Path to save the CSV file
            data: Dictionary mapping column names to data lists
            headers: Optional custom headers (defaults to data keys)

        Raises:
            DataExportError: If export fails
        """
        try:
            self.ensure_directory(file_path)

            if headers is None:
                headers = list(data.keys())

            # Get all columns as lists
            columns = [data[h] for h in headers if h in data]

            with open(file_path, mode='w', newline='') as file:
                writer = csv.writer(file, delimiter=self.delimiter)
                writer.writerow(headers)

                # Write rows
                for row in zip(*columns):
                    formatted_row = [
                        round(val, self.precision) if isinstance(val, float) else val
                        for val in row
                    ]
                    writer.writerow(formatted_row)

        except Exception as e:
            raise DataExportError(f"Failed to export CSV: {e}")

    def export_xy_data(self, file_path: str, x_data: List[float],
                       y_data: List[float], x_header: str = "X",
                       y_header: str = "Y") -> None:
        """
        Export simple X-Y data to CSV.

        Args:
            file_path: Path to save the CSV file
            x_data: X-axis values
            y_data: Y-axis values
            x_header: Header for X column
            y_header: Header for Y column
        """
        self.export(file_path, {x_header: x_data, y_header: y_data},
                   headers=[x_header, y_header])

    def load_xy_data(self, file_path: str) -> Tuple[List[float], List[float]]:
        """
        Load X-Y data from CSV file.

        Args:
            file_path: Path to the CSV file

        Returns:
            Tuple of (x_data, y_data) lists

        Raises:
            DataExportError: If load fails
        """
        try:
            x_data = []
            y_data = []

            with open(file_path, mode='r', newline='') as file:
                reader = csv.reader(file, delimiter=self.delimiter)
                next(reader)  # Skip header

                for row in reader:
                    if len(row) >= 2:
                        x_data.append(float(row[0]))
                        y_data.append(float(row[1]))

            return x_data, y_data

        except Exception as e:
            raise DataExportError(f"Failed to load CSV: {e}")
