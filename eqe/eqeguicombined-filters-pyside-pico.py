import time
import csv
import scipy
from ctypes import c_double, byref, c_uint32, create_string_buffer, c_bool
from cornerstone_mono import Cornerstone_Mono
from TLPMX import TLPMX, TLPM_DEFAULT_CHANNEL
import warnings
import matplotlib.pyplot as plt
import pandas as pd
import sys
import re
import os
import datetime
import threading
import numpy as np
from scipy.optimize import curve_fit
from picoscope_driver import PicoScopeDriver
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLineEdit, QLabel, QMessageBox, QFileDialog, QInputDialog,
    QGridLayout, QSpacerItem, QSizePolicy
)
from PySide6.QtCore import Qt, QTimer, Signal, QObject
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar

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

# Global variables for PicoScope lock-in
picoscope = None
chopper_freq = 81  # Default chopper frequency

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

# Initialize Oriel Cornerstone Monochromator
# Note: Cornerstone_Mono may need VISA, but we'll keep it for now since it's for the monochromator, not the lock-in
import pyvisa as visa
rm = visa.ResourceManager()

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

# Initialize PicoScope
def initialize_picoscope(hostname=None, freq=81):
    """
    Connects to the PicoScope and initializes software lock-in.
    
    Args:
        hostname (str): Ignored (kept for API compatibility). Pass None or empty string.
        freq (float): The chopper frequency in Hz (default: 81 Hz).
    
    Returns:
        bool: True if connection is successful, False otherwise.
    """
    global picoscope, chopper_freq
    try:
        # Connect to PicoScope
        picoscope = PicoScopeDriver()
        if not picoscope.connect():
            raise Exception("Could not connect to PicoScope")
        
        # Set the reference frequency for software lock-in
        picoscope.set_reference_frequency(freq)
        chopper_freq = freq
        
        print(f"PicoScope connected successfully")
        print(f"Signal input: CH A, Reference input: CH B (external chopper)")
        print(f"Reference frequency: {freq} Hz (for software lock-in)")
        print("Using software lock-in amplifier with phase-sensitive detection")
        print(f"Input range: ±20V (no clipping!)")
        
        return True

    except Exception as e:
        print(f"Failed to connect to PicoScope: {e}")
        QMessageBox.critical(None, "Connection Error", 
                           f"Failed to connect to PicoScope: {e}\n\n"
                           f"Make sure:\n"
                           f"1. PicoScope is connected via USB\n"
                           f"2. PicoSDK drivers are installed\n"
                           f"3. Python picosdk package is installed\n"
                           f"   (pip install picosdk)")
        return False

# Function to set the lock-in amplifier parameters (no-op for PicoScope)
def set_lockin_parameters(gain=0, time_constant=0.1):
    """
    Legacy function for setting lock-in parameters.
    PicoScope doesn't need these settings - integration time is controlled by num_cycles.

    Args:
        gain (int): Ignored (kept for compatibility)
        time_constant (float): Ignored (kept for compatibility)
    """
    # PicoScope doesn't need these settings
    # Integration time is controlled by num_cycles parameter in software_lockin()
    pass

# Function to determine optimal lock-in phase using software lock-in
def adjust_lockin_phase(pixel_number):
    """
    Uses software lock-in to measure signal and determine optimal phase.
    The software lock-in calculates X, Y components and finds the phase
    that maximizes the signal magnitude.
    
    Returns:
        tuple: (optimal_phase, signal_magnitude, signal_quality)
    """
    if not picoscope:
        print("PicoScope not connected.")
        QMessageBox.critical(None, "Error", "PicoScope not connected")
        return None, None, None

    global phase_x_values, phase_y_values, phase_fit_x_values, phase_fit_y_values
    global phase_optimal, phase_signal, phase_r_squared

    # Set monochromator to 532 nm for phase adjustment
    usb_mono.SendCommand("grating 1", False)
    usb_mono.WaitForIdle()
    usb_mono.SendCommand("gowave 532", False)
    usb_mono.WaitForIdle()
    usb_mono.SendCommand("shutter o", False)
    usb_mono.WaitForIdle()
    
    # Wait for light to stabilize
    time.sleep(1.0)

    print("Performing software lock-in measurement for phase optimization...")
    
    # Perform software lock-in measurement
    result = picoscope.software_lockin(
        chopper_freq,
        num_cycles=50  # More cycles for better stability and averaging
    )
    
    if result is None:
        print("Failed to perform lock-in measurement")
        QMessageBox.critical(None, "Error", "Failed to perform lock-in measurement")
        return None, None, None
    
    # Extract results
    X = result['X']
    Y = result['Y']
    R = result['R']
    theta_deg = result['theta']
    measured_freq = result['freq']
    
    print(f"Lock-in results:")
    print(f"  X (in-phase):    {X:+.6f} V")
    print(f"  Y (quadrature):  {Y:+.6f} V")
    print(f"  R (magnitude):   {R:+.6f} V")
    print(f"  Phase:           {theta_deg:+.1f}°")
    print(f"  Measured freq:   {measured_freq:.2f} Hz")
    
    # The optimal phase is where the signal is maximum
    # This is the phase of the signal itself
    phase_optimal = theta_deg % 360
    phase_signal = R  # Magnitude is the signal strength
    
    # Store the optimal phase (software lock-in uses magnitude R, phase-independent)
    # Phase info is stored but not actively used since we use R = sqrt(X² + Y²)
    
    # Calculate signal quality (SNR estimate)
    # Higher R relative to noise floor indicates better signal
    signal_data = result['signal_data']
    noise_estimate = np.std(signal_data)
    if noise_estimate > 0:
        phase_r_squared = min(1.0, R / (10 * noise_estimate))  # Normalized quality metric
    else:
        phase_r_squared = 1.0
    
    # Create visualization of X vs Y (Lissajous-like plot)
    phase_x_values.clear()
    phase_y_values.clear()
    
    # Plot the phase sweep showing how signal varies with assumed phase
    test_phases = np.linspace(0, 360, 37)
    for test_phase in test_phases:
        # Calculate what the signal would be if we rotated by this phase
        phase_rad = np.deg2rad(test_phase)
        rotated_signal = X * np.cos(phase_rad) + Y * np.sin(phase_rad)
        phase_x_values.append(test_phase)
        phase_y_values.append(rotated_signal)
    
    # Generate smooth fit curve (cosine shape expected)
    phase_fit_x_values = np.linspace(0, 360, 1000).tolist()
    phase_rad_fit = np.deg2rad(np.array(phase_fit_x_values))
    phase_fit_y_values = (X * np.cos(phase_rad_fit - np.deg2rad(phase_optimal)) + 
                          Y * np.sin(phase_rad_fit - np.deg2rad(phase_optimal))).tolist()
    
    # Update phase plot
    ax_phase.cla()
    ax_phase.plot(phase_x_values, phase_y_values, 'o', label='Projected Signal', markersize=4)
    ax_phase.plot(phase_fit_x_values, phase_fit_y_values, '-', label='Expected Response', linewidth=2)
    ax_phase.axvline(phase_optimal, color='r', linestyle='--', label=f'Optimal Phase: {phase_optimal:.1f}°')
    ax_phase.axhline(R, color='g', linestyle=':', label=f'Max Signal: {R:.4f} V')
    ax_phase.set_xlabel('Phase (degrees)', fontsize=10)
    ax_phase.set_ylabel('Signal (V)', fontsize=10)
    ax_phase.set_title(f'Software Lock-in Phase Analysis for Pixel {pixel_number}', fontsize=10)
    ax_phase.tick_params(axis='both', which='major', labelsize=8)
    ax_phase.legend(fontsize=8)
    ax_phase.grid(True)
    fig_phase.subplots_adjust(left=0.15, right=0.85, top=0.85, bottom=0.15)
    canvas_phase.draw()
    
    print(f"Optimal phase set to {phase_optimal:.1f}° with signal magnitude {phase_signal:.6f} V")
    
    return phase_optimal, phase_signal, phase_r_squared

# Function to read the lock-in output
def read_lockin_output():
    """
    Performs software lock-in measurement to extract signal at chopper frequency.
    Returns the magnitude of the lock-in signal converted to current.
    
    Returns:
        float: The measured current in Amps, or None if error.
    """
    if not picoscope:
        print("PicoScope not connected.")
        return None
    
    try:
        # Perform software lock-in measurement - optimized parameters
        # Strategy: 5 measurements × 100 cycles each (proven stable at 0.66% CV)
        R_values = []
        num_measurements = 5  # Optimal for stability
        
        for i in range(num_measurements):
            # Each measurement: 100 cycles for good averaging
            # This provides excellent stability and noise rejection
            result = picoscope.software_lockin(
                chopper_freq,
                num_cycles=100  # Optimal for balance of speed and stability
            )
            
            if result is not None:
                # Use the magnitude (R) directly - this is phase-independent!
                # R = sqrt(X^2 + Y^2) gives us the signal amplitude regardless of phase
                # This eliminates instability from phase drift or trigger timing issues
                R_values.append(result['R'])
            else:
                print(f"Warning: Lock-in measurement {i+1}/{num_measurements} failed")
        
        if not R_values:
            print("Error: All lock-in measurements failed")
            return None
        
        # Use MEDIAN and TRIMMED MEAN for robust averaging
        # This rejects outliers from lamp flicker and chopper variations
        R_array = np.array(R_values)
        
        # Calculate median for reference
        median_signal = np.median(R_array)
        
        # Trimmed mean: remove outliers beyond 2 standard deviations from median
        deviations = np.abs(R_array - median_signal)
        threshold = 2 * np.std(deviations)
        mask = deviations <= threshold
        R_trimmed = R_array[mask]
        
        # Use trimmed mean if we have enough measurements remaining
        if len(R_trimmed) >= 3:
            average_signal = np.mean(R_trimmed)
            std_signal = np.std(R_trimmed)
            n_outliers = len(R_values) - len(R_trimmed)
        else:
            # If too many outliers, use median (most robust)
            average_signal = median_signal
            std_signal = np.std(R_array)
            n_outliers = 0
        
        # Calculate coefficient of variation for quality metric
        cv = 100 * std_signal / average_signal if average_signal > 0 else 0
        
        print(f"Lock-in measurement: {average_signal:.6f} ± {std_signal:.6f} V (n={len(R_trimmed)}/{num_measurements}, outliers={n_outliers}, CV={cv:.2f}%)")
        
        # Check for saturation
        if abs(average_signal) > 0.95:
            print(f"Warning: Signal near saturation ({average_signal:.3f} V)")
        
        # Apply correction factor and transimpedance amplifier gain
        # Assuming 1 MΩ transimpedance gain (adjust as needed)
        adjusted_voltage = average_signal / correction_factor
        current = adjusted_voltage * 10 ** -6  # Convert to Amps (from V with 1MΩ gain)
        
        return current
        
    except Exception as e:
        print(f"Error reading from PicoScope: {e}")
        import traceback
        traceback.print_exc()
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
        optimal_phase, final_signal, r_squared = adjust_lockin_phase(pixel_number)
        print(f"Phase adjustment complete: Phase={optimal_phase}°, Signal={final_signal} V, R²={r_squared}")
    except Exception as e:
        print(f"Error during phase adjustment: {e}")
        import traceback
        traceback.print_exc()
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
            output = read_lockin_output()
            if output is None:
                QMessageBox.critical(None, "Measurement Error", "Failed to read output from PicoScope.")
                return
        except Exception as e:
            print(f"Error reading lock-in output: {e}")
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
        if 'picoscope' in globals() and picoscope:
            picoscope.close()
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

        # Initialize PicoScope before building UI
        self.initialize_picoscope_with_dialog()

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

    def initialize_picoscope_with_dialog(self):
        """Prompt user for chopper frequency and initialize PicoScope connection."""
        # Ask for chopper frequency only (PicoScope connects via USB, no hostname needed)
        freq_str, ok = QInputDialog.getText(
            None,
            "PicoScope Connection",
            "Enter chopper frequency (Hz):",
            QLineEdit.Normal,
            "81"
        )
        
        if ok and freq_str:
            try:
                chopper_freq = float(freq_str)
                # Connect to PicoScope (no hostname needed - USB connection)
                if not initialize_picoscope(None, chopper_freq):
                    show_error("Failed to connect to PicoScope.\n\n"
                             "Please check:\n"
                             "1. PicoScope is connected via USB\n"
                             "2. PicoSDK drivers are installed\n"
                             "3. Python picosdk package is installed (pip install picosdk)")
            except ValueError:
                show_error("Invalid frequency value. Please enter a number.")
        else:
            show_error("Chopper frequency is required.")

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