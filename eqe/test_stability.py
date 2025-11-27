"""
Stability Test Script for EQE Measurement System

This script tests the stability of power and current measurements over time
using the same models and methods as the main application. This ensures
direct comparison with actual measurement conditions.

Note: Power and current measurements require different hardware setups
and must be tested separately.

Usage:
    cd eqe
    python test_stability.py [options]

Options:
    --test-type: 'power' or 'current' (default: 'current')
    --wavelength: Wavelength to test at in nm (default: 550)
    --duration: Test duration in minutes (default: 5)
    --interval: Measurement interval in seconds (default: 2)
    --pixel: Pixel number for current test (default: 1)
    --output: Output CSV file path (default: auto-generated)

Examples:
    cd eqe
    python test_stability.py
    python test_stability.py --wavelength 600 --duration 10
    python test_stability.py --test-type power --duration 5
"""

import time
import csv
import argparse
import datetime
import numpy as np
from typing import List, Tuple
import matplotlib.pyplot as plt
import sys
import os
from pathlib import Path

# Add the parent directory to Python path to enable absolute imports
# This allows the script to import from eqe package
script_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(script_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# Import the actual models used by the application
from eqe.models.power_measurement import PowerMeasurementModel
from eqe.models.current_measurement import CurrentMeasurementModel
from eqe.controllers.thorlabs_power_meter import ThorlabsPowerMeterController
from eqe.controllers.monochromator import MonochromatorController
from eqe.controllers.picoscope_lockin import PicoScopeController
from eqe.config.settings import DEVICE_CONFIGS, DeviceType
from eqe.utils.data_handling import MeasurementDataLogger

import pyvisa


class StabilityTest:
    """Test measurement stability over time."""
    
    def __init__(self):
        """Initialize test with device controllers."""
        self.logger = MeasurementDataLogger()
        self.rm = pyvisa.ResourceManager()
        
        # Device controllers
        self.power_meter = None
        self.monochromator = None
        self.lockin = None
        
        # Measurement models
        self.power_model = None
        self.current_model = None
        
    def initialize_devices(self) -> bool:
        """Initialize all devices."""
        print("\n" + "="*70)
        print("INITIALIZING DEVICES")
        print("="*70)
        
        try:
            # Initialize power meter
            print("\n[1/3] Initializing Thorlabs Power Meter...")
            self.power_meter = ThorlabsPowerMeterController()
            self.power_meter.connect()
            print("✓ Power meter connected")
            
            # Initialize monochromator
            print("\n[2/3] Initializing Monochromator...")
            config = DEVICE_CONFIGS[DeviceType.MONOCHROMATOR]
            self.monochromator = MonochromatorController(self.rm)
            self.monochromator.connect(
                interface=config["interface"],
                timeout_msec=config["timeout_msec"]
            )
            serial_number = self.monochromator.serial_number
            print(f"✓ Monochromator connected (S/N: {serial_number})")
            
            # Initialize PicoScope lock-in
            print("\n[3/3] Initializing PicoScope Lock-in...")
            config = DEVICE_CONFIGS[DeviceType.PICOSCOPE_LOCKIN]
            self.lockin = PicoScopeController()
            if not self.lockin.connect():
                raise Exception("Failed to connect to PicoScope")
            
            chopper_freq = config.get("default_chopper_freq", 81)
            num_cycles = config.get("default_num_cycles", 100)
            self.lockin.set_reference_frequency(chopper_freq)
            self.lockin.set_num_cycles(num_cycles)
            print(f"✓ PicoScope connected (Freq: {chopper_freq} Hz, Cycles: {num_cycles})")
            
            # Create measurement models
            self.power_model = PowerMeasurementModel(
                self.power_meter, self.monochromator, self.logger
            )
            self.current_model = CurrentMeasurementModel(
                self.lockin, self.monochromator, self.logger
            )
            
            print("\n" + "="*70)
            print("✓ ALL DEVICES INITIALIZED SUCCESSFULLY")
            print("="*70 + "\n")
            return True
            
        except Exception as e:
            print(f"\n✗ Device initialization failed: {e}")
            return False
    
    def test_power_stability(self, wavelength: float, duration_min: float, 
                            interval_sec: float) -> Tuple[List[float], List[float]]:
        """
        Test power measurement stability.
        
        Args:
            wavelength: Wavelength to test at (nm)
            duration_min: Test duration in minutes
            interval_sec: Interval between measurements in seconds
            
        Returns:
            Tuple[List[float], List[float]]: (timestamps, power_values)
        """
        print("\n" + "="*70)
        print(f"POWER STABILITY TEST")
        print("="*70)
        print(f"Wavelength: {wavelength} nm")
        print(f"Duration: {duration_min} minutes ({duration_min * 60:.0f} seconds)")
        print(f"Interval: {interval_sec} seconds")
        print(f"Expected measurements: ~{int(duration_min * 60 / interval_sec)}")
        print("="*70 + "\n")
        
        timestamps = []
        power_values = []
        
        # Configure monochromator
        print(f"Configuring monochromator to {wavelength} nm...")
        confirmed_wavelength = self.monochromator.configure_for_wavelength(wavelength)
        print(f"✓ Monochromator at {confirmed_wavelength} nm\n")
        
        # Open shutter
        self.monochromator.open_shutter()
        
        # Wait for stabilization
        print("Waiting 2 seconds for initial stabilization...")
        time.sleep(2)
        
        # Start test
        start_time = time.time()
        end_time = start_time + (duration_min * 60)
        measurement_count = 0
        
        print("\nStarting measurements...")
        print("-" * 70)
        print(f"{'Time (s)':>10} | {'Power (W)':>15} | {'Power (μW)':>15} | {'Notes':>20}")
        print("-" * 70)
        
        try:
            while time.time() < end_time:
                current_time = time.time() - start_time
                
                # Use the same method as the application
                # Read power using power meter with configured averaging
                from eqe.config.settings import POWER_MEASUREMENT_CONFIG
                num_measurements = POWER_MEASUREMENT_CONFIG["num_measurements"]
                correction_factor = POWER_MEASUREMENT_CONFIG["correction_factor"]
                
                power = self.power_meter.measure_power_average(
                    num_measurements=num_measurements,
                    correction_factor=correction_factor
                )
                
                timestamps.append(current_time)
                power_values.append(power)
                measurement_count += 1
                
                # Display with statistics
                if len(power_values) > 1:
                    mean = np.mean(power_values)
                    std = np.std(power_values)
                    cv = (std / mean * 100) if mean > 0 else 0
                    note = f"CV: {cv:.2f}%"
                else:
                    note = "Initial"
                
                print(f"{current_time:>10.1f} | {power:>15.6e} | {power*1e6:>15.3f} | {note:>20}")
                
                # Wait for next measurement
                time.sleep(interval_sec)
                
        except KeyboardInterrupt:
            print("\n\nTest interrupted by user")
        finally:
            # Close shutter
            self.monochromator.close_shutter()
        
        print("-" * 70)
        print(f"\n✓ Completed {measurement_count} measurements")
        
        # Calculate statistics
        if power_values:
            self._print_statistics("Power", power_values, unit="W", scale=1e6, scale_unit="μW")
        
        return timestamps, power_values
    
    def test_current_stability(self, wavelength: float, duration_min: float,
                              interval_sec: float, pixel_number: int = 1) -> Tuple[List[float], List[float]]:
        """
        Test current measurement stability.
        
        Args:
            wavelength: Wavelength to test at (nm)
            duration_min: Test duration in minutes
            interval_sec: Interval between measurements in seconds
            pixel_number: Pixel number (for documentation)
            
        Returns:
            Tuple[List[float], List[float]]: (timestamps, current_values)
        """
        print("\n" + "="*70)
        print(f"CURRENT STABILITY TEST")
        print("="*70)
        print(f"Wavelength: {wavelength} nm")
        print(f"Pixel: {pixel_number}")
        print(f"Duration: {duration_min} minutes ({duration_min * 60:.0f} seconds)")
        print(f"Interval: {interval_sec} seconds")
        print(f"Expected measurements: ~{int(duration_min * 60 / interval_sec)}")
        print("="*70 + "\n")
        
        timestamps = []
        current_values = []
        
        # Configure monochromator
        print(f"Configuring monochromator to {wavelength} nm...")
        confirmed_wavelength = self.monochromator.configure_for_wavelength(wavelength)
        print(f"✓ Monochromator at {confirmed_wavelength} nm\n")
        
        # Open shutter
        self.monochromator.open_shutter()
        
        # Wait for stabilization
        print("Waiting 2 seconds for initial stabilization...")
        time.sleep(2)
        
        # Start test
        start_time = time.time()
        end_time = start_time + (duration_min * 60)
        measurement_count = 0
        
        print("\nStarting measurements...")
        print("-" * 70)
        print(f"{'Time (s)':>10} | {'Current (A)':>15} | {'Current (nA)':>15} | {'Notes':>20}")
        print("-" * 70)
        
        try:
            while time.time() < end_time:
                current_time = time.time() - start_time
                
                # Use the same method as the application
                current = self.current_model._read_lockin_current()
                
                timestamps.append(current_time)
                current_values.append(current)
                measurement_count += 1
                
                # Display with statistics
                if len(current_values) > 1:
                    mean = np.mean(current_values)
                    std = np.std(current_values)
                    cv = (std / mean * 100) if mean > 0 else 0
                    note = f"CV: {cv:.2f}%"
                else:
                    note = "Initial"
                
                print(f"{current_time:>10.1f} | {current:>15.6e} | {current*1e9:>15.3f} | {note:>20}")
                
                # Wait for next measurement
                time.sleep(interval_sec)
                
        except KeyboardInterrupt:
            print("\n\nTest interrupted by user")
        finally:
            # Close shutter
            self.monochromator.close_shutter()
        
        print("-" * 70)
        print(f"\n✓ Completed {measurement_count} measurements")
        
        # Calculate statistics
        if current_values:
            self._print_statistics("Current", current_values, unit="A", scale=1e9, scale_unit="nA")
        
        return timestamps, current_values
    
    def _print_statistics(self, name: str, values: List[float], 
                         unit: str = "", scale: float = 1.0, scale_unit: str = ""):
        """Print statistical summary of measurements."""
        values_array = np.array(values)
        
        mean = np.mean(values_array)
        std = np.std(values_array)
        min_val = np.min(values_array)
        max_val = np.max(values_array)
        cv = (std / mean * 100) if mean > 0 else 0
        
        print(f"\n{'='*70}")
        print(f"STATISTICS - {name}")
        print("="*70)
        print(f"Number of measurements: {len(values)}")
        print(f"Mean:       {mean:>15.6e} {unit} ({mean*scale:>10.3f} {scale_unit})")
        print(f"Std Dev:    {std:>15.6e} {unit} ({std*scale:>10.3f} {scale_unit})")
        print(f"CV:         {cv:>15.2f} %")
        print(f"Min:        {min_val:>15.6e} {unit} ({min_val*scale:>10.3f} {scale_unit})")
        print(f"Max:        {max_val:>15.6e} {unit} ({max_val*scale:>10.3f} {scale_unit})")
        print(f"Range:      {max_val-min_val:>15.6e} {unit} ({(max_val-min_val)*scale:>10.3f} {scale_unit})")
        print("="*70)
    
    def save_results(self, timestamps: List[float], values: List[float],
                    test_type: str, wavelength: float, filename: str = None):
        """Save test results to CSV file."""
        # Create stability_tests subdirectory if it doesn't exist
        output_dir = Path("stability_tests")
        output_dir.mkdir(exist_ok=True)
        
        if filename is None:
            date_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = output_dir / f"stability_test_{test_type}_{wavelength}nm_{date_str}.csv"
        else:
            filename = output_dir / filename
        
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            
            # Write header with metadata
            writer.writerow([f"# Stability Test - {test_type.capitalize()}"])
            writer.writerow([f"# Wavelength: {wavelength} nm"])
            writer.writerow([f"# Date: {datetime.datetime.now().isoformat()}"])
            writer.writerow([f"# Number of measurements: {len(values)}"])
            
            if values:
                mean = np.mean(values)
                std = np.std(values)
                cv = (std / mean * 100) if mean > 0 else 0
                writer.writerow([f"# Mean: {mean:.6e}"])
                writer.writerow([f"# Std Dev: {std:.6e}"])
                writer.writerow([f"# CV: {cv:.2f}%"])
            
            writer.writerow([])  # Blank line
            
            # Write data
            if test_type == "power":
                writer.writerow(["Time (s)", "Power (W)", "Power (μW)"])
                for t, v in zip(timestamps, values):
                    writer.writerow([f"{t:.1f}", f"{v:.6e}", f"{v*1e6:.3f}"])
            elif test_type == "current":
                writer.writerow(["Time (s)", "Current (A)", "Current (nA)"])
                for t, v in zip(timestamps, values):
                    writer.writerow([f"{t:.1f}", f"{v:.6e}", f"{v*1e9:.3f}"])
        
        print(f"\n✓ Results saved to: {filename}")
    
    def plot_results(self, timestamps: List[float], values: List[float],
                    test_type: str, wavelength: float):
        """Plot test results."""
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8))
        
        # Convert to arrays
        t = np.array(timestamps)
        v = np.array(values)
        
        # Plot 1: Time series
        if test_type == "power":
            v_scaled = v * 1e6  # Convert to μW
            unit = "μW"
            title = f"Power Stability at {wavelength} nm"
        else:
            v_scaled = v * 1e9  # Convert to nA
            unit = "nA"
            title = f"Current Stability at {wavelength} nm"
        
        ax1.plot(t, v_scaled, 'o-', markersize=3, linewidth=1)
        ax1.set_xlabel("Time (seconds)", fontsize=12)
        ax1.set_ylabel(f"{test_type.capitalize()} ({unit})", fontsize=12)
        ax1.set_title(title, fontsize=14, fontweight='bold')
        ax1.grid(True, alpha=0.3)
        
        # Add mean and ±1σ lines
        mean = np.mean(v_scaled)
        std = np.std(v_scaled)
        ax1.axhline(mean, color='r', linestyle='--', label=f'Mean: {mean:.3f} {unit}')
        ax1.axhline(mean + std, color='orange', linestyle=':', alpha=0.7, label=f'+1σ: {mean+std:.3f} {unit}')
        ax1.axhline(mean - std, color='orange', linestyle=':', alpha=0.7, label=f'-1σ: {mean-std:.3f} {unit}')
        ax1.legend(loc='best')
        
        # Plot 2: Histogram
        ax2.hist(v_scaled, bins=30, edgecolor='black', alpha=0.7)
        ax2.set_xlabel(f"{test_type.capitalize()} ({unit})", fontsize=12)
        ax2.set_ylabel("Frequency", fontsize=12)
        ax2.set_title("Distribution", fontsize=12)
        ax2.grid(True, alpha=0.3, axis='y')
        
        # Add statistics text
        cv = (std / mean * 100) if mean > 0 else 0
        stats_text = f"Mean: {mean:.3f} {unit}\nStd: {std:.3f} {unit}\nCV: {cv:.2f}%\nN: {len(v)}"
        ax2.text(0.98, 0.98, stats_text,
                transform=ax2.transAxes,
                verticalalignment='top',
                horizontalalignment='right',
                bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5),
                fontsize=10)
        
        plt.tight_layout()
        
        # Save plot in stability_tests subdirectory
        output_dir = Path("stability_tests")
        output_dir.mkdir(exist_ok=True)
        
        date_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        plot_filename = output_dir / f"stability_plot_{test_type}_{wavelength}nm_{date_str}.png"
        plt.savefig(plot_filename, dpi=150, bbox_inches='tight')
        print(f"✓ Plot saved to: {plot_filename}")
        
        plt.show()
    
    def cleanup(self):
        """Clean up and close all devices."""
        print("\n" + "="*70)
        print("CLEANING UP")
        print("="*70)
        
        try:
            if self.monochromator:
                self.monochromator.close_shutter()
                self.monochromator.disconnect()
                print("✓ Monochromator closed")
            
            if self.power_meter:
                self.power_meter.disconnect()
                print("✓ Power meter disconnected")
            
            if self.lockin:
                self.lockin.disconnect()
                print("✓ PicoScope disconnected")
                
        except Exception as e:
            print(f"Warning during cleanup: {e}")
        
        print("="*70 + "\n")


def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description="Test measurement stability of EQE system",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument('--test-type', type=str, default='current',
                       choices=['power', 'current'],
                       help='Type of test to run (power or current require different hardware setups, default: current)')
    parser.add_argument('--wavelength', type=float, default=550.0,
                       help='Wavelength to test at in nm (default: 550)')
    parser.add_argument('--duration', type=float, default=5.0,
                       help='Test duration in minutes (default: 5)')
    parser.add_argument('--interval', type=float, default=2.0,
                       help='Measurement interval in seconds (default: 2)')
    parser.add_argument('--pixel', type=int, default=1,
                       help='Pixel number for current test (default: 1)')
    parser.add_argument('--output', type=str, default=None,
                       help='Output CSV file path (default: auto-generated)')
    parser.add_argument('--no-plot', action='store_true',
                       help='Skip plotting results')
    
    args = parser.parse_args()
    
    # Create test instance
    test = StabilityTest()
    
    try:
        # Initialize devices
        if not test.initialize_devices():
            print("\n✗ Failed to initialize devices. Exiting.")
            return 1
        
        # Run power stability test
        if args.test_type == 'power':
            timestamps, values = test.test_power_stability(
                args.wavelength, args.duration, args.interval
            )
            
            if timestamps:
                output_file = args.output if args.output else None
                test.save_results(timestamps, values, 'power', args.wavelength, output_file)
                
                if not args.no_plot:
                    test.plot_results(timestamps, values, 'power', args.wavelength)
        
        # Run current stability test
        elif args.test_type == 'current':
            timestamps, values = test.test_current_stability(
                args.wavelength, args.duration, args.interval, args.pixel
            )
            
            if timestamps:
                output_file = args.output if args.output else None
                test.save_results(timestamps, values, 'current', args.wavelength, output_file)
                
                if not args.no_plot:
                    test.plot_results(timestamps, values, 'current', args.wavelength)
        
        print("\n" + "="*70)
        print("✓ ALL TESTS COMPLETED SUCCESSFULLY")
        print("="*70 + "\n")
        
        return 0
        
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        return 1
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        test.cleanup()


if __name__ == "__main__":
    exit(main())
