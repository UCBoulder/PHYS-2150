"""
Unit tests for eqe/utils/data_handling.py

Tests DataHandler validation and filename generation functions.
"""

import pytest
import re
from datetime import datetime

from eqe.utils.data_handling import DataHandler, DataValidationError


class TestValidateCellNumber:
    """Tests for DataHandler.validate_cell_number()"""

    def test_valid_cell_numbers(self):
        """Valid cell numbers (letter + 2 digits) should pass."""
        assert DataHandler.validate_cell_number('A03') is True
        assert DataHandler.validate_cell_number('A23') is True
        assert DataHandler.validate_cell_number('R26') is True
        assert DataHandler.validate_cell_number('R39') is True
        assert DataHandler.validate_cell_number('Z99') is True

    def test_invalid_too_short(self):
        """Cell numbers with wrong format should fail."""
        assert DataHandler.validate_cell_number('A') is False
        assert DataHandler.validate_cell_number('A1') is False
        assert DataHandler.validate_cell_number('') is False

    def test_invalid_too_long(self):
        """Cell numbers with too many characters should fail."""
        assert DataHandler.validate_cell_number('A123') is False
        assert DataHandler.validate_cell_number('AB12') is False

    def test_invalid_format(self):
        """Invalid formats should fail."""
        assert DataHandler.validate_cell_number('123') is False  # Old format
        assert DataHandler.validate_cell_number('1A2') is False
        assert DataHandler.validate_cell_number('a03') is False  # Lowercase
        assert DataHandler.validate_cell_number('A.3') is False

    def test_invalid_with_spaces(self):
        """Strings with spaces should fail."""
        assert DataHandler.validate_cell_number(' A03') is False
        assert DataHandler.validate_cell_number('A03 ') is False
        assert DataHandler.validate_cell_number('A 3') is False


class TestValidatePixelNumber:
    """Tests for DataHandler.validate_pixel_number()"""

    def test_valid_pixel_numbers(self):
        """Pixel numbers 1-8 should pass."""
        for pixel in range(1, 9):
            assert DataHandler.validate_pixel_number(pixel) is True

    def test_invalid_pixel_zero(self):
        """Pixel 0 should fail."""
        assert DataHandler.validate_pixel_number(0) is False

    def test_invalid_pixel_negative(self):
        """Negative pixel numbers should fail."""
        assert DataHandler.validate_pixel_number(-1) is False

    def test_invalid_pixel_too_high(self):
        """Pixel numbers above 8 should fail."""
        assert DataHandler.validate_pixel_number(9) is False
        assert DataHandler.validate_pixel_number(10) is False
        assert DataHandler.validate_pixel_number(100) is False


class TestGenerateFilename:
    """Tests for DataHandler.generate_filename()"""

    def test_power_filename_format(self):
        """Power filename should follow template."""
        filename = DataHandler.generate_filename('power', 'A03')

        # Should contain date, type, and cell number
        assert 'power' in filename
        assert 'A03' in filename
        assert filename.endswith('.csv')

        # Date should be in YYYY_MM_DD format
        date_pattern = r'\d{4}_\d{2}_\d{2}'
        assert re.search(date_pattern, filename)

    def test_current_filename_format(self):
        """Current filename should include pixel number."""
        filename = DataHandler.generate_filename('current', 'A03', pixel_number=3)

        assert 'current' in filename
        assert 'A03' in filename
        assert '3' in filename
        assert filename.endswith('.csv')

    def test_phase_filename_format(self):
        """Phase filename should follow template."""
        filename = DataHandler.generate_filename('phase', 'A03')

        assert 'phase' in filename
        assert 'A03' in filename
        assert filename.endswith('.csv')

    def test_current_requires_pixel(self):
        """Current measurement type requires pixel number."""
        with pytest.raises(DataValidationError, match="Pixel number required"):
            DataHandler.generate_filename('current', 'A03')

    def test_invalid_cell_number_raises(self):
        """Invalid cell number should raise DataValidationError."""
        with pytest.raises(DataValidationError):
            DataHandler.generate_filename('power', '12')  # Too short

        with pytest.raises(DataValidationError):
            DataHandler.generate_filename('power', 'abc')  # Non-numeric

    def test_invalid_pixel_number_raises(self):
        """Invalid pixel number should raise DataValidationError."""
        with pytest.raises(DataValidationError):
            DataHandler.generate_filename('current', 'A03', pixel_number=0)

        with pytest.raises(DataValidationError):
            DataHandler.generate_filename('current', 'A03', pixel_number=9)

    def test_unknown_measurement_type_raises(self):
        """Unknown measurement type should raise DataValidationError."""
        with pytest.raises(DataValidationError, match="Unknown measurement type"):
            DataHandler.generate_filename('unknown', 'A03')

    def test_filename_uses_current_date(self):
        """Filename should use current date."""
        filename = DataHandler.generate_filename('power', 'A03')
        today = datetime.now().strftime('%Y_%m_%d')
        assert today in filename
