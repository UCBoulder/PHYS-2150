import tkinter as tk
from tkinter import messagebox, filedialog, simpledialog
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure
from decimal import Decimal, ROUND_HALF_UP
import threading
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import time
import sys
import pyvisa as visa
import datetime
import re

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
        device = rm.open_resource(device_address)
        device.timeout = 30000  # Set timeout to 30 seconds
        break

# Exit the application if the device is not found
if not device_address:
    messagebox.showerror("Error", "Keithley 2450 device not found. Please connect and power on the device and try again.")
    sys.exit(1)

# Function to export the data to a CSV file with a predefined filename
def export_to_csv(combined_data, cell_number, pixel_number):
    date = datetime.datetime.now().strftime("%Y_%m_%d")
    file_name = f"{date}_JV_cell{cell_number}_pixel{pixel_number}.csv"
    file_path = filedialog.asksaveasfilename(
        initialfile=file_name,
        defaultextension=".csv",
        filetypes=[("CSV files", "*.csv")]
    )
    if file_path:
        combined_data.to_csv(file_path, index=False)
        print(f"Data successfully exported to {file_path}")
        messagebox.showinfo("Export Successful", f"Data successfully exported to {file_path}")
    return file_path

# Function to configure the plot
def configure_plot():
    ax.set_xlabel('Voltage (V)', fontsize=14)
    ax.set_ylabel('Current (mA)', fontsize=14)
    ax.set_title('J-V Characterization', fontsize=14)
    ax.tick_params(axis='both', which='major', labelsize=14)

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
    root.destroy()
    sys.exit()

# Function to perform the measurement and update the plot
def perform_measurement(pixel_number):
    global combined_data
    clear_plot()
    print("Starting measurement...")
    start_voltage = float(start_voltage_entry.get())
    stop_voltage = float(stop_voltage_entry.get())
    step_voltage = float(step_voltage_entry.get())

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
    root.update()

    forward_voltages_plot = []
    forward_currents_plot = []
    backward_voltages_plot = []
    backward_currents_plot = []

    forward_line, = ax.plot([], [], '.', label="Forward Scan", color='#0077BB')
    ax.legend(fontsize=14)

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
            time.sleep(0.1)
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
                root.update()

    time.sleep(2)

    backward_line, = ax.plot([], [], '.', label="Reverse Scan", color='#EE7733')
    ax.legend(fontsize=14)

    # Backward sweep
    for i, voltage in enumerate(backward_voltages):
        if stop_thread.is_set():
            break
        if is_closing:
            print("Measurement interrupted due to application closing.")
            return
        try:
            device.write(f"SOUR:VOLT {voltage}")
            time.sleep(0.1)
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
                root.update()

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

    # Reset the Start/Stop button
    measure_button.config(text="Start Measurement", bg="#CCDDAA", command=toggle_measurement)

    if stop_thread.is_set():
        print("Measurement stopped.")
    else:
        print("Measurement complete.")
        # Auto-prompt to save data
        cell_number = cell_number_var.get().strip()
        if not cell_number or not re.match(r'^(C60_\d+|\d+-\d+)$', cell_number):
            messagebox.showerror("Input Error", "Invalid cell number format.")
        else:
            export_to_csv(combined_data, cell_number, pixel_number)

# Function to start the measurement in a separate thread
def start_measurement_thread(pixel_number):
    stop_thread.clear()
    measure_button.config(bg="#CCDDAA")
    measurement_thread = threading.Thread(target=perform_measurement, args=(pixel_number,))
    measurement_thread.start()

# Function to stop the measurement
def stop_measurement():
    stop_thread.set()

# Function to toggle measurement state with pixel number prompt
def toggle_measurement():
    if measure_button.config('text')[-1] == 'Start Measurement':
        # Prompt for pixel number
        pixel_number = simpledialog.askinteger(
            "Pixel Selection",
            "Enter pixel number (1-6):",
            minvalue=1,
            maxvalue=6,
            parent=root
        )
        if pixel_number is None:  # User cancelled
            return
        start_measurement_thread(pixel_number)
        measure_button.config(text="Stop Measurement", bg="#FFCCCC", command=stop_measurement)
    else:
        stop_measurement()
        measure_button.config(text="Start Measurement", bg="#CCDDAA", command=toggle_measurement)

# Function to clear the plot
def clear_plot():
    voltages_plot.clear()
    currents_plot.clear()
    ax.clear()
    configure_plot()
    canvas.draw()

# Function to show cell number popup
def show_cell_number_popup():
    popup = tk.Toplevel(root)
    popup.title("Enter Cell Number")
    popup.geometry("340x150")
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
    popup.bind('<Return>', lambda event: on_ok())
    popup.bind('<Escape>', lambda event: prevent_close())
    popup.protocol("WM_DELETE_WINDOW", prevent_close)

# Create the main GUI window
root = tk.Tk()
root.title("J-V Characterization")
root.wm_title("PHYS 2150 J-V Characterization")

start_voltage_entry = tk.StringVar(value="-0.2")
stop_voltage_entry = tk.StringVar(value="1.1")
step_voltage_entry = tk.StringVar(value=".01")
cell_number_var = tk.StringVar(value="")  # Initialize cell number variable

# Create input frame for voltage inputs
input_frame = tk.Frame(root)
input_frame.grid(row=0, column=0, padx=10, pady=10)

tk.Label(input_frame, text="Start Voltage:", font=("Helvetica", 14)).grid(row=0, column=0, sticky='w')
tk.Entry(input_frame, textvariable=start_voltage_entry, font=("Helvetica", 14)).grid(row=0, column=1, sticky='w')

tk.Label(input_frame, text="Stop Voltage:", font=("Helvetica", 14)).grid(row=1, column=0, sticky='w')
tk.Entry(input_frame, textvariable=stop_voltage_entry, font=("Helvetica", 14)).grid(row=1, column=1, sticky='w')

tk.Label(input_frame, text="Step Voltage:", font=("Helvetica", 14)).grid(row=2, column=0, sticky='w')
tk.Entry(input_frame, textvariable=step_voltage_entry, font=("Helvetica", 14)).grid(row=2, column=1, sticky='w')

# Create input frame for cell number display
cell_frame = tk.Frame(root)
cell_frame.grid(row=0, column=1, padx=10, pady=10)

tk.Label(cell_frame, text="Cell Number:", font=("Helvetica", 14)).grid(row=0, column=0, sticky='w')
tk.Entry(cell_frame, textvariable=cell_number_var, font=("Helvetica", 14), state='readonly').grid(row=0, column=1, sticky='w')

# Button widget to start/stop the measurement
measure_button = tk.Button(root, text="Start Measurement", font=("Helvetica", 14), bg="#CCDDAA", command=toggle_measurement)
measure_button.grid(column=0, row=4, columnspan=2, padx=5, pady=5)

# Create a figure for the plot
fig, ax = plt.subplots()

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

# Trigger cell number popup after 1 second
root.after(1000, show_cell_number_popup)

# Bind the on_close function to the window's close event
root.protocol("WM_DELETE_WINDOW", on_close)

root.mainloop()