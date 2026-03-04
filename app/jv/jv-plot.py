import os
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

# Directory containing the CSV files
# Default to current working directory - users should change this to their data directory
# or pass directory as command line argument
import sys
if len(sys.argv) > 1:
    directory = sys.argv[1]
else:
    directory = os.getcwd()
    print(f"Usage: python jv-plot.py <data_directory>")
    print(f"No directory specified, using current directory: {directory}")

# Initialize a plot
plt.figure(figsize=(10, 6))

# Loop through each file in the directory
for filename in os.listdir(directory):
    if filename.endswith('.csv'):
        # Construct the full file path
        filepath = os.path.join(directory, filename)
        # Read the CSV file
        data = pd.read_csv(filepath)
        
        # Multiply current values by -1
        #data['Forward Scan (mA)'] = data['Forward Scan (mA)'] * -1
        if 'Reverse Scan (mA)' in data.columns:
            data['Reverse Scan (mA)'] = data['Reverse Scan (mA)'] * -1
        
        # Plot each current measurement against voltage
        #plt.plot(data['Voltage (V)'], data['Forward Scan (mA)'], label=f'{filename} - Forward Scan (mA)')
        if 'Reverse Scan (mA)' in data.columns:
            plt.plot(data['Voltage (V)'], data['Reverse Scan (mA)'], label=f'{filename} - Reverse Scan (mA)')
        
        # Calculate Pmax, Isc, and Voc for Forward Scan (mA)
        # power_forward = data['Voltage (V)'] * data['Forward Scan (mA)']
        # pmax_forward = power_forward.max()
        # pmax_index_forward = power_forward.idxmax()
        # pmax_voltage_forward = data['Voltage (V)'].iloc[pmax_index_forward]
        # pmax_current_forward = data['Forward Scan (mA)'].iloc[pmax_index_forward]

        # Find the index of the row with the voltage closest to zero
        isc_index_forward = np.argmin(np.abs(data['Voltage (V)'].values))
        # Use this index to find the corresponding current value for Isc
        isc_forward = data['Forward Scan (mA)'].iloc[isc_index_forward]
        isc_voltage_forward = data['Voltage (V)'].iloc[isc_index_forward]

        # Find the index of the row with the current closest to zero for Voc calculation
        # voc_index_forward = np.argmin(np.abs(data['Forward Scan (mA)'].values))
        # voc_forward = data['Voltage (V)'].iloc[voc_index_forward]
        # voc_current_forward = data['Forward Scan (mA)'].iloc[voc_index_forward]

        # # Plot markers for Isc, Voc, and Pmax for Forward Scan (mA)
        # plt.scatter(isc_voltage_forward, isc_forward, color='red', marker='x', s=100, label=f'Isc Forward ({isc_forward:.2f}mA)')
        # plt.scatter(voc_forward, voc_current_forward, color='green', marker='x', s=100, label=f'Voc Forward ({voc_forward:.2f}V)')
        # plt.scatter(pmax_voltage_forward, pmax_current_forward, color='blue', marker='x', s=100, label=f'Pmax Forward ({pmax_forward:.2f}mW)')

        # Calculate Pmax, Isc, and Voc for Reverse Scan (mA) if it exists
        if 'Reverse Scan (mA)' in data.columns:
            power_reverse = data['Voltage (V)'] * data['Reverse Scan (mA)']
            pmax_reverse = power_reverse.max()
            pmax_index_reverse = power_reverse.idxmax()
            pmax_voltage_reverse = data['Voltage (V)'].iloc[pmax_index_reverse]
            pmax_current_reverse = data['Reverse Scan (mA)'].iloc[pmax_index_reverse]

            # Find the index of the row with the voltage closest to zero
            isc_index_reverse = np.argmin(np.abs(data['Voltage (V)'].values))
            # Use this index to find the corresponding current value for Isc
            isc_reverse = data['Reverse Scan (mA)'].iloc[isc_index_reverse]
            isc_voltage_reverse = data['Voltage (V)'].iloc[isc_index_reverse]

            # Find the index of the row with the current closest to zero for Voc calculation
            voc_index_reverse = np.argmin(np.abs(data['Reverse Scan (mA)'].values))
            voc_reverse = data['Voltage (V)'].iloc[voc_index_reverse]
            voc_current_reverse = data['Reverse Scan (mA)'].iloc[voc_index_reverse]

            # Plot markers for Isc, Voc, and Pmax for Reverse Scan (mA)
            plt.scatter(isc_voltage_reverse, isc_reverse, color='orange', marker='x', s=100, label=f'Isc Reverse ({isc_reverse:.2f}mA)')
            plt.scatter(voc_reverse, voc_current_reverse, color='purple', marker='x', s=100, label=f'Voc Reverse ({voc_reverse:.2f}V)')
            plt.scatter(pmax_voltage_reverse, pmax_current_reverse, color='cyan', marker='x', s=100, label=f'Pmax Reverse ({pmax_reverse:.2f}mW)')

# Show the plot with legends
plt.legend()
plt.xlabel('Voltage (V)')
plt.ylabel('Current (mA)')
plt.title('JV Plot')
plt.grid(True)
plt.show()