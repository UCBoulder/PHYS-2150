import pandas as pd
import matplotlib.pyplot as plt
import os

# Directory containing the CSV files
directory = './data/temp'

# Initialize a plot
plt.figure(figsize=(10, 6))

# Loop through each file in the directory
for filename in os.listdir(directory):
    if filename.endswith('.csv'):
        # Construct the full file path
        filepath = os.path.join(directory, filename)
        
        # Check if the file exists
        if os.path.exists(filepath):
            # Read the CSV file
            data = pd.read_csv(filepath, parse_dates=['Timestamp'])
            
            # Calculate elapsed time in minutes
            data['Elapsed Time'] = (data['Timestamp'] - data['Timestamp'].iloc[0]).dt.total_seconds() / 60
            
            # Filter data to include only up to 20 minutes
            data = data[data['Elapsed Time'] <= 20]
            
            # Plot temperature against elapsed time
            plt.plot(data['Elapsed Time'], data['Temperature'], label=f'{filename}')
            
            # Calculate and print statistics if needed
            max_temp = data['Temperature'].max()
            min_temp = data['Temperature'].min()
            mean_temp = data['Temperature'].mean()

            print(f"File: {filename}")
            print(f"Max Temperature: {max_temp} °C, Min Temperature: {min_temp} °C, Mean Temperature: {mean_temp} °C")

# Labeling the plot
plt.xlabel('Elapsed Time (minutes)')
plt.ylabel('Temperature (°C)')
plt.title('Temperature vs Elapsed Time')
plt.legend()
plt.grid(True)

# Show the plot
plt.show()