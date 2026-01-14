"""
Unit tests for data export functionality.

Tests CSV export, JV data export, and EQE data saving.
"""

import pytest
import tempfile
import os
import csv
from pathlib import Path
from datetime import datetime

from common.utils.data_export import CSVExporter, DataExportError
from jv.utils.data_export import JVDataExporter
from jv.models.jv_measurement import JVMeasurementResult, SweepData


class TestCSVExporter:
    """Tests for the common CSVExporter class."""

    @pytest.fixture
    def exporter(self):
        """Create CSV exporter with default settings."""
        return CSVExporter()

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for test files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    def test_generate_timestamp_format(self):
        """Timestamp should be in YYYY_MM_DD format."""
        timestamp = CSVExporter.generate_timestamp()

        # Should match format
        assert len(timestamp) == 10  # YYYY_MM_DD
        parts = timestamp.split('_')
        assert len(parts) == 3
        assert len(parts[0]) == 4  # Year
        assert len(parts[1]) == 2  # Month
        assert len(parts[2]) == 2  # Day

    def test_ensure_directory_creates_path(self, temp_dir):
        """ensure_directory should create missing directories."""
        new_dir = os.path.join(temp_dir, "nested", "path")
        file_path = os.path.join(new_dir, "test.csv")

        result = CSVExporter.ensure_directory(file_path)

        assert os.path.isdir(new_dir)
        assert result == Path(file_path)

    def test_export_basic_data(self, exporter, temp_dir):
        """Should export basic column data to CSV."""
        file_path = os.path.join(temp_dir, "test.csv")
        data = {
            "X": [1.0, 2.0, 3.0],
            "Y": [10.0, 20.0, 30.0]
        }

        exporter.export(file_path, data)

        assert os.path.exists(file_path)

        with open(file_path, 'r') as f:
            reader = csv.reader(f)
            rows = list(reader)

        assert rows[0] == ["X", "Y"]
        assert rows[1] == ["1.0", "10.0"]
        assert rows[2] == ["2.0", "20.0"]
        assert rows[3] == ["3.0", "30.0"]

    def test_export_with_custom_headers(self, exporter, temp_dir):
        """Should use custom headers when provided."""
        file_path = os.path.join(temp_dir, "test.csv")
        data = {
            "col1": [1.0, 2.0],
            "col2": [3.0, 4.0]
        }

        exporter.export(file_path, data, headers=["col1", "col2"])

        with open(file_path, 'r') as f:
            reader = csv.reader(f)
            header = next(reader)

        assert header == ["col1", "col2"]

    def test_export_respects_precision(self, temp_dir):
        """Should round floats to specified precision."""
        exporter = CSVExporter(precision=2)
        file_path = os.path.join(temp_dir, "test.csv")
        data = {
            "Value": [1.23456789, 2.987654321]
        }

        exporter.export(file_path, data)

        with open(file_path, 'r') as f:
            reader = csv.reader(f)
            next(reader)  # Skip header
            rows = list(reader)

        assert rows[0] == ["1.23"]
        assert rows[1] == ["2.99"]

    def test_export_xy_data(self, exporter, temp_dir):
        """Should export X-Y data with custom headers."""
        file_path = os.path.join(temp_dir, "xy.csv")

        exporter.export_xy_data(
            file_path,
            x_data=[400, 500, 600],
            y_data=[1.0, 2.0, 1.5],
            x_header="Wavelength (nm)",
            y_header="Power (mW)"
        )

        with open(file_path, 'r') as f:
            reader = csv.reader(f)
            header = next(reader)
            rows = list(reader)

        assert header == ["Wavelength (nm)", "Power (mW)"]
        assert len(rows) == 3

    def test_load_xy_data(self, exporter, temp_dir):
        """Should load X-Y data from CSV."""
        file_path = os.path.join(temp_dir, "xy.csv")

        # Write test data
        exporter.export_xy_data(
            file_path,
            x_data=[1.0, 2.0, 3.0],
            y_data=[10.0, 20.0, 30.0]
        )

        # Load it back
        x_data, y_data = exporter.load_xy_data(file_path)

        assert x_data == [1.0, 2.0, 3.0]
        assert y_data == [10.0, 20.0, 30.0]

    def test_export_error_on_invalid_path(self, exporter):
        """Should raise DataExportError on invalid path."""
        # Use a path that can't be written (e.g., read-only or invalid chars)
        if os.name == 'nt':  # Windows
            invalid_path = "Z:\\nonexistent\\drive\\file.csv"
        else:
            invalid_path = "/root/no_permission/file.csv"

        with pytest.raises(DataExportError):
            exporter.export(invalid_path, {"X": [1, 2, 3]})


class TestJVDataExporter:
    """Tests for JV-specific data export."""

    @pytest.fixture
    def exporter(self):
        """Create JV data exporter."""
        return JVDataExporter()

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for test files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.fixture
    def sample_result(self):
        """Create a sample JV measurement result."""
        result = JVMeasurementResult()
        result.pixel_number = 3

        # Add forward sweep data
        for v in [0.0, 0.1, 0.2, 0.3, 0.4, 0.5]:
            current = 35.0 - v * 50  # Decreasing current
            result.forward.add_point(v, current)

        # Add reverse sweep data
        for v in [0.5, 0.4, 0.3, 0.2, 0.1, 0.0]:
            current = 35.0 - v * 50 + 0.5  # Slightly higher (hysteresis)
            result.reverse.add_point(v, current)

        result.measurement_complete = True
        return result

    def test_generate_filename_format(self, exporter):
        """Filename should include date, cell, and pixel."""
        filename = exporter.generate_filename(cell_number="195", pixel_number=3)

        # Should have today's date
        today = datetime.now().strftime("%Y_%m_%d")
        assert today in filename
        assert "195" in filename
        assert "3" in filename
        assert filename.endswith(".csv")

    def test_save_measurement(self, exporter, sample_result, temp_dir):
        """Should save measurement result to CSV."""
        file_path = os.path.join(temp_dir, "jv_test.csv")

        exporter.save_measurement(sample_result, file_path)

        assert os.path.exists(file_path)

        with open(file_path, 'r') as f:
            reader = csv.reader(f)
            header = next(reader)
            rows = list(reader)

        # Should have 3 columns
        assert len(header) == 3
        assert "Voltage" in header[0]
        assert "Forward" in header[1]
        assert "Reverse" in header[2]

        # Should have rows (grouped by voltage)
        assert len(rows) >= 1

    def test_save_measurement_raw(self, exporter, sample_result, temp_dir):
        """Should save raw sequential data."""
        file_path = os.path.join(temp_dir, "jv_raw.csv")

        exporter.save_measurement_raw(sample_result, file_path)

        assert os.path.exists(file_path)

        with open(file_path, 'r') as f:
            reader = csv.reader(f)
            header = next(reader)
            rows = list(reader)

        # Should have direction column
        assert "Direction" in header

        # Should have all data points
        expected_rows = len(sample_result.forward.voltages) + len(sample_result.reverse.voltages)
        assert len(rows) == expected_rows

        # Check direction values
        directions = [row[-1] for row in rows]
        assert "forward" in directions
        assert "reverse" in directions

    def test_result_to_dataframe(self, exporter, sample_result):
        """Should convert result to DataFrame."""
        df = exporter.result_to_dataframe(sample_result)

        # Should have 3 columns
        assert len(df.columns) == 3

        # Should have voltage sorted
        voltage_col = df.columns[0]
        voltages = df[voltage_col].tolist()
        assert voltages == sorted(voltages)


class TestEQEDataHandlerSave:
    """Tests for EQE data handler save methods."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for test files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    def test_save_power_measurement(self, temp_dir):
        """Should save power measurement data."""
        from eqe.utils.data_handling import DataHandler

        file_path = os.path.join(temp_dir, "power.csv")
        wavelengths = [400.0, 500.0, 600.0, 700.0]
        powers = [1e-3, 2e-3, 1.5e-3, 0.8e-3]

        DataHandler.save_measurement_data(
            file_path=file_path,
            wavelengths=wavelengths,
            measurements=powers,
            measurement_type="power"
        )

        assert os.path.exists(file_path)

        with open(file_path, 'r') as f:
            reader = csv.reader(f)
            header = next(reader)
            rows = list(reader)

        assert "Wavelength" in header[0]
        assert len(rows) == 4

    def test_save_current_measurement(self, temp_dir):
        """Should save current measurement data."""
        from eqe.utils.data_handling import DataHandler

        file_path = os.path.join(temp_dir, "current.csv")
        wavelengths = [400.0, 500.0, 600.0]
        currents = [1e-7, 5e-7, 3e-7]

        DataHandler.save_measurement_data(
            file_path=file_path,
            wavelengths=wavelengths,
            measurements=currents,
            measurement_type="current"
        )

        assert os.path.exists(file_path)

        with open(file_path, 'r') as f:
            reader = csv.reader(f)
            header = next(reader)
            rows = list(reader)

        assert len(rows) == 3

    def test_save_current_with_stats(self, temp_dir):
        """Should save current measurement with statistics (n, std_dev)."""
        from eqe.utils.data_handling import DataHandler
        from unittest.mock import patch

        file_path = os.path.join(temp_dir, "current_stats.csv")
        wavelengths = [400.0, 500.0]
        currents = [1e-7, 5e-7]
        stats = [
            {'std_dev': 1e-9, 'n': 10},
            {'std_dev': 2e-9, 'n': 10},
        ]

        # Enable stats export
        with patch.dict('eqe.utils.data_handling.DATA_EXPORT_CONFIG', {
            'include_measurement_stats': True,
            'headers': {
                'current_with_stats': [
                    "Wavelength (nm)", "Current_mean (nA)",
                    "Current_std (nA)", "n"
                ]
            },
            'csv_delimiter': ',',
            'precision': 6
        }):
            DataHandler.save_measurement_data(
                file_path=file_path,
                wavelengths=wavelengths,
                measurements=currents,
                measurement_type="current",
                measurement_stats=stats
            )

        assert os.path.exists(file_path)

        with open(file_path, 'r') as f:
            reader = csv.reader(f)
            header = next(reader)
            rows = list(reader)

        # Should have stats columns: wavelength, current, std, n
        assert len(header) == 4
        assert header == ["Wavelength (nm)", "Current_mean (nA)",
                          "Current_std (nA)", "n"]
        assert len(rows) == 2

        # Verify std_dev is correctly converted to nA
        # First row: std=1e-9 A = 1 nA
        row1 = rows[0]
        std_value = float(row1[2])
        assert abs(std_value - 1.0) < 0.01  # 1 nA


class TestDataExportRobustness:
    """Tests for edge cases and robustness."""

    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    def test_export_empty_data(self, temp_dir):
        """Should handle empty data gracefully."""
        exporter = CSVExporter()
        file_path = os.path.join(temp_dir, "empty.csv")

        exporter.export(file_path, {"X": [], "Y": []})

        with open(file_path, 'r') as f:
            content = f.read()

        # Should have header but no data rows
        assert "X" in content
        assert content.count('\n') == 1  # Just header

    def test_export_single_row(self, temp_dir):
        """Should handle single row data."""
        exporter = CSVExporter()
        file_path = os.path.join(temp_dir, "single.csv")

        exporter.export(file_path, {"Value": [42.0]})

        with open(file_path, 'r') as f:
            reader = csv.reader(f)
            rows = list(reader)

        assert len(rows) == 2  # Header + 1 row

    def test_export_large_dataset(self, temp_dir):
        """Should handle large datasets efficiently."""
        import numpy as np

        exporter = CSVExporter()
        file_path = os.path.join(temp_dir, "large.csv")

        # 10,000 points
        data = {
            "X": list(np.linspace(0, 1000, 10000)),
            "Y": list(np.random.normal(0, 1, 10000))
        }

        exporter.export(file_path, data)

        with open(file_path, 'r') as f:
            reader = csv.reader(f)
            rows = list(reader)

        assert len(rows) == 10001  # Header + 10000 rows

    def test_export_special_float_values(self, temp_dir):
        """Should handle special float values."""
        import numpy as np

        exporter = CSVExporter()
        file_path = os.path.join(temp_dir, "special.csv")

        # Very small and very large values
        data = {
            "Small": [1e-15, 2e-15, 3e-15],
            "Large": [1e15, 2e15, 3e15]
        }

        exporter.export(file_path, data)

        # Should not raise
        x, y = exporter.load_xy_data(file_path)
        assert len(x) == 3

    def test_jv_export_with_empty_sweeps(self, temp_dir):
        """Should handle JV result with empty sweeps."""
        exporter = JVDataExporter()
        file_path = os.path.join(temp_dir, "empty_sweeps.csv")

        result = JVMeasurementResult()
        # Only forward data, no reverse
        result.forward.add_point(0.0, 35.0)
        result.forward.add_point(0.5, 10.0)

        exporter.save_measurement(result, file_path)

        assert os.path.exists(file_path)

