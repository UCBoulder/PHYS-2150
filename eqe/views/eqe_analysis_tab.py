"""
EQE Analysis Tab View (Staff Mode)

This module contains the hidden EQE analysis tab for staff and TAs to
visualize and validate EQE calculations. Activated via Ctrl+Shift+E.
"""

import csv
from pathlib import Path
from typing import Optional, List, Tuple

import numpy as np
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel,
    QPushButton, QFileDialog, QMessageBox
)
from PySide6.QtCore import Qt
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure


class EQEAnalysisTab(QWidget):
    """
    Hidden EQE analysis tab for staff testing and validation.

    Allows loading power and current data from files or current session,
    calculating EQE, and visualizing results.
    """

    # Physical constants for EQE calculation
    H = 6.62607015e-34   # Planck's constant (J·s)
    C = 2.99792458e8     # Speed of light (m/s)
    Q = 1.602176634e-19  # Electron charge (C)

    def __init__(self, parent: Optional[QWidget] = None):
        """Initialize the EQE analysis tab."""
        super().__init__(parent)

        # Experiment model reference (set externally)
        self.experiment_model = None

        # Data storage
        self.power_wavelengths: Optional[np.ndarray] = None
        self.power_values: Optional[np.ndarray] = None
        self.current_wavelengths: Optional[np.ndarray] = None
        self.current_values: Optional[np.ndarray] = None
        self.eqe_wavelengths: Optional[np.ndarray] = None
        self.eqe_values: Optional[np.ndarray] = None

        # Create UI
        self._create_widgets()
        self._setup_layout()
        self._connect_signals()
        self._update_button_states()

    def set_experiment_model(self, model) -> None:
        """
        Set the experiment model for accessing session data.

        Args:
            model: EQEExperimentModel instance
        """
        self.experiment_model = model
        self._update_button_states()

    def _create_widgets(self) -> None:
        """Create all UI widgets."""
        # Data source group
        self.data_group = QGroupBox("Data Source")

        # Session data button
        self.session_btn = QPushButton("Use Current Session")
        self.session_btn.setToolTip("Load power and current data from the current measurement session")

        # File loading buttons
        self.load_power_btn = QPushButton("Load Power CSV")
        self.power_label = QLabel("No power data loaded")
        self.power_label.setStyleSheet("color: gray;")

        self.load_current_btn = QPushButton("Load Current CSV")
        self.current_label = QLabel("No current data loaded")
        self.current_label.setStyleSheet("color: gray;")

        # Calculate button
        self.calculate_btn = QPushButton("Calculate EQE")
        self.calculate_btn.setEnabled(False)

        # Status label
        self.status_label = QLabel("")

        # Metrics group
        self.metrics_group = QGroupBox("EQE Metrics")
        self.peak_eqe_label = QLabel("Peak EQE: --")
        self.bandgap_label = QLabel("Bandgap edge: --")
        self.points_label = QLabel("Data points: --")

        # Plot
        self.figure = Figure(figsize=(8, 5), dpi=100)
        self.canvas = FigureCanvas(self.figure)
        self.toolbar = NavigationToolbar(self.canvas, self)
        self.ax = self.figure.add_subplot(111)
        self._setup_plot()

    def _setup_plot(self) -> None:
        """Configure the plot appearance."""
        self.ax.set_xlabel("Wavelength (nm)", fontsize=11)
        self.ax.set_ylabel("EQE (%)", fontsize=11)
        self.ax.set_title("External Quantum Efficiency", fontsize=12, fontweight='bold')
        self.ax.grid(True, alpha=0.3)
        self.ax.set_xlim(300, 800)
        self.ax.set_ylim(0, 100)
        self.figure.tight_layout()

    def _setup_layout(self) -> None:
        """Set up the widget layout."""
        main_layout = QVBoxLayout(self)

        # Data source group layout
        data_layout = QVBoxLayout(self.data_group)

        # Session button row
        session_row = QHBoxLayout()
        session_row.addWidget(self.session_btn)
        session_row.addStretch()
        data_layout.addLayout(session_row)

        # Separator
        separator = QLabel("─── OR load from files ───")
        separator.setAlignment(Qt.AlignCenter)
        separator.setStyleSheet("color: gray;")
        data_layout.addWidget(separator)

        # Power file row
        power_row = QHBoxLayout()
        power_row.addWidget(self.load_power_btn)
        power_row.addWidget(self.power_label, 1)
        data_layout.addLayout(power_row)

        # Current file row
        current_row = QHBoxLayout()
        current_row.addWidget(self.load_current_btn)
        current_row.addWidget(self.current_label, 1)
        data_layout.addLayout(current_row)

        main_layout.addWidget(self.data_group)

        # Calculate row
        calc_row = QHBoxLayout()
        calc_row.addWidget(self.calculate_btn)
        calc_row.addWidget(self.status_label, 1)
        main_layout.addLayout(calc_row)

        # Metrics group layout
        metrics_layout = QHBoxLayout(self.metrics_group)
        metrics_layout.addWidget(self.peak_eqe_label)
        metrics_layout.addWidget(self.bandgap_label)
        metrics_layout.addWidget(self.points_label)
        main_layout.addWidget(self.metrics_group)

        # Plot area
        main_layout.addWidget(self.toolbar)
        main_layout.addWidget(self.canvas, 1)

    def _connect_signals(self) -> None:
        """Connect widget signals to slots."""
        self.session_btn.clicked.connect(self._load_from_session)
        self.load_power_btn.clicked.connect(self._load_power_file)
        self.load_current_btn.clicked.connect(self._load_current_file)
        self.calculate_btn.clicked.connect(self._calculate_eqe)

    def _update_button_states(self) -> None:
        """Update button enabled states based on data availability."""
        # Session button enabled if model has data
        session_available = self._session_data_available()
        self.session_btn.setEnabled(session_available)
        if not session_available:
            self.session_btn.setToolTip("No measurement data in current session")
        else:
            self.session_btn.setToolTip("Load power and current data from the current measurement session")

        # Calculate button enabled if both datasets loaded
        has_power = self.power_wavelengths is not None and len(self.power_wavelengths) > 0
        has_current = self.current_wavelengths is not None and len(self.current_wavelengths) > 0
        self.calculate_btn.setEnabled(has_power and has_current)

    def _session_data_available(self) -> bool:
        """Check if session data is available from the experiment model."""
        if not self.experiment_model:
            return False

        try:
            # Check power model
            power_model = self.experiment_model.power_model
            if not power_model or not power_model.wavelengths:
                return False

            # Check current model
            current_model = self.experiment_model.current_model
            if not current_model or not current_model.wavelengths:
                return False

            return True
        except AttributeError:
            return False

    def _load_from_session(self) -> None:
        """Load data from the current measurement session."""
        if not self.experiment_model:
            QMessageBox.warning(self, "Error", "No experiment model available")
            return

        try:
            # Get power data
            power_model = self.experiment_model.power_model
            self.power_wavelengths = np.array(power_model.wavelengths)
            self.power_values = np.array(power_model.powers)
            self.power_label.setText(f"From session ({len(self.power_wavelengths)} points)")
            self.power_label.setStyleSheet("color: green;")

            # Get current data
            current_model = self.experiment_model.current_model
            self.current_wavelengths = np.array(current_model.wavelengths)
            self.current_values = np.array(current_model.currents)
            self.current_label.setText(f"From session ({len(self.current_wavelengths)} points)")
            self.current_label.setStyleSheet("color: green;")

            self.status_label.setText("Session data loaded successfully")
            self._update_button_states()

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load session data: {e}")

    def _load_power_file(self) -> None:
        """Load power data from a CSV file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Load Power Data", "", "CSV files (*.csv);;All files (*)"
        )
        if not file_path:
            return

        try:
            wavelengths, powers = self._read_csv(file_path)
            self.power_wavelengths = wavelengths
            self.power_values = powers

            filename = Path(file_path).name
            self.power_label.setText(f"{filename} ({len(wavelengths)} points)")
            self.power_label.setStyleSheet("color: green;")
            self.status_label.setText(f"Loaded power data from {filename}")
            self._update_button_states()

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load power file: {e}")

    def _load_current_file(self) -> None:
        """Load current data from a CSV file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Load Current Data", "", "CSV files (*.csv);;All files (*)"
        )
        if not file_path:
            return

        try:
            wavelengths, currents = self._read_csv(file_path)
            self.current_wavelengths = wavelengths
            self.current_values = currents

            filename = Path(file_path).name
            self.current_label.setText(f"{filename} ({len(wavelengths)} points)")
            self.current_label.setStyleSheet("color: green;")
            self.status_label.setText(f"Loaded current data from {filename}")
            self._update_button_states()

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load current file: {e}")

    def _read_csv(self, file_path: str) -> Tuple[np.ndarray, np.ndarray]:
        """
        Read wavelength and value data from a CSV file.

        Args:
            file_path: Path to CSV file

        Returns:
            Tuple of (wavelengths, values) arrays
        """
        wavelengths = []
        values = []

        with open(file_path, 'r') as f:
            reader = csv.reader(f)
            header = next(reader)  # Skip header

            for row in reader:
                if len(row) >= 2:
                    wavelengths.append(float(row[0]))
                    values.append(float(row[1]))

        return np.array(wavelengths), np.array(values)

    def _calculate_eqe(self) -> None:
        """Calculate and display EQE from loaded data."""
        if self.power_wavelengths is None or self.current_wavelengths is None:
            QMessageBox.warning(self, "Error", "Please load both power and current data first")
            return

        try:
            # Interpolate to common wavelength grid
            # Use the wavelengths from current measurement as the base
            common_wavelengths = self.current_wavelengths

            # Interpolate power to match current wavelengths
            interpolated_power = np.interp(
                common_wavelengths,
                self.power_wavelengths,
                self.power_values
            )

            # Calculate EQE
            # EQE = (I * h * c) / (q * P * λ)
            wavelengths_m = common_wavelengths * 1e-9  # nm to meters
            eqe = (self.current_values * self.H * self.C) / (self.Q * interpolated_power * wavelengths_m)
            eqe_percent = eqe * 100

            # Store results
            self.eqe_wavelengths = common_wavelengths
            self.eqe_values = eqe_percent

            # Update plot
            self._update_plot()

            # Update metrics
            self._update_metrics()

            self.status_label.setText("EQE calculated successfully")
            self.status_label.setStyleSheet("color: green;")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to calculate EQE: {e}")
            self.status_label.setText(f"Calculation error: {e}")
            self.status_label.setStyleSheet("color: red;")

    def _update_plot(self) -> None:
        """Update the EQE plot with calculated data."""
        self.ax.clear()

        if self.eqe_wavelengths is not None and self.eqe_values is not None:
            self.ax.plot(
                self.eqe_wavelengths,
                self.eqe_values,
                'b-o',
                markersize=4,
                linewidth=1.5,
                label='EQE'
            )

            # Add peak indicator
            peak_idx = np.argmax(self.eqe_values)
            peak_wl = self.eqe_wavelengths[peak_idx]
            peak_eqe = self.eqe_values[peak_idx]
            self.ax.axhline(y=peak_eqe, color='r', linestyle='--', alpha=0.5,
                          label=f'Peak: {peak_eqe:.1f}%')

            # Set axis limits based on data
            wl_margin = (self.eqe_wavelengths[-1] - self.eqe_wavelengths[0]) * 0.05
            self.ax.set_xlim(
                self.eqe_wavelengths[0] - wl_margin,
                self.eqe_wavelengths[-1] + wl_margin
            )

            max_eqe = max(self.eqe_values)
            self.ax.set_ylim(0, max(max_eqe * 1.15, 10))

            self.ax.legend(loc='upper right')

        self.ax.set_xlabel("Wavelength (nm)", fontsize=11)
        self.ax.set_ylabel("EQE (%)", fontsize=11)
        self.ax.set_title("External Quantum Efficiency", fontsize=12, fontweight='bold')
        self.ax.grid(True, alpha=0.3)
        self.figure.tight_layout()
        self.canvas.draw()

    def _update_metrics(self) -> None:
        """Update the metrics display."""
        if self.eqe_values is None:
            return

        # Peak EQE
        peak_idx = np.argmax(self.eqe_values)
        peak_eqe = self.eqe_values[peak_idx]
        peak_wl = self.eqe_wavelengths[peak_idx]
        self.peak_eqe_label.setText(f"Peak EQE: {peak_eqe:.1f}% at {peak_wl:.0f} nm")

        # Bandgap edge (50% of peak from red end)
        half_peak = peak_eqe / 2
        bandgap_wl = None
        for i in range(len(self.eqe_values) - 1, -1, -1):
            if self.eqe_values[i] > half_peak:
                bandgap_wl = self.eqe_wavelengths[i]
                break

        if bandgap_wl:
            bandgap_ev = 1240 / bandgap_wl  # E(eV) = 1240 / λ(nm)
            self.bandgap_label.setText(f"Bandgap edge: ~{bandgap_wl:.0f} nm ({bandgap_ev:.2f} eV)")
        else:
            self.bandgap_label.setText("Bandgap edge: --")

        # Data points
        self.points_label.setText(f"Data points: {len(self.eqe_values)}")

    def clear_data(self) -> None:
        """Clear all loaded data and reset the display."""
        self.power_wavelengths = None
        self.power_values = None
        self.current_wavelengths = None
        self.current_values = None
        self.eqe_wavelengths = None
        self.eqe_values = None

        self.power_label.setText("No power data loaded")
        self.power_label.setStyleSheet("color: gray;")
        self.current_label.setText("No current data loaded")
        self.current_label.setStyleSheet("color: gray;")

        self.peak_eqe_label.setText("Peak EQE: --")
        self.bandgap_label.setText("Bandgap edge: --")
        self.points_label.setText("Data points: --")

        self.status_label.setText("")

        self.ax.clear()
        self._setup_plot()
        self.canvas.draw()

        self._update_button_states()
