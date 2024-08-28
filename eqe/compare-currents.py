import pandas as pd
import matplotlib.pyplot as plt

# Read the CSV files into DataFrames
df1 = pd.read_csv('c:/Users/krist/Documents/GitHub/PHYS-2150/eqe/data/20240828/350-450-5-5mv.csv')
df2 = pd.read_csv('c:/Users/krist/Documents/GitHub/PHYS-2150/eqe/data/20240828/350-450-5-100mv.csv')
df3 = pd.read_csv('c:/Users/krist/Documents/GitHub/PHYS-2150/eqe/data/20240828/350-450-5-200mv.csv')

# Plot the data
plt.figure(figsize=(10, 6))

plt.plot(df1['Wavelength (nm)'], df1['Current (A)'], label='File 1', marker='o')
plt.plot(df2['Wavelength (nm)'], df2['Current (A)'], label='File 2', marker='o')
plt.plot(df3['Wavelength (nm)'], df3['Current (A)'], label='File 3', marker='o')

# Customize the plot
plt.xlabel('Wavelength (nm)')
plt.ylabel('Current (A)')
plt.title('Current vs Wavelength')
plt.legend()

# Display the plot
plt.show()