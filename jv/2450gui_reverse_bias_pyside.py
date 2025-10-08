import sys
import threading
import time
import numpy as np
import pandas as pd
import pyvisa as visa
import matplotlib
matplotlib.use('QtAgg')  # Explicitly set Qt6 backend for PySide6
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavigationToolbar
from decimal import Decimal, ROUND_HALF_UP
import datetime
import re
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLineEdit, QLabel, QMessageBox, QFileDialog, QInputDialog,
    QGridLayout, QSpacerItem, QSizePolicy
)
from PySide6.QtCore import Qt, QTimer, Signal, QObject
from PySide6.QtGui import QScreen

# Initialize the VISA resource manager
rm = visa.ResourceManager()

# Initialize lists to store the measurements for plotting
voltages_plot = []
currents_plot = []

# Set up variables for threading and closing the application
stop_thread = threading.Event()
lock = threading.Lock()
is_closing = False

# Signal emitter for thread-safe file saving
class SignalEmitter(QObject):
    save_file_dialog = Signal(str, str, pd.DataFrame)  # For J-V data

signal_emitter = SignalEmitter()

# Search for the device
device_address = None
for resource in rm.list_resources():
    if resource.startswith("USB0::0x05E6::0x2450"):
        device_address = resource
        print(f"Keithley 2450 found at {device_address}")
        device = rm.open_resource(device_address)
        device.timeout = 30000  # Set timeout to 30 seconds
        break

# Exit the application if the device is not found
if not device_address:
    app = QApplication(sys.argv)
    QMessageBox.critical(None, "Error", "Keithley 2450 device not found. Please connect and power on the device and try again.")
    sys.exit(1)

# Function to perform the measurement and update the plot
def perform_measurement(pixel_number):
    global combined_data
    clear_plot(pixel_number)
    print("Starting measurement...")

    try:
        start_voltage = float(start_voltage_var.text())
        stop_voltage = float(stop_voltage_var.text())
        step_voltage = float(step_voltage_var.text())
    except ValueError:
        QTimer.singleShot(0, lambda: QMessageBox.critical(None, "Input Error", "Please enter valid numerical values for voltages and step size."))
        QTimer.singleShot(0, reset_measure_button)
        return

    # Ensure stop_voltage is inclusive for both forward and backward sweeps
    total_range = stop_voltage - start_voltage
    steps_needed = total_range / step_voltage
    if not steps_needed.is_integer():
        stop_voltage += (step_voltage - (total_range % step_voltage))

    forward_voltages = np.arange(start_voltage, stop_voltage + (step_voltage / 2), step_voltage)
    backward_voltages = np.arange(stop_voltage, start_voltage - (step_voltage / 2), -step_voltage)

    forward_voltages = np.round(forward_voltages, decimals=2)
    backward_voltages = np.round(backward_voltages, decimals=2)

    device.write("*RST")
    device.write("SENS:FUNC \"CURR\"")
    device.write("SENS:CURR:RANG 10")
    device.write("SENS:CURR:RSEN ON")
    device.write("SOUR:FUNC VOLT")
    device.write("SOUR:VOLT:RANG 2")
    device.write("SOUR:VOLT:ILIM 1")
    device.write("OUTP ON")

    fig.tight_layout()
    canvas.draw()
    QApplication.processEvents()

    forward_voltages_plot = []
    forward_currents_plot = []
    backward_voltages_plot = []
    backward_currents_plot = []

    forward_line, = ax.plot([], [], '.', label="Forward Scan", color='#0077BB')
    ax.legend(fontsize=10)

    device.write(f"SOUR:VOLT {start_voltage}")
    time.sleep(2)

    # Forward sweep
    for i, voltage in enumerate(forward_voltages):
        if stop_thread.is_set():
            break
        if is_closing:
            print("Measurement interrupted due to application closing.")
            return
        try:
            device.write(f"SOUR:VOLT {voltage}")
            time.sleep(0.5)
            current_reading = device.query("MEAS:CURR?")
            current_reading = Decimal(current_reading)
            forward_voltages_plot.append(voltage)
            forward_current = (current_reading * Decimal(10**3)).quantize(Decimal('0.00001'), rounding=ROUND_HALF_UP)
            forward_current = float(forward_current)
            forward_currents_plot.append(forward_current)
        except Exception as e:
            print(f"Error during measurement: {e}")
            return

        if i % 10 == 0 or i == len(forward_voltages) - 1:
            with lock:
                forward_line.set_data(forward_voltages_plot, forward_currents_plot)
                ax.relim()
                ax.autoscale_view()
                fig.tight_layout()
                canvas.draw()
                QApplication.processEvents()

    time.sleep(2)

    backward_line, = ax.plot([], [], '.', label="Reverse Scan", color='#EE7733')
    ax.legend(fontsize=10)

    # Backward sweep
    for i, voltage in enumerate(backward_voltages):
        if stop_thread.is_set():
            break
        if is_closing:
            print("Measurement interrupted due to application closing.")
            return
        try:
            device.write(f"SOUR:VOLT {voltage}")
            time.sleep(0.5)
            current_reading = device.query("MEAS:CURR?")
            current_reading = Decimal(current_reading)
            backward_voltages_plot.append(voltage)
            backward_current = (current_reading * Decimal(10**3)).quantize(Decimal('0.00001'), rounding=ROUND_HALF_UP)
            backward_current = float(backward_current)
            backward_currents_plot.append(backward_current)
        except Exception as e:
            print(f"Error during measurement: {e}")
            return

        if i % 10 == 0 or i == len(backward_voltages) - 1:
            with lock:
                backward_line.set_data(backward_voltages_plot, backward_currents_plot)
                ax.relim()
                ax.autoscale_view()
                fig.tight_layout()
                canvas.draw()
                QApplication.processEvents()

    # Combine forward and reverse scan data
    combined_data = pd.DataFrame({
        "Voltage (V)": np.concatenate((forward_voltages_plot, backward_voltages_plot)),
        "Forward Scan (mA)": np.concatenate((forward_currents_plot, [None] * len(backward_currents_plot))),
        "Reverse Scan (mA)": np.concatenate(([None] * len(forward_currents_plot), backward_currents_plot))
    })

    combined_data = combined_data.groupby("Voltage (V)").agg({
        "Forward Scan (mA)": "first",
        "Reverse Scan (mA)": "first"
    }).reset_index()

    try:
        device.write("OUTP OFF")
    except Exception as e:
        print(f"Error disabling output: {e}")

    QTimer.singleShot(0, reset_measure_button)

    if stop_thread.is_set():
        print("Measurement stopped.")
    else:
        print("Measurement complete.")
        cell_number = cell_number_var.text().strip()
        if not cell_number or not re.match(r'^\d{3}$', cell_number):
            QTimer.singleShot(0, lambda: QMessageBox.critical(None, "Input Error", "Invalid cell number format."))
        else:
            date = datetime.datetime.now().strftime("%Y_%m_%d")
            file_name = f"{date}_JV_cell{cell_number}_pixel{pixel_number}.csv"
            # Emit the signal to show the save dialog in the main thread
            signal_emitter.save_file_dialog.emit(file_name, "Save J-V Data", combined_data)

def reset_measure_button():
    measure_button.setText("Start Measurement")
    measure_button.setStyleSheet("background-color: #CCDDAA; color: black;")
    measure_button.clicked.disconnect()
    measure_button.clicked.connect(toggle_measurement)

# Function to start the measurement in a separate thread
def start_measurement_thread(pixel_number):
    stop_thread.clear()
    measure_button.setStyleSheet("background-color: #CCDDAA; color: black;")
    measurement_thread = threading.Thread(target=perform_measurement, args=(pixel_number,))
    measurement_thread.start()

# Function to stop the measurement
def stop_measurement():
    stop_thread.set()

# Function to toggle measurement state with pixel number prompt
def toggle_measurement():
    if measure_button.text() == "Start Measurement":
        # Prompt for pixel number
        pixel_input, ok = QInputDialog.getText(None, "Pixel Selection", "Enter pixel number (1-8):")
        if not ok or not pixel_input:
            return  # User canceled or entered nothing
        try:
            pixel_number = int(pixel_input)
            if pixel_number < 1 or pixel_number > 8:
                QMessageBox.critical(None, "Input Error", "Pixel number must be between 1 and 8.")
                return
        except ValueError:
            QMessageBox.critical(None, "Input Error", "Please enter a valid integer for pixel number.")
            return
        
        start_measurement_thread(pixel_number)
        measure_button.setText("Stop Measurement")
        measure_button.setStyleSheet("background-color: #FFCCCC; color: black;")
        measure_button.clicked.disconnect()
        measure_button.clicked.connect(stop_measurement)
    else:
        stop_measurement()
        measure_button.setText("Start Measurement")
        measure_button.setStyleSheet("background-color: #CCDDAA; color: black;")
        measure_button.clicked.disconnect()
        measure_button.clicked.connect(toggle_measurement)

# Function to configure the plot
def configure_plot(pixel_number):
    ax.set_xlabel('Voltage (V)', fontsize=10)
    ax.set_ylabel('Current (mA)', fontsize=10)
    ax.set_title(f'J-V Characterization of Pixel {pixel_number}', fontsize=10)
    ax.tick_params(axis='both', which='major', labelsize=8)
    fig.tight_layout()
    fig.subplots_adjust(bottom=0.2, left=0.15, right=0.85, top=0.85)

# Function to clear the plot
def clear_plot(pixel_number):
    voltages_plot.clear()
    currents_plot.clear()
    ax.clear()
    configure_plot(pixel_number)
    canvas.draw()

# Main GUI window
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PHYS 2150 J-V Characterization")
        self.setGeometry(100, 100, 800, 600)

        # Main widget and layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout()  # Use QHBoxLayout for two columns
        main_widget.setLayout(main_layout)

        # Column 0: Input fields and Start Measurement button (10% width)
        input_widget = QWidget()
        input_layout = QVBoxLayout()
        input_widget.setLayout(input_layout)

        # Calculate 10% of screen width
        screen = QApplication.primaryScreen()
        screen_width = screen.size().width()
        input_width = int(screen_width * 0.1)  # 10% of screen width
        input_widget.setFixedWidth(input_width)

        # Input fields in a QGridLayout
        input_grid = QGridLayout()
        input_grid.setVerticalSpacing(10)
        input_grid.setHorizontalSpacing(10)

        # Start Voltage
        start_voltage_label = QLabel("Start Voltage:")
        start_voltage_label.setStyleSheet("font-size: 14px;")
        global start_voltage_var
        start_voltage_var = QLineEdit("-0.2")
        start_voltage_var.setStyleSheet("font-size: 14px;")
        start_voltage_var.setFixedHeight(30)
        input_grid.addWidget(start_voltage_label, 0, 0)
        input_grid.addWidget(start_voltage_var, 1, 0)

        # Stop Voltage
        stop_voltage_label = QLabel("Stop Voltage:")
        stop_voltage_label.setStyleSheet("font-size: 14px;")
        global stop_voltage_var
        stop_voltage_var = QLineEdit("1.5")
        stop_voltage_var.setStyleSheet("font-size: 14px;")
        stop_voltage_var.setFixedHeight(30)
        input_grid.addWidget(stop_voltage_label, 2, 0)
        input_grid.addWidget(stop_voltage_var, 3, 0)

        # Step Voltage
        step_voltage_label = QLabel("Step Voltage:")
        step_voltage_label.setStyleSheet("font-size: 14px;")
        global step_voltage_var
        step_voltage_var = QLineEdit("0.02")
        step_voltage_var.setStyleSheet("font-size: 14px;")
        step_voltage_var.setFixedHeight(30)
        input_grid.addWidget(step_voltage_label, 4, 0)
        input_grid.addWidget(step_voltage_var, 5, 0)

        # Spacer between Step Voltage and Cell Number
        spacer1 = QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Fixed)
        input_grid.addItem(spacer1, 6, 0)

        # Cell Number
        cell_number_label = QLabel("Cell Number:")
        cell_number_label.setStyleSheet("font-size: 14px;")
        global cell_number_var
        cell_number_var = QLineEdit("")
        cell_number_var.setStyleSheet("font-size: 14px;")
        cell_number_var.setFixedHeight(30)
        cell_number_var.setReadOnly(True)
        input_grid.addWidget(cell_number_label, 7, 0)
        input_grid.addWidget(cell_number_var, 8, 0)

        # Spacer between Cell Number and Start Measurement button
        spacer2 = QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Fixed)
        input_grid.addItem(spacer2, 9, 0)

        # Start Measurement button
        global measure_button
        measure_button = QPushButton("Start Measurement")
        measure_button.setStyleSheet("font-size: 14px; background-color: #CCDDAA; color: black;")
        measure_button.setFixedHeight(30)
        measure_button.clicked.connect(toggle_measurement)
        input_grid.addWidget(measure_button, 10, 0, alignment=Qt.AlignHCenter)

        input_layout.addLayout(input_grid)
        input_layout.addStretch(1)  # Push inputs to top
        main_layout.addWidget(input_widget)

        # Column 1: Plot (Column 2 in user terminology)
        plot_widget = QWidget()
        plot_layout = QVBoxLayout()
        plot_widget.setLayout(plot_layout)

        global fig, ax, canvas
        fig, ax = plt.subplots(figsize=(14, 14), dpi=100)  # 1.75x larger
        configure_plot(1)  # Default pixel number
        canvas = FigureCanvas(fig)
        canvas.setMinimumSize(525, 525)  # 300*1.75=525
        canvas.setMaximumSize(700, 700)  # 400*1.75=700
        toolbar = NavigationToolbar(canvas, self)
        plot_layout.addWidget(canvas, alignment=Qt.AlignHCenter)
        plot_layout.addWidget(toolbar, alignment=Qt.AlignHCenter)
        plot_layout.addStretch(1)

        main_layout.addWidget(plot_widget)

        # Set stretch factors to control column widths
        main_layout.setStretch(0, 1)  # Input column (fixed width, minimal stretch)
        main_layout.setStretch(1, 9)  # Plot column (expands to fill space)

        # Connect signals
        signal_emitter.save_file_dialog.connect(self.handle_save_file_dialog)

        # Show cell number popup
        QTimer.singleShot(1000, self.show_cell_number_popup)

    def handle_save_file_dialog(self, file_name, dialog_title, combined_data):
        file_path, _ = QFileDialog.getSaveFileName(self, dialog_title, file_name, "CSV files (*.csv)")
        if file_path:
            try:
                combined_data.to_csv(file_path, index=False)
                print(f"Data saved to {file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Save Error", f"Failed to save file: {e}")
        # Always reset the button after the dialog is closed
        reset_measure_button()

    def show_cell_number_popup(self):
        cell_number, ok = QInputDialog.getText(self, "Enter Cell Number",
                                               "Enter Cell Number (e.g., 195):")
        if ok and cell_number and re.match(r'^\d{3}$', cell_number):
            cell_number_var.setText(cell_number)
        else:
            QMessageBox.warning(self, "Invalid Input",
                                "Cell number must be a 3-digit number (e.g., 195).")
            self.show_cell_number_popup()

    def closeEvent(self, event):
        global is_closing
        is_closing = True
        stop_thread.set()
        if 'device' in globals():
            try:
                device.write("OUTP OFF")
                device.close()
            except Exception as e:
                print(f"Error closing device: {e}")
        if 'rm' in globals():
            rm.close()
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.showMaximized()  # Start maximized
    sys.exit(app.exec())