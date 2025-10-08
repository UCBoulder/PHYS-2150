import time
import csv
import scipy
from ctypes import c_double, byref, c_uint32, create_string_buffer, c_bool
from cornerstone_mono import Cornerstone_Mono
from TLPMX import TLPMX, TLPM_DEFAULT_CHANNEL
import warnings
import pyvisa as visa
import matplotlib.pyplot as plt
import pandas as pd
import sys
import re
import os
import datetime
import threading
import numpy as np
import serial
import serial.tools.list_ports
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLineEdit, QLabel, QMessageBox, QFileDialog, QInputDialog,
    QGridLayout, QSpacerItem, QSizePolicy
)
from PySide6.QtCore import Qt, QTimer, Signal, QObject
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar

# Initialize the VISA resource manager
rm = visa.ResourceManager()
warnings.simplefilter("ignore")

# Initialize lists to store the measurements for plotting
current_x_values = []
current_y_values = []
power_x_values = []
power_y_values = []
phase_x_values = []
phase_y_values = []
phase_fit_x_values = []
phase_fit_y_values = []
phase_optimal = None  # Store optimal phase angle
phase_signal = None   # Store signal at optimal phase
phase_r_squared = None  # Store R^2 of the fit
power_thread = None
current_thread = None
pixel_number = 1  # Default pixel number for startup

# Set up variables for threading and closing the application
stop_thread = threading.Event()
is_closing = False

# Signal emitter for thread-safe file saving
class SignalEmitter(QObject):
    save_file_dialog = Signal(str, str, list, list)  # For power and current data
    save_phase_data = Signal(str, int, float, float, float)  # For phase data
    invoke_popup = Signal()  # For popup creation
    close_popup = Signal()  # For popup closure
    show_r_squared_warning = Signal(int)  # For R^2 < 0.90 warning

signal_emitter = SignalEmitter()

# Function to display pop up error messages
def show_error(message):
    app = application_instance = QApplication.instance()
    msg = QMessageBox()
    msg.setWindowTitle("Error")
    msg.setText(message)
    msg.setIcon(QMessageBox.Critical)
    msg.exec_()
    app.quit()
    sys.exit()

# Initialize Thorlabs Power Meter
def initialize_thorlabs_power_meter():
    tlPM = TLPMX()
    deviceCount = c_uint32()
    try:
        tlPM.findRsrc(byref(deviceCount))
        if deviceCount.value == 0:
            show_error("No Thorlabs power meter devices found. Please check the connection.")
    except Exception as e:
        show_error(f"Failed to find Thorlabs power meter: {e}")

    resourceName = create_string_buffer(1024)
    try:
        tlPM.getRsrcName(0, resourceName)
        tlPM.open(resourceName, c_bool(True), c_bool(True))
    except Exception as e:
        show_error(f"Failed to open Thorlabs power meter: {e}")
    return tlPM

tlPM = initialize_thorlabs_power_meter()

# Initialize the Keithley 2110
def initialize_keithley():
    resources = rm.list_resources()
    for resource in resources:
        if '2110' in resource:
            try:
                return rm.open_resource(resource)
            except Exception as e:
                show_error(f"Failed to open Keithley 2110: {e}")
    show_error("Keithley 2110 not found. Please check the connection.")

keithley = initialize_keithley()

# Initialize Oriel Cornerstone Monochromator
try:
    usb_mono = Cornerstone_Mono(rm, rem_ifc="usb", timeout_msec=29000)
    monochromator_serial_number = usb_mono.serial_number
    print(f"Monochromator Serial Number: {monochromator_serial_number}")
except Exception as e:
    show_error(f"Failed to initialize Monochromator: {e}")

# Define the correction factors for each serial number
correction_factors = {
    "130B5203": 0.45, # EQE2
    "130B5201": 0.45, # EQE3
    "130B5202": 0.45 # EQE1
}

# Get the correction factor based on the monochromator serial number
correction_factor = correction_factors.get(monochromator_serial_number, 0)  # Default to 0 if not found
print(f"Correction Factor: {correction_factor}")

# Find the COM port for the SR510 lock-in amplifier and initialize the serial connection
def initialize_serial_connection():
    ports = serial.tools.list_ports.comports()
    for port in ports:
        if "Prolific PL2303GT USB Serial COM Port" in port.description:
            try:
                return serial.Serial(
                    port=port.device,
                    baudrate=19200,
                    parity=serial.PARITY_ODD,
                    stopbits=serial.STOPBITS_TWO,
                    bytesize=serial.EIGHTBITS,
                    timeout=2
                )
            except Exception as e:
                show_error(f"Failed to initialize serial connection: {e}")
    show_error("COM port not found for SR510 lock-in amplifier.")

ser = initialize_serial_connection()

# Function to read the lock-in amplifier response
def read_lockin_response():
    response = ""
    while True:
        char = ser.read().decode()
        response += char
        if char == '\r':
            break
    return response.strip()

# Function to wait for the lock-in amplifier to be ready
def wait_for_lockin_ready():
    while True:
        status_command = 'Y\r'
        ser.write(status_command.encode())
        time.sleep(1)
        response = ser.read(ser.in_waiting or 1).decode().strip()
        if response:
            status_byte = int(response)
            if status_byte & (1 << 0):
                break
        else:
            print("No response received from SR510.")
            break

# Function to set the lock-in amplifier parameters
def set_lockin_parameters():
    ser.write('G 24\r'.encode())  # Set sensitivity to 500 mV
    ser.write('B 0\r'.encode())   # Bandpass: OUT
    ser.write('L 1,0\r'.encode()) # Line: OUT
    ser.write('L 2,0\r'.encode()) # LINE x2: OUT
    ser.write('D 0\r'.encode())   # DYN RES: LOW
    ser.write('S 0\r'.encode())   # DISPLAY: X
    ser.write('E 0\r'.encode())   # Expand: X1 (OFF)
    ser.write('O 0\r'.encode())   # Offset: OFF
    ser.write('T 1,5\r'.encode()) # Pre Time constant: 100ms
    ser.write('T 2,1\r'.encode()) # Post Time constant: 0.1s
    ser.write('M 0\r'.encode())   # Reference frequency: f
    ser.write('R 0\r'.encode())   # Input: Square wave
    wait_for_lockin_ready()

# Function to adjust the lock-in amplifier phase
def adjust_lockin_phase(pixel_number):
    def read_output():
        ser.write('Q\r'.encode())
        time.sleep(0.5)
        return read_lockin_response()

    def set_phase(phase):
        ser.write(f'P {phase}\r'.encode())
        wait_for_lockin_ready()

    def sample_phase_response():
        phases = np.linspace(0, 360, 7)  # Sample 7 points (60-degree steps)
        signals = []
        
        for phase in phases:
            if stop_thread.is_set():
                print("Phase adjustment stopped.")
                return None, None
            set_phase(phase)
            try:
                signal = float(read_output())
                signals.append(signal)
                print(f"Phase: {phase:.1f}°, Signal: {signal:.6f}")
            except ValueError as e:
                print(f"Error reading signal at phase {phase}: {e}")
                return None, None
        
        return phases, np.array(signals)

    def fit_sine(phases, signals):
        x = np.radians(phases)
        def sine_func(x, amplitude, phase_shift, offset):
            return amplitude * np.sin(x + phase_shift) + offset
        p0 = [(np.max(signals) - np.min(signals))/2, 0, np.mean(signals)]
        try:
            from scipy.optimize import curve_fit
            popt, _ = curve_fit(sine_func, x, signals, p0=p0)
            return popt
        except Exception as e:
            print(f"Error during sine fitting: {e}")
            return None

    def calculate_r_squared(phases, signals, popt):
        if popt is None:
            return None
        amplitude, phase_shift, offset = popt
        x = np.radians(phases)
        fitted = amplitude * np.sin(x + phase_shift) + offset
        ss_tot = np.sum((signals - np.mean(signals))**2)
        ss_res = np.sum((signals - fitted)**2)
        if ss_tot == 0:  # Avoid division by zero
            return None
        r_squared = 1 - ss_res / ss_tot
        return r_squared

    usb_mono.SendCommand("grating 1", False)
    usb_mono.WaitForIdle()
    usb_mono.SendCommand("gowave 532", False)
    usb_mono.WaitForIdle()
    usb_mono.SendCommand("shutter o", False)
    usb_mono.WaitForIdle()

    set_lockin_parameters()

    print("Sampling phase response...")
    phases, signals = sample_phase_response()
    if phases is None or signals is None:
        QMessageBox.critical(None, "Error", "Failed to sample phase response")
        return None, None

    print("Fitting sine wave to phase response...")
    fit_params = fit_sine(phases, signals)
    if fit_params is None:
        QMessageBox.critical(None, "Error", "Failed to fit sine wave to phase response")
        return None, None

    amplitude, phase_shift, offset = fit_params
    optimal_phase = (np.degrees(-phase_shift) + 90) % 360
    print(f"Setting optimal phase to {optimal_phase:.1f}°")
    set_phase(optimal_phase)
    
    final_signal = float(read_output())
    if final_signal < 0:
        optimal_phase = (np.degrees(-phase_shift) + 270) % 360
        print(f"Signal negative, adjusting phase to {optimal_phase:.1f}°")
        set_phase(optimal_phase)
        final_signal = float(read_output())

    r_squared = calculate_r_squared(phases, signals, fit_params)
    global phase_optimal, phase_signal, phase_r_squared
    phase_optimal = optimal_phase
    phase_signal = final_signal
    phase_r_squared = r_squared

    # Store data for plotting
    phase_x_values.clear()
    phase_y_values.clear()
    phase_fit_x_values.clear()
    phase_fit_y_values.clear()
    phase_x_values.extend(phases)
    phase_y_values.extend(signals)
    phase_fit_x_values.extend(np.linspace(0, 360, 1000))
    phase_fit_y_values.extend(amplitude * np.sin(np.radians(phase_fit_x_values) + phase_shift) + offset)

    # Update the phase plot with consistent size and font sizes
    ax_phase.cla()
    ax_phase.plot(phase_x_values, phase_y_values, 'o', label='Measured')
    ax_phase.plot(phase_fit_x_values, phase_fit_y_values, '-', label='Fitted Sine')
    ax_phase.set_xlabel('Phase (degrees)', fontsize=10)
    ax_phase.set_ylabel('Signal (V)', fontsize=10)
    ax_phase.set_title(f'Phase Response and Sine Fit for Pixel {pixel_number}', fontsize=10)
    ax_phase.tick_params(axis='both', which='major', labelsize=8)
    ax_phase.legend()
    ax_phase.grid(True)
    # Use fixed margins to prevent resizing
    fig_phase.subplots_adjust(left=0.15, right=0.85, top=0.85, bottom=0.15)
    canvas_phase.draw()

    return optimal_phase, final_signal

# Function to send a command to the lock-in amplifier and read the response
def send_command_to_lockin(command):
    ser.write(f"{command}\r".encode())
    return read_lockin_response()

# Function to parse the sensitivity response from the lock-in amplifier
def parse_sensitivity_response(response):
    sensitivity_map = {
        1: 10e-9, 2: 20e-9, 3: 50e-9, 4: 100e-9, 5: 200e-9, 6: 500e-9,
        7: 1e-6, 8: 2e-6, 9: 5e-6, 10: 10e-6, 11: 20e-6, 12: 50e-6,
        13: 100e-6, 14: 200e-6, 15: 500e-6, 16: 1e-3, 17: 2e-3, 18: 5e-3,
        19: 10e-3, 20: 20e-3, 21: 50e-3, 22: 100e-3, 23: 200e-3, 24: 500e-3
    }
    sensitivity_index = int(response.strip())
    return sensitivity_map.get(sensitivity_index, 1)  # Default to 1 if not found

# Function to read the lock-in status and read output from Keithley 2110
def read_lockin_status_and_keithley_output():
    try:
        if not ser.is_open:
            ser.open()
        while True:
            print("Flushing input buffer and sending 'Y' command...")
            ser.flushInput()
            ser.write('Y\r'.encode())
            time.sleep(1)
            
            response = ser.read(ser.in_waiting or 1).decode().strip()
            print(f"Received response: {response}")
            if response:
                try:
                    status_byte = int(response.split('\r')[0].strip())
                    print(f"Parsed status byte: {status_byte}")
                    is_locked = not (status_byte & (1 << 3))
                    has_reference = not (status_byte & (1 << 2))
                    is_overloaded = status_byte & (1 << 4)
                    print(f"Lock status: {is_locked}, Reference status: {has_reference}, Overload status: {is_overloaded}")
                    if is_locked and has_reference and not is_overloaded:
                        while True:
                            print("Querying sensitivity...")
                            sensitivity_response = send_command_to_lockin("G")
                            sensitivity_value = parse_sensitivity_response(sensitivity_response)
                            print(f"Sensitivity value: {sensitivity_value}")

                            print("Reading DC voltage from Keithley 2110...")
                            keithley.write(":SENS:FUNC 'VOLT:DC'")
                            voltage_readings = []
                            for _ in range(100):
                                voltage = float(keithley.query(":READ?"))
                                voltage_readings.append(voltage)
                            average_voltage = sum(voltage_readings) / len(voltage_readings)
                            print(f"Average voltage: {average_voltage}")
                            
                            if average_voltage > 10:
                                print("Average voltage > 10, increasing sensitivity...")
                                ser.write('K 22\r'.encode())
                                print("Sent command to increase sensitivity.")
                                print("Waiting 5 seconds after increasing sensitivity.")
                                time.sleep(5)  # Wait for the sensitivity change to take effect
                                break  # Break out of the inner while loop to re-read the status
                            
                            adjusted_voltage = (average_voltage * sensitivity_value / 10) / correction_factor
                            print(f"Adjusted Voltage: {adjusted_voltage}")
                            current = adjusted_voltage * 10 ** -6  # Accounts for transimpedance amplifier gain

                            if current:
                                print(f"Returning current: {current}")
                                return current
                            else:
                                print("No output response received.")
                                continue
                    else:
                        print("Device not ready or overloaded.")
                        continue
                except ValueError as e:
                    print(f"Error parsing response: {e}")
                    continue
            else:
                print("No status response received.")
                continue
    except Exception as e:
        print(f"Error: {e}")
    return None

# Function to set the monochromator to 532 nm for alignment
def align_monochromator():
    print("Aligning monochromator...")
    usb_mono.SendCommand("filter 1", False)
    usb_mono.SendCommand("grating 1", False)
    usb_mono.SendCommand("gowave 532", False)
    usb_mono.SendCommand("shutter o", False)
    usb_mono.WaitForIdle()

def start_power_measurement():
    clear_power_plot()
    print("Starting light power measurement...")
    try:
        start_wavelength = float(start_wavelength_var.text())
        end_wavelength = float(end_wavelength_var.text())
        step_size = float(step_size_var.text())
    except ValueError:
        QMessageBox.critical(None, "Input Error", "Please enter valid numerical values for wavelength and step size.")
        start_power_button.setText("Start Power Measurement")
        start_power_button.setStyleSheet("background-color: #CCDDAA; color: black;")
        start_power_button.clicked.disconnect()
        start_power_button.clicked.connect(toggle_power_measurement)
        return

    if start_wavelength <= 420:
        usb_mono.SendCommand("filter 3", False)
        usb_mono.WaitForIdle()
        print("Setting filter to 3 (no filter).")
    
    print("Measuring actual signal...")
    usb_mono.SendCommand("shutter o", False)
    usb_mono.WaitForIdle()

    current_wavelength = start_wavelength
    while current_wavelength <= end_wavelength:
        if stop_thread.is_set():
            break

        if current_wavelength < 685:
            usb_mono.SendCommand("grating 1", False)
        else:
            usb_mono.SendCommand("grating 2", False)
            
        usb_mono.SendCommand(f"gowave {current_wavelength}", False)
        usb_mono.WaitForIdle()

        print(f"Current Wavelength: {current_wavelength}")
        if current_wavelength > 420 and current_wavelength <= 420 + step_size:
            usb_mono.SendCommand("filter 1", False)
            usb_mono.WaitForIdle()      
            print("Setting filter to 1 (400 nm).")  

        if current_wavelength > 800 and current_wavelength <= 800 + step_size:
            usb_mono.SendCommand("filter 2", False)
            usb_mono.WaitForIdle()
            print("Setting filter to 2 (780 nm).")

        confirmed_mono_wavelength = usb_mono.GetQueryResponse("wave?")
        confirmed_mono_wavelength_float = float(confirmed_mono_wavelength)
        tlPM.setWavelength(c_double(confirmed_mono_wavelength_float), TLPM_DEFAULT_CHANNEL)
        time.sleep(0.2)

        power_values = []
        for _ in range(200):
            power = c_double()
            tlPM.measPower(byref(power), TLPM_DEFAULT_CHANNEL)
            power_values.append(power.value)
        average_power = (sum(power_values) / len(power_values)) * 2

        power_x_values.append(confirmed_mono_wavelength_float)
        power_y_values.append(average_power)  
        power_y_values_microwatts = [average_power * 1e6 for average_power in power_y_values]

        ax_power.plot(power_x_values, power_y_values_microwatts, '.-', color='#0077BB', label='Power Measurement')
        if not ax_power.get_legend():
            ax_power.legend()
        canvas_power.draw()
        QApplication.processEvents()

        current_wavelength += step_size

    usb_mono.SendCommand("shutter c", False)
    usb_mono.WaitForIdle()

    if not stop_thread.is_set() and power_x_values and power_y_values:
        cell_number = cell_number_var.text().strip()
        date = datetime.datetime.now().strftime("%Y_%m_%d")
        if not cell_number or not re.match(r'^\d{3}$', cell_number):
            QMessageBox.critical(None, "Input Error", "Cell number must be a three-digit number (e.g., 195).")
        else:
            file_name = f"{date}_power_cell{cell_number}.csv"
            # Emit signal to handle file saving in the main thread
            signal_emitter.save_file_dialog.emit(file_name, "Save Power Data", power_x_values, power_y_values)

    # Reset button state
    start_power_button.setText("Start Power Measurement")
    start_power_button.setStyleSheet("background-color: #CCDDAA; color: black;")
    start_power_button.clicked.disconnect()
    start_power_button.clicked.connect(toggle_power_measurement)

    if stop_thread.is_set():
        print("Measurement stopped.")
    else:
        print("Measurement complete.")
        align_monochromator()

def start_current_measurement(pixel_number):
    print(f"Starting current measurement for pixel {pixel_number}")
    
    # Create custom dialog in the main thread using a signal
    def show_popup():
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel
        from PySide6.QtCore import Qt
        class NonClosableDialog(QDialog):
            def keyPressEvent(self, event):
                if event.key() == Qt.Key_Escape:
                    event.ignore()  # Ignore Esc key
                else:
                    super().keyPressEvent(event)
        
        popup = NonClosableDialog()
        popup.setWindowTitle("Processing")
        popup.setFixedSize(300, 100)  # 300px wide, 100px tall
        popup.setWindowFlags(Qt.Window | Qt.WindowTitleHint | Qt.CustomizeWindowHint)  # No close button
        popup.setModal(True)  # Block GUI interactions
        layout = QVBoxLayout()
        label = QLabel("Please Wait...")
        label.setAlignment(Qt.AlignCenter)
        label.setStyleSheet("font-size: 14px;")
        layout.addWidget(label)
        popup.setLayout(layout)
        popup.show()
        print(f"Custom dialog created with width: 300px")
        return popup

    # Run popup in main thread
    from PySide6.QtCore import QMetaObject, Qt
    popup = None
    def invoke_popup():
        nonlocal popup
        popup = show_popup()
    try:
        print("Invoking popup...")
        QMetaObject.invokeMethod(signal_emitter, "invoke_popup", Qt.BlockingQueuedConnection)
    except Exception as e:
        print(f"Error invoking popup: {e}")
        QMessageBox.critical(None, "Popup Error", f"Failed to show processing popup: {e}")
        return
    
    phase_x_values.clear()
    phase_y_values.clear()
    phase_fit_x_values.clear()
    phase_fit_y_values.clear()
    ax_phase.cla()
    configure_phase_plot(pixel_number)
    canvas_phase.draw()
    QApplication.processEvents()

    # Run phase adjustment
    try:
        print("Starting phase adjustment...")
        optimal_phase, final_signal = adjust_lockin_phase(pixel_number)
        print(f"Phase adjustment complete: {optimal_phase}, {final_signal}")
    except Exception as e:
        print(f"Error during phase adjustment: {e}")
        QMessageBox.critical(None, "Phase Adjustment Error", f"Failed to adjust phase: {e}")
        signal_emitter.close_popup.emit()
        return

    # Close popup in main thread
    print("Closing popup...")
    signal_emitter.close_popup.emit()
    QApplication.processEvents()

    # # Save phase data using signal
    # if phase_optimal is not None and phase_signal is not None and phase_r_squared is not None:
    #     cell_number = cell_number_var.text().strip()
    #     date = datetime.datetime.now().strftime("%Y_%m_%d")
    #     if not cell_number or not re.match(r'^\d{3}$', cell_number):
    #         QMessageBox.critical(None, "Input Error", "Cell number must be a three-digit number (e.g., 195).")
    #         return
    #     file_name = f"{date}_phase_cell{cell_number}.csv"
    #     print(f"Emitting save_phase_data signal for {file_name}")
    #     signal_emitter.save_phase_data.emit(file_name, pixel_number, phase_optimal, phase_signal, phase_r_squared)
    # else:
    #     print("Phase data not saved due to invalid results")
    #     QMessageBox.critical(None, "Phase Data Error", "Phase adjustment results are invalid.")
    #     return

    # Check R^2 value and show warning if < 0.90
    if phase_r_squared is not None and phase_r_squared < 0.90:
        print(f"R^2 value {phase_r_squared:.4f} is below 0.90 for pixel {pixel_number}")
        signal_emitter.show_r_squared_warning.emit(pixel_number)

    clear_current_plot(pixel_number)
    print("Starting photocell measurement...")
    try:
        start_wavelength = float(start_wavelength_var.text())
        end_wavelength = float(end_wavelength_var.text())
        step_size = float(step_size_var.text())
    except ValueError:
        QMessageBox.critical(None, "Input Error", "Please enter valid numerical values for wavelength and step size.")
        start_current_button.setText("Start Current Measurement")
        start_current_button.setStyleSheet("background-color: #CCDDAA; color: black;")
        start_current_button.clicked.disconnect()
        start_current_button.clicked.connect(toggle_current_measurement)
        return

    if start_wavelength <= 400:
        usb_mono.SendCommand("filter 3", False)
        usb_mono.WaitForIdle()
        print("Setting filter to 3 (no filter).")
    usb_mono.SendCommand("shutter o", False)
    usb_mono.WaitForIdle()

    set_lockin_parameters()

    current_wavelength = start_wavelength
    usb_mono.SendCommand(f"gowave {current_wavelength}", False)
    usb_mono.WaitForIdle()
    time.sleep(1)
    while current_wavelength <= end_wavelength:
        if stop_thread.is_set():
            break

        if current_wavelength < 685:
            usb_mono.SendCommand("grating 1", False)
        else:
            usb_mono.SendCommand("grating 2", False)
            
        usb_mono.SendCommand(f"gowave {current_wavelength}", False)
        usb_mono.WaitForIdle()

        print(f"Current Wavelength: {current_wavelength}")
        if current_wavelength > 420 and current_wavelength <= 420 + step_size:
            usb_mono.SendCommand("filter 1", False)
            usb_mono.WaitForIdle()       
            print("Setting filter to 1 (400 nm).")  
        if current_wavelength > 800 and current_wavelength <= 800 + step_size:
            usb_mono.SendCommand("filter 2", False)
            usb_mono.WaitForIdle()
            print("Setting filter to 2 (780 nm).")
        confirmed_mono_wavelength = usb_mono.GetQueryResponse("wave?")
        confirmed_mono_wavelength_float = float(confirmed_mono_wavelength)

        try:
            output = read_lockin_status_and_keithley_output()
            if output is None:
                QMessageBox.critical(None, "Measurement Error", "Failed to read output from SR510.")
                return
        except Exception as e:
            print(f"Error reading lock-in/Keithley output: {e}")
            QMessageBox.critical(None, "Measurement Error", f"Failed to read output: {e}")
            return

        current_x_values.append(confirmed_mono_wavelength_float)
        current_y_values.append(output)
        current_y_values_nanoamps = [output * 1e9 for output in current_y_values]

        ax_current.plot(current_x_values, current_y_values_nanoamps, '.-', color='#0077BB')
        canvas_current.draw()
        QApplication.processEvents()

        current_wavelength += step_size

    usb_mono.SendCommand("shutter c", False)
    usb_mono.WaitForIdle()

    if not stop_thread.is_set() and current_x_values and current_y_values:
        cell_number = cell_number_var.text().strip()
        date = datetime.datetime.now().strftime("%Y_%m_%d")
        if not cell_number or not re.match(r'^\d{3}$', cell_number):
            QMessageBox.critical(None, "Input Error", "Cell number must be a three-digit number (e.g., 195).")
        else:
            file_name = f"{date}_current_cell{cell_number}_pixel{pixel_number}.csv"
            print(f"Emitting save_file_dialog signal for {file_name}")
            signal_emitter.save_file_dialog.emit(file_name, "Save Current Data", current_x_values, current_y_values)

    start_current_button.setText("Start Current Measurement")
    start_current_button.setStyleSheet("background-color: #CCDDAA; color: black;")
    start_current_button.clicked.disconnect()
    start_current_button.clicked.connect(toggle_current_measurement)

    if stop_thread.is_set():
        print("Measurement stopped.")
    else:
        print("Measurement complete.")
        align_monochromator()

def measure_power_thread():
    global power_thread
    stop_thread.clear()
    power_thread = threading.Thread(target=start_power_measurement)
    power_thread.start()

def measure_current_thread(pixel_number):
    global current_thread
    stop_thread.clear()
    current_thread = threading.Thread(target=start_current_measurement, args=(pixel_number,))
    current_thread.start()

def stop_measurement():
    stop_thread.set()

def toggle_power_measurement():
    if start_power_button.text() == "Start Power Measurement":
        measure_power_thread()
        start_power_button.setText("Stop Power Measurement")
        start_power_button.setStyleSheet("background-color: #FFCCCC; color: black;")
        start_power_button.clicked.disconnect()
        start_power_button.clicked.connect(stop_measurement)
    else:
        stop_measurement()
        start_power_button.setText("Start Power Measurement")
        start_power_button.setStyleSheet("background-color: #CCDDAA; color: black;")
        start_power_button.clicked.disconnect()
        start_power_button.clicked.connect(toggle_power_measurement)

def toggle_current_measurement():
    global current_thread
    if start_current_button.text() == "Start Current Measurement":
        # Prompt for pixel number using QInputDialog.getText for flexibility
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
        
        stop_thread.clear()
        current_thread = threading.Thread(target=start_current_measurement, args=(pixel_number,))
        current_thread.start()
        start_current_button.setText("Stop Current Measurement")
        start_current_button.setStyleSheet("background-color: #FFCCCC; color: black;")
        start_current_button.clicked.disconnect()
        start_current_button.clicked.connect(toggle_current_measurement)
    else:
        stop_measurement()
        start_current_button.setText("Start Current Measurement")
        start_current_button.setStyleSheet("background-color: #CCDDAA; color: black;")
        start_current_button.clicked.disconnect()
        start_current_button.clicked.connect(toggle_current_measurement)

def on_close():
    global is_closing
    is_closing = True
    stop_thread.set()

    if 'power_thread' in globals() and power_thread and power_thread.is_alive():
        power_thread.join()
    if 'current_thread' in globals() and current_thread and current_thread.is_alive():
        current_thread.join()

    try:
        if 'tlPM' in globals():
            tlPM.close()
        if 'keithley' in globals():
            keithley.close()
        if 'ser' in globals():
            ser.close()
    except Exception as e:
        print(f"Error closing resources: {e}")

    app.quit()
    sys.exit()

def configure_power_plot():
    ax_power.set_xlabel('Wavelength (nm)', fontsize=10)
    ax_power.set_ylabel(r'Power ($\mu$W)', fontsize=10)
    ax_power.set_title('Incident Light Power Measurements', fontsize=10)
    ax_power.tick_params(axis='both', which='major', labelsize=8)
    fig_power.tight_layout()
    fig_power.subplots_adjust(bottom=0.2, left=0.15, right=0.85, top=0.85)

def configure_current_plot(pixel_number):
    ax_current.set_xlabel('Wavelength (nm)', fontsize=10)
    ax_current.set_ylabel('Current (nA)', fontsize=10)
    ax_current.set_title(f'PV Current Measurements for Pixel {pixel_number}', fontsize=10)
    ax_current.tick_params(axis='both', which='major', labelsize=8)
    fig_current.tight_layout()
    fig_current.subplots_adjust(bottom=0.2, left=0.15, right=0.85, top=0.85)

def configure_phase_plot(pixel_number):
    ax_phase.set_xlabel('Phase (degrees)', fontsize=10)
    ax_phase.set_ylabel('Signal (V)', fontsize=10)
    ax_phase.set_title(f'Phase Response and Sine Fit for Pixel {pixel_number}', fontsize=10)
    ax_phase.tick_params(axis='both', which='major', labelsize=8)
    fig_phase.tight_layout()
    fig_phase.subplots_adjust(bottom=0.2, left=0.15, right=0.85, top=0.85)

def clear_power_plot():
    ax_power.cla()
    power_x_values.clear()
    power_y_values.clear()
    configure_power_plot()
    canvas_power.draw()

def clear_current_plot(pixel_number):
    ax_current.cla()
    current_x_values.clear()
    current_y_values.clear()
    configure_current_plot(pixel_number)
    canvas_current.draw()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PHYS 2150 EQE Measurement")
        self.setGeometry(100, 100, 1200, 800)

        # Main widget and layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout()
        main_widget.setLayout(main_layout)

        # Top section: Grid layout for input fields and buttons
        input_grid = QGridLayout()
        input_grid.setVerticalSpacing(10)
        input_grid.setHorizontalSpacing(20)

        # Column 0: Start Wavelength
        start_wavelength_label = QLabel("Start Wavelength (nm):")
        start_wavelength_label.setStyleSheet("font-size: 14px;")
        global start_wavelength_var
        start_wavelength_var = QLineEdit("350")
        start_wavelength_var.setStyleSheet("font-size: 14px;")
        start_wavelength_var.setFixedHeight(30)
        input_grid.addWidget(start_wavelength_label, 0, 0)
        input_grid.addWidget(start_wavelength_var, 1, 0)

        # Column 1: End Wavelength and Align Button
        end_wavelength_label = QLabel("End Wavelength (nm):")
        end_wavelength_label.setStyleSheet("font-size: 14px;")
        global end_wavelength_var
        end_wavelength_var = QLineEdit("750")
        end_wavelength_var.setStyleSheet("font-size: 14px;")
        end_wavelength_var.setFixedHeight(30)
        align_button = QPushButton("Enable Green Alignment Dot")
        align_button.setStyleSheet("font-size: 14px; background-color: #CCDDAA; color: black;")
        align_button.setFixedHeight(30)
        align_button.clicked.connect(align_monochromator)
        input_grid.addWidget(end_wavelength_label, 0, 1)
        input_grid.addWidget(end_wavelength_var, 1, 1)
        input_grid.addWidget(align_button, 4, 1, alignment=Qt.AlignCenter)

        # Column 2: Step Size and Cell Number
        step_size_label = QLabel("Step Size (nm):")
        step_size_label.setStyleSheet("font-size: 14px;")
        global step_size_var
        step_size_var = QLineEdit("10")
        step_size_var.setStyleSheet("font-size: 14px;")
        step_size_var.setFixedHeight(30)
        cell_number_label = QLabel("Cell Number:")
        cell_number_label.setStyleSheet("font-size: 14px;")
        global cell_number_var
        cell_number_var = QLineEdit("195")
        cell_number_var.setStyleSheet("font-size: 14px;")
        cell_number_var.setFixedHeight(30)
        input_grid.addWidget(step_size_label, 0, 2)
        input_grid.addWidget(step_size_var, 1, 2)
        input_grid.addWidget(cell_number_label, 2, 2)
        input_grid.addWidget(cell_number_var, 3, 2)

        main_layout.addLayout(input_grid)

        # Spacer to push plots down
        main_layout.addSpacerItem(QSpacerItem(20, 20, QSizePolicy.Minimum, QSizePolicy.Fixed))

        # Plot section: Horizontal layout for plots
        plot_layout = QHBoxLayout()

        # Column 0: Power Plot
        power_column_widget = QWidget()
        power_column_layout = QVBoxLayout()
        power_column_widget.setLayout(power_column_layout)
        global fig_power, ax_power, canvas_power
        fig_power, ax_power = plt.subplots(figsize=(8, 8), dpi=100)
        configure_power_plot()
        canvas_power = FigureCanvas(fig_power)
        canvas_power.setMinimumSize(300, 300)
        canvas_power.setMaximumSize(400, 400)
        toolbar_power = NavigationToolbar(canvas_power, self)
        power_column_layout.addWidget(canvas_power, alignment=Qt.AlignHCenter)
        power_column_layout.addWidget(toolbar_power, alignment=Qt.AlignHCenter)
        global start_power_button
        start_power_button = QPushButton("Start Power Measurement")
        start_power_button.setStyleSheet("font-size: 14px; background-color: #CCDDAA; color: black;")
        start_power_button.setFixedHeight(30)
        start_power_button.clicked.connect(toggle_power_measurement)
        power_column_layout.addWidget(start_power_button, alignment=Qt.AlignHCenter)
        power_column_layout.addStretch(1)
        plot_layout.addWidget(power_column_widget)

        # Column 1: Current Plot
        current_column_widget = QWidget()
        current_column_layout = QVBoxLayout()
        current_column_widget.setLayout(current_column_layout)
        global fig_current, ax_current, canvas_current
        fig_current, ax_current = plt.subplots(figsize=(8, 8), dpi=100)
        configure_current_plot(pixel_number)
        canvas_current = FigureCanvas(fig_current)
        canvas_current.setMinimumSize(300, 300)
        canvas_current.setMaximumSize(400, 400)
        toolbar_current = NavigationToolbar(canvas_current, self)
        current_column_layout.addWidget(canvas_current, alignment=Qt.AlignHCenter)
        current_column_layout.addWidget(toolbar_current, alignment=Qt.AlignHCenter)
        global start_current_button
        start_current_button = QPushButton("Start Current Measurement")
        start_current_button.setStyleSheet("font-size: 14px; background-color: #CCDDAA; color: black;")
        start_current_button.setFixedHeight(30)
        start_current_button.clicked.connect(toggle_current_measurement)
        current_column_layout.addWidget(start_current_button, alignment=Qt.AlignHCenter)
        current_column_layout.addStretch(1)
        plot_layout.addWidget(current_column_widget)

        # Column 2: Phase Plot
        phase_column_widget = QWidget()
        phase_column_layout = QVBoxLayout()
        phase_column_widget.setLayout(phase_column_layout)
        global fig_phase, ax_phase, canvas_phase
        fig_phase, ax_phase = plt.subplots(figsize=(8, 8), dpi=100)
        configure_phase_plot(pixel_number)
        canvas_phase = FigureCanvas(fig_phase)
        canvas_phase.setMinimumSize(300, 300)
        canvas_phase.setMaximumSize(400, 400)
        toolbar_phase = NavigationToolbar(canvas_phase, self)
        phase_column_layout.addWidget(canvas_phase, alignment=Qt.AlignHCenter)
        phase_column_layout.addWidget(toolbar_phase, alignment=Qt.AlignHCenter)
        phase_column_layout.addStretch(1)
        plot_layout.addWidget(phase_column_widget)

        main_layout.addLayout(plot_layout)
        main_layout.addStretch(1)

        # Connect signals
        signal_emitter.save_file_dialog.connect(self.handle_save_file_dialog)
        # signal_emitter.save_phase_data.connect(self.handle_save_phase_data)
        signal_emitter.invoke_popup.connect(self.invoke_popup)
        signal_emitter.close_popup.connect(self.close_popup)
        signal_emitter.show_r_squared_warning.connect(self.show_r_squared_warning)

        # Show cell number popup
        QTimer.singleShot(1000, self.show_cell_number_popup)

    def invoke_popup(self):
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel
        from PySide6.QtCore import Qt
        class NonClosableDialog(QDialog):
            def keyPressEvent(self, event):
                if event.key() == Qt.Key_Escape:
                    event.ignore()  # Ignore Esc key
                else:
                    super().keyPressEvent(event)
        
        popup = NonClosableDialog(self)
        popup.setWindowTitle("Processing")
        popup.setFixedSize(300, 100)  # 300px wide, 100px tall
        popup.setWindowFlags(Qt.Window | Qt.WindowTitleHint | Qt.CustomizeWindowHint)  # No close button
        popup.setModal(True)  # Block GUI interactions
        layout = QVBoxLayout()
        label = QLabel("Please Wait...")
        label.setAlignment(Qt.AlignCenter)
        label.setStyleSheet("font-size: 14px;")
        layout.addWidget(label)
        popup.setLayout(layout)
        popup.show()
        self._popup = popup
        print(f"Custom dialog created with width: 300px")

    def close_popup(self):
        if hasattr(self, '_popup') and self._popup:
            self._popup.accept()
            self._popup = None
            print("Custom dialog closed successfully")

    def show_r_squared_warning(self, pixel_number):
        QMessageBox.warning(
            self,
            "Low R² Value",
            f"Is the lamp on? If it is, pixel {pixel_number} might be dead. Check in with a TA.",
            QMessageBox.Ok
        )

    def handle_save_file_dialog(self, file_name, dialog_title, x_values, y_values):
        file_path, _ = QFileDialog.getSaveFileName(self, dialog_title, file_name, "CSV files (*.csv)")
        if file_path:
            try:
                with open(file_path, mode='w', newline='') as file:
                    writer = csv.writer(file)
                    writer.writerow(["Wavelength (nm)", "Power (W)" if "power" in file_name.lower() else "Current (A)"])
                    for x, y in zip(x_values, y_values):
                        writer.writerow([x, y])
                print(f"Data saved to {file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Save Error", f"Failed to save file: {e}")

    # def handle_save_phase_data(self, file_name, pixel_number, phase_optimal, phase_signal, phase_r_squared):
    #     file_path, _ = QFileDialog.getSaveFileName(self, "Save Phase Data", file_name, "CSV files (*.csv)")
    #     if file_path:
    #         try:
    #             if not os.path.exists(file_path):
    #                 df = pd.DataFrame({
    #                     "Pixel #": [1, 2, 3, 4, 5, 6, 7, 8],
    #                     "Set Angle": [None]*8,
    #                     "Signal": [None]*8,
    #                     "R^2 Value": [None]*8
    #                 })
    #             else:
    #                 try:
    #                     df = pd.read_csv(file_path)
    #                     if "Pixel #" not in df.columns:
    #                         legacy_data = df[["set angle", "signal", "r-value"]].values
    #                         df = pd.DataFrame({
    #                             "Pixel #": [1, 2, 3, 4, 5, 6, 7, 8],
    #                             "Set Angle": [None]*8,
    #                             "Signal": [None]*8,
    #                             "R^2 Value": [None]*8
    #                         })
    #                         for i, row in enumerate(legacy_data[:8]):
    #                             df.at[i, "Set Angle"] = row[0]
    #                             df.at[i, "Signal"] = row[1]
    #                             df.at[i, "R^2 Value"] = row[2]
    #                     else:
    #                         existing_pixels = df["Pixel #"].tolist()
    #                         for i in range(1, 9):
    #                             if i not in existing_pixels:
    #                                 df = pd.concat([df, pd.DataFrame({
    #                                     "Pixel #": [i],
    #                                     "Set Angle": [None],
    #                                     "Signal": [None],
    #                                     "R^2 Value": [None]
    #                                 })], ignore_index=True)
    #                         df = df[df["Pixel #"].isin([1, 2, 3, 4, 5, 6, 7, 8])].sort_values("Pixel #").reset_index(drop=True)
    #                 except Exception as e:
    #                     print(f"Error reading CSV: {e}")
    #                     df = pd.DataFrame({
    #                         "Pixel #": [1, 2, 3, 4, 5, 6, 7, 8],
    #                         "Set Angle": [None]*8,
    #                         "Signal": [None]*8,
    #                         "R^2 Value": [None]*8
    #                     })

    #             pixel_index = pixel_number - 1
    #             if 0 <= pixel_index < 8:
    #                 df.at[pixel_index, "Set Angle"] = f"{phase_optimal:.2f}"
    #                 df.at[pixel_index, "Signal"] = phase_signal
    #                 df.at[pixel_index, "R^2 Value"] = f"{phase_r_squared:.4f}"

    #             df.to_csv(file_path, index=False)
    #             print(f"Phase data for pixel {pixel_number} saved to {file_path}")
    #         except Exception as e:
    #             QMessageBox.critical(self, "Save Error", f"Failed to save phase data: {e}")

    def show_cell_number_popup(self):
        cell_number, ok = QInputDialog.getText(self, "Enter Cell Number",
                                               "Enter Cell Number (e.g., 195):")
        if ok and cell_number and re.match(r'^\d{3}$', cell_number):
            cell_number_var.setText(cell_number)
        else:
            QMessageBox.warning(self, "Invalid Input",
                                "Cell number must be a three-digit number (e.g., 195).")
            self.show_cell_number_popup()

    def closeEvent(self, event):
        # Ensure popup is closed on window close
        if hasattr(self, '_popup') and self._popup:
            self._popup.accept()
        on_close()
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.showMaximized()  # Start maximized
    sys.exit(app.exec())