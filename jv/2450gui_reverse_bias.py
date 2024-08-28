import tkinter as tk
from tkinter import messagebox
from tkinter import filedialog
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure
from decimal import Decimal, ROUND_HALF_UP
import threading
import numpy as np
import pandas as pd
import time
import sys
import pyvisa as visa

# Initialize the VISA resource manager
rm = visa.ResourceManager()

# Initialize lists to store the measurements for plotting
voltages_plot = []
currents_plot = []
all_measurements = []

# Set up variables for threading and closing the application
stop_thread = threading.Event()
lock = threading.Lock()
is_closing = False

# Search for the device
device_address = None
for resource in rm.list_resources():
    if resource.startswith("USB0::0x05E6::0x2450"):
        device_address = resource
        print(f"Keithley 2450 found at {device_address}")
        # Open a session to the device
        device = rm.open_resource(device_address)
        device.timeout = 30000  # Set timeout to 30 seconds
        break

# Exit the application if the device is not found and notify user
if not device_address:
    messagebox.showerror("Error", "Keithley 2450 device not found. Please connect and power on the device and try again.")
    sys.exit(1)

# Function to export the data to a CSV file
def export_to_csv(voltages_plot, all_measurements):
    file_path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV files", "*.csv")])
    if not file_path:
        return
    combined_data.to_csv(file_path, index=False)
    messagebox.showinfo("Export Successful", f"Data successfully exported to {file_path}")

# Function to configure the plot
def configure_plot():
    ax.set_xlabel('Voltage (V)')
    ax.set_ylabel('Current (mA)')
    ax.set_title('J-V Characterization')

# Function to clean up and close the application
def on_close():
    global is_closing
    is_closing = True
    print("Closing application")
    stop_thread.set()
    if 'device' in globals():
        try:
            device.write("OUTP OFF")  # Disable the output
            device.close()
        except Exception as e:
            print(f"Error closing device: {e}")
    if 'rm' in globals():
        rm.close()
    root.destroy()  # Ensure the GUI is properly closed
    sys.exit()  # Explicitly exit the application

# Function to perform the measurement and update the plot
def perform_measurement():
    global combined_data
    clear_plot()
    print("Starting measurement...")
    # Start a timer for performance debugging
    #t = time.time() 
    start_voltage = float(start_voltage_entry.get())
    stop_voltage = float(stop_voltage_entry.get())
    step_voltage = float(step_voltage_entry.get())

    # Ensure stop_voltage is inclusive for both forward and backward sweeps
    total_range = stop_voltage - start_voltage
    steps_needed = total_range / step_voltage
    if not steps_needed.is_integer():
        # Adjust stop_voltage slightly to ensure it's inclusive
        stop_voltage += (step_voltage - (total_range % step_voltage))

    forward_voltages = np.arange(start_voltage, stop_voltage + (step_voltage / 2), step_voltage)
    backward_voltages = np.arange(stop_voltage, start_voltage - (step_voltage / 2), -step_voltage)

    # Round the voltages to mitigate floating-point issues
    forward_voltages = np.round(forward_voltages, decimals=2)
    backward_voltages = np.round(backward_voltages, decimals=2)

    # Sending SCPI commands to the device
    device.write("*RST") # Reset the device
    device.write("SENS:FUNC \"CURR\"") # Set the measurement function to current
    device.write("SENS:CURR:RANG 10") # Set the current range to 10 mA
    device.write("SENS:CURR:RSEN ON") # Enable 4-wire sense
    device.write("SOUR:FUNC VOLT") # Set the source function to voltage
    device.write("SOUR:VOLT:RANG 2") # Set the voltage range to 2 V
    device.write("SOUR:VOLT:ILIM 1") # Set the current limit to 1 A
    device.write("OUTP ON") # Enable the output

    # Update the plot
    fig.tight_layout() 
    canvas.draw() 
    root.update() 

    # Initialize lists to store measurements
    forward_voltages_plot = []
    forward_currents_plot = []
    backward_voltages_plot = []
    backward_currents_plot = []

    # Create line object for forward sweep
    forward_line, = ax.plot([], [], '.', label="Forward Scan", color='#0077BB')
    ax.legend()

    device.write(f"SOUR:VOLT {start_voltage}") # Set the initial voltage
    time.sleep(2) # Stabilization time

    # Forward sweep
    for i, voltage in enumerate(forward_voltages):
        if stop_thread.is_set():
            break
        if is_closing:
            print("Measurement interrupted due to application closing.")
            return
        try:
            device.write(f"SOUR:VOLT {voltage}")
            time.sleep(0.1)  # Stabilization time
            current_reading = device.query("MEAS:CURR?")
            current_reading = Decimal(current_reading)
            forward_voltages_plot.append(voltage)
            forward_current = (current_reading * Decimal(10**3)).quantize(Decimal('0.00001'), rounding=ROUND_HALF_UP)  # Convert to mA
            forward_current = float(forward_current)
            forward_currents_plot.append(forward_current)
        except Exception as e:
            print(f"Error during measurement: {e}")
            return

        # Update plot during forward sweep every 10 iterations
        if i % 10 == 0 or i == len(forward_voltages) - 1:
            with lock:
                forward_line.set_data(forward_voltages_plot, forward_currents_plot)
                ax.relim()
                ax.autoscale_view()
                fig.tight_layout()
                canvas.draw()
                root.update()

    time.sleep(2)  # Short delay between sweeps

    # Create line object for backward sweep
    backward_line, = ax.plot([], [], '.', label="Reverse Scan", color='#EE7733')
    ax.legend()

    # Backward sweep
    for i, voltage in enumerate(backward_voltages):
        if stop_thread.is_set():
            break
        if is_closing:
            print("Measurement interrupted due to application closing.")
            return
        try:
            device.write(f"SOUR:VOLT {voltage}")
            time.sleep(0.1)  # Stabilization time
            current_reading = device.query("MEAS:CURR?")
            current_reading = Decimal(current_reading)
            backward_voltages_plot.append(voltage)
            backward_current = (current_reading * Decimal(10**3)).quantize(Decimal('0.00001'), rounding=ROUND_HALF_UP)
            backward_current = float(backward_current)
            backward_currents_plot.append(backward_current)
        except Exception as e:
            print(f"Error during measurement: {e}")
            return

        # Update plot during backward sweep every 10 iterations
        if i % 10 == 0 or i == len(backward_voltages) - 1:
            with lock:
                backward_line.set_data(backward_voltages_plot, backward_currents_plot)
                ax.relim()
                ax.autoscale_view()
                fig.tight_layout()
                canvas.draw()
                root.update()

    # Combine forward and reverse Scan data
    combined_data = pd.DataFrame({
        "Voltage (V)": np.concatenate((forward_voltages_plot, backward_voltages_plot)),
        "Forward Scan (mA)": np.concatenate((forward_currents_plot, [None] * len(backward_currents_plot))),
        "Reverse Scan (mA)": np.concatenate(([None] * len(forward_currents_plot), backward_currents_plot))
    })

    # Group by voltage and aggregate forward and reverse Scan currents
    combined_data = combined_data.groupby("Voltage (V)").agg({
        "Forward Scan (mA)": "first",
        "Reverse Scan (mA)": "first"
    }).reset_index()

    try:
        device.write("OUTP OFF") # Disable the output
    except Exception as e:
        print(f"Error disabling output: {e}")

    # Reset the Start/Stop button text and functionality
    measure_button.config(text="Start Measurement", bg="#CCDDAA", command=toggle_measurement) 

    if stop_thread.is_set():
        print("Measurement stopped.")
    else:
        print("Measurement complete.")
    
    # Stop and print elapsed time for performance debugging
    #print(f"Time taken: {time.time() - t:.2f} seconds") 


# Function to start the measurement in a separate thread
def start_measurement_thread():
    stop_thread.clear()
    measure_button.config(bg="#CCDDAA")
    measurement_thread = threading.Thread(target=perform_measurement)
    measurement_thread.start()

# Function to stop the measurement
def stop_measurement():
    stop_thread.set()

# Function to clear the plot
def clear_plot():
    voltages_plot.clear()
    currents_plot.clear()
    ax.clear()  # Clear the current axes
    configure_plot()  # Reconfigure the plot
    canvas.draw()  # Draw the canvas

# Create the main GUI window
root = tk.Tk()
root.title("J-V Characterization")
root.wm_title("PHYS 2150 J-V Characterization")

start_voltage_entry = tk.StringVar(value="-0.2") # Default start voltage
stop_voltage_entry = tk.StringVar(value="1.1") # Default stop voltage
step_voltage_entry = tk.StringVar(value=".01") # Default step voltage

# Create and place voltage range input fields
tk.Label(root, text="Start Voltage:", font=("Helvetica", 12)).grid(row=0, column=0)
tk.Entry(root, textvariable=start_voltage_entry, font=("Helvetica", 12)).grid(row=0, column=1)

tk.Label(root, text="Stop Voltage:", font=("Helvetica", 12)).grid(row=1, column=0)
tk.Entry(root, textvariable=stop_voltage_entry, font=("Helvetica", 12)).grid(row=1, column=1)

tk.Label(root, text="Step Voltage:", font=("Helvetica", 12)).grid(row=2, column=0)
tk.Entry(root, textvariable=step_voltage_entry, font=("Helvetica", 12)).grid(row=2, column=1)

# Button widget to clear the plot
clear_button = tk.Button(root, text="Clear Plot", command=clear_plot)
clear_button.grid(row=5, column=0, columnspan=1, padx=5, pady=5)

# Button widget to export the data to a CSV file
export_button = tk.Button(root, text="Export to CSV", command=lambda: export_to_csv(voltages_plot, all_measurements))
export_button.grid(row=5, column=1, columnspan=1, padx=5, pady=5)

# Function to toggle measurement state
def toggle_measurement():
    if measure_button.config('text')[-1] == 'Start Measurement':
        start_measurement_thread()
        measure_button.config(text="Stop Measurement", bg="#FFCCCC", command=stop_measurement)
    else:
        stop_measurement()
        measure_button.config(text="Start Measurement", bg="#CCDDAA", command=toggle_measurement)

# Button widget to start/stop the measurement
measure_button = tk.Button(root, text="Start Measurement", font=("Helvetica", 12), bg="#CCDDAA", command=toggle_measurement)
measure_button.grid(column=0, row=4, columnspan=2, padx=5, pady=5)

# Create a figure for the plot
fig = Figure(figsize=(5, 4), dpi=100)
ax = fig.add_subplot(111)

# Initial configuration of the plot
configure_plot()  

# Create a canvas for the plot
canvas = FigureCanvasTkAgg(fig, master=root) 
canvas.draw()
canvas.get_tk_widget().grid(row=6, column=0, columnspan=2, sticky="nsew")

# Create a toolbar for the plot
toolbar_frame = tk.Frame(root)
toolbar_frame.grid(row=7, column=0, columnspan=2, sticky="ew")
toolbar = NavigationToolbar2Tk(canvas, toolbar_frame)
toolbar.update()

# Make the canvas and toolbar_frame expand and fill the space
root.grid_rowconfigure(6, weight=1)
root.grid_rowconfigure(7, weight=0)
root.grid_columnconfigure(0, weight=1)
root.grid_columnconfigure(1, weight=1)

# Bind the on_close function to the window's close event
root.protocol("WM_DELETE_WINDOW", on_close)

root.mainloop()