"""
Measurement Statistics Widget

Displays real-time measurement statistics to students in a clear, pedagogically
meaningful format. This is CRITICAL for learning objectives around measurement
uncertainty.

Students need to see:
- Mean value with uncertainty
- Number of measurements (n)
- Quality indicator (based on coefficient of variation)
- Wavelength context (when applicable)
"""

from PySide6.QtWidgets import (
    QGroupBox, QVBoxLayout, QHBoxLayout, QLabel
)
from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QFont

from common.utils import MeasurementStats
from ..config.settings import GUI_CONFIG


class MeasurementStatsWidget(QGroupBox):
    """
    Widget displaying real-time measurement statistics.

    Shows students the key statistical information they need:
    - Current measurement value with uncertainty
    - Sample size and outliers
    - Quality assessment (Excellent/Good/Fair/Check)

    This directly supports PHYS 2150 learning objectives about
    measurement distributions and uncertainty.
    """

    def __init__(self, parent=None):
        """Initialize the measurement stats widget."""
        super().__init__("Measurement Statistics", parent)

        self._current_wavelength = None
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the user interface."""
        layout = QVBoxLayout()
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        # Wavelength label (context)
        self.wavelength_label = QLabel("")
        self.wavelength_label.setStyleSheet("font-size: 11px; color: #888;")
        self.wavelength_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.wavelength_label)

        # Main measurement value
        self.value_label = QLabel("--")
        font = QFont()
        font.setPointSize(16)
        font.setBold(True)
        self.value_label.setFont(font)
        self.value_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.value_label)

        # Uncertainty label
        self.uncertainty_label = QLabel("")
        self.uncertainty_label.setStyleSheet("font-size: 11px; color: #aaa;")
        self.uncertainty_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.uncertainty_label)

        # Statistics row (n, outliers, CV)
        stats_row = QHBoxLayout()
        stats_row.setSpacing(16)

        # Measurements count
        self.n_label = QLabel("n: --")
        self.n_label.setStyleSheet("font-size: 10px; color: #888;")
        stats_row.addWidget(self.n_label)

        stats_row.addStretch()

        # Outliers
        self.outliers_label = QLabel("outliers: 0")
        self.outliers_label.setStyleSheet("font-size: 10px; color: #888;")
        stats_row.addWidget(self.outliers_label)

        stats_row.addStretch()

        # CV (coefficient of variation)
        self.cv_label = QLabel("CV: --")
        self.cv_label.setStyleSheet("font-size: 10px; color: #888;")
        stats_row.addWidget(self.cv_label)

        layout.addLayout(stats_row)

        # Quality indicator
        self.quality_label = QLabel("Quality: --")
        self.quality_label.setAlignment(Qt.AlignCenter)
        self.quality_label.setStyleSheet(
            "font-size: 12px; font-weight: bold; padding: 6px; "
            "border-radius: 4px; background-color: #333;"
        )
        layout.addWidget(self.quality_label)

        # Push content to top
        layout.addStretch()

        self.setLayout(layout)

        # Initialize to empty state
        self.clear()

    def set_wavelength(self, wavelength_nm: float) -> None:
        """
        Set the current wavelength context.

        Args:
            wavelength_nm: Current measurement wavelength in nm
        """
        self._current_wavelength = wavelength_nm
        self.wavelength_label.setText(f"at {wavelength_nm:.0f} nm")

    @Slot(object)
    def update_stats(self, stats: MeasurementStats) -> None:
        """
        Update the display with new measurement statistics.

        This is the main method called by the tiered logger when new
        statistics are available.

        Args:
            stats: MeasurementStats object containing measurement data
        """
        # Update wavelength if provided in stats
        if stats.wavelength_nm is not None:
            self.set_wavelength(stats.wavelength_nm)

        # Update main value
        # Format based on magnitude
        if abs(stats.mean) >= 1e-3:
            self.value_label.setText(f"{stats.mean:.4f} {stats.unit}")
        elif abs(stats.mean) >= 1e-6:
            self.value_label.setText(f"{stats.mean*1e6:.2f} \u00b5{stats.unit}")
        else:
            self.value_label.setText(f"{stats.mean*1e9:.2f} n{stats.unit}")

        # Update uncertainty
        if abs(stats.std_dev) >= 1e-3:
            self.uncertainty_label.setText(f"\u00b1 {stats.std_dev:.4f} {stats.unit}")
        elif abs(stats.std_dev) >= 1e-6:
            self.uncertainty_label.setText(f"\u00b1 {stats.std_dev*1e6:.2f} \u00b5{stats.unit}")
        else:
            self.uncertainty_label.setText(f"\u00b1 {stats.std_dev*1e9:.2f} n{stats.unit}")

        # Update statistics
        self.n_label.setText(f"n: {stats.n_measurements}/{stats.n_total}")
        self.outliers_label.setText(f"outliers: {stats.n_outliers}")
        self.cv_label.setText(f"CV: {stats.cv_percent:.1f}%")

        # Update quality indicator with color coding
        quality = stats.quality
        if quality == "Excellent":
            color = "#00aa00"  # Green
        elif quality == "Good":
            color = "#88aa00"  # Yellow-green
        elif quality == "Fair":
            color = "#aaaa00"  # Yellow
        else:
            color = "#aa4400"  # Orange-red

        self.quality_label.setText(f"Quality: {quality}")
        self.quality_label.setStyleSheet(
            f"font-size: 12px; font-weight: bold; padding: 4px; "
            f"border-radius: 4px; background-color: {color}; color: white;"
        )

    def clear(self) -> None:
        """Clear the display to initial state."""
        self._current_wavelength = None
        self.wavelength_label.setText("")
        self.value_label.setText("--")
        self.uncertainty_label.setText("")
        self.n_label.setText("n: --")
        self.outliers_label.setText("outliers: 0")
        self.cv_label.setText("CV: --")
        self.quality_label.setText("Quality: --")
        self.quality_label.setStyleSheet(
            "font-size: 12px; font-weight: bold; padding: 4px; "
            "border-radius: 4px; background-color: #333;"
        )
