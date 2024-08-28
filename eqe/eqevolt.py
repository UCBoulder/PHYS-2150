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

# Initialize Cornerstone_Mono and Keithley 2110 objects
warnings.simplefilter("ignore")
rm = visa.ResourceManager()
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

if keithley_resource is None:
    print("Keithley 2110 not found. Please check the connection.")
    sys.exit()

keithley = rm.open_resource(keithley_resource)

def on_close():
    # Perform any necessary cleanup here
    print("Closing application")
    keithley.close()
    rm.close()
    root.destroy()  # Ensure the GUI is properly closed
    sys.exit()  # Explicitly exit the application

# Function to perform the measurement and update the plot
def start_measurement():
    print("Starting measurement...")
    start_wavelength = float(start_wavelength_var.get())
    end_wavelength = float(end_wavelength_var.get())
    step_size = float(step_size_var.get())

    # Check if the start wavelength is less than 400 nm and prompt the user
    if start_wavelength <= 400:
        messagebox.showinfo("Check Filters", "Please ensure no filters are installed.")
    
    global x_values, y_values
    x_values = []
    y_values = []

    usb_mono.SendCommand("shutter o", False)
    usb_mono.WaitForIdle()
    usb_mono.SendCommand(f"gowave {start_wavelength}", False)
    usb_mono.WaitForIdle()
    time.sleep(2)
    

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
        time.sleep(3)

        # Read the DC voltage from the Keithley 2110 and calculate the current
        keithley.write(":SENS:FUNC 'VOLT:DC'")
        voltage_readings = []
        for _ in range(20):
            amplified_voltage = float(keithley.query(":READ?"))
            voltage_readings.append(amplified_voltage)
        average_amplified_voltage = sum(voltage_readings) / len(voltage_readings)
        unamplified_voltage = average_amplified_voltage / 200  # Calculate the unamplified voltage
        current = (unamplified_voltage / 10**6) * 10**6  # Convert to microamps

        x_values.append(confirmed_mono_wavelength_float)
        y_values.append(current)

        ax.plot(x_values, y_values, 'bo-')

        fig.tight_layout()
        canvas.draw()

        current_wavelength += step_size
        root.update()

    usb_mono.SendCommand("shutter c", False)
    usb_mono.WaitForIdle() 

# Function to save the data to a CSV file
def save_data():
    if not x_values or not y_values:
        messagebox.showwarning("No Data", "No data to save. Please run a measurement first.")
        return

    file_path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV files", "*.csv"), ("All files", "*.*")])
    if file_path:
        with open(file_path, mode='w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(["Wavelength (nm)", "Current (A)"])
            writer.writerows(zip(x_values, y_values))
        messagebox.showinfo("Data Saved", f"Data successfully saved to {file_path}")

# Function to align the wavelength to 532 nm and open the shutter
def align_wavelength():
    usb_mono.SendCommand("grating 1", False)
    usb_mono.WaitForIdle()
    usb_mono.SendCommand("gowave 532", False)
    usb_mono.WaitForIdle()
    usb_mono.SendCommand("shutter o", False)
    usb_mono.WaitForIdle()
    messagebox.showinfo("Alignment", "Wavelength set to 532 nm and shutter opened.")

# Create the main window
root = tk.Tk()
root.title("Wavelength Measurement")

# Create and grid the input fields
start_wavelength_var = tk.StringVar(value="375")
end_wavelength_var = tk.StringVar(value="825")
step_size_var = tk.StringVar(value="10")

tk.Label(root, text="Start Wavelength (nm):", font=("Helvetica", 12)).grid(row=0, column=0)
tk.Entry(root, textvariable=start_wavelength_var, font=("Helvetica", 12)).grid(row=0, column=1)

tk.Label(root, text="End Wavelength (nm):", font=("Helvetica", 12)).grid(row=1, column=0)
tk.Entry(root, textvariable=end_wavelength_var, font=("Helvetica", 12)).grid(row=1, column=1)

tk.Label(root, text="Step Size (nm):", font=("Helvetica", 12)).grid(row=2, column=0)
tk.Entry(root, textvariable=step_size_var, font=("Helvetica", 12)).grid(row=2, column=1)

# Create a frame for the plot
plot_frame = ttk.Frame(root)
plot_frame.grid(row=3, column=0, columnspan=2)

# Create the matplotlib figure and axes
fig, ax = plt.subplots()
ax.set_xlabel('Confirmed Mono Wavelength', fontsize=12)
ax.set_ylabel('Current (µA)', fontsize=12)
ax.set_title('Current vs. Confirmed Mono Wavelength', fontsize=12)
ax.tick_params(axis='both', which='major', labelsize=12)

canvas = FigureCanvasTkAgg(fig, master=plot_frame)  # A tk.DrawingArea.
canvas.draw()
canvas.get_tk_widget().pack(padx=10, pady=10)

# Add a button to start the measurement
start_button = tk.Button(root, text="Start Measurement", font=("Helvetica", 12), command=start_measurement)
start_button.grid(row=4, column=0, columnspan=2)

# Add a button to save the data to a CSV file
save_button = tk.Button(root, text="Save Data", font=("Helvetica", 12), command=save_data)
save_button.grid(row=5, column=0, columnspan=2)

# Add a button to align the wavelength to 532 nm and open the shutter
align_button = tk.Button(root, text="Align", font=("Helvetica", 12), command=align_wavelength)
align_button.grid(row=6, column=0, columnspan=2)

# Bind the on_close function to the window's close event
root.protocol("WM_DELETE_WINDOW", on_close)

root.mainloop()