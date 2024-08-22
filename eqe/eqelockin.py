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
import serial
import serial.tools.list_ports
import threading

# Initialize Cornerstone_Mono and SR510 objects
warnings.simplefilter("ignore")
rm = visa.ResourceManager()
usb_mono = Cornerstone_Mono(rm, rem_ifc="usb", timeout_msec=29000)

def find_com_port():
    ports = serial.tools.list_ports.comports()
    for port in ports:
        if "Prolific PL2303GT USB Serial COM Port" in port.description:
            return port.device
    raise Exception("COM port not found")

# Initialize SR510 serial connection
ser = serial.Serial(
    port=find_com_port(),  # Automatically find the correct COM port
    baudrate=19200,
    parity=serial.PARITY_ODD,
    stopbits=serial.STOPBITS_TWO,
    bytesize=serial.EIGHTBITS,
    timeout=2           # Timeout for read operations
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
    # Send the command to set sensitivity to 200
    initial_sensitivity_command = 'G 23\r'
    print(f"Setting initial sensitivity with command: {initial_sensitivity_command.strip()}")
    ser.write(initial_sensitivity_command.encode())
    wait_for_ready()  # Wait for the command to complete


def increase_sensitivity():
    # Send the command to increase sensitivity
    sensitivity_up_command = 'K 22\r'  # Command to increase sensitivity one level
    print(f"Increasing sensitivity with command: {sensitivity_up_command.strip()}")
    ser.write(sensitivity_up_command.encode())
    wait_for_ready()  # Wait for the command to complete

def convert_phase_to_range(phase):
    """Convert phase to be within the range of -180 to +180 degrees and format to one decimal place."""
    phase = phase % 360
    if phase > 180:
        phase -= 360
    return f"{phase:.1f}"

def adjust_phase_to_minimize_output():
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
        print(f"Phase: {convert_phase_to_range(phase)}, Output response: {output_response}")
        try:
            signal_value = float(output_response)
            return abs(signal_value) <= 0.0005
        except ValueError as e:
            print(f"Error parsing output response: {e}")
            return False

    usb_mono.SendCommand("grating 1", False)
    usb_mono.WaitForIdle()
    usb_mono.SendCommand("gowave 532", False)
    usb_mono.WaitForIdle()
    usb_mono.SendCommand("shutter o", False)
    usb_mono.WaitForIdle()

    # Get the current phase
    ser.write('P\r'.encode())
    current_phase = float(read_response())
    print(f"Current phase: {convert_phase_to_range(current_phase)}")

    increment = 45  # Start with a larger increment
    best_phase = current_phase
    min_output = float('inf')

    while increment >= 0.1:
        for direction in [-1, 1]:
            new_phase = (best_phase + direction * increment) % 360
            set_phase(new_phase)
            output_response = read_output()
            print(f"Phase: {convert_phase_to_range(new_phase)}, Output response: {output_response}")

            try:
                signal_value = float(output_response)
                if abs(signal_value) < abs(min_output):
                    min_output = signal_value
                    best_phase = new_phase
            except ValueError as e:
                print(f"Error parsing output response: {e}")

        increment /= 2  # Reduce the increment size for finer adjustments

    print(f"Minimized output at phase: {convert_phase_to_range(best_phase)} with signal value: {min_output}")

    # Ensure the output is positive
    if min_output < 0:
        best_phase = (best_phase + 180) % 360
        set_phase(best_phase)
        print(f"Adjusted phase to {convert_phase_to_range(best_phase)} degrees to ensure positive output.")

    # Loop to verify the phase 180 degrees from the best phase
    while not verify_phase((best_phase + 180) % 360):
        print(f"Phase {convert_phase_to_range(best_phase)} does not meet the condition at 180 degrees.")
        # Continue adjusting the phase from the best phase found so far
        increment = 45  # Reset increment for further adjustments
        while increment >= 0.1:
            for direction in [-1, 1]:
                new_phase = (best_phase + direction * increment) % 360
                set_phase(new_phase)
                output_response = read_output()
                print(f"Phase: {convert_phase_to_range(new_phase)}, Output response: {output_response}")

                try:
                    signal_value = float(output_response)
                    if abs(signal_value) < abs(min_output):
                        min_output = signal_value
                        best_phase = new_phase
                except ValueError as e:
                    print(f"Error parsing output response: {e}")

            increment /= 2  # Reduce the increment size for finer adjustments

        print(f"Minimized output at phase: {convert_phase_to_range(best_phase)} with signal value: {min_output}")

        # Ensure the output is positive
        if min_output < 0:
            best_phase = (best_phase + 180) % 360
            set_phase(best_phase)
            print(f"Adjusted phase to {convert_phase_to_range(best_phase)} degrees to ensure positive output.")

    print(f"Phase {convert_phase_to_range(best_phase)} and {convert_phase_to_range(best_phase + 180)} both meet the condition.")
    # Set phase to 90 or 270 degrees from the best phase
    for offset in [90, 270]:
        phase_offset = (best_phase + offset) % 360
        set_phase(phase_offset)
        output_response = read_output()
        print(f"Phase: {convert_phase_to_range(phase_offset)}, Output response: {output_response}")

        try:
            signal_value = float(output_response)
            if signal_value > 0:
                print(f"Set phase to {convert_phase_to_range(phase_offset)} degrees with positive signal value: {signal_value}")
                return best_phase, min_output
        except ValueError as e:
            print(f"Error parsing output response: {e}")

    return best_phase, min_output

def check_status_and_read_output():
    try:
        if not ser.is_open:
            ser.open()
        while True:
            ser.flushInput()
            status_command = 'Y\r'
            ser.write(status_command.encode())
            time.sleep(1)
            response = ser.read(ser.in_waiting or 1).decode().strip()
            if response:
                try:
                    # Clean the response and handle scientific notation
                    status_byte = int(response.split('\r')[0].strip())
                    is_locked = not (status_byte & (1 << 3))
                    has_reference = not (status_byte & (1 << 2))
                    is_overloaded = status_byte & (1 << 4)
                    if is_locked and has_reference and not is_overloaded:
                        output_command = 'Q\r'
                        ser.write(output_command.encode())
                        time.sleep(1)
                        output_response = ser.read(ser.in_waiting or 1).decode().strip()
                        if output_response:
                            return float(output_response.split('\r')[0].strip())
                        else:
                            print("No output response received.")
                            continue
                    # elif is_overloaded:
                    #     increase_sensitivity()
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
    return None

# Initialize lists to store the measurements
x_values = []
y_values = []

# Set up variables for threading and closing the application
stop_thread = threading.Event()
lock = threading.Lock()
is_closing = False

def on_close():
    global is_closing
    is_closing = True
    print("Closing application")
    stop_thread.set()
    rm.close()
    root.destroy()
    sys.exit()

def start_measurement():
    global x_values, y_values
    x_values.clear()
    y_values.clear()
    print("Starting measurement...")

    start_wavelength = float(start_wavelength_var.get())
    end_wavelength = float(end_wavelength_var.get())
    step_size = float(step_size_var.get())

    if start_wavelength <= 400:
        messagebox.showinfo("Check Filters", "Please ensure no filters are installed.")

    set_initial_parameters()
    usb_mono.SendCommand("shutter o", False)
    usb_mono.WaitForIdle()

    current_wavelength = start_wavelength
    while current_wavelength <= end_wavelength:
        if stop_thread.is_set():
            break
        if is_closing:
            print("Measurement interrupted due to application closing.")
            return

        if current_wavelength < 685:
            usb_mono.SendCommand("grating 1", False)
        else:
            usb_mono.SendCommand("grating 2", False)

        usb_mono.SendCommand(f"gowave {current_wavelength}", False)
        usb_mono.WaitForIdle()

        if current_wavelength > 420 and current_wavelength <= 420 + step_size:
            messagebox.showinfo("Install Filter", "Please install the 400 nm filter and click OK to proceed.")

        if current_wavelength > 800 and current_wavelength <= 800 + step_size:
            messagebox.showinfo("Install Filter", "Please install the 780 nm filter and click OK to proceed.")

        confirmed_mono_wavelength = usb_mono.GetQueryResponse("wave?")
        confirmed_mono_wavelength_float = float(confirmed_mono_wavelength)

        output = check_status_and_read_output()
        print(f"Current Wavelength: {current_wavelength} Current Output: {output}")

        x_values.append(confirmed_mono_wavelength_float)
        y_values.append(output)

        ax.plot(x_values, y_values, 'bo-')

        fig.tight_layout()
        canvas.draw()

        current_wavelength += step_size
        root.update()

    usb_mono.SendCommand("shutter c", False)
    usb_mono.WaitForIdle()

    # Reset the Start/Stop button text and functionality
    measure_button.config(text="Start Measurement", bg="#CCDDAA", command=toggle_measurement)

def start_measurement_thread():
    stop_thread.clear()
    measure_button.config(bg="#CCDDAA")
    measurement_thread = threading.Thread(target=start_measurement)
    measurement_thread.start()

def stop_measurement():
    stop_thread.set()

def toggle_measurement():
    if measure_button.config('text')[-1] == 'Start Measurement':
        start_measurement_thread()
        measure_button.config(text="Stop Measurement", bg="#FFCCCC", command=stop_measurement)
    else:
        stop_measurement()
        measure_button.config(text="Start Measurement", bg="#CCDDAA", command=toggle_measurement)

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

def align_wavelength():
    usb_mono.SendCommand("grating 1", False)
    usb_mono.WaitForIdle()
    usb_mono.SendCommand("gowave 532", False)
    usb_mono.WaitForIdle()
    usb_mono.SendCommand("shutter o", False)
    usb_mono.WaitForIdle()
    messagebox.showinfo("Alignment", "Wavelength set to 532 nm and shutter opened.")

def adjust_phase():
    best_phase, min_output = adjust_phase_to_minimize_output()
    #messagebox.showinfo("Phase Adjustment", f"Phase adjusted to {convert_phase_to_range(best_phase)} degrees to minimize output.")

root = tk.Tk()
root.title("Wavelength Measurement")

start_wavelength_var = tk.StringVar(value="375")
end_wavelength_var = tk.StringVar(value="850")
step_size_var = tk.StringVar(value="10")

tk.Label(root, text="Start Wavelength (nm):", font=("Helvetica", 12)).grid(row=0, column=0)
tk.Entry(root, textvariable=start_wavelength_var, font=("Helvetica", 12)).grid(row=0, column=1)

tk.Label(root, text="End Wavelength (nm):", font=("Helvetica", 12)).grid(row=1, column=0)
tk.Entry(root, textvariable=end_wavelength_var, font=("Helvetica", 12)).grid(row=1, column=1)

tk.Label(root, text="Step Size (nm):", font=("Helvetica", 12)).grid(row=2, column=0)
tk.Entry(root, textvariable=step_size_var, font=("Helvetica", 12)).grid(row=2, column=1)

plot_frame = ttk.Frame(root)
plot_frame.grid(row=3, column=0, columnspan=2)

fig, ax = plt.subplots()
ax.set_xlabel('Confirmed Mono Wavelength', fontsize=12)
ax.set_ylabel('Output', fontsize=12)
ax.set_title('Output vs. Confirmed Mono Wavelength', fontsize=12)
ax.tick_params(axis='both', which='major', labelsize=12)

canvas = FigureCanvasTkAgg(fig, master=plot_frame)
canvas.draw()
canvas.get_tk_widget().pack(padx=10, pady=10)

measure_button = tk.Button(root, text="Start Measurement", font=("Helvetica", 12), bg="#CCDDAA", command=toggle_measurement)
measure_button.grid(row=4, column=0, columnspan=2)

save_button = tk.Button(root, text="Save Data", font=("Helvetica", 12), command=save_data)
save_button.grid(row=5, column=0, columnspan=2)

align_button = tk.Button(root, text="Align", font=("Helvetica", 12), command=align_wavelength)
align_button.grid(row=6, column=0, columnspan=2)

adjust_phase_button = tk.Button(root, text="Adjust Phase", font=("Helvetica", 12), command=adjust_phase)
adjust_phase_button.grid(row=7, column=0, columnspan=2)

root.protocol("WM_DELETE_WINDOW", on_close)

root.mainloop()