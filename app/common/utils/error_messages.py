"""
Student-friendly error message templates for PHYS 2150 applications.

Maps technical errors to actionable guidance that answers:
1. What happened?
2. Why might it have happened?
3. What should I do?
"""

from dataclasses import dataclass
from typing import List, Optional, Dict


@dataclass
class ErrorTemplate:
    """Template for a student-friendly error message."""
    title: str
    message: str
    causes: List[str]
    actions: List[str]


# EQE Application Error Templates
EQE_ERRORS: Dict[str, ErrorTemplate] = {
    "acquisition_failed": ErrorTemplate(
        title="Data Acquisition Problem",
        message="The oscilloscope couldn't capture a measurement.",
        causes=[
            "USB cable is loose or disconnected",
            "Another program is using the oscilloscope",
            "The oscilloscope needs to be power-cycled",
        ],
        actions=[
            "Check the USB cable connection",
            "Close any other programs that might use the oscilloscope",
            "Unplug and reconnect the USB cable, then click Retry",
        ]
    ),

    "no_reference_signal": ErrorTemplate(
        title="No Chopper Signal Detected",
        message="The lock-in amplifier isn't seeing the chopper reference signal.",
        causes=[
            "Chopper wheel not spinning (should hear it humming)",
            "Chopper cable disconnected from 'Reference' input",
            "Chopper frequency set incorrectly",
        ],
        actions=[
            "Verify the chopper is running (~81 Hz)",
            "Check the reference cable connection",
            "Ask a TA for help with optical alignment if problem persists",
        ]
    ),

    "chopper_not_running": ErrorTemplate(
        title="Chopper Not Running",
        message="The measured frequency doesn't match the expected chopper frequency.",
        causes=[
            "Chopper wheel is not spinning (you should hear it humming)",
            "Chopper power switch is off",
            "Chopper reference cable is disconnected",
        ],
        actions=[
            "Turn on the chopper and wait for it to reach stable speed",
            "Check that the chopper power switch is ON",
            "Verify the reference cable is connected to the PicoScope",
            "You should hear a steady hum when the chopper is running",
        ]
    ),

    "signal_saturation": ErrorTemplate(
        title="Signal Too Strong",
        message="The detected signal is near the measurement limit.",
        causes=[
            "Light intensity is too high",
            "Probe may be misaligned onto a bright spot",
        ],
        actions=[
            "Reduce the lamp intensity",
            "Check probe alignment under the microscope",
            "Try a neutral density filter if available",
        ]
    ),

    "signal_too_low": ErrorTemplate(
        title="Signal Too Weak",
        message="The photocurrent is very small or undetectable.",
        causes=[
            "Probe not making good contact with the pixel",
            "This pixel may be damaged or inactive",
            "Lamp may need more warm-up time",
            "Wavelength outside the cell's response range",
        ],
        actions=[
            "Check probe position under the microscope",
            "Try a different pixel on this cell",
            "Wait a few minutes for the lamp to stabilize",
            "Ask a TA if the problem persists",
        ]
    ),

    "phase_quality_low": ErrorTemplate(
        title="Phase Adjustment Quality Low",
        message="The lock-in phase calibration didn't achieve good quality.",
        causes=[
            "Lamp may be dim or unstable",
            "Reference signal is weak",
            "Optical alignment may have shifted",
        ],
        actions=[
            "Wait for the lamp to warm up fully",
            "Check the chopper reference connection",
            "Ask a TA to verify the optical alignment",
        ]
    ),

    "monochromator_not_found": ErrorTemplate(
        title="Monochromator Not Found",
        message="Could not connect to the wavelength selector.",
        causes=[
            "Monochromator is not powered on",
            "USB cable is disconnected",
            "Another program is controlling the monochromator",
        ],
        actions=[
            "Check that the monochromator power is on",
            "Verify the USB cable connection",
            "Close Newport MonoUtility if it's open",
            "Restart the application",
        ]
    ),

    "picoscope_not_found": ErrorTemplate(
        title="Oscilloscope Not Found",
        message="Could not connect to the PicoScope.",
        causes=[
            "PicoScope USB cable is disconnected",
            "PicoScope software (PicoScope 6) may be open",
            "USB port issue",
        ],
        actions=[
            "Check the USB cable connection",
            "Close PicoScope 6 if it's running",
            "Try a different USB port",
            "Restart the application",
        ]
    ),

    "power_meter_not_found": ErrorTemplate(
        title="Power Meter Not Found",
        message="Could not connect to the Thorlabs power meter.",
        causes=[
            "Power meter is not powered on",
            "USB cable is disconnected",
            "Thorlabs Optical Power Monitor may be open",
        ],
        actions=[
            "Check that the power meter is on",
            "Verify the USB cable connection",
            "Close Thorlabs software if open",
        ]
    ),

    "measurement_timeout": ErrorTemplate(
        title="Measurement Took Too Long",
        message="The measurement didn't complete in the expected time.",
        causes=[
            "Signal is very weak, requiring long integration",
            "Hardware communication issue",
            "System may be busy with other tasks",
        ],
        actions=[
            "Check that the probe is on an active area",
            "Try the measurement again",
            "Restart the application if problem persists",
        ]
    ),

    "wavelength_out_of_range": ErrorTemplate(
        title="Wavelength Out of Range",
        message="The requested wavelength is outside the monochromator's range.",
        causes=[
            "Start or end wavelength set incorrectly",
        ],
        actions=[
            "Use wavelengths between 350 and 1100 nm",
            "Check the measurement parameters",
        ]
    ),
}


# J-V Application Error Templates
JV_ERRORS: Dict[str, ErrorTemplate] = {
    "keithley_not_found": ErrorTemplate(
        title="SMU Not Found",
        message="Could not connect to the Keithley 2450.",
        causes=[
            "Keithley is not powered on",
            "USB or GPIB cable is disconnected",
            "Another program is using the instrument",
        ],
        actions=[
            "Check that the Keithley 2450 is powered on",
            "Verify the cable connection",
            "Close any other measurement software",
            "Restart the application",
        ]
    ),

    "compliance_reached": ErrorTemplate(
        title="Current Limit Reached",
        message="The measurement hit the current compliance limit.",
        causes=[
            "Solar cell is generating more current than expected",
            "Short circuit in the probe connections",
            "Compliance limit set too low",
        ],
        actions=[
            "Check probe connections for shorts",
            "Increase the compliance limit if appropriate",
            "Verify the cell is positioned correctly",
        ]
    ),

    "measurement_error": ErrorTemplate(
        title="Measurement Error",
        message="An error occurred during the I-V sweep.",
        causes=[
            "Probe contact was lost during measurement",
            "Voltage range exceeded instrument limits",
            "Communication error with instrument",
        ],
        actions=[
            "Check probe contact with the cell",
            "Verify voltage sweep parameters",
            "Try the measurement again",
        ]
    ),

    "data_save_failed": ErrorTemplate(
        title="Could Not Save Data",
        message="Failed to save the measurement data to file.",
        causes=[
            "Disk is full",
            "File is open in another program",
            "Invalid characters in filename",
        ],
        actions=[
            "Check available disk space",
            "Close any programs that might have the file open",
            "Try saving with a different filename",
        ]
    ),
}


def get_error(error_key: str, app: str = "eqe") -> Optional[ErrorTemplate]:
    """
    Get an error template by key.

    Args:
        error_key: The error identifier (e.g., "acquisition_failed")
        app: Application name ("eqe" or "jv")

    Returns:
        ErrorTemplate if found, None otherwise
    """
    errors = EQE_ERRORS if app == "eqe" else JV_ERRORS
    return errors.get(error_key)


def format_error_message(template: ErrorTemplate) -> str:
    """
    Format an error template as a plain text message.

    Args:
        template: The error template to format

    Returns:
        Formatted error message string
    """
    lines = [
        template.title,
        "",
        template.message,
        "",
    ]

    if template.causes:
        lines.append("Possible causes:")
        for cause in template.causes:
            lines.append(f"  - {cause}")
        lines.append("")

    if template.actions:
        lines.append("What to do:")
        for action in template.actions:
            lines.append(f"  - {action}")

    return "\n".join(lines)
