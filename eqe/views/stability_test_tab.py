"""
Stability Test Tab View

This module contains the stability test tab for testing power and current
measurement stability over time.
"""

import datetime
import csv
from pathlib import Path
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel,
    QLineEdit, QRadioButton, QPushButton, QMessageBox, QFileDialog, QApplication
)
from PySide6.QtCore import Signal, Qt, QTimer, Slot
from typing import List, Optional
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import numpy as np

from ..models.stability_test import StabilityTestModel


class StabilityTestTab(QWidget):
    """
    Stability test tab for testing measurement stability.
    
    Provides UI for configuring and running power/current stability tests
    with real-time plotting and statistics.
    """
    
    # Signals
    test_started = Signal(str)  # test_type
    test_completed = Signal()
    
    # Internal signals for thread-safe UI updates from Python threads
    _measurement_signal = Signal(float, float)  # time, value
    _status_signal = Signal(str)  # status message
    _error_signal = Signal(str)  # error message
    _complete_signal = Signal()  # test complete
    
    def __init__(self, stability_model: Optional[StabilityTestModel] = None):
        """
        Initialize the stability test tab.
        
        Args:
            stability_model: Stability test model instance
        """
        super().__init__()
        
        self.stability_model = stability_model
        
        # Connect internal signals to slots (for thread-safe updates)
        self._measurement_signal.connect(self._on_measurement_update)
        self._status_signal.connect(self._on_status_update)
        self._error_signal.connect(self._on_test_error)
        self._complete_signal.connect(self._on_test_complete)
        
        # Data storage
        self.timestamps: List[float] = []
        self.values: List[float] = []
        self.test_type: Optional[str] = None
        self.wavelength: float = 550.0
        
        # Create UI components
        self._create_widgets()
        self._setup_layout()
        self._connect_signals()
        
        # Set default values
        self._set_defaults()
    
    def set_stability_model(self, model: StabilityTestModel) -> None:
        """
        Set the stability test model.
        
        Args:
            model: Stability test model instance
        """
        self.stability_model = model
        
        # Set up callbacks (not Qt signals - using regular Python callbacks)
        if model:
            model.set_measurement_callback(self._on_measurement_update_threadsafe)
            model.set_completion_callback(self._on_test_complete_threadsafe)
            model.set_error_callback(self._on_test_error_threadsafe)
            model.set_status_callback(self._on_status_update_threadsafe)
    
    def _create_widgets(self) -> None:
        """Create all UI widgets."""
        # Test configuration group
        self.config_group = QGroupBox("Test Configuration")
        
        # Test type radio buttons
        self.power_radio = QRadioButton("Power Test")
        self.current_radio = QRadioButton("Current Test")
        self.current_radio.setChecked(True)  # Default
        
        # Parameter inputs
        self.wavelength_input = QLineEdit()
        self.wavelength_input.setPlaceholderText("550")
        self.wavelength_input.setMaximumWidth(100)
        
        self.duration_input = QLineEdit()
        self.duration_input.setPlaceholderText("5")
        self.duration_input.setMaximumWidth(100)
        
        self.interval_input = QLineEdit()
        self.interval_input.setPlaceholderText("2")
        self.interval_input.setMaximumWidth(100)
        
        self.pixel_label = QLabel("Pixel #:")
        self.pixel_input = QLineEdit()
        self.pixel_input.setPlaceholderText("1")
        self.pixel_input.setMaximumWidth(100)
        
        # Control buttons
        self.start_button = QPushButton("Start Test")
        self.start_button.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        self.start_button.setMaximumWidth(150)
        
        self.stop_button = QPushButton("Stop Test")
        self.stop_button.setStyleSheet("background-color: #f44336; color: white; font-weight: bold;")
        self.stop_button.setMaximumWidth(150)
        self.stop_button.setEnabled(False)
        
        self.save_button = QPushButton("Save Results")
        self.save_button.setMaximumWidth(150)
        self.save_button.setEnabled(False)
        
        # Status label
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("font-weight: bold; color: #555;")
        
        # Statistics display
        self.stats_group = QGroupBox("Statistics")
        self.mean_label = QLabel("Mean: -")
        self.std_label = QLabel("Std Dev: -")
        self.cv_label = QLabel("CV: -")
        self.cv_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        self.count_label = QLabel("Count: 0")
        self.range_label = QLabel("Range: -")
        
        # Plot canvas
        self.figure = Figure(figsize=(10, 6))
        self.canvas = FigureCanvas(self.figure)
        # Prevent canvas from capturing focus - allows buttons to receive clicks
        self.canvas.setFocusPolicy(Qt.NoFocus)
        self.ax_time = self.figure.add_subplot(121)
        self.ax_hist = self.figure.add_subplot(122)
        
        # Initialize empty plot
        self._clear_plot()
    
    def _setup_layout(self) -> None:
        """Set up the tab layout."""
        main_layout = QVBoxLayout()
        
        # Configuration group layout
        config_layout = QVBoxLayout()
        
        # Test type row
        type_row = QHBoxLayout()
        type_row.addWidget(QLabel("Test Type:"))
        type_row.addWidget(self.power_radio)
        type_row.addWidget(self.current_radio)
        type_row.addStretch()
        config_layout.addLayout(type_row)
        
        # Parameters row
        params_row = QHBoxLayout()
        params_row.addWidget(QLabel("Wavelength (nm):"))
        params_row.addWidget(self.wavelength_input)
        params_row.addSpacing(20)
        params_row.addWidget(QLabel("Duration (min):"))
        params_row.addWidget(self.duration_input)
        params_row.addSpacing(20)
        params_row.addWidget(QLabel("Interval (s):"))
        params_row.addWidget(self.interval_input)
        params_row.addSpacing(20)
        params_row.addWidget(self.pixel_label)
        params_row.addWidget(self.pixel_input)
        params_row.addStretch()
        config_layout.addLayout(params_row)
        
        # Control buttons row
        button_row = QHBoxLayout()
        button_row.addWidget(self.start_button)
        button_row.addWidget(self.stop_button)
        button_row.addWidget(self.save_button)
        button_row.addStretch()
        config_layout.addLayout(button_row)
        
        # Status row
        status_row = QHBoxLayout()
        status_row.addWidget(QLabel("Status:"))
        status_row.addWidget(self.status_label)
        status_row.addStretch()
        config_layout.addLayout(status_row)
        
        self.config_group.setLayout(config_layout)
        main_layout.addWidget(self.config_group)
        
        # Statistics group layout
        stats_layout = QVBoxLayout()
        stats_layout.addWidget(self.mean_label)
        stats_layout.addWidget(self.std_label)
        stats_layout.addWidget(self.cv_label)
        stats_layout.addWidget(self.count_label)
        stats_layout.addWidget(self.range_label)
        self.stats_group.setLayout(stats_layout)
        
        # Plot and stats row
        plot_row = QHBoxLayout()
        plot_row.addWidget(self.canvas, stretch=4)
        plot_row.addWidget(self.stats_group, stretch=1)
        main_layout.addLayout(plot_row)
        
        self.setLayout(main_layout)
    
    def _connect_signals(self) -> None:
        """Connect UI signals."""
        self.start_button.clicked.connect(self._on_start_clicked)
        self.stop_button.clicked.connect(self._on_stop_clicked)
        self.save_button.clicked.connect(self._on_save_clicked)
        
        # Connect radio buttons to update pixel visibility
        self.power_radio.toggled.connect(self._on_test_type_changed)
        self.current_radio.toggled.connect(self._on_test_type_changed)
    
    def _set_defaults(self) -> None:
        """Set default values for inputs."""
        self.wavelength_input.setText("550")
        self.duration_input.setText("5")
        self.interval_input.setText("2")
        self.pixel_input.setText("1")
        
        # Update pixel visibility based on initial test type
        self._on_test_type_changed()
    
    def _on_test_type_changed(self) -> None:
        """Handle test type change (show/hide pixel field)."""
        # Show pixel field only for current tests
        is_current_test = self.current_radio.isChecked()
        self.pixel_label.setVisible(is_current_test)
        self.pixel_input.setVisible(is_current_test)

    def _set_inputs_enabled(self, enabled: bool) -> None:
        """Enable or disable all input widgets (but not control buttons)."""
        self.power_radio.setEnabled(enabled)
        self.current_radio.setEnabled(enabled)
        self.wavelength_input.setEnabled(enabled)
        self.duration_input.setEnabled(enabled)
        self.interval_input.setEnabled(enabled)
        self.pixel_input.setEnabled(enabled)
    
    def _on_start_clicked(self) -> None:
        """Handle start button click."""
        if not self.stability_model:
            QMessageBox.warning(self, "Error", "Stability model not initialized. Please wait for device initialization to complete.")
            return
        
        # Get parameters
        try:
            wavelength = float(self.wavelength_input.text())
            duration = float(self.duration_input.text())
            interval = float(self.interval_input.text())
            pixel_number = int(self.pixel_input.text())
        except ValueError:
            QMessageBox.warning(self, "Invalid Input", 
                              "Please enter valid numeric values")
            return
        
        # Validate
        if wavelength <= 0 or duration <= 0 or interval <= 0:
            QMessageBox.warning(self, "Invalid Input",
                              "Values must be positive")
            return
        
        # Clear previous data
        self.timestamps = []
        self.values = []
        self._clear_plot()
        self._update_statistics()
        
        # Determine test type
        if self.power_radio.isChecked():
            self.test_type = "power"
        else:
            self.test_type = "current"
        
        self.wavelength = wavelength
        
        # Update UI state
        # Disable individual input widgets instead of config_group
        # (disabling config_group would also disable the stop button!)
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.save_button.setEnabled(False)
        self._set_inputs_enabled(False)
        
        # Start test
        self.test_started.emit(self.test_type)

        if self.test_type == "power":
            self.stability_model.start_power_test(wavelength, duration, interval)
        else:
            self.stability_model.start_current_test(wavelength, duration, interval, pixel_number)
    
    def _on_stop_clicked(self) -> None:
        """Handle stop button click."""
        if self.stability_model:
            self.stability_model.stop_test()
        self.stop_button.setEnabled(False)
    
    def _on_save_clicked(self) -> None:
        """Handle save button click."""
        if not self.timestamps or not self.values:
            QMessageBox.warning(self, "No Data", "No test data to save")
            return
        
        # Create default filename
        date_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        default_filename = f"stability_test_{self.test_type}_{self.wavelength:.0f}nm_{date_str}.csv"
        
        # Get save location
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Save Test Results",
            str(Path("stability_tests") / default_filename),
            "CSV Files (*.csv)"
        )
        
        if filename:
            self._save_results(filename)
            QMessageBox.information(self, "Saved", f"Results saved to:\n{filename}")
    
    # Thread-safe callback wrappers (called from worker thread)
    # These emit Qt signals which are automatically queued to the main thread
    def _on_measurement_update_threadsafe(self, timestamp: float, value: float) -> None:
        """Thread-safe wrapper for measurement updates - emits signal."""
        self._measurement_signal.emit(timestamp, value)
    
    def _on_test_complete_threadsafe(self, timestamps: List[float], values: List[float]) -> None:
        """Thread-safe wrapper for test completion - emits signal."""
        # Store data as instance variables since we can't pass lists through signals
        self.timestamps = timestamps
        self.values = values
        self._complete_signal.emit()
    
    def _on_test_error_threadsafe(self, error_message: str) -> None:
        """Thread-safe wrapper for errors - emits signal."""
        self._error_signal.emit(error_message)
    
    def _on_status_update_threadsafe(self, status: str) -> None:
        """Thread-safe wrapper for status updates - emits signal."""
        self._status_signal.emit(status)
    
    # UI update methods (called on main thread via Qt signals)
    @Slot(float, float)
    def _on_measurement_update(self, timestamp: float, value: float) -> None:
        """
        Handle measurement update from model.
        
        Args:
            timestamp: Time since test start (seconds)
            value: Measured value
        """
        self.timestamps.append(timestamp)
        self.values.append(value)

        # Update plot and statistics
        self._update_plot()
        self._update_statistics()
    
    @Slot()
    def _on_test_complete(self) -> None:
        """
        Handle test completion.
        
        Note: timestamps and values are already stored as instance variables
        by the threadsafe wrapper before this signal is emitted.
        """
        # Update UI state
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.save_button.setEnabled(True)
        self._set_inputs_enabled(True)
        
        # Final plot update
        self._update_plot()
        self._update_statistics()
        
        # Emit completion signal
        self.test_completed.emit()
        
        # Show completion message
        if self.values:
            stats = StabilityTestModel.calculate_statistics(self.values)
            QMessageBox.information(
                self, "Test Complete",
                f"Test completed with {stats['count']} measurements\n"
                f"CV: {stats['cv_percent']:.2f}%"
            )
    
    @Slot(str)
    def _on_test_error(self, error_message: str) -> None:
        """
        Handle test error.
        
        Args:
            error_message: Error message
        """
        # Update UI state
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self._set_inputs_enabled(True)

        self.status_label.setText(f"Error: {error_message}")
        self.status_label.setStyleSheet("font-weight: bold; color: red;")
        
        QMessageBox.critical(self, "Test Error", error_message)
    
    @Slot(str)
    def _on_status_update(self, status: str) -> None:
        """
        Handle status update.
        
        Args:
            status: Status message
        """
        self.status_label.setText(status)
        self.status_label.setStyleSheet("font-weight: bold; color: #555;")
    
    def _clear_plot(self) -> None:
        """Clear the plot."""
        self.ax_time.clear()
        self.ax_hist.clear()
        
        # Set up time series plot
        self.ax_time.set_xlabel('Time (s)')
        if self.test_type == "power":
            self.ax_time.set_ylabel('Power (μW)')
            self.ax_time.set_title('Power vs Time')
        else:
            self.ax_time.set_ylabel('Current (A)')
            self.ax_time.set_title('Current vs Time')
        self.ax_time.grid(True, alpha=0.3)
        
        # Set up histogram
        self.ax_hist.set_xlabel('Value')
        self.ax_hist.set_ylabel('Frequency')
        self.ax_hist.set_title('Distribution')
        
        self.figure.tight_layout()
        self.canvas.draw_idle()
        self.canvas.flush_events()
    
    def _update_plot(self) -> None:
        """Update the plot with current data."""
        if not self.timestamps or not self.values:
            return
        
        # Clear axes
        self.ax_time.clear()
        self.ax_hist.clear()
        
        # Convert power to μW for display if needed
        if self.test_type == "power":
            display_values = [v * 1e6 for v in self.values]
            ylabel = 'Power (μW)'
            title = 'Power vs Time'
        else:
            display_values = self.values
            ylabel = 'Current (A)'
            title = 'Current vs Time'
        
        # Time series plot
        self.ax_time.plot(self.timestamps, display_values, 'b.-', linewidth=1, markersize=3)
        
        # Add mean and ±1σ bands
        if len(self.values) > 1:
            stats = StabilityTestModel.calculate_statistics(self.values)
            if self.test_type == "power":
                mean_display = stats['mean'] * 1e6
                std_display = stats['std'] * 1e6
            else:
                mean_display = stats['mean']
                std_display = stats['std']
            
            self.ax_time.axhline(mean_display, color='r', linestyle='--', 
                                linewidth=1, label='Mean')
            self.ax_time.axhline(mean_display + std_display, color='orange', 
                                linestyle=':', linewidth=1, label='±1σ')
            self.ax_time.axhline(mean_display - std_display, color='orange', 
                                linestyle=':', linewidth=1)
            self.ax_time.legend()
        
        self.ax_time.set_xlabel('Time (s)')
        self.ax_time.set_ylabel(ylabel)
        self.ax_time.set_title(title)
        self.ax_time.grid(True, alpha=0.3)
        
        # Histogram
        if len(display_values) > 1:
            self.ax_hist.hist(display_values, bins=min(20, len(display_values)//2 or 1),
                            color='skyblue', edgecolor='black', alpha=0.7)
            self.ax_hist.set_xlabel('Value')
            self.ax_hist.set_ylabel('Frequency')
            self.ax_hist.set_title('Distribution')
        
        self.figure.tight_layout()
        self.canvas.draw_idle()
        self.canvas.flush_events()

    def _update_statistics(self) -> None:
        """Update the statistics display."""
        if not self.values:
            self.mean_label.setText("Mean: -")
            self.std_label.setText("Std Dev: -")
            self.cv_label.setText("CV: -")
            self.count_label.setText("Count: 0")
            self.range_label.setText("Range: -")
            return
        
        stats = StabilityTestModel.calculate_statistics(self.values)
        
        # Format based on test type
        if self.test_type == "power":
            mean_str = f"{stats['mean']*1e6:.3f} μW"
            std_str = f"{stats['std']*1e6:.3f} μW"
            range_str = f"{stats['range']*1e6:.3f} μW"
        else:
            mean_str = f"{stats['mean']:.6e} A"
            std_str = f"{stats['std']:.6e} A"
            range_str = f"{stats['range']:.6e} A"
        
        self.mean_label.setText(f"Mean: {mean_str}")
        self.std_label.setText(f"Std Dev: {std_str}")
        self.cv_label.setText(f"CV: {stats['cv_percent']:.2f}%")
        self.count_label.setText(f"Count: {stats['count']}")
        self.range_label.setText(f"Range: {range_str}")
        
        # Color code CV
        cv = stats['cv_percent']
        if cv < 1.0:
            color = "green"
        elif cv < 3.0:
            color = "orange"
        else:
            color = "red"
        self.cv_label.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {color};")
    
    def _save_results(self, filename: str) -> None:
        """
        Save results to CSV file.
        
        Args:
            filename: Output file path
        """
        # Ensure directory exists
        filepath = Path(filename)
        filepath.parent.mkdir(parents=True, exist_ok=True)
        
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            
            # Write header with metadata
            writer.writerow([f"# Stability Test - {self.test_type.capitalize()}"])
            writer.writerow([f"# Wavelength: {self.wavelength} nm"])
            writer.writerow([f"# Date: {datetime.datetime.now().isoformat()}"])
            writer.writerow([f"# Number of measurements: {len(self.values)}"])
            
            if self.values:
                stats = StabilityTestModel.calculate_statistics(self.values)
                writer.writerow([f"# Mean: {stats['mean']:.6e}"])
                writer.writerow([f"# Std Dev: {stats['std']:.6e}"])
                writer.writerow([f"# CV: {stats['cv_percent']:.2f}%"])
            
            writer.writerow([])  # Blank line
            
            # Write data
            if self.test_type == "power":
                writer.writerow(["Time (s)", "Power (W)", "Power (μW)"])
                for t, v in zip(self.timestamps, self.values):
                    writer.writerow([f"{t:.1f}", f"{v:.6e}", f"{v*1e6:.3f}"])
            else:
                writer.writerow(["Time (s)", "Current (A)"])
                for t, v in zip(self.timestamps, self.values):
                    writer.writerow([f"{t:.1f}", f"{v:.6e}"])
        
        # Also save plot
        plot_filename = filepath.with_suffix('.png')
        self.figure.savefig(plot_filename, dpi=150, bbox_inches='tight')
