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
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
import serial
import serial.tools.list_ports
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk

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

# Function to display pop up error messages
def show_error(message):
    messagebox.showerror("Error", message)
    root.destroy()
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

# Find the COM port for the SR510 lock-in amplifier (connected with a USB to serial adaptor) and initialize the serial connection
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
        messagebox.showerror("Error", "Failed to sample phase response")
        return None, None

    print("Fitting sine wave to phase response...")
    fit_params = fit_sine(phases, signals)
    if fit_params is None:
        messagebox.showerror("Error", "Failed to fit sine wave to phase response")
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

    # Update the phase plot
    ax_phase.cla()
    ax_phase.plot(phase_x_values, phase_y_values, 'o', label='Measured')
    ax_phase.plot(phase_fit_x_values, phase_fit_y_values, '-', label='Fitted Sine')
    ax_phase.set_xlabel('Phase (degrees)', fontsize=12)
    ax_phase.set_ylabel('Signal (V)', fontsize=12)
    ax_phase.set_title(f'Phase Response and Sine Fit for Pixel {pixel_number}', fontsize=12)
    ax_phase.tick_params(axis='both', which='major', labelsize=12)
    ax_phase.legend()
    ax_phase.grid(True)
    fig_phase.tight_layout()  # Reapply to ensure fit
    fig_phase.subplots_adjust(bottom=0.15)  # Ensure label space
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
    # finally:
    #     ser.close()
    #     print("Serial connection closed.")
    return None

# Function to set the monochromator to 532 nm for alignment
def align_monochromator():
    print("Aligning monochromator...")
    usb_mono.SendCommand("filter 1", False)
    usb_mono.SendCommand("grating 1", False)
    usb_mono.SendCommand("gowave 532", False)
    usb_mono.SendCommand("shutter o", False)
    usb_mono.WaitForIdle()
    #messagebox.showinfo("Alignment", "Monochromator aligned to 532 nm with grating 1, filter 1, and shutter opened.")

def start_power_measurement():
    clear_power_plot()
    print("Starting light power measurement...")
    start_wavelength = float(start_wavelength_var.get())
    end_wavelength = float(end_wavelength_var.get())
    step_size = float(step_size_var.get())

    # Check if the start wavelength is less than 420 nm and set filter to 3 (no filter)
    if start_wavelength <= 420:
        usb_mono.SendCommand("filter 3", False)
        usb_mono.WaitForIdle()
        print("Setting filter to 3 (no filter).")
    
    # Second loop: Measure actual signal with shutter open
    print("Measuring actual signal...")
    usb_mono.SendCommand("shutter o", False)
    usb_mono.WaitForIdle()

    current_wavelength = start_wavelength
    while current_wavelength <= end_wavelength:
        if stop_thread.is_set():
            break

        # Check the wavelength and switch gratings accordingly
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
        time.sleep(0.2)  # Wait for the power reading to stabilize

        # Measure power 200 times and calculate the average
        power_values = []
        for _ in range(200):
            power = c_double()
            tlPM.measPower(byref(power), TLPM_DEFAULT_CHANNEL)
            power_values.append(power.value)
        average_power = (sum(power_values) / len(power_values)) * 2  # Multiply by 2 to account for the 50% duty cycle of the chopper

        power_x_values.append(confirmed_mono_wavelength_float)
        power_y_values.append(average_power)  
        power_y_values_microwatts = [average_power * 1e6 for average_power in power_y_values] # Plot in microwatts

        ax_power.plot(power_x_values, power_y_values_microwatts, '.-', color='#0077BB', label='Power Measurement')
        if not ax_power.get_legend():  # Add legend only once
            ax_power.legend()
        canvas_power.draw()

        current_wavelength += step_size
        root.update()

    usb_mono.SendCommand("shutter c", False)
    usb_mono.WaitForIdle() 

    # Save power data only if not stopped
    if not stop_thread.is_set() and power_x_values and power_y_values:
        cell_number = cell_number_var.get().strip()
        date = datetime.datetime.now().strftime("%Y_%m_%d")
        if not cell_number or not re.match(r'^(C60_\d+|\d+-\d+)$', cell_number):
            messagebox.showerror("Input Error", "Cell number must be in format C60_XX or XXXX-XX (e.g., C60_01, 2501-04).")
        else:
            file_name = f"{date}_power_cell{cell_number}.csv"
            file_path = filedialog.asksaveasfilename(
                initialfile=file_name,
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv")]
            )
            if file_path:
                with open(file_path, mode='w', newline='') as file:
                    writer = csv.writer(file)
                    writer.writerow(["Wavelength (nm)", "Power (W)"])
                    for x, y in zip(power_x_values, power_y_values):
                        writer.writerow([x, y])
                print(f"Power data saved to {file_path}")

    # Reset the Start/Stop button text and functionality
    start_power_button.config(text="Start Power Measurement", bg="#CCDDAA", command=toggle_power_measurement) 

    if stop_thread.is_set():
        print("Measurement stopped.")
    else:
        print("Measurement complete.")
        align_monochromator()

def start_current_measurement(pixel_number):
    # Create self-disappearing popup centered over current plot
    popup = tk.Toplevel(root)
    popup.title("Processing")
    popup.geometry("200x100")
    tk.Label(popup, text="Please Wait....", font=("Helvetica", 14)).pack(pady=20)
    popup.transient(root)
    popup.grab_set()
    # Center popup over current plot
    canvas_x = canvas_current.get_tk_widget().winfo_rootx()
    canvas_y = canvas_current.get_tk_widget().winfo_rooty()
    canvas_width = canvas_current.get_tk_widget().winfo_width()
    canvas_height = canvas_current.get_tk_widget().winfo_height()
    popup_x = canvas_x + (canvas_width - 200) // 2
    popup_y = canvas_y + (canvas_height - 100) // 2
    popup.geometry(f"200x100+{popup_x}+{popup_y}")
    popup.update()

    # Clear phase plot
    phase_x_values.clear()
    phase_y_values.clear()
    phase_fit_x_values.clear()
    phase_fit_y_values.clear()
    ax_phase.cla()
    configure_phase_plot(pixel_number)
    canvas_phase.draw()

    # Run phase adjustment in a separate thread
    def run_phase_adjustment():
        adjust_lockin_phase(pixel_number)
        root.after(0, popup.destroy)  # Close popup on main thread

    phase_thread = threading.Thread(target=run_phase_adjustment)
    phase_thread.start()
    phase_thread.join()  # Wait for phase adjustment to complete

    # Save phase data
    if phase_optimal is not None and phase_signal is not None and phase_r_squared is not None:
        cell_number = cell_number_var.get().strip()
        date = datetime.datetime.now().strftime("%Y_%m_%d")
        if not cell_number or not re.match(r'^(C60_\d+|\d+-\d+)$', cell_number):
            messagebox.showerror("Input Error", "Cell number must be in format C60_XX or XXXX-XX (e.g., C60_01, 2501-04).")
            return
        file_name = f"{date}_phase_cell{cell_number}.csv"
        file_path = filedialog.asksaveasfilename(
            initialfile=file_name,
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv")]
        )
        if file_path:
            # Create or update DataFrame
            if not os.path.exists(file_path):
                # Initialize DataFrame with 6 rows for pixels 1-6
                df = pd.DataFrame({
                    "Pixel #": [1, 2, 3, 4, 5, 6],
                    "Set Angle": [None, None, None, None, None, None],
                    "Signal": [None, None, None, None, None, None],
                    "R^2 Value": [None, None, None, None, None, None]
                })
            else:
                try:
                    # Read existing file
                    df = pd.read_csv(file_path)
                    # Check if it has the expected columns
                    if "Pixel #" not in df.columns:
                        # Handle legacy file (no pixel # column)
                        legacy_data = df[["set angle", "signal", "r-value"]].values
                        # Initialize new DataFrame with 6 rows
                        df = pd.DataFrame({
                            "Pixel #": [1, 2, 3, 4, 5, 6],
                            "Set Angle": [None, None, None, None, None, None],
                            "Signal": [None, None, None, None, None, None],
                            "R^2 Value": [None, None, None, None, None, None]
                        })
                        # Copy legacy data to corresponding rows
                        for i, row in enumerate(legacy_data[:6]):  # Limit to 6 rows
                            df.at[i, "Set Angle"] = row[0]
                            df.at[i, "Signal"] = row[1]
                            df.at[i, "R^2 Value"] = row[2]
                    else:
                        # Ensure 6 rows (fill with empty if needed)
                        existing_pixels = df["Pixel #"].tolist()
                        for i in range(1, 7):
                            if i not in existing_pixels:
                                df = pd.concat([df, pd.DataFrame({
                                    "Pixel #": [i],
                                    "Set Angle": [None],
                                    "Signal": [None],
                                    "R^2 Value": [None]
                                })], ignore_index=True)
                        df = df[df["Pixel #"].isin([1, 2, 3, 4, 5, 6])].sort_values("Pixel #").reset_index(drop=True)
                except Exception as e:
                    print(f"Error reading CSV: {e}")
                    # Fallback: Initialize new DataFrame
                    df = pd.DataFrame({
                        "Pixel #": [1, 2, 3, 4, 5, 6],
                        "Set Angle": [None, None, None, None, None, None],
                        "Signal": [None, None, None, None, None, None],
                        "R^2 Value": [None, None, None, None, None, None]
                    })

            # Update row for the current pixel with formatted values
            pixel_index = pixel_number - 1  # 0-based index
            df.at[pixel_index, "Set Angle"] = f"{phase_optimal:.2f}"
            df.at[pixel_index, "Signal"] = phase_signal
            df.at[pixel_index, "R^2 Value"] = f"{phase_r_squared:.4f}"

            # Save DataFrame back to file
            df.to_csv(file_path, index=False)
            print(f"Phase data for pixel {pixel_number} saved to {file_path}")

    # Start current measurement
    clear_current_plot(pixel_number)
    print("Starting photocell measurement...")
    start_wavelength = float(start_wavelength_var.get())
    end_wavelength = float(end_wavelength_var.get())
    step_size = float(step_size_var.get())

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

        output = read_lockin_status_and_keithley_output()
        if output is None:
            messagebox.showerror("Measurement Error", "Failed to read output from SR510.")
            return

        current_x_values.append(confirmed_mono_wavelength_float)
        current_y_values.append(output)
        current_y_values_nanoamps = [output * 1e9 for output in current_y_values]

        ax_current.plot(current_x_values, current_y_values_nanoamps, '.-', color='#0077BB')
        canvas_current.draw()

        current_wavelength += step_size
        root.update()

    usb_mono.SendCommand("shutter c", False)
    usb_mono.WaitForIdle()

    # Save current data only if not stopped
    if not stop_thread.is_set() and current_x_values and current_y_values:
        cell_number = cell_number_var.get().strip()
        date = datetime.datetime.now().strftime("%Y_%m_%d")
        if not cell_number or not re.match(r'^(C60_\d+|\d+-\d+)$', cell_number):
            messagebox.showerror("Input Error", "Cell number must be in format C60_XX or XXXX-XX (e.g., C60_01, 2501-04).")
        else:
            file_name = f"{date}_current_cell{cell_number}_pixel{pixel_number}.csv"
            file_path = filedialog.asksaveasfilename(
                initialfile=file_name,
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv")]
            )
            if file_path:
                with open(file_path, mode='w', newline='') as file:
                    writer = csv.writer(file)
                    writer.writerow(["Wavelength (nm)", "Current (A)"])
                    for x, y in zip(current_x_values, current_y_values):
                        writer.writerow([x, y])
                print(f"Current data saved to {file_path}")

    # Reset button
    start_current_button.config(text="Start Current Measurement", bg="#CCDDAA", command=toggle_current_measurement)

    if stop_thread.is_set():
        print("Measurement stopped.")
    else:
        print("Measurement complete.")
        align_monochromator()

# Function to start power measurement in a separate thread   
def measure_power_thread():
    global power_thread
    stop_thread.clear()
    power_thread = threading.Thread(target=start_power_measurement)
    power_thread.start()

# Function to measure current for a specific pixel number
def measure_current_thread(pixel_number):
    global current_thread
    stop_thread.clear()
    current_thread = threading.Thread(target=start_current_measurement, args=(pixel_number,))
    current_thread.start()

# Function to stop measurement threads
def stop_measurement():
    stop_thread.set()

# Function to toggle measurement state
def toggle_power_measurement():
    if start_power_button.config('text')[-1] == 'Start Power Measurement':
        measure_power_thread()
        start_power_button.config(text="Stop Power Measurement", bg="#FFCCCC", command=stop_measurement)
    else:
        stop_measurement()
        start_power_button.config(text="Start Power Measurement", bg="#CCDDAA", command=toggle_power_measurement)

# Function to toggle measurement state and request pixel number before current measurement starts
def toggle_current_measurement():
    global current_thread
    if start_current_button.config('text')[-1] == 'Start Current Measurement':
        # Prompt for pixel number
        pixel_number = simpledialog.askinteger("Pixel Selection", "Enter pixel number (1-6):", minvalue=1, maxvalue=6, parent=root)
        if pixel_number is None:  # User cancelled
            return
        stop_thread.clear()
        current_thread = threading.Thread(target=start_current_measurement, args=(pixel_number,))
        current_thread.start()
        start_current_button.config(text="Stop Current Measurement", bg="#FFCCCC", command=toggle_current_measurement)
    else:
        stop_thread.set()
        if current_thread and current_thread.is_alive():
            current_thread.join(timeout=1.0)
        start_current_button.config(text="Start Current Measurement", bg="#CCDDAA", command=toggle_current_measurement)

# Function to handle window close event
def on_close():
    global is_closing
    is_closing = True
    stop_thread.set()

    # Wait for threads to finish
    if 'power_thread' in globals() and power_thread and power_thread.is_alive():
        power_thread.join()
    if 'current_thread' in globals() and current_thread and current_thread.is_alive():
        current_thread.join()

    # Close any open resources
    try:
        if 'tlPM' in globals():
            tlPM.close()
        if 'keithley' in globals():
            keithley.close()
        if 'ser' in globals():
            ser.close()
    except Exception as e:
        print(f"Error closing resources: {e}")

    root.destroy()
    print("Application closed.")
    sys.exit()

# Function to configure the power plot
def configure_power_plot():
    ax_power.set_xlabel('Wavelength (nm)', fontsize=12)
    ax_power.set_ylabel(r'Power ($\mu$W)', fontsize=12)
    ax_power.set_title('Incident Light Power Measurements', fontsize=12)
    ax_power.tick_params(axis='both', which='major', labelsize=12)
    fig_power.tight_layout()  # Ensure layout fits labels
    fig_power.subplots_adjust(bottom=0.15)  # Adjust bottom margin

# Function to configure the current plot
def configure_current_plot(pixel_number):
    ax_current.set_xlabel('Wavelength (nm)', fontsize=12)
    ax_current.set_ylabel('Current (nA)', fontsize=12)
    ax_current.set_title(f'PV Current Measurements for Pixel {pixel_number}', fontsize=12)
    ax_current.tick_params(axis='both', which='major', labelsize=12)
    fig_current.tight_layout()  # Ensure layout fits labels
    fig_current.subplots_adjust(bottom=0.15)  # Adjust bottom margin

# Function to configure the phase plot
def configure_phase_plot(pixel_number):
    ax_phase.set_xlabel('Phase (degrees)', fontsize=12)
    ax_phase.set_ylabel('Signal (V)', fontsize=12)
    ax_phase.set_title(f'Phase Response and Sine Fit for Pixel {pixel_number}', fontsize=12)
    ax_phase.tick_params(axis='both', which='major', labelsize=12)
    fig_phase.tight_layout()  # Ensure layout fits labels
    fig_phase.subplots_adjust(bottom=0.15)  # Adjust bottom margin
    
# Function to clear the power plot
def clear_power_plot():
    ax_power.cla()  # Clear the axes
    power_x_values.clear()
    power_y_values.clear()
    configure_power_plot()
    canvas_power.draw()  # Redraw the canvas

# Function to clear the current plot
def clear_current_plot(pixel_number):
    ax_current.cla()  # Clear the axes
    current_x_values.clear()
    current_y_values.clear()
    configure_current_plot(pixel_number)
    canvas_current.draw()  # Redraw the canvas

# Create the main GUI window
root = tk.Tk()
root.title("PHYS 2150 EQE Measurement")

# Create frames for the plots
plot_frame_power = tk.Frame(root)
plot_frame_power.grid(row=4, column=0, padx=20, pady=5, sticky="nsew")  # Reduced pady
plot_frame_current = tk.Frame(root)
plot_frame_current.grid(row=4, column=1, padx=20, pady=5, sticky="nsew")  # Reduced pady
plot_frame_phase = tk.Frame(root)
plot_frame_phase.grid(row=4, column=2, padx=20, pady=5, sticky="nsew")  # Reduced pady

# Create the matplotlib figure and axes for power measurements with adjusted size
fig_power, ax_power = plt.subplots(figsize=(5.5, 4.5))  # Increased figsize
fig_power.tight_layout()  # Apply tight_layout at initialization
fig_power.subplots_adjust(bottom=0.15)  # Adjust bottom margin for label
configure_power_plot()
canvas_power = FigureCanvasTkAgg(fig_power, master=plot_frame_power)
canvas_power.draw()
canvas_power.get_tk_widget().grid(row=0, column=0, sticky="nsew")

# Create the matplotlib figure and axes for current measurements with adjusted size
fig_current, ax_current = plt.subplots(figsize=(5.5, 4.5))  # Increased figsize
fig_current.tight_layout()  # Apply tight_layout at initialization
fig_current.subplots_adjust(bottom=0.15)  # Adjust bottom margin for label
configure_current_plot(pixel_number)
canvas_current = FigureCanvasTkAgg(fig_current, master=plot_frame_current)
canvas_current.draw()
canvas_current.get_tk_widget().grid(row=0, column=0, sticky="nsew")

# Create the matplotlib figure and axes for phase measurements with adjusted size
fig_phase, ax_phase = plt.subplots(figsize=(5.5, 4.5))  # Increased figsize
fig_phase.tight_layout()  # Apply tight_layout at initialization
fig_phase.subplots_adjust(bottom=0.15)  # Adjust bottom margin for label
configure_phase_plot(pixel_number)
canvas_phase = FigureCanvasTkAgg(fig_phase, master=plot_frame_phase)
canvas_phase.draw()
canvas_phase.get_tk_widget().grid(row=0, column=0, sticky="nsew")

# Create toolbar frames for each plot
toolbar_frame_power = tk.Frame(root)
toolbar_frame_power.grid(row=5, column=0, sticky="ew", padx=20, pady=0)
toolbar_power = NavigationToolbar2Tk(canvas_power, toolbar_frame_power)
toolbar_power.update()

toolbar_frame_current = tk.Frame(root)
toolbar_frame_current.grid(row=5, column=1, sticky="ew", padx=20, pady=0)
toolbar_current = NavigationToolbar2Tk(canvas_current, toolbar_frame_current)
toolbar_current.update()

toolbar_frame_phase = tk.Frame(root)
toolbar_frame_phase.grid(row=5, column=2, sticky="ew", padx=20, pady=0)
toolbar_phase = NavigationToolbar2Tk(canvas_phase, toolbar_frame_phase)
toolbar_phase.update()

# Create button frames to center buttons under plots
button_frame_power = tk.Frame(root)
button_frame_power.grid(row=6, column=0, sticky="nsew", padx=20, pady=5)
button_frame_current = tk.Frame(root)
button_frame_current.grid(row=6, column=1, sticky="nsew", padx=20, pady=5)
button_frame_phase = tk.Frame(root)  # Placeholder frame for phase plot
button_frame_phase.grid(row=6, column=2, sticky="nsew", padx=20, pady=5)

# Add the start buttons for the measurements, centered in their frames
start_power_button = tk.Button(button_frame_power, text="Start Power Measurement", font=("Helvetica", 14), bg="#CCDDAA", command=toggle_power_measurement)
start_power_button.pack(anchor="center")

start_current_button = tk.Button(button_frame_current, text="Start Current Measurement", font=("Helvetica", 14), bg="#CCDDAA", command=toggle_current_measurement)
start_current_button.pack(anchor="center")

# Make the canvas and frames expand and fill the space
plot_frame_power.grid_rowconfigure(0, weight=1)
plot_frame_power.grid_columnconfigure(0, weight=1)
plot_frame_current.grid_rowconfigure(0, weight=1)
plot_frame_current.grid_columnconfigure(0, weight=1)
plot_frame_phase.grid_rowconfigure(0, weight=1)
plot_frame_phase.grid_columnconfigure(0, weight=1)

root.grid_rowconfigure(4, weight=1)
root.grid_rowconfigure(5, weight=0)
root.grid_rowconfigure(6, weight=0)
root.grid_columnconfigure(0, weight=1)
root.grid_columnconfigure(1, weight=1)
root.grid_columnconfigure(2, weight=1)

# Create the input fields
start_wavelength_var = tk.StringVar(value="350")
end_wavelength_var = tk.StringVar(value="850")
step_size_var = tk.StringVar(value="10")

# Add input fields for cell number in the third column
input_frame_third = tk.Frame(root)
input_frame_third.grid(row=1, column=2, padx=10, pady=10)

tk.Label(input_frame_third, text="Cell Number:", font=("Helvetica", 14)).grid(row=0, column=0, sticky='w')
cell_number_var = tk.StringVar(value="C60_01")  # Default cell number
tk.Entry(input_frame_third, textvariable=cell_number_var, font=("Helvetica", 14)).grid(row=0, column=1, sticky='w')

# Create a frame to hold the labels and entries
input_frame = tk.Frame(root)
input_frame.grid(row=1, column=0, padx=10, pady=10)

# Place the labels and entries inside the frame
tk.Label(input_frame, text="Start Wavelength (nm):", font=("Helvetica", 14)).grid(row=0, column=0, sticky='w')
tk.Entry(input_frame, textvariable=start_wavelength_var, font=("Helvetica", 14)).grid(row=0, column=1, sticky='w')

tk.Label(input_frame, text="End Wavelength (nm):", font=("Helvetica", 14)).grid(row=1, column=0, sticky='w')
tk.Entry(input_frame, textvariable=end_wavelength_var, font=("Helvetica", 14)).grid(row=1, column=1, sticky='w')

tk.Label(input_frame, text="Step Size (nm):", font=("Helvetica", 14)).grid(row=2, column=0, sticky='w')
tk.Entry(input_frame, textvariable=step_size_var, font=("Helvetica", 14)).grid(row=2, column=1, sticky='w')

# Add the align button in the center column above the current plot
align_button = tk.Button(root, text="Enable Green Alignment Dot", font=("Helvetica", 14), command=align_monochromator)
align_button.grid(row=1, column=1, padx=20, pady=10)

def show_cell_number_popup():
    popup = tk.Toplevel(root)
    popup.title("Enter Cell Number")
    popup.geometry("340x150")  # Wider popup
    # Center popup over main window
    root_x = root.winfo_rootx()
    root_y = root.winfo_rooty()
    root_width = root.winfo_width()
    root_height = root.winfo_height()
    popup_x = root_x + (root_width - 340) // 2
    popup_y = root_y + (root_height - 150) // 2
    popup.geometry(f"340x150+{popup_x}+{popup_y}")
    popup.transient(root)
    popup.grab_set()

    tk.Label(popup, text="Enter Cell Number (e.g., C60_01, 2501-04):", font=("Helvetica", 12)).pack(pady=10)
    entry = tk.Entry(popup, font=("Helvetica", 12))
    entry.pack(pady=10)
    entry.focus_set()

    def on_ok():
        cell_number = entry.get().strip()
        if cell_number and re.match(r'^(C60_\d+|\d+-\d+)$', cell_number):
            cell_number_var.set(cell_number)
            popup.destroy()
        else:
            messagebox.showwarning("Invalid Input", "Cell number must be in format C60_XX or XXXX-XX (e.g., C60_01, 2501-04).", parent=popup)

    def prevent_close():
        messagebox.showwarning("Invalid Input", "Cell number must be in format C60_XX or XXXX-XX (e.g., C60_01, 2501-04).", parent=popup)

    tk.Button(popup, text="OK", font=("Helvetica", 12), command=on_ok).pack(pady=10)
    popup.bind('<Return>', lambda event: on_ok())  # Allow Enter key to submit
    popup.bind('<Escape>', lambda event: prevent_close())  # Prevent Esc from closing
    popup.protocol("WM_DELETE_WINDOW", prevent_close)  # Prevent close button from closing

# Trigger cell number popup after 1 second
root.after(1000, show_cell_number_popup)

# Bind the on_close function to the window's close event
root.protocol("WM_DELETE_WINDOW", on_close)

root.mainloop()