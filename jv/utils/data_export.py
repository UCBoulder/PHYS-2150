"""
JV Data Export Utility

Handles saving J-V measurement data to CSV files with proper formatting.
"""

import datetime
from typing import Optional
import pandas as pd
import numpy as np

from ..models.jv_measurement import JVMeasurementResult
from ..config.settings import DATA_EXPORT_CONFIG


class JVDataExporter:
    """
    Utility class for exporting J-V measurement data to CSV files.
    """

    def __init__(self, config: Optional[dict] = None):
        """
        Initialize the data exporter.

        Args:
            config: Optional configuration override
        """
        self.config = config or DATA_EXPORT_CONFIG.copy()

    def generate_filename(self, cell_number: str, pixel_number: int) -> str:
        """
        Generate a filename based on cell/pixel and date.

        Args:
            cell_number: Cell identifier (e.g., "195")
            pixel_number: Pixel number (1-8)

        Returns:
            str: Generated filename
        """
        date_format = self.config.get("date_format", "%Y_%m_%d")
        date_str = datetime.datetime.now().strftime(date_format)

        template = self.config.get(
            "file_template",
            "{date}_IV_cell{cell_number}_pixel{pixel_number}.csv"
        )

        return template.format(
            date=date_str,
            cell_number=cell_number,
            pixel_number=pixel_number,
        )

    def save_measurement(
        self,
        result: JVMeasurementResult,
        file_path: str,
    ) -> None:
        """
        Save measurement result to a CSV file.

        The format includes voltage, currents, and statistics (std_dev, n):
        - Voltage column with all voltage values
        - Forward Scan columns: current, std_dev, n
        - Reverse Scan columns: current, std_dev, n

        After grouping by voltage, forward and reverse values are combined.

        Args:
            result: Measurement result containing forward and reverse sweeps
            file_path: Path to save the CSV file
        """
        headers = self.config.get("headers", {})
        voltage_header = headers.get("voltage", "Voltage (V)")
        forward_header = headers.get("forward_current", "Forward Scan (mA)")
        forward_std_header = headers.get("forward_std", "Forward Std (mA)")
        forward_n_header = headers.get("forward_n", "Forward n")
        reverse_header = headers.get("reverse_current", "Reverse Scan (mA)")
        reverse_std_header = headers.get("reverse_std", "Reverse Std (mA)")
        reverse_n_header = headers.get("reverse_n", "Reverse n")

        # Build combined data with statistics
        forward_voltages = result.forward.voltages
        forward_currents = result.forward.currents
        forward_stds = result.forward.std_devs
        forward_ns = result.forward.n_measurements
        reverse_voltages = result.reverse.voltages
        reverse_currents = result.reverse.currents
        reverse_stds = result.reverse.std_devs
        reverse_ns = result.reverse.n_measurements

        # Create DataFrame with both sweeps (including statistics)
        combined_data = pd.DataFrame({
            voltage_header: np.concatenate((forward_voltages, reverse_voltages)),
            forward_header: np.concatenate((
                forward_currents,
                [None] * len(reverse_currents)
            )),
            forward_std_header: np.concatenate((
                forward_stds,
                [None] * len(reverse_currents)
            )),
            forward_n_header: np.concatenate((
                forward_ns,
                [None] * len(reverse_currents)
            )),
            reverse_header: np.concatenate((
                [None] * len(forward_currents),
                reverse_currents
            )),
            reverse_std_header: np.concatenate((
                [None] * len(forward_currents),
                reverse_stds
            )),
            reverse_n_header: np.concatenate((
                [None] * len(forward_currents),
                reverse_ns
            )),
        })

        # Group by voltage to combine forward and reverse values
        combined_data = combined_data.groupby(voltage_header).agg({
            forward_header: "first",
            forward_std_header: "first",
            forward_n_header: "first",
            reverse_header: "first",
            reverse_std_header: "first",
            reverse_n_header: "first",
        }).reset_index()

        # Save to CSV
        combined_data.to_csv(file_path, index=False)

    def save_measurement_raw(
        self,
        result: JVMeasurementResult,
        file_path: str,
    ) -> None:
        """
        Save measurement as raw sequential data (alternative format).

        This format preserves the measurement order with a direction column.

        Args:
            result: Measurement result
            file_path: Path to save the CSV file
        """
        headers_raw = self.config.get("headers_raw", {})
        voltage_header = headers_raw.get("voltage", "Voltage (V)")
        current_header = headers_raw.get("current", "Current (mA)")
        direction_header = headers_raw.get("direction", "Direction")

        rows = []

        # Add forward sweep data
        for v, i in zip(result.forward.voltages, result.forward.currents):
            rows.append({
                direction_header: "Forward",
                voltage_header: v,
                current_header: i,
            })

        # Add reverse sweep data
        for v, i in zip(result.reverse.voltages, result.reverse.currents):
            rows.append({
                direction_header: "Reverse",
                voltage_header: v,
                current_header: i,
            })

        df = pd.DataFrame(rows)
        df.to_csv(file_path, index=False)

    def result_to_dataframe(
        self,
        result: JVMeasurementResult,
    ) -> pd.DataFrame:
        """
        Convert measurement result to a pandas DataFrame with statistics.

        Args:
            result: Measurement result

        Returns:
            pd.DataFrame: Combined data with statistics
        """
        headers = self.config.get("headers", {})
        voltage_header = headers.get("voltage", "Voltage (V)")
        forward_header = headers.get("forward_current", "Forward Scan (mA)")
        forward_std_header = headers.get("forward_std", "Forward Std (mA)")
        forward_n_header = headers.get("forward_n", "Forward n")
        reverse_header = headers.get("reverse_current", "Reverse Scan (mA)")
        reverse_std_header = headers.get("reverse_std", "Reverse Std (mA)")
        reverse_n_header = headers.get("reverse_n", "Reverse n")

        # Get unique voltages (sorted)
        all_voltages = sorted(set(
            result.forward.voltages + result.reverse.voltages
        ))

        # Create voltage to data mappings
        forward_current_map = dict(zip(result.forward.voltages, result.forward.currents))
        forward_std_map = dict(zip(result.forward.voltages, result.forward.std_devs))
        forward_n_map = dict(zip(result.forward.voltages, result.forward.n_measurements))
        reverse_current_map = dict(zip(result.reverse.voltages, result.reverse.currents))
        reverse_std_map = dict(zip(result.reverse.voltages, result.reverse.std_devs))
        reverse_n_map = dict(zip(result.reverse.voltages, result.reverse.n_measurements))

        # Build DataFrame with statistics
        data = {
            voltage_header: all_voltages,
            forward_header: [forward_current_map.get(v) for v in all_voltages],
            forward_std_header: [forward_std_map.get(v) for v in all_voltages],
            forward_n_header: [forward_n_map.get(v) for v in all_voltages],
            reverse_header: [reverse_current_map.get(v) for v in all_voltages],
            reverse_std_header: [reverse_std_map.get(v) for v in all_voltages],
            reverse_n_header: [reverse_n_map.get(v) for v in all_voltages],
        }

        return pd.DataFrame(data)

    def save_stability_test(
        self,
        timestamps: list,
        voltages: list,
        currents: list,
        file_path: str,
    ) -> None:
        """
        Save stability test data to CSV file.

        Args:
            timestamps: List of timestamps (seconds since start)
            voltages: List of voltages (V)
            currents: List of currents (mA)
            file_path: Path to save the CSV file
        """
        headers = self.config.get("headers_stability", {})
        timestamp_header = headers.get("timestamp", "Timestamp (s)")
        voltage_header = headers.get("voltage", "Voltage (V)")
        current_header = headers.get("current", "Current (mA)")

        # Create DataFrame
        df = pd.DataFrame({
            timestamp_header: timestamps,
            voltage_header: voltages,
            current_header: currents,
        })

        # Save to CSV
        df.to_csv(file_path, index=False)

    def generate_stability_filename(
        self,
        cell_number: str,
        pixel_number: int,
    ) -> str:
        """
        Generate a filename for stability test data.

        Args:
            cell_number: Cell identifier
            pixel_number: Pixel number

        Returns:
            str: Generated filename
        """
        date_format = self.config.get("date_format", "%Y_%m_%d")
        date_str = datetime.datetime.now().strftime(date_format)

        template = self.config.get(
            "stability_file_template",
            "{date}_IV_stability_cell{cell_number}_pixel{pixel_number}.csv"
        )

        return template.format(
            date=date_str,
            cell_number=cell_number,
            pixel_number=pixel_number,
        )
