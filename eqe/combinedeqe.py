import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import numpy as np
import time
import sys
import warnings
import pyvisa as visa
import csv
from cornerstone_mono import Cornerstone_Mono
from TLPMX import TLPMX, TLPM_DEFAULT_CHANNEL
from ctypes import c_uint32, create_string_buffer, c_bool, c_double, byref

# Initialize TLPMX, Cornerstone_Mono, and Keithley 2110 objects
warnings.simplefilter("ignore")
rm = visa.ResourceManager()
tlPM = TLPMX()
deviceCount = c_uint32()
tlPM.findRsrc(byref(deviceCount))
resourceName = create_string_buffer(1024)
tlPM.getRsrcName(0, resourceName)
tlPM.open(resourceName, c_bool(True), c_bool(True))
usb_mono = Cornerstone_Mono(rm, rem_ifc="usb", timeout_msec=29000)

# List all available VISA resources
resources = rm.list_resources()
print("Available VISA resources:", resources)

# Use the correct resource string for the Keithley 2110
keithley_resource = None
for resource in resources:
    if '2110' in resource:
        keithley_resource = resource
        break

def on_close():
    # Perform any necessary cleanup here
    print("Closing application")
    tlPM.close()
    rm.close()
    root.destroy()  # Ensure the GUI is properly closed
    sys.exit()  # Explicitly exit the application

# Function to perform the light power measurement and update the plot
def start_light_power_measurement():
    print("Starting light power measurement...")
    start_wavelength = float(start_wavelength_var.get())
    end_wavelength = float(end_wavelength_var.get())
    step_size = float(step_size_var.get())

    # Check if the start wavelength is less than 400 nm and prompt the user
    if start_wavelength <= 400:
        messagebox.showinfo("Check Filters", "Please ensure no filters are installed.")
    
    global power_x_values, power_y_values
    power_x_values = []
    power_y_values = []

    # First loop: Measure background light with shutter closed
    print("Measuring background light...")
    background_y_values = []

    current_wavelength = start_wavelength
    while current_wavelength <= end_wavelength:
        tlPM.setWavelength(c_double(current_wavelength), TLPM_DEFAULT_CHANNEL)
        time.sleep(0.1)  # Wait for the power reading to stabilize
        power = c_double()
        tlPM.measPower(byref(power), TLPM_DEFAULT_CHANNEL)
        background_y_values.append(power.value)
        print(f"Background Light at {current_wavelength} nm: {power.value}")
        current_wavelength += step_size

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
        if current_wavelength > 400 and current_wavelength <= 400 + step_size:
            messagebox.showinfo("Install Filter", "Please install the 400 nm filter and click OK to proceed.")
        
        # Prompt the user to install the 780 nm filter
        if current_wavelength > 780 and current_wavelength <= 780 + step_size:
            messagebox.showinfo("Install Filter", "Please install the 780 nm filter and click OK to proceed.")

        confirmed_mono_wavelength = usb_mono.GetQueryResponse("wave?")
        confirmed_mono_wavelength_float = float(confirmed_mono_wavelength)
        tlPM.setWavelength(c_double(confirmed_mono_wavelength_float), TLPM_DEFAULT_CHANNEL)

        power = c_double()
        tlPM.measPower(byref(power), TLPM_DEFAULT_CHANNEL)

        power_x_values.append(confirmed_mono_wavelength_float)
        power_y_values.append(power.value - background_y_values[len(power_x_values) - 1])  # Subtract background light

        ax_power.plot(power_x_values, power_y_values, 'bo-', label='Power Measurement')

        fig_power.tight_layout()
        canvas_power.draw()

        current_wavelength += step_size
        root.update()

    usb_mono.SendCommand("shutter c", False)
    usb_mono.WaitForIdle() 

# Function to perform the photocell current measurement and update the plot
def start_photocell_measurement():
    print("Starting photocell measurement...")
    start_wavelength = float(start_wavelength_var.get())
    end_wavelength = float(end_wavelength_var.get())
    step_size = float(step_size_var.get())

    global current_x_values, current_y_values
    current_x_values = []
    current_y_values = []

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
        if current_wavelength > 400 and current_wavelength <= 400 + step_size:
            messagebox.showinfo("Install Filter", "Please install the 400 nm filter and click OK to proceed.")
        
        # Prompt the user to install the 780 nm filter
        if current_wavelength > 780 and current_wavelength <= 780 + step_size:
            messagebox.showinfo("Install Filter", "Please install the 780 nm filter and click OK to proceed.")

        confirmed_mono_wavelength = usb_mono.GetQueryResponse("wave?")
        confirmed_mono_wavelength_float = float(confirmed_mono_wavelength)

        # Measure photocell current using Keithley 2110
        keithley = rm.open_resource(keithley_resource)
        keithley.write(":SENS:FUNC 'CURR'")
        keithley.write(":SENS:CURR:RANG:AUTO ON")
        current = float(keithley.query(":READ?"))
        keithley.close()

        current_x_values.append(confirmed_mono_wavelength_float)
        current_y_values.append(current)

        ax_current.plot(current_x_values, current_y_values, 'ro-', label='Current Measurement')

        fig_current.tight_layout()
        canvas_current.draw()

        current_wavelength += step_size
        root.update()

# Function to save the data to a CSV file
def save_data():
    if not power_x_values and not current_x_values:
        messagebox.showwarning("No Data", "No data to save. Please run a measurement first.")
        return

    file_path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV files", "*.csv"), ("All files", "*.*")])
    if file_path:
        with open(file_path, mode='w', newline='') as file:
            writer = csv.writer(file)
            if power_x_values:
                writer.writerow(["Wavelength (nm)", "Power Measurements"])
                writer.writerows(zip(power_x_values, power_y_values))
            if current_x_values:
                writer.writerow(["Wavelength (nm)", "Current Measurements"])
                writer.writerows(zip(current_x_values, current_y_values))
        messagebox.showinfo("Data Saved", f"Data successfully saved to {file_path}")

# Function to align the monochromator
def align_monochromator():
    print("Aligning monochromator...")
    usb_mono.SendCommand("grating 1", False)
    usb_mono.SendCommand("gowave 532", False)
    usb_mono.SendCommand("shutter o", False)
    usb_mono.WaitForIdle()
    messagebox.showinfo("Alignment", "Monochromator aligned to 532 nm with grating 1 and shutter opened.")

# Create the main window
root = tk.Tk()
root.title("Wavelength Measurement")

# Create and grid the input fields
start_wavelength_var = tk.StringVar(value="325")
end_wavelength_var = tk.StringVar(value="1100")
step_size_var = tk.StringVar(value="25")

tk.Label(root, text="Start Wavelength (nm):", font=("Helvetica", 12)).grid(row=0, column=0, columnspan=2)
tk.Entry(root, textvariable=start_wavelength_var, font=("Helvetica", 12)).grid(row=0, column=2, columnspan=2)

tk.Label(root, text="End Wavelength (nm):", font=("Helvetica", 12)).grid(row=1, column=0, columnspan=2)
tk.Entry(root, textvariable=end_wavelength_var, font=("Helvetica", 12)).grid(row=1, column=2, columnspan=2)

tk.Label(root, text="Step Size (nm):", font=("Helvetica", 12)).grid(row=2, column=0, columnspan=2)
tk.Entry(root, textvariable=step_size_var, font=("Helvetica", 12)).grid(row=2, column=2, columnspan=2)

# Create frames for the plots
plot_frame_power = ttk.Frame(root)
plot_frame_power.grid(row=3, column=0, columnspan=2, padx=10, pady=10)

plot_frame_current = ttk.Frame(root)
plot_frame_current.grid(row=3, column=2, columnspan=2, padx=10, pady=10)

# Create the matplotlib figures and axes for power and current
fig_power, ax_power = plt.subplots()
ax_power.set_xlabel('Confirmed Mono Wavelength', fontsize=12)
ax_power.set_ylabel('Power Measurements', fontsize=12)
ax_power.set_title('Power Measurements vs. Confirmed Mono Wavelength', fontsize=12)
ax_power.tick_params(axis='both', which='major', labelsize=12)

canvas_power = FigureCanvasTkAgg(fig_power, master=plot_frame_power)  # A tk.DrawingArea.
canvas_power.draw()
canvas_power.get_tk_widget().pack()

fig_current, ax_current = plt.subplots()
ax_current.set_xlabel('Confirmed Mono Wavelength', fontsize=12)
ax_current.set_ylabel('Current Measurements', fontsize=12)
ax_current.set_title('Current Measurements vs. Confirmed Mono Wavelength', fontsize=12)
ax_current.tick_params(axis='both', which='major', labelsize=12)

canvas_current = FigureCanvasTkAgg(fig_current, master=plot_frame_current)  # A tk.DrawingArea.
canvas_current.draw()
canvas_current.get_tk_widget().pack()

# Add buttons to start the measurements
start_light_power_button = tk.Button(root, text="Start Light Power Measurement", font=("Helvetica", 12), command=start_light_power_measurement)
start_light_power_button.grid(row=4, column=0, columnspan=2)

start_photocell_button = tk.Button(root, text="Start Photocell Measurement", font=("Helvetica", 12), command=start_photocell_measurement)
start_photocell_button.grid(row=4, column=2, columnspan=2)

# Add a button to save the data to a CSV file
save_button = tk.Button(root, text="Save Data", font=("Helvetica", 12), command=save_data)
save_button.grid(row=5, column=0, columnspan=4)

# Add a button to align the monochromator
align_button = tk.Button(root, text="Align", font=("Helvetica", 12), command=align_monochromator)
align_button.grid(row=6, column=0, columnspan=4)

# Bind the on_close function to the window's close event
root.protocol("WM_DELETE_WINDOW", on_close)

root.mainloop()