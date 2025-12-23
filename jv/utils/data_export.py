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
            "{date}_JV_cell{cell_number}_pixel{pixel_number}.csv"
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

        The format matches the original application output:
        - Voltage column with all voltage values
        - Forward Scan column with forward currents (None for reverse-only rows)
        - Reverse Scan column with reverse currents (None for forward-only rows)

        After grouping by voltage, forward and reverse values are combined.

        Args:
            result: Measurement result containing forward and reverse sweeps
            file_path: Path to save the CSV file
        """
        headers = self.config.get("headers", {})
        voltage_header = headers.get("voltage", "Voltage (V)")
        forward_header = headers.get("forward_current", "Forward Scan (mA)")
        reverse_header = headers.get("reverse_current", "Reverse Scan (mA)")

        # Build combined data similar to original implementation
        forward_voltages = result.forward.voltages
        forward_currents = result.forward.currents
        reverse_voltages = result.reverse.voltages
        reverse_currents = result.reverse.currents

        # Create DataFrame with both sweeps
        combined_data = pd.DataFrame({
            voltage_header: np.concatenate((forward_voltages, reverse_voltages)),
            forward_header: np.concatenate((
                forward_currents,
                [None] * len(reverse_currents)
            )),
            reverse_header: np.concatenate((
                [None] * len(forward_currents),
                reverse_currents
            )),
        })

        # Group by voltage to combine forward and reverse values
        combined_data = combined_data.groupby(voltage_header).agg({
            forward_header: "first",
            reverse_header: "first",
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
        headers = self.config.get("headers", {})
        voltage_header = headers.get("voltage", "Voltage (V)")

        rows = []

        # Add forward sweep data
        for v, i in zip(result.forward.voltages, result.forward.currents):
            rows.append({
                voltage_header: v,
                "Current (mA)": i,
                "Direction": "forward",
            })

        # Add reverse sweep data
        for v, i in zip(result.reverse.voltages, result.reverse.currents):
            rows.append({
                voltage_header: v,
                "Current (mA)": i,
                "Direction": "reverse",
            })

        df = pd.DataFrame(rows)
        df.to_csv(file_path, index=False)

    def result_to_dataframe(
        self,
        result: JVMeasurementResult,
    ) -> pd.DataFrame:
        """
        Convert measurement result to a pandas DataFrame.

        Args:
            result: Measurement result

        Returns:
            pd.DataFrame: Combined data
        """
        headers = self.config.get("headers", {})
        voltage_header = headers.get("voltage", "Voltage (V)")
        forward_header = headers.get("forward_current", "Forward Scan (mA)")
        reverse_header = headers.get("reverse_current", "Reverse Scan (mA)")

        # Get unique voltages (sorted)
        all_voltages = sorted(set(
            result.forward.voltages + result.reverse.voltages
        ))

        # Create voltage to current mappings
        forward_map = dict(zip(
            result.forward.voltages,
            result.forward.currents
        ))
        reverse_map = dict(zip(
            result.reverse.voltages,
            result.reverse.currents
        ))

        # Build DataFrame
        data = {
            voltage_header: all_voltages,
            forward_header: [forward_map.get(v) for v in all_voltages],
            reverse_header: [reverse_map.get(v) for v in all_voltages],
        }

        return pd.DataFrame(data)
