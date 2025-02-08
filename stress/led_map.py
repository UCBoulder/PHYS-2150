import serial
from past.builtins import raw_input
from TLPMX import TLPMX, TLPM_DEFAULT_CHANNEL
from ctypes import c_double, byref, c_uint32, create_string_buffer, c_bool
import warnings
import time
import csv
import matplotlib.pyplot as plt
import numpy as np

def show_error(message):
    print(f"Error: {message}")



printer_serial = serial.Serial('COM5', 115200)

# Ensure the printer is ready before proceeding
time.sleep(2)
printer_serial.flushInput()
printer_serial.write("\n".encode())

ready = False
start_time = time.time()
while time.time() - start_time < 5:  # 5-second timeout
    if (printer_serial.in_waiting):
        line = printer_serial.readline().decode().strip().lower()
        if "start" in line or "echo:busy" in line or "ok" in line:
            ready = True
            break

if not ready:
    show_error("3D printer did not signal readiness within 5 seconds.")

# Initialize Thorlabs Power Meter
def initialize_thorlabs_power_meter():
    tlPM = TLPMX()
    deviceCount = c_uint32()
    try:
        tlPM.findRsrc(byref(deviceCount))
        if (deviceCount.value == 0):
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

# Set wavelength to 660 nm
tlPM.setWavelength(c_double(660.0), TLPM_DEFAULT_CHANNEL)

# Define your grid ranges
x_positions = [0, 10, 20]  # Example values
y_positions = [0, 10, 20]

printer_serial.write("G28 Z\n".encode())
response = printer_serial.readline().decode().strip()
while response.lower() != "ok":
    response = printer_serial.readline().decode().strip()

printer_serial.write("G0 Z32\n".encode())
response = printer_serial.readline().decode().strip()
while response.lower() != "ok":
    response = printer_serial.readline().decode().strip()

def measure_thorlabs_power(tlPM):
    power_values = []
    for _ in range(200):
        reading = c_double()
        tlPM.measPower(byref(reading), TLPM_DEFAULT_CHANNEL)
        power_values.append(reading.value)
    # Multiply by 2 if using a 50% duty cycle chopper
    return (sum(power_values) / len(power_values)) * 2

def find_approx_max_position(printer_serial, tlPM, x_center=105, y_center=65, delta=5):
    """Coarse scan around (x_center,y_center) to find approximate max power."""
    best_power = -1
    best_coords = (x_center, y_center)
    x_range = range(x_center - delta, x_center + delta + 1, 1)
    y_range = range(y_center - delta, y_center + delta + 1, 1)
    for x in x_range:
        for y in y_range:
            printer_serial.write(f"G0 X{x} Y{y}\n".encode())
            # Wait for 'ok'
            resp = printer_serial.readline().decode().strip()
            while resp.lower() != "ok":
                resp = printer_serial.readline().decode().strip()
            # Measure power
            pwr = measure_thorlabs_power(tlPM)
            if pwr > best_power:
                best_power = pwr
                best_coords = (x, y)
    return best_coords

def measure_distribution(printer_serial, tlPM, center_x, center_y):
    """Measure a grid distribution around (center_x, center_y) and save it as CSV."""
    half_grid = 10
    x_range = range(center_x - half_grid, center_x + half_grid + 1, 1)
    y_range = range(center_y - half_grid, center_y + half_grid + 1, 1)
    results = []
    
    with open('distribution.csv', 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['X', 'Y', 'Power'])
        
        for x in x_range:
            for y in y_range:
                printer_serial.write(f"G0 X{x} Y{y}\n".encode())
                resp = printer_serial.readline().decode().strip()
                while resp.lower() != "ok":
                    resp = printer_serial.readline().decode().strip()
                pwr = measure_thorlabs_power(tlPM)
                print(f"X={x}, Y={y}, Power={pwr}")
                writer.writerow([x, y, pwr])
                results.append((x, y, pwr))
    
    return results

def identify_hotspot_area(distribution_results):
    """Return the bounding box (min_x, max_x, min_y, max_y) where power >= 90% of peak."""
    if not distribution_results:
        return None

    peak_power = max(p for (_, _, p) in distribution_results)
    threshold = 0.9 * peak_power
    coords_within_90 = [(x, y) for (x, y, p) in distribution_results if p >= threshold]
    if not coords_within_90:
        return None

    min_x = min(x for (x, _) in coords_within_90)
    max_x = max(x for (x, _) in coords_within_90)
    min_y = min(y for (_, y) in coords_within_90)
    max_y = max(y for (_, y) in coords_within_90)

    return (min_x, max_x, min_y, max_y)

def plot_heatmap(results):
    xs = sorted(list(set([r[0] for r in results])))
    ys = sorted(list(set([r[1] for r in results])))
    power_map = np.zeros((len(ys), len(xs)))

    # Build matrix
    for (x, y, p) in results:
        i = ys.index(y)
        j = xs.index(x)
        power_map[i, j] = p

    peak_power = np.max(power_map)
    peak_idx = np.unravel_index(np.argmax(power_map), power_map.shape)
    peak_y = ys[peak_idx[0]]
    peak_x = xs[peak_idx[1]]
    
    plt.figure(figsize=(8, 6))
    # Modify extent to match actual data range
    plt.imshow(power_map, 
               extent=[min(xs), max(xs), min(ys), max(ys)], 
               origin='lower', 
               aspect='equal',  # Changed to equal for proper aspect ratio
               cmap='viridis')
    plt.colorbar(label='Power (W)')
    
    # Add 90% contour
    threshold = 0.9 * peak_power
    plt.contour(xs, ys, power_map, levels=[threshold], 
                colors='red', linewidths=2)
    
    # Add centered rectangle
    rect = plt.Rectangle((peak_x - 5, peak_y - 6.5), 10, 13,
                        fill=False, edgecolor='white',
                        linestyle='--', linewidth=1)
    plt.gca().add_patch(rect)
    
    plt.xlabel('X Position (mm)')
    plt.ylabel('Y Position (mm)')
    plt.title(f'Power Distribution (Peak: {peak_power:.2e} W)')
    plt.show()

# Example usage:
# 1) Find approximate max near (105, 65)
max_x, max_y = find_approx_max_position(printer_serial, tlPM, 105, 65, 5)
# 2) Scan 100x100 around that max
print(f"Max found at approx: {max_x}, {max_y}")
dist_data = measure_distribution(printer_serial, tlPM, max_x, max_y)
hotspot = identify_hotspot_area(dist_data)
if hotspot:
    print("Region >=90% of peak power:", hotspot)
plot_heatmap(dist_data)

# for x in x_positions:
#     for y in y_positions:
#         # Send G-code to move to (x, y)
#         printer_serial.write(f"G0 X{x} Y{y}\n".encode())
#         response = printer_serial.readline().decode().strip()
#         while response.lower() != "ok":
#             response = printer_serial.readline().decode().strip()
        
#         # Measure power using tlPM
#         power = measure_thorlabs_power(tlPM)  # Implement reading power
#         print(f"X={x}, Y={y}, Power={power}")

        # (Optionally store results in a list or CSV)