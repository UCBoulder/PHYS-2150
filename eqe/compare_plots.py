import pandas as pd
import matplotlib.pyplot as plt

# Read the data from the CSV files
data1 = pd.read_csv('c:/Users/krist/Documents/GitHub/PHYS-2150/eqe/data/20240827/power-directly-out-of-mono.csv')
data2 = pd.read_csv('c:/Users/krist/Documents/GitHub/PHYS-2150/eqe/data/20240827/pm-nobackground-removed.csv')

# Normalize the data
data1['Normalized Power (W)'] = data1['Power (W)'] / data1['Power (W)'].max()
data2['Normalized Power (W)'] = data2['Power (W)'] / data2['Power (W)'].max()

# Ensure both datasets have the same wavelengths
merged_data = pd.merge(data1, data2, on='Wavelength (nm)', suffixes=('_1', '_2'))

# Calculate the fraction data2/data1
merged_data['Fraction Power (W)'] = merged_data['Normalized Power (W)_2'] / merged_data['Normalized Power (W)_1']

# Plot the results
fig, ax = plt.subplots(figsize=(10, 6))

# Plot fraction data
ax.plot(merged_data['Wavelength (nm)'], merged_data['Fraction Power (W)'], 'g.-', label='Fraction Power (W) (data2/data1)')

# Set plot titles and labels
ax.set_title('Fraction Power Comparison')
ax.set_xlabel('Wavelength (nm)')
ax.set_ylabel('Fraction Power (W)')
ax.legend()

# Show the plot
plt.show()