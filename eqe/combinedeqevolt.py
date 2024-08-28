import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import numpy as np
import pandas as pd
import time
import sys
import warnings
import pyvisa as visa
import csv
from cornerstone_mono import Cornerstone_Mono
from TLPMX import TLPMX, TLPM_DEFAULT_CHANNEL
from ctypes import c_uint32, create_string_buffer, c_bool, c_double, byref
import serial
import serial.tools.list_ports

# Constants
BAUDRATE = 19200
PARITY = serial.PARITY_ODD
STOPBITS = serial.STOPBITS_TWO
BYTESIZE = serial.EIGHTBITS
TIMEOUT = 2
SENSITIVITY_COMMAND = 'G 23\r'
PHASE_INCREMENT = 45
PHASE_THRESHOLD = 0.0005
POWER_MEASUREMENTS = 50

# Initialize the VISA resource manager
rm = visa.ResourceManager()
warnings.simplefilter("ignore")

# Initialize Thorlabs Power Meter
tlPM = TLPMX()
deviceCount = c_uint32()
tlPM.findRsrc(byref(deviceCount))
resourceName = create_string_buffer(1024)
tlPM.getRsrcName(0, resourceName)
tlPM.open(resourceName, c_bool(True), c_bool(True))

# Use the correct resource string for the Keithley 2110
resources = rm.list_resources()
keithley_resource = None
for resource in resources:
    if '2110' in resource:
        keithley_resource = resource
        break

if keithley_resource is None:
    print("Keithley 2110 not found. Please check the connection.")
    sys.exit()

keithley = rm.open_resource(keithley_resource)

# Initilize Monochromator
usb_mono = Cornerstone_Mono(rm, rem_ifc="usb", timeout_msec=29000)

# Find the COM port for the SR510 lock-in amplifier and initialize the serial connection
def find_com_port():
    ports = serial.tools.list_ports.comports()
    for port in ports:
        if "Prolific PL2303GT USB Serial COM Port" in port.description:
            return port.device
    raise Exception("COM port not found")
ser = serial.Serial(
    port=find_com_port(),
    baudrate=BAUDRATE,
    parity=PARITY,
    stopbits=STOPBITS,
    bytesize=BYTESIZE,
    timeout=TIMEOUT
)

def read_response():
    response = ""
    while True:
        char = ser.read().decode()
        response += char
        if char == '\r':
            break
    return response.strip()

def wait_for_ready():
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

def set_initial_parameters():
    ser.write(SENSITIVITY_COMMAND.encode())
    wait_for_ready()

def adjust_phase():
    def read_output():
        ser.write('Q\r'.encode())
        time.sleep(0.5)
        return read_response()

    def set_phase(phase):
        phase_command = f'P {phase}\r'
        ser.write(phase_command.encode())
        wait_for_ready()

    def verify_phase(phase):
        set_phase(phase)
        output_response = read_output()
        print(f"Phase: {normalize_phase_angle(phase)}, Output response: {output_response}")
        try:
            signal_value = float(output_response)
            return abs(signal_value) <= PHASE_THRESHOLD
        except ValueError as e:
            print(f"Error parsing output response: {e}")
            return False
        
    def normalize_phase_angle(phase):
        phase = phase % 360
        if phase > 180:
            phase -= 360
        return f"{phase:.1f}"


    usb_mono.SendCommand("grating 1", False)
    usb_mono.WaitForIdle()
    usb_mono.SendCommand("gowave 532", False)
    usb_mono.WaitForIdle()
    usb_mono.SendCommand("shutter o", False)
    usb_mono.WaitForIdle()

    ser.write('P\r'.encode())
    current_phase = float(read_response())
    print(f"Current phase: {normalize_phase_angle(current_phase)}")

    increment = PHASE_INCREMENT
    best_phase = current_phase
    min_output = float('inf')

    while increment >= 0.1:
        for direction in [-1, 1]:
            new_phase = (best_phase + direction * increment) % 360
            set_phase(new_phase)
            output_response = read_output()
            print(f"Phase: {normalize_phase_angle(new_phase)}, Output response: {output_response}")

            try:
                signal_value = float(output_response)
                if abs(signal_value) < abs(min_output):
                    min_output = signal_value
                    best_phase = new_phase
            except ValueError as e:
                print(f"Error parsing output response: {e}")

        increment /= 2

    print(f"Minimized output at phase: {normalize_phase_angle(best_phase)} with signal value: {min_output}")

    if min_output < 0:
        best_phase = (best_phase + 180) % 360
        set_phase(best_phase)
        print(f"Adjusted phase to {normalize_phase_angle(best_phase)} degrees to ensure positive output.")

    while not verify_phase((best_phase + 180) % 360):
        print(f"Phase {normalize_phase_angle(best_phase)} does not meet the condition at 180 degrees.")
        increment = PHASE_INCREMENT
        while increment >= 0.1:
            for direction in [-1, 1]:
                new_phase = (best_phase + direction * increment) % 360
                set_phase(new_phase)
                output_response = read_output()
                print(f"Phase: {normalize_phase_angle(new_phase)}, Output response: {output_response}")

                try:
                    signal_value = float(output_response)
                    if abs(signal_value) < abs(min_output):
                        min_output = signal_value
                        best_phase = new_phase
                except ValueError as e:
                    print(f"Error parsing output response: {e}")

            increment /= 2

        print(f"Minimized output at phase: {normalize_phase_angle(best_phase)} with signal value: {min_output}")

        if min_output < 0:
            best_phase = (best_phase + 180) % 360
            set_phase(best_phase)
            print(f"Adjusted phase to {normalize_phase_angle(best_phase)} degrees to ensure positive output.")

    print(f"Phase {normalize_phase_angle(best_phase)} and {normalize_phase_angle(best_phase + 180)} both meet the condition.")
    for offset in [90, 270]:
        phase_offset = (best_phase + offset) % 360
        set_phase(phase_offset)
        output_response = read_output()
        print(f"Phase: {normalize_phase_angle(phase_offset)}, Output response: {output_response}")

        try:
            signal_value = float(output_response)
            if signal_value > 0:
                print(f"Set phase to {normalize_phase_angle(phase_offset)} degrees with positive signal value: {signal_value}")
                messagebox.showinfo("Phase Adjustment", f"Set phase to {normalize_phase_angle(phase_offset)} degrees with positive signal value: {signal_value}")
                return best_phase, min_output
        except ValueError as e:
            print(f"Error parsing output response: {e}")

    return best_phase, min_output

def send_command_to_lockin(command):
    ser.write(f"{command}\r".encode())
    return read_response()

def parse_sensitivity_response(response):
    sensitivity_map = {
        1: 10e-9, 2: 20e-9, 3: 50e-9, 4: 100e-9, 5: 200e-9, 6: 500e-9,
        7: 1e-6, 8: 2e-6, 9: 5e-6, 10: 10e-6, 11: 20e-6, 12: 50e-6,
        13: 100e-6, 14: 200e-6, 15: 500e-6, 16: 1e-3, 17: 2e-3, 18: 5e-3,
        19: 10e-3, 20: 20e-3, 21: 50e-3, 22: 100e-3, 23: 200e-3, 24: 500e-3
    }
    sensitivity_index = int(response.strip())
    return sensitivity_map.get(sensitivity_index, 1)  # Default to 1 if not found

def parse_voltage_response(response):
    return float(response.strip())

def read_lockin_status_and_output():
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
                            for _ in range(50):
                                voltage = float(keithley.query(":READ?"))
                                voltage_readings.append(voltage)
                            average_voltage = sum(voltage_readings) / len(voltage_readings)
                            print(f"Average voltage: {average_voltage}")
                            
                            if average_voltage > 8:
                                print("Average voltage > 10, increasing sensitivity...")
                                ser.write('K 22\r'.encode())
                                print("Sent command to increase sensitivity.")
                                print("Waiting 5 seconds after increasing sensitivity.")
                                time.sleep(5)  # Wait for the sensitivity change to take effect
                                break  # Break out of the inner while loop to re-read the status
                            # elif average_voltage < 2:
                            #     print("Average voltage < 2, decreasing sensitivity...")
                            #     ser.write('K 23\r'.encode())
                            #     print("Sent command to decrease sensitivity.")
                            #     time.sleep(1)  # Wait for the sensitivity change to take effect
                            #     print("Waited 1 second after decreasing sensitivity.")
                            #     break  # Break out of the inner while loop to re-read the status
                            
                            adjusted_voltage = average_voltage * sensitivity_value
                            print(f"Adjusted Voltage: {adjusted_voltage}")
                            current = adjusted_voltage

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
    finally:
        ser.close()
        print("Serial connection closed.")
    return None

def align_monochromator():
    print("Aligning monochromator...")
    usb_mono.SendCommand("grating 1", False)
    usb_mono.SendCommand("gowave 532", False)
    usb_mono.SendCommand("shutter o", False)
    usb_mono.WaitForIdle()
    messagebox.showinfo("Alignment", "Monochromator aligned to 532 nm with grating 1 and shutter opened.")

def start_power_measurement():
    print("Starting light power measurement...")
    start_wavelength = float(start_wavelength_var.get())
    end_wavelength = float(end_wavelength_var.get())
    step_size = float(step_size_var.get())

    # Check if the start wavelength is less than 400 nm and prompt the user
    if start_wavelength <= 420:
        messagebox.showinfo("Check Filters", "Please ensure no filters are installed.")
    
    global power_x_values, power_y_values
    power_x_values = []
    power_y_values = []

    # # First loop: Measure background light with shutter closed
    # print("Measuring background light...")
    # background_y_values = []
    # wavelengths = []

    # current_wavelength = start_wavelength
    # usb_mono.SendCommand("shutter c", False)
    # while current_wavelength <= end_wavelength:
    #     tlPM.setWavelength(c_double(current_wavelength), TLPM_DEFAULT_CHANNEL)
    #     time.sleep(0.2)  # Wait for the power reading to stabilize

    #     # Measure power 50 times and calculate the average
    #     power_values = []
    #     for _ in range(50):
    #         power = c_double()
    #         tlPM.measPower(byref(power), TLPM_DEFAULT_CHANNEL)
    #         power_values.append(power.value)
    #     average_power = sum(power_values) / len(power_values)

    #     background_y_values.append(average_power)
    #     wavelengths.append(current_wavelength)
    #     print(f"Background Light at {current_wavelength} nm: {average_power} W")
    #     current_wavelength += step_size

    # # Create a DataFrame and write to CSV
    # background_data = pd.DataFrame({
    #     'Wavelength (nm)': wavelengths,
    #     'Background Light (W)': background_y_values
    # })

    # background_data.to_csv('background_light_measurements.csv', index=False)
    # print("Background light measurements saved to 'background_light_measurements.csv'")

    # Second loop: Measure actual signal with shutter open
    print("Measuring actual signal...")
    usb_mono.SendCommand("shutter o", False)
    usb_mono.WaitForIdle()

    current_wavelength = start_wavelength
    while current_wavelength <= end_wavelength:

        # Check the wavelength and switch gratings accordingly
        if current_wavelength < 685:
            usb_mono.SendCommand("grating 1", False)
        else:
            usb_mono.SendCommand("grating 2", False)
            
        usb_mono.SendCommand(f"gowave {current_wavelength}", False)
        usb_mono.WaitForIdle()

        # Prompt the user to install the 400 nm filter
        print(f"Current Wavelength: {current_wavelength}")
        if current_wavelength > 420 and current_wavelength <= 420 + step_size:
            messagebox.showinfo("Install Filter", "Please install the 400 nm filter and click OK to proceed.")
        
        # Prompt the user to install the 780 nm filter
        if current_wavelength > 800 and current_wavelength <= 800 + step_size:
            messagebox.showinfo("Install Filter", "Please install the 780 nm filter and click OK to proceed.")

        confirmed_mono_wavelength = usb_mono.GetQueryResponse("wave?")
        confirmed_mono_wavelength_float = float(confirmed_mono_wavelength)
        tlPM.setWavelength(c_double(confirmed_mono_wavelength_float), TLPM_DEFAULT_CHANNEL)
        time.sleep(0.2)  # Wait for the power reading to stabilize

        # Measure power 50 times and calculate the average
        power_values = []
        for _ in range(200):
            power = c_double()
            tlPM.measPower(byref(power), TLPM_DEFAULT_CHANNEL)
            power_values.append(power.value)
        average_power = sum(power_values) / len(power_values)

        power_x_values.append(confirmed_mono_wavelength_float)
        power_y_values.append(average_power )  # Subtract background light

        ax_power.plot(power_x_values, power_y_values, 'bo-', label='Power Measurement')

        fig_power.tight_layout()
        canvas_power.draw()

        current_wavelength += step_size
        root.update()

    usb_mono.SendCommand("shutter c", False)
    usb_mono.WaitForIdle() 

def start_photocell_measurement():
    print("Starting photocell measurement...")
    start_wavelength = float(start_wavelength_var.get())
    end_wavelength = float(end_wavelength_var.get())
    step_size = float(step_size_var.get())

    if start_wavelength <= 400:
        messagebox.showinfo("Check Filters", "Please ensure no filters are installed.")
    
    global current_x_values, current_y_values
    current_x_values = []
    current_y_values = []

    usb_mono.SendCommand("shutter o", False)
    usb_mono.WaitForIdle()

    current_wavelength = start_wavelength
    usb_mono.SendCommand(f"gowave {current_wavelength}", False)
    usb_mono.WaitForIdle()
    time.sleep(1)
    while current_wavelength <= end_wavelength:

        if current_wavelength < 685:
            usb_mono.SendCommand("grating 1", False)
        else:
            usb_mono.SendCommand("grating 2", False)
            
        usb_mono.SendCommand(f"gowave {current_wavelength}", False)
        usb_mono.WaitForIdle()

        print(f"Current Wavelength: {current_wavelength}")
        if current_wavelength > 420 and current_wavelength <= 420 + step_size:
            messagebox.showinfo("Install Filter", "Please install the 400 nm filter and click OK to proceed.")
        
        if current_wavelength > 800 and current_wavelength <= 800 + step_size:
            messagebox.showinfo("Install Filter", "Please install the 780 nm filter and click OK to proceed.")

        confirmed_mono_wavelength = usb_mono.GetQueryResponse("wave?")
        confirmed_mono_wavelength_float = float(confirmed_mono_wavelength)

        output = read_lockin_status_and_output()
        if output is None:
            messagebox.showerror("Measurement Error", "Failed to read output from SR510.")
            return

        current_x_values.append(confirmed_mono_wavelength_float)
        current_y_values.append(output)

        ax_current.plot(current_x_values, current_y_values, 'bo-')

        fig_current.tight_layout()
        canvas_current.draw()

        current_wavelength += step_size
        root.update()

    usb_mono.SendCommand("shutter c", False)
    usb_mono.WaitForIdle()

    # Reset the Start/Stop button text and functionality
    # measure_button.config(text="Start Measurement", bg="#CCDDAA", command=toggle_measurement)

def save_power_data():
    if not power_x_values or not power_y_values:
        messagebox.showerror("No Data", "No power data available to save.")
        return

    file_path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV files", "*.csv")])
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

    file_path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV files", "*.csv")])
    if not file_path:
        return

    with open(file_path, mode='w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(["Wavelength (nm)", "Current (A)"])
        for x, y in zip(current_x_values, current_y_values):
            writer.writerow([x, y])

    messagebox.showinfo("Data Saved", f"Current data saved to {file_path}")

def on_close():
    # Perform any necessary cleanup here
    print("Closing application")
    tlPM.close()
    rm.close()
    ser.close()
    root.destroy()  # Ensure the GUI is properly closed
    sys.exit()  # Explicitly exit the application

# Create the main window
root = tk.Tk()
root.title("PHYS 2150 EQE Measurement")

# Create frames for the plots
plot_frame_power = tk.Frame(root)
plot_frame_power.grid(row=4, column=0, padx=10, pady=10)

plot_frame_current = tk.Frame(root)
plot_frame_current.grid(row=4, column=1, padx=10, pady=10)

# Create and grid the input fields
start_wavelength_var = tk.StringVar(value="350")
end_wavelength_var = tk.StringVar(value="850")
step_size_var = tk.StringVar(value="10")

# Create a frame to hold the labels and entries
input_frame = tk.Frame(root)
input_frame.grid(row=1, column=0, padx=10, pady=10)

# Place the labels and entries inside the frame
tk.Label(input_frame, text="Start Wavelength (nm):", font=("Helvetica", 12)).grid(row=0, column=0, sticky='w')
tk.Entry(input_frame, textvariable=start_wavelength_var, font=("Helvetica", 12)).grid(row=0, column=1, sticky='w')

tk.Label(input_frame, text="End Wavelength (nm):", font=("Helvetica", 12)).grid(row=1, column=0, sticky='w')
tk.Entry(input_frame, textvariable=end_wavelength_var, font=("Helvetica", 12)).grid(row=1, column=1, sticky='w')

tk.Label(input_frame, text="Step Size (nm):", font=("Helvetica", 12)).grid(row=2, column=0, sticky='w')
tk.Entry(input_frame, textvariable=step_size_var, font=("Helvetica", 12)).grid(row=2, column=1, sticky='w')

# Create the matplotlib figure and axes for power measurements
fig_power, ax_power = plt.subplots()
ax_power.set_xlabel('Confirmed Mono Wavelength (nm)', fontsize=12)
ax_power.set_ylabel('Power Measurements (W)', fontsize=12)
ax_power.set_title('Power Measurements', fontsize=12)
ax_power.tick_params(axis='both', which='major', labelsize=12)

canvas_power = FigureCanvasTkAgg(fig_power, master=plot_frame_power)
canvas_power.draw()
canvas_power.get_tk_widget().pack(padx=10, pady=10)

# Create the matplotlib figure and axes for current measurements
fig_current, ax_current = plt.subplots()
ax_current.set_xlabel('Confirmed Mono Wavelength (nm)', fontsize=12)
ax_current.set_ylabel('Current Measurements (A)', fontsize=12)
ax_current.set_title('Current Measurements', fontsize=12)
ax_current.tick_params(axis='both', which='major', labelsize=12)

canvas_current = FigureCanvasTkAgg(fig_current, master=plot_frame_current)
canvas_current.draw()
canvas_current.get_tk_widget().pack(padx=10, pady=10)

# Add the start and save buttons for the power measurements in the left column below the power plot
start_power_button = tk.Button(root, text="Start Power Measurement", font=("Helvetica", 12), command=start_power_measurement)
start_power_button.grid(row=5, column=0, padx=10, pady=10)

save_power_button = tk.Button(root, text="Save Power Data", font=("Helvetica", 12), command=save_power_data)
save_power_button.grid(row=6, column=0, padx=10, pady=10)

# Add the align and phase buttons in the right column above the current plot
align_button = tk.Button(root, text="Align Monochromator", font=("Helvetica", 12), command=align_monochromator)
align_button.grid(row=0, column=1, padx=10, pady=10)

adjust_phase_button = tk.Button(root, text="Adjust Phase", font=("Helvetica", 12), command=adjust_phase)
adjust_phase_button.grid(row=1, column=1, padx=10, pady=10)

# Add the start and save buttons for the current measurements in the right column below the current plot
start_current_button = tk.Button(root, text="Start Photocell Measurement", font=("Helvetica", 12), command=start_photocell_measurement)
start_current_button.grid(row=5, column=1, padx=10, pady=10)

save_current_button = tk.Button(root, text="Save Current Data", font=("Helvetica", 12), command=save_current_data)
save_current_button.grid(row=6, column=1, padx=10, pady=10)

# Bind the on_close function to the window's close event
root.protocol("WM_DELETE_WINDOW", on_close)

root.mainloop()