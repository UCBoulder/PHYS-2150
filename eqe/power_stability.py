import time
import csv
from ctypes import c_double, byref, c_uint32, create_string_buffer, c_bool
from cornerstone_mono import Cornerstone_Mono
from TLPMX import TLPMX, TLPM_DEFAULT_CHANNEL
import warnings
import pyvisa as visa
import matplotlib.pyplot as plt
import pandas as pd
import os

# Initialize the VISA resource manager
rm = visa.ResourceManager()
warnings.simplefilter("ignore")

# Initialize Thorlabs Power Meter
tlPM = TLPMX()
deviceCount = c_uint32()
tlPM.findRsrc(byref(deviceCount))

if deviceCount.value == 0:
    raise Exception("No Thorlabs power meter devices found.")

resourceName = create_string_buffer(1024)
tlPM.getRsrcName(0, resourceName)
print(f"Resource Name: {resourceName.value.decode()}")  # Print the resource name for debugging

try:
    tlPM.open(resourceName, c_bool(True), c_bool(True))
except Exception as e:
    print(f"Failed to open resource: {e}")
    raise

# Initialize Monochromator
usb_mono = Cornerstone_Mono(rm, rem_ifc="usb", timeout_msec=29000)

def measure_power_over_wavelengths(start_wavelength, end_wavelength, step_size):
    power_measurements = []
    current_wavelength = start_wavelength

    while current_wavelength <= end_wavelength:
        # Check the wavelength and switch gratings accordingly
        if current_wavelength < 685:
            usb_mono.SendCommand("grating 1", False)
        else:
            usb_mono.SendCommand("grating 2", False)
            
        usb_mono.SendCommand(f"gowave {current_wavelength}", False)
        usb_mono.WaitForIdle()

        confirmed_mono_wavelength = usb_mono.GetQueryResponse("wave?")
        confirmed_mono_wavelength_float = float(confirmed_mono_wavelength)
        tlPM.setWavelength(c_double(confirmed_mono_wavelength_float), TLPM_DEFAULT_CHANNEL)
        time.sleep(0.2)  # Wait for the power reading to stabilize

        # Measure power 50 times and calculate the average
        power_values = []
        for _ in range(50):
            power = c_double()
            tlPM.measPower(byref(power), TLPM_DEFAULT_CHANNEL)
            power_values.append(power.value)
        
        average_power = sum(power_values) / len(power_values)
        power_measurements.append(average_power)
        current_wavelength += step_size

    return power_measurements

def main():
    start_wavelength = 350.0  # Example start wavelength
    end_wavelength = 850.0    # Example end wavelength
    step_size = 10.0          # Example step size
    num_iterations = 10       # Number of times to repeat the measurement

    # Erase the CSV file if it exists
    if os.path.exists('stable_power_measurements.csv'):
        os.remove('stable_power_measurements.csv')

    # Initialize CSV file with headers
    with open('stable_power_measurements.csv', 'w', newline='') as csvfile:
        csvwriter = csv.writer(csvfile)
        headers = ['Wavelength (nm)'] + [f'Measurement {i+1}' for i in range(num_iterations)]
        csvwriter.writerow(headers)

    # Perform measurements and write to CSV
    for iteration in range(num_iterations):
        print(f"Starting measurement iteration {iteration + 1}...")
        usb_mono.SendCommand("shutter o", False)
        usb_mono.WaitForIdle()
        power_measurements = measure_power_over_wavelengths(start_wavelength, end_wavelength, step_size)
        # usb_mono.SendCommand("shutter c", False)
        # usb_mono.WaitForIdle() 

        # Read existing data
        with open('stable_power_measurements.csv', 'r') as csvfile:
            csvreader = csv.reader(csvfile)
            rows = list(csvreader)

        # Append new measurements to the existing data
        for i, power in enumerate(power_measurements):
            if iteration == 0:
                rows.append([start_wavelength + i * step_size, power])
            else:
                rows[i + 1].append(power)

        # Write updated data back to CSV
        with open('stable_power_measurements.csv', 'w', newline='') as csvfile:
            csvwriter = csv.writer(csvfile)
            csvwriter.writerows(rows)

        print(f"Completed measurement iteration {iteration + 1}")

    # Plot the results
    plot_results('stable_power_measurements.csv')

def plot_results(csv_filename):
    # Read the CSV file into a DataFrame
    df = pd.read_csv(csv_filename)

    # Plot the data
    plt.figure(figsize=(10, 6))
    for column in df.columns[1:]:
        plt.plot(df['Wavelength (nm)'], df[column], marker='o', label=column)

    # Customize the plot
    plt.xlabel('Wavelength (nm)')
    plt.ylabel('Power (W)')
    plt.title('Power Stability Over Time')
    plt.legend()
    plt.grid(True)

    # Display the plot
    plt.show()

if __name__ == "__main__":
    main()