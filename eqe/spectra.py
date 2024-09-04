import numpy as np

def read_data(file_path):
    data = np.loadtxt(file_path)
    wavelengths = data[:, 0]
    intensities = data[:, 1]
    return wavelengths, intensities

def find_fwhm(wavelengths, intensities):
    # Find the peak intensity and its corresponding wavelength
    peak_index = np.argmax(intensities)
    peak_intensity = intensities[peak_index]
    peak_wavelength = wavelengths[peak_index]

    # Calculate the half maximum
    half_max = peak_intensity / 2

    # Find the wavelengths where the intensity crosses the half maximum
    left_idx = np.where(intensities[:peak_index] <= half_max)[0][-1]
    right_idx = np.where(intensities[peak_index:] <= half_max)[0][0] + peak_index

    left_wavelength = wavelengths[left_idx]
    right_wavelength = wavelengths[right_idx]

    # Calculate the FWHM
    fwhm = right_wavelength - left_wavelength
    return fwhm, peak_wavelength, peak_intensity

def main():
    file_path = 'c:/Users/krist/Documents/GitHub/PHYS-2150/eqe/data/spectra/532nm-9l00um-nof.txt'  # Replace with your file path
    wavelengths, intensities = read_data(file_path)
    fwhm, peak_wavelength, peak_intensity = find_fwhm(wavelengths, intensities)
    
    print(f"Peak Wavelength: {peak_wavelength}")
    print(f"Peak Intensity: {peak_intensity}")
    print(f"Full Width at Half Maximum (FWHM): {fwhm}")

if __name__ == "__main__":
    main()