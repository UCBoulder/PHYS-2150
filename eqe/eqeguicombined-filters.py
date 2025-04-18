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
import datetime
import threading
import numpy as np
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
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

# # Define the correction factors for each serial number
# correction_factors = {
#     "130B5203": 0.37, # EQE2
#     "130B5201": 0.44, # EQE3
#     "130B5202": 0.45 # EQE1
# }

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
# Modify the adjust_lockin_phase function
def adjust_lockin_phase():
    def read_output():
        ser.write('Q\r'.encode())
        time.sleep(0.5)
        return read_lockin_response()

    def set_phase(phase):
        ser.write(f'P {phase}\r'.encode())
        wait_for_lockin_ready()

    def sample_phase_response():
        phases = np.linspace(0, 360, 37)  # Sample 37 points (0 to 360 degrees inclusive)
        signals = []
        
        for phase in phases:
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
        optimal_phase = (optimal_phase + 180) % 360
        print(f"Signal negative, adjusting phase to {optimal_phase:.1f}°")
        set_phase(optimal_phase)
        final_signal = float(read_output())

    message = f"Set phase to {optimal_phase:.1f}° with signal value: {final_signal:.6f}"
    print(message)
    messagebox.showinfo("Phase Adjustment", message)

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
    ax_phase.set_xlabel('Phase (degrees)')
    ax_phase.set_ylabel('Signal (V)')
    ax_phase.set_title('Phase Response and Sine Fit')
    ax_phase.legend()
    ax_phase.grid(True)
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
        power_y_values.append(average_power )  
        power_y_values_microwatts = [average_power * 1e6 for average_power in power_y_values] # Plot in microwatts

        ax_power.plot(power_x_values, power_y_values_microwatts, '.-', color='#0077BB', label='Power Measurement')

        fig_power.tight_layout()
        canvas_power.draw()

        current_wavelength += step_size
        root.update()

    usb_mono.SendCommand("shutter c", False)
    usb_mono.WaitForIdle() 

    # Reset the Start/Stop button text and functionality
    start_power_button.config(text="Start Power Measurement", bg="#CCDDAA", command=toggle_power_measurement) 

    if stop_thread.is_set():
        print("Measurement stopped.")
    else:
        print("Measurement complete.")
        align_monochromator()

def start_current_measurement():
    clear_current_plot()
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
        current_y_values_nanoamps = [output * 1e9 for output in current_y_values] # Plot in nanoamps


        ax_current.plot(current_x_values, current_y_values_nanoamps, '.-', color='#0077BB')

        fig_current.tight_layout()
        canvas_current.draw()

        current_wavelength += step_size
        root.update()

    usb_mono.SendCommand("shutter c", False)
    usb_mono.WaitForIdle()

    # Reset the Start/Stop button text and functionality
    start_current_button.config(text="Start Current Measurement", bg="#CCDDAA", command=toggle_current_measurement) 

    if stop_thread.is_set():
        print("Measurement stopped.")
    else:
        print("Measurement complete.")
        align_monochromator()

def save_power_data():
    if not power_x_values or not power_y_values:
        messagebox.showerror("No Data", "No power data available to save.")
        return

    cell_number = cell_number_var.get().strip()
    date = datetime.datetime.now().strftime("%Y_%m_%d")
    
    # Validate inputs
    if not cell_number:
        messagebox.showerror("Input Error", "Cell number cannot be empty.")
        return
    
    file_name = f"{date}_power_cell{cell_number}.csv"
    file_path = filedialog.asksaveasfilename(
        initialfile=file_name,
        defaultextension=".csv",
        filetypes=[("CSV files", "*.csv")]
    )
    if not file_path:
        return

    with open(file_path, mode='w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(["Wavelength (nm)", "Power (W)"])
        for x, y in zip(power_x_values, power_y_values):
            writer.writerow([x, y])

    messagebox.showinfo("Data Saved", f"Power data saved to {file_path}")
    
def save_current_data():
    if not current_x_values or not current_y_values:
        messagebox.showerror("No Data", "No current data available to save.")
        return

    cell_number = cell_number_var.get().strip()
    pixel_number = pixel_number_var.get().strip()
    date = datetime.datetime.now().strftime("%Y_%m_%d")
    
    # Validate inputs
    if not cell_number:
        messagebox.showerror("Input Error", "Cell number cannot be empty.")
        return
    if not pixel_number or pixel_number not in [str(i) for i in range(1, 7)]:
        messagebox.showerror("Input Error", "Pixel number must be 1-6.")
        return
    
    file_name = f"{date}_current_cell{cell_number}_pixel{pixel_number}.csv"
    file_path = filedialog.asksaveasfilename(
        initialfile=file_name,
        defaultextension=".csv",
        filetypes=[("CSV files", "*.csv")]
    )
    if not file_path:
        return

    with open(file_path, mode='w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(["Wavelength (nm)", "Current (A)"])
        for x, y in zip(current_x_values, current_y_values):
            writer.writerow([x, y])

    messagebox.showinfo("Data Saved", f"Current data saved to {file_path}")

def measure_power_thread():
    global power_thread

    stop_thread.clear()
    #measure_button.config(text="Stop Measurement", command=stop_measurements)

    power_thread = threading.Thread(target=start_power_measurement)

    power_thread.start()

def measure_current_thread():
    global current_thread

    stop_thread.clear()
    #measure_button.config(text="Stop Measurement", command=stop_measurements)

    current_thread = threading.Thread(target=start_current_measurement)

    current_thread.start()

def stop_measurement():
    stop_thread.set()
    #power_thread.join()
    #current_thread.join()
    #measure_button.config(text="Start Measurement", command=start_measurements)

# Function to toggle measurement state
def toggle_power_measurement():
    if start_power_button.config('text')[-1] == 'Start Power Measurement':
        measure_power_thread()
        start_power_button.config(text="Stop Power Measurement", bg="#FFCCCC", command=stop_measurement)
    else:
        stop_measurement()
        start_power_button.config(text="Start Power Measurement", bg="#CCDDAA", command=toggle_power_measurement)

# Function to toggle measurement state
def toggle_current_measurement():
    if start_current_button.config('text')[-1] == 'Start Current Measurement':
        measure_current_thread()
        start_current_button.config(text="Stop Current Measurement", bg="#FFCCCC", command=stop_measurement)
    else:
        stop_measurement()
        start_current_button.config(text="Start Current Measurement", bg="#CCDDAA", command=toggle_current_measurement)





def on_close():
    is_closing = True
    # Set the stop event to stop any running threads
    stop_thread.set()

    # Wait for threads to finish
    if 'power_thread' in globals() and power_thread.is_alive():
        power_thread.join()
    if 'current_thread' in globals() and current_thread.is_alive():
        current_thread.join()

    # Close any open resources
    try:
        if 'tlPM' in globals():
            tlPM.close()
        if 'keithley' in globals():
            keithley.close()
        # No close method for usb_mono, so we skip it
        if 'ser' in globals():
            ser.close()
    except Exception as e:
        print(f"Error closing resources: {e}")

    # Destroy the Tkinter root window
    root.destroy()
    print("Application closed.")
    sys.exit()  # Explicitly exit the application

# def on_close():
#     global is_closing
#     is_closing = True
#     print("Closing application")
#     stop_thread.set()
#     if 'device' in globals():
#         try:
#             device.write("OUTP OFF")  # Disable the output
#             device.close()
#         except Exception as e:
#             print(f"Error closing device: {e}")
#     if 'rm' in globals():
#         rm.close()
#     root.destroy()  # Ensure the GUI is properly closed
#     sys.exit()  # Explicitly exit the application

# Function to configure the power plot
def configure_power_plot():
    ax_power.set_xlabel('Wavelength (nm)', fontsize=12)
    ax_power.set_ylabel(r'Power ($\mu$W)', fontsize=12)
    ax_power.set_title('Incident Light Power Measurements', fontsize=12)
    ax_power.tick_params(axis='both', which='major', labelsize=12)

# Function to configure the current plot
def configure_current_plot():
    ax_current.set_xlabel('Wavelength (nm)', fontsize=12)
    ax_current.set_ylabel('Current (nA)', fontsize=12)
    ax_current.set_title('PV Current Measurements', fontsize=12)
    ax_current.tick_params(axis='both', which='major', labelsize=12)

# Function to clear the power plot
def clear_power_plot():
    ax_power.cla()  # Clear the axes
    power_x_values.clear()
    power_y_values.clear()
    configure_power_plot()
    canvas_power.draw()  # Redraw the canvas

# Function to clear the current plot
def clear_current_plot():
    ax_current.cla()  # Clear the axes
    current_x_values.clear()
    current_y_values.clear()
    configure_current_plot()
    canvas_current.draw()  # Redraw the canvas

# Create the main GUI window
root = tk.Tk()
root.title("PHYS 2150 EQE Measurement")

# Create frames for the plots
plot_frame_power = tk.Frame(root)
plot_frame_power.grid(row=4, column=0, padx=20, pady=10, sticky="nsew")
plot_frame_current = tk.Frame(root)
plot_frame_current.grid(row=4, column=1, padx=20, pady=10, sticky="nsew")

# Create the matplotlib figure and axes for power measurements
fig_power, ax_power = plt.subplots()
configure_power_plot()
canvas_power = FigureCanvasTkAgg(fig_power, master=plot_frame_power)
canvas_power.draw()
canvas_power.get_tk_widget().grid(row=0, column=0, sticky="nsew")

# Create the matplotlib figure and axes for current measurements
fig_current, ax_current = plt.subplots()
configure_current_plot()
canvas_current = FigureCanvasTkAgg(fig_current, master=plot_frame_current)
canvas_current.draw()
canvas_current.get_tk_widget().grid(row=0, column=0, sticky="nsew")

# Create a toolbar for the plot
toolbar_frame_power = tk.Frame(root)
toolbar_frame_current = tk.Frame(root)
toolbar_frame_power.grid(row=5, column=0, columnspan=2, sticky="ew", padx=20)
toolbar_frame_current.grid(row=5, column=1, columnspan=2, sticky="ew", padx=20)
toolbar_current = NavigationToolbar2Tk(canvas_current, toolbar_frame_current)
toolbar_power = NavigationToolbar2Tk(canvas_power, toolbar_frame_power)
toolbar_current.update()
toolbar_power.update()

# Make the canvas and toolbar_frame expand and fill the space
plot_frame_power.grid_rowconfigure(0, weight=1)
plot_frame_power.grid_columnconfigure(0, weight=1)
plot_frame_current.grid_rowconfigure(0, weight=1)
plot_frame_current.grid_columnconfigure(0, weight=1)

root.grid_rowconfigure(4, weight=1)
root.grid_rowconfigure(5, weight=0)
root.grid_columnconfigure(0, weight=1)
root.grid_columnconfigure(1, weight=1)

# Add phase plot setup
plot_frame_phase = tk.Frame(root)
plot_frame_phase.grid(row=4, column=2, padx=20, pady=10, sticky="nsew")
fig_phase, ax_phase = plt.subplots()
ax_phase.set_xlabel('Phase (degrees)', fontsize=12)
ax_phase.set_ylabel('Signal (V)', fontsize=12)
ax_phase.set_title('Phase Response and Sine Fit', fontsize=12)
ax_phase.tick_params(axis='both', which='major', labelsize=12)
canvas_phase = FigureCanvasTkAgg(fig_phase, master=plot_frame_phase)
canvas_phase.draw()
canvas_phase.get_tk_widget().grid(row=0, column=0, sticky="nsew")

toolbar_frame_phase = tk.Frame(root)
toolbar_frame_phase.grid(row=5, column=2, sticky="ew", padx=20)
toolbar_phase = NavigationToolbar2Tk(canvas_phase, toolbar_frame_phase)
toolbar_phase.update()

plot_frame_phase.grid_rowconfigure(0, weight=1)
plot_frame_phase.grid_columnconfigure(0, weight=1)
root.grid_columnconfigure(2, weight=1)

# Create the input fields
start_wavelength_var = tk.StringVar(value="350")
end_wavelength_var = tk.StringVar(value="850")
step_size_var = tk.StringVar(value="10")

# Add input fields for cell number and pixel number in the third column
input_frame_third = tk.Frame(root)
input_frame_third.grid(row=1, column=2, padx=10, pady=10)

tk.Label(input_frame_third, text="Cell Number:", font=("Helvetica", 14)).grid(row=0, column=0, sticky='w')
cell_number_var = tk.StringVar(value="C60_01")  # Default cell number
tk.Entry(input_frame_third, textvariable=cell_number_var, font=("Helvetica", 14)).grid(row=0, column=1, sticky='w')

tk.Label(input_frame_third, text="Pixel Number:", font=("Helvetica", 14)).grid(row=1, column=0, sticky='w')
pixel_number_var = tk.StringVar(value="1")  # Default pixel
pixel_dropdown = ttk.Combobox(input_frame_third, textvariable=pixel_number_var, values=[str(i) for i in range(1, 7)], state="readonly", font=("Helvetica", 14))
pixel_dropdown.grid(row=1, column=1, sticky='w')

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

# Add the start and save buttons for the power measurements in the left column below the power plot
start_power_button = tk.Button(root, text="Start Power Measurement", font=("Helvetica", 14), bg="#CCDDAA", command=toggle_power_measurement)
start_power_button.grid(row=5, column=0, padx=20, sticky='e')      

save_power_button = tk.Button(root, text="Save Power Data", font=("Helvetica", 14), command=save_power_data)
save_power_button.grid(row=6, column=0, padx=20, pady=10, sticky='e')

# Add the clear button for the power measurements plot
clear_power_button = tk.Button(root, text="Clear Power Data", font=("Helvetica", 14), command=clear_power_plot)
clear_power_button.grid(row=6, column=0, padx=20, pady=10, sticky='w')

# Add the align and phase buttons in the right column above the current plot
align_button = tk.Button(root, text="Enable Green Alignment Dot", font=("Helvetica", 14), command=align_monochromator)
align_button.grid(row=2, column=1, padx=20, pady=10, sticky='e')

adjust_lockin_phase_button = tk.Button(root, text="Adjust Lock-in Phase", font=("Helvetica", 14), command=adjust_lockin_phase)
adjust_lockin_phase_button.grid(row=2, column=1, padx=20, pady=10, sticky='w')

# Add the start and save buttons for the current measurements in the right column below the current plot
start_current_button = tk.Button(root, text="Start Current Measurement", font=("Helvetica", 14), bg="#CCDDAA", command=toggle_current_measurement)
start_current_button.grid(row=5, column=1, padx=20, sticky='e')

save_current_button = tk.Button(root, text="Save Current Data", font=("Helvetica", 14), command=save_current_data)
save_current_button.grid(row=6, column=1, padx=20, pady=10, sticky='e')

# Add the clear button for the current measurements plot
clear_current_button = tk.Button(root, text="Clear Current Data", font=("Helvetica", 14), command=clear_current_plot)
clear_current_button.grid(row=6, column=1, padx=20, pady=10, sticky='w')

# Bind the on_close function to the window's close event
root.protocol("WM_DELETE_WINDOW", on_close)

root.mainloop()