import os
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

# Directory containing the CSV files
directory = './data/'

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
        data['Forward Bias'] = data['Forward Bias'] * -1
        if 'Reverse Bias' in data.columns:
            data['Reverse Bias'] = data['Reverse Bias'] * -1
        
        # Plot each current measurement against voltage
        plt.plot(data['Voltage'], data['Forward Bias'], label=f'{filename} - Forward Bias')
        if 'Reverse Bias' in data.columns:
            plt.plot(data['Voltage'], data['Reverse Bias'], label=f'{filename} - Reverse Bias')
        
        # Calculate Pmax, Isc, and Voc for Forward Bias
        power_forward = data['Voltage'] * data['Forward Bias']
        pmax_forward = power_forward.max()
        pmax_index_forward = power_forward.idxmax()
        pmax_voltage_forward = data['Voltage'].iloc[pmax_index_forward]
        pmax_current_forward = data['Forward Bias'].iloc[pmax_index_forward]

        # Find the index of the row with the voltage closest to zero
        isc_index_forward = np.argmin(np.abs(data['Voltage'].values))
        # Use this index to find the corresponding current value for Isc
        isc_forward = data['Forward Bias'].iloc[isc_index_forward]
        isc_voltage_forward = data['Voltage'].iloc[isc_index_forward]

        # Find the index of the row with the current closest to zero for Voc calculation
        voc_index_forward = np.argmin(np.abs(data['Forward Bias'].values))
        voc_forward = data['Voltage'].iloc[voc_index_forward]
        voc_current_forward = data['Forward Bias'].iloc[voc_index_forward]

        # Plot markers for Isc, Voc, and Pmax for Forward Bias
        plt.scatter(isc_voltage_forward, isc_forward, color='red', marker='x', s=100, label=f'Isc Forward ({isc_forward:.2f}mA)')
        plt.scatter(voc_forward, voc_current_forward, color='green', marker='x', s=100, label=f'Voc Forward ({voc_forward:.2f}V)')
        plt.scatter(pmax_voltage_forward, pmax_current_forward, color='blue', marker='x', s=100, label=f'Pmax Forward ({pmax_forward:.2f}mW)')

        # Calculate Pmax, Isc, and Voc for Reverse Bias if it exists
        if 'Reverse Bias' in data.columns:
            power_reverse = data['Voltage'] * data['Reverse Bias']
            pmax_reverse = power_reverse.max()
            pmax_index_reverse = power_reverse.idxmax()
            pmax_voltage_reverse = data['Voltage'].iloc[pmax_index_reverse]
            pmax_current_reverse = data['Reverse Bias'].iloc[pmax_index_reverse]

            # Find the index of the row with the voltage closest to zero
            isc_index_reverse = np.argmin(np.abs(data['Voltage'].values))
            # Use this index to find the corresponding current value for Isc
            isc_reverse = data['Reverse Bias'].iloc[isc_index_reverse]
            isc_voltage_reverse = data['Voltage'].iloc[isc_index_reverse]

            # Find the index of the row with the current closest to zero for Voc calculation
            voc_index_reverse = np.argmin(np.abs(data['Reverse Bias'].values))
            voc_reverse = data['Voltage'].iloc[voc_index_reverse]
            voc_current_reverse = data['Reverse Bias'].iloc[voc_index_reverse]

            # Plot markers for Isc, Voc, and Pmax for Reverse Bias
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