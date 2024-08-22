import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# Constants
h = 6.62607015e-34  # Planck's constant (Joule second)
c = 3.0e8  # Speed of light (meters per second)
e = 1.602176634e-19  # Elementary charge (Coulombs)

# Read the data from the CSV files
power_data = pd.read_csv('power_measurements.csv')
current_data = pd.read_csv('current_measurements.csv')

# Convert current measurements to Amperes
current_data['Current (A)'] = current_data['Current (A)'] * 1e-4 /2

# Calculate the EQE
wavelength_meters = current_data['Wavelength (nm)'] * 1e-9  # Convert nm to meters
eqe = (current_data['Current (A)'] / power_data['Power Measurements (W)']) * (h * c / (e * wavelength_meters))

# Create a DataFrame to store the results
eqe_data = pd.DataFrame({
    'Wavelength (nm)': current_data['Wavelength (nm)'],
    'EQE': eqe
})

# Save the EQE data to a CSV file
eqe_data.to_csv('eqe_results.csv', index=False)

# Plot the results
fig, axs = plt.subplots(3, 1, figsize=(10, 15))

# Plot Power Measurements
axs[0].plot(power_data['Wavelength (nm)'], power_data['Power Measurements (W)'], 'b.-')
axs[0].set_title('Power Measurements')
axs[0].set_xlabel('Wavelength (nm)')
axs[0].set_ylabel('Power (W)')

# Plot Current Measurements
axs[1].plot(current_data['Wavelength (nm)'], current_data['Current (A)'], 'r.-')
axs[1].set_title('Current Measurements')
axs[1].set_xlabel('Wavelength (nm)')
axs[1].set_ylabel('Current (A)')

# Plot EQE
axs[2].plot(eqe_data['Wavelength (nm)'], eqe_data['EQE'], 'g.-')
axs[2].set_title('External Quantum Efficiency (EQE)')
axs[2].set_xlabel('Wavelength (nm)')
axs[2].set_ylabel('EQE')

# Adjust layout with padding
plt.tight_layout(pad=3.0)

# Show the plot
plt.show()