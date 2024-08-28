import pandas as pd
import numpy as np

# Read the data from the CSV file
data = pd.read_csv('c:/Users/krist/Documents/GitHub/PHYS-2150/eqe/data/astmg173.csv')

# Filter the data between 300 and 850 nm
filtered_data = data[(data['Wvlgth nm'] >= 300) & (data['Wvlgth nm'] <= 850)]

# Integrate the power between 300 and 850 nm
total_power = np.trapz(filtered_data['Global tilt  W*m-2*nm-1'], filtered_data['Wvlgth nm'])

# Filter the data between 300 and 375 nm
filtered_data_300_375 = data[(data['Wvlgth nm'] >= 300) & (data['Wvlgth nm'] <= 375)]

# Integrate the power between 300 and 375 nm
power_300_375 = np.trapz(filtered_data_300_375['Global tilt  W*m-2*nm-1'], filtered_data_300_375['Wvlgth nm'])

# Calculate the fraction of power from 300 to 375 nm
fraction_power_300_375 = power_300_375 / total_power

print(f"Total Power (300-850 nm): {total_power}")
print(f"Power (300-375 nm): {power_300_375}")
print(f"Fraction of Power (300-375 nm): {fraction_power_300_375}")