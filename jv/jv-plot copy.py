import os
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

# Directory containing the CSV files
directory = 'C:/Users/krbu4353/GitHub/PHYS-2150/jv/data/2025_09_10/'

# Pixel area in cm^2
pixel_area = 0.14

# Initialize a plot
plt.figure(figsize=(10, 6))

# Loop through each file in the directory
for filename in os.listdir(directory):
    if filename.endswith('.csv'):
        # Construct the full file path
        filepath = os.path.join(directory, filename)
        # Read the CSV file
        data = pd.read_csv(filepath)
        
        # Multiply current values by -1 if needed
        data['Forward Scan (mA)'] = data['Forward Scan (mA)'] * -1

        # Convert current to current density (mA/cm^2)
        data['Forward Scan (mA/cm^2)'] = data['Forward Scan (mA)'] / pixel_area

        # Plot current density vs voltage for forward scan
        plt.plot(data['Voltage (V)'], data['Forward Scan (mA/cm^2)'], label=f'{filename} - Forward Scan (mA/cm²)')

        # Calculate Pmax, Isc, and Voc for Forward Scan (mA/cm^2)
        power_forward = data['Voltage (V)'] * data['Forward Scan (mA/cm^2)']
        pmax_forward = power_forward.max()
        pmax_index_forward = power_forward.idxmax()
        pmax_voltage_forward = data['Voltage (V)'].iloc[pmax_index_forward]
        pmax_current_forward = data['Forward Scan (mA/cm^2)'].iloc[pmax_index_forward]

        # Find the index of the row with the voltage closest to zero
        isc_index_forward = np.argmin(np.abs(data['Voltage (V)'].values))
        isc_forward = data['Forward Scan (mA/cm^2)'].iloc[isc_index_forward]
        isc_voltage_forward = data['Voltage (V)'].iloc[isc_index_forward]

        # Find the index of the row with the current closest to zero for Voc calculation
        voc_index_forward = np.argmin(np.abs(data['Forward Scan (mA/cm^2)'].values))
        voc_forward = data['Voltage (V)'].iloc[voc_index_forward]
        voc_current_forward = data['Forward Scan (mA/cm^2)'].iloc[voc_index_forward]

        # Plot markers for Isc, Voc, and Pmax for Forward Scan (mA/cm^2)
        plt.scatter(isc_voltage_forward, isc_forward, color='red', marker='x', s=100, label=f'Jsc Forward ({isc_forward:.2f} mA/cm²)')
        plt.scatter(voc_forward, voc_current_forward, color='green', marker='x', s=100, label=f'Voc Forward ({voc_forward:.2f} V)')
        plt.scatter(pmax_voltage_forward, pmax_current_forward, color='blue', marker='x', s=100, label=f'Pmax Forward ({pmax_forward:.2f} mW/cm²)')

# Show the plot with legends
plt.legend()
plt.xlabel('Voltage (V)')
plt.ylabel('Current Density (mA/cm²)')
plt.title('JV Plot')
plt.grid(True)
plt.show()