import tkinter as tk
from tkinter import messagebox
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import threading
import time
import sys
import csv
import pyvisa as visa
from datetime import datetime

# Initialize the VISA resource manager
rm = visa.ResourceManager()

# Initialize variables
temperatures_plot = []
timestamps_plot = []
stop_thread = threading.Event()
running = True
lock = threading.Lock()  # Create a lock object

# Assuming device initialization code here
device_address = None
for resource in rm.list_resources():
    if resource.startswith("USB0::0x05E6::0x2110"):
        device_address = resource
        print(f"Keithley 2110 found at {device_address}")
        device = rm.open_resource(device_address)
        device.timeout = 30000  # Set timeout to 30 seconds
        break

if not device_address:
    messagebox.showerror("Error", "Keithley 2110 device not found.")
    sys.exit(1)

# Reset the device
device.write("*RST")

def measure_temperature():
    while not stop_thread.is_set():
        # Simulate reading temperature (replace with actual command)
        temperature_reading = float(device.query("MEAS:TCO?"))
        with lock:  # Acquire the lock before modifying the lists
            temperatures_plot.append(temperature_reading)
            timestamps_plot.append(datetime.now())
        time.sleep(1)  # Measure every second

def update_plot():
    with lock:  # Acquire the lock before accessing the lists
        if temperatures_plot:
            # Update the plot
            ax.clear()
            ax.plot(timestamps_plot, temperatures_plot, '-o')
            # Calculate max and min with a margin of 1°C
            max_temp = max(temperatures_plot) + 1
            min_temp = min(temperatures_plot) - 1
            ax.set_ylim(min_temp, max_temp)  # Set y-axis limits
            ax.set_xlabel('Time')  # Set x-axis label
            ax.set_ylabel('Temperature (°C)')  # Set y-axis label
            canvas.draw()
    if running:  # Check if the application is still running
        root.after(1000, update_plot)  # Check for updates every second

def start_measurement():
    global measurement_thread
    stop_thread.clear()
    measurement_thread = threading.Thread(target=measure_temperature)
    measurement_thread.start()

def stop_measurement():
    stop_thread.set()
    measurement_thread.join()

def on_closing():
    global running
    running = False  # Set the running flag to False
    stop_measurement()
    root.destroy()

def export_to_csv():
    with lock:  # Acquire the lock before accessing the lists
        with open('temperature_data.csv', 'w', newline='') as csvfile:
            csvwriter = csv.writer(csvfile)
            csvwriter.writerow(['Timestamp', 'Temperature'])
            for timestamp, temp in zip(timestamps_plot, temperatures_plot):
                csvwriter.writerow([timestamp.strftime('%Y-%m-%d %H:%M:%S'), temp])
    messagebox.showinfo("Export Data", "Data exported to temperature_data.csv successfully.")

root = tk.Tk()
root.protocol("WM_DELETE_WINDOW", on_closing)

fig, ax = plt.subplots()
canvas = FigureCanvasTkAgg(fig, master=root)
canvas_widget = canvas.get_tk_widget()
canvas_widget.pack()

# Add Start and Stop buttons
start_button = tk.Button(root, text="Start Measurement", command=start_measurement)
start_button.pack(side=tk.LEFT)

stop_button = tk.Button(root, text="Stop Measurement", command=stop_measurement)
stop_button.pack(side=tk.LEFT)

# Add Export to CSV button
export_button = tk.Button(root, text="Export Data to CSV", command=export_to_csv)
export_button.pack(side=tk.LEFT)

# Start the plot update loop
update_plot()

root.mainloop()