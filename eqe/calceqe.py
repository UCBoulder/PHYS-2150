import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# Constants
h = 6.62607015e-34  # Planck's constant (Joule second)
c = 3.0e8  # Speed of light (meters per second)
e = 1.602176634e-19  # Elementary charge (Coulombs)

# Read the power data from the CSV file
power_data = pd.read_csv('c:/Users/krbu4353/GitHub/PHYS-2150/eqe/data/2025_02_06_power_cell2501-10.csv')

# List of current data files
current_files = [
    #'c:/Users/krist/Documents/GitHub/PHYS-2150/eqe/data/20240904/030/cm1.csv',
    'c:/Users/krbu4353/GitHub/PHYS-2150/eqe/data/2025_02_06_current_cell2501-10_pixel1.csv',
   # 'c:/Users/krist/Documents/GitHub/PHYS-2150/eqe/data/20240828/c6-100.csv',
   # 'c:/Users/krist/Documents/GitHub/PHYS-2150/eqe/data/20240828/c6sens.csv',
   # 'c:/Users/krist/Documents/GitHub/PHYS-2150/eqe/data/20240828/c6sens2.csv'


]

# Plot the results
fig, axs = plt.subplots(3, 1, figsize=(10, 15))

# Plot Power Measurements
axs[0].plot(power_data['Wavelength (nm)'], power_data['Power (W)'], 'b.-')
axs[0].set_title('Power Measurements')
axs[0].set_xlabel('Wavelength (nm)')
axs[0].set_ylabel('Power (W)')
axs[0].grid(True)
axs[0].set_xticks(np.arange(min(power_data['Wavelength (nm)']), max(power_data['Wavelength (nm)']) + 1, 20))

# Loop through each current data file
for i, current_file in enumerate(current_files):
    # Read the current data from the CSV file
    current_data = pd.read_csv(current_file)
    
    # Normalize current measurements
    #current_data['Current (A)'] = current_data['Current (A)'] / current_data['Current (A)'].max()
    
    # Calculate the EQE
    wavelength_meters = current_data['Wavelength (nm)'] * 1e-9  # Convert nm to meters
    eqe = (current_data['Current (A)'] / power_data['Power (W)']) * (h * c / (e * wavelength_meters))
    
    # Plot Current Measurements
    axs[1].plot(current_data['Wavelength (nm)'], current_data['Current (A)'], label=f'Current {i+1}')
    
    # Plot EQE
    axs[2].plot(current_data['Wavelength (nm)'], eqe, label=f'EQE {i+1}')

# Set titles and labels for Current Measurements plot
axs[1].set_title('Current Measurements')
axs[1].set_xlabel('Wavelength (nm)')
axs[1].set_ylabel('Current (A)')
axs[1].legend()
axs[1].grid(True)
axs[1].set_xticks(np.arange(min(current_data['Wavelength (nm)']), max(current_data['Wavelength (nm)']) + 1, 20))

# Set titles and labels for EQE plot
axs[2].set_title('External Quantum Efficiency (EQE)')
axs[2].set_xlabel('Wavelength (nm)')
axs[2].set_ylabel('EQE')
axs[2].legend()
axs[2].grid(True)
axs[2].set_xticks(np.arange(min(current_data['Wavelength (nm)']), max(current_data['Wavelength (nm)']) + 1, 20))

# Adjust layout with padding
plt.tight_layout(pad=3.0)

# Show the plot
plt.show()