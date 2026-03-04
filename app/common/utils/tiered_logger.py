"""
Tiered logging system for PHYS 2150 measurement applications.

Provides three output tiers:
- Tier 1 (student): GUI status bar, plain language, pedagogically relevant
- Tier 2 (info): Console output, device IDs and timing, visible if terminal open
- Tier 3 (debug): Log file only, full technical details for staff debugging

Staff debug mode (Ctrl+Shift+D) promotes debug messages to console.
"""

import logging
import os
from enum import Enum
from pathlib import Path
from typing import Optional, Callable, List, Dict, Any
from logging.handlers import RotatingFileHandler


def _get_log_directory() -> Path:
    """Get the default log directory (%LOCALAPPDATA%\\PHYS2150\\)."""
    local_app_data = os.environ.get('LOCALAPPDATA')
    if local_app_data:
        log_dir = Path(local_app_data) / 'PHYS2150'
    else:
        # Fallback if LOCALAPPDATA not set (shouldn't happen on Windows)
        log_dir = Path.home() / 'PHYS2150'
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


class LogTier(Enum):
    """Output tiers for the logging system."""
    STUDENT = "STUDENT"  # Tier 1: GUI, always visible to students
    INFO = "INFO"        # Tier 2: Console, visible if terminal open
    DEBUG = "DEBUG"      # Tier 3: File only (unless staff mode)


class MeasurementStats:
    """Container for measurement statistics to display to students."""

    def __init__(
        self,
        mean: float,
        std_dev: float,
        n_measurements: int,
        n_total: int,
        n_outliers: int = 0,
        cv_percent: float = 0.0,
        wavelength_nm: Optional[float] = None,
        unit: str = "V",
        measurement_type: str = "current",
        quality_thresholds: Optional[Dict[str, float]] = None,
        low_signal_threshold: Optional[float] = None
    ):
        self.mean = mean
        self.std_dev = std_dev
        self.n_measurements = n_measurements
        self.n_total = n_total
        self.n_outliers = n_outliers
        self.cv_percent = cv_percent
        self.wavelength_nm = wavelength_nm
        self.unit = unit
        self.measurement_type = measurement_type  # "current" or "power"
        self.quality_thresholds = quality_thresholds  # Optional CV thresholds dict
        self.low_signal_threshold = low_signal_threshold  # Optional signal level threshold

    @property
    def std_error(self) -> float:
        """
        Calculate standard error of the mean (absolute value).

        SEM = σ / √n

        This represents uncertainty in the mean, not spread of measurements.
        Key learning goal: students should understand SD vs SEM distinction.
        """
        if self.n_measurements > 0:
            return self.std_dev / (self.n_measurements ** 0.5)
        return 0.0

    @property
    def sem_percent(self) -> float:
        """
        Calculate standard error of the mean as percentage of mean (relative SEM).

        SEM% = (SEM / mean) × 100% = (std_dev / (mean × √n)) × 100%

        This is the appropriate metric for data quality assessment:
        - Reflects uncertainty in the reported value (the mean)
        - Rewards taking more measurements (√n in denominator)
        - Independent of measurement technique (unlike CV for chopped signals)
        """
        if self.mean != 0 and self.n_measurements > 0:
            return (self.std_error / abs(self.mean)) * 100.0
        return 0.0

    @property
    def quality(self) -> str:
        """
        Return quality assessment based on SEM% (standard error of mean) and measurement type.

        Uses measurement-specific SEM% thresholds if provided, otherwise falls back
        to CV%-based legacy defaults for backward compatibility.

        For signals below low_signal_threshold, returns "Low signal" instead
        of "Check measurement" to distinguish weak but valid signals from
        measurement problems.
        """
        # Use provided thresholds or fall back to legacy defaults
        if self.quality_thresholds:
            # New approach: use SEM% (uncertainty in the mean)
            thresholds = self.quality_thresholds
            metric = self.sem_percent
        else:
            # Legacy defaults using CV% (maintain backward compatibility)
            thresholds = {
                "excellent": 1.0,
                "good": 5.0,
                "fair": 10.0
            }
            metric = self.cv_percent

        if metric < thresholds["excellent"]:
            return "Excellent"
        elif metric < thresholds["good"]:
            return "Good"
        elif metric < thresholds["fair"]:
            return "Fair"
        else:
            # Check if this is a low signal condition (weak but valid)
            if self.low_signal_threshold is not None and abs(self.mean) < self.low_signal_threshold:
                return "Low signal"
            return "Check measurement"

    def format_for_student(self) -> str:
        """Format statistics for student-facing display."""
        location = f" at {self.wavelength_nm:.0f} nm" if self.wavelength_nm else ""
        return (
            f"Measurement{location}: {self.mean:.4g} ± {self.std_dev:.4g} {self.unit} "
            f"({self.n_measurements}/{self.n_total} measurements, {self.quality})"
        )

    def format_for_console(self) -> str:
        """Format statistics for console output with human-readable units."""
        # Determine scale factor based on mean value magnitude
        # Use same scale for both mean and std_dev for consistency
        abs_mean = abs(self.mean)
        if abs_mean >= 1e-3 or abs_mean == 0:
            scale, prefix = 1, ""
        elif abs_mean >= 1e-6:
            scale, prefix = 1e6, "µ"
        elif abs_mean >= 1e-9:
            scale, prefix = 1e9, "n"
        else:
            scale, prefix = 1e12, "p"

        mean_scaled = self.mean * scale
        std_scaled = self.std_dev * scale
        sem_scaled = self.std_error * scale
        unit_str = f"{prefix}{self.unit}"

        location = f"{self.wavelength_nm:.0f}nm: " if self.wavelength_nm else ""
        return (
            f"{location}{mean_scaled:.2f} ± {sem_scaled:.2f} {unit_str} "
            f"(n={self.n_measurements}/{self.n_total}, SEM={self.sem_percent:.2f}%)"
        )


class TieredLogger:
    """
    Tiered logging system for undergraduate lab software.

    Routes messages to appropriate outputs based on audience:
    - student(): GUI status bar, plain language
    - info(): Console, brief technical info
    - debug(): File only (or console in staff mode)

    Usage:
        logger = TieredLogger("eqe")
        logger.student("Measuring at 550 nm...")
        logger.info("PicoScope 2204A connected")
        logger.debug("Timebase 12, 2000 samples, fs=24414 Hz")
    """

    _instances: Dict[str, 'TieredLogger'] = {}
    _staff_debug_mode: bool = False

    def __init__(
        self,
        name: str,
        log_dir: Optional[Path] = None,
        gui_callback: Optional[Callable[[str], None]] = None,
        stats_callback: Optional[Callable[[MeasurementStats], None]] = None,
        error_callback: Optional[Callable[[str, str, List[str], List[str]], None]] = None
    ):
        """
        Initialize the tiered logger.

        Args:
            name: Logger name (e.g., "eqe", "jv")
            log_dir: Directory for log files (default: current directory)
            gui_callback: Callback for student-tier messages (status bar)
            stats_callback: Callback for measurement statistics (stats widget)
            error_callback: Callback for error dialogs (title, message, causes, actions)
        """
        self.name = name
        self.log_dir = log_dir or _get_log_directory()
        self.gui_callback = gui_callback
        self.stats_callback = stats_callback
        self.error_callback = error_callback

        # Set up Python logging for console and file
        self._setup_logging()

        # Store instance for class-level access
        TieredLogger._instances[name] = self

    def _setup_logging(self) -> None:
        """Configure Python logging handlers."""
        self._logger = logging.getLogger(f"phys2150.{self.name}")
        self._logger.setLevel(logging.DEBUG)
        self._logger.handlers.clear()

        # Console handler (INFO level by default)
        self._console_handler = logging.StreamHandler()
        self._console_handler.setLevel(logging.INFO)
        console_format = logging.Formatter(
            '%(asctime)s %(message)s',
            datefmt='%H:%M:%S'
        )
        self._console_handler.setFormatter(console_format)
        self._logger.addHandler(self._console_handler)

        # File handler (DEBUG level, with rotation)
        log_file = self.log_dir / f"{self.name}_debug.log"
        try:
            file_handler = RotatingFileHandler(
                log_file,
                maxBytes=5*1024*1024,  # 5 MB
                backupCount=3
            )
            file_handler.setLevel(logging.DEBUG)
            file_format = logging.Formatter(
                '%(asctime)s [%(levelname)s] %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            file_handler.setFormatter(file_format)
            self._logger.addHandler(file_handler)
        except Exception:
            pass  # Silently ignore file logging errors

    @classmethod
    def get_logger(cls, name: str) -> 'TieredLogger':
        """Get or create a logger instance by name."""
        if name not in cls._instances:
            cls._instances[name] = TieredLogger(name)
        return cls._instances[name]

    @classmethod
    def set_staff_debug_mode(cls, enabled: bool) -> None:
        """
        Enable or disable staff debug mode.

        When enabled, DEBUG-level messages appear in console.
        Toggle with Ctrl+Shift+D in the application.
        """
        cls._staff_debug_mode = enabled
        # Update all logger instances
        for logger in cls._instances.values():
            if enabled:
                logger._console_handler.setLevel(logging.DEBUG)
            else:
                logger._console_handler.setLevel(logging.INFO)

    @classmethod
    def is_staff_debug_mode(cls) -> bool:
        """Check if staff debug mode is enabled."""
        return cls._staff_debug_mode

    @classmethod
    def debug_output(cls, message: str) -> None:
        """
        Output debug message to console if staff debug mode is enabled.

        This is a convenience method for quick debug output without needing
        a logger instance. Uses the first available logger or prints directly.

        Args:
            message: Debug message to output
        """
        if not cls._staff_debug_mode:
            return

        import sys
        from datetime import datetime
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"{timestamp} {message}", flush=True)

    def set_gui_callback(self, callback: Optional[Callable[[str], None]]) -> None:
        """Set callback for student-tier GUI messages."""
        self.gui_callback = callback

    def set_stats_callback(
        self,
        callback: Optional[Callable[[MeasurementStats], None]]
    ) -> None:
        """Set callback for measurement statistics display."""
        self.stats_callback = callback

    def set_error_callback(
        self,
        callback: Optional[Callable[[str, str, List[str], List[str]], None]]
    ) -> None:
        """Set callback for error dialogs."""
        self.error_callback = callback

    # -------------------------------------------------------------------------
    # Tier 1: Student-facing messages (GUI status bar)
    # -------------------------------------------------------------------------

    def student(self, message: str) -> None:
        """
        Log a student-facing message.

        These appear in the GUI status bar and should be:
        - Plain language (no jargon)
        - Connected to physics concepts
        - Actionable when relevant

        Args:
            message: Student-friendly status message
        """
        # Always log to file
        self._logger.info(f"[STUDENT] {message}")

        # Send to GUI callback
        if self.gui_callback:
            try:
                self.gui_callback(message)
            except Exception:
                pass

    def student_stats(self, stats: MeasurementStats) -> None:
        """
        Display measurement statistics to students.

        This is CRITICAL for learning objectives around uncertainty.

        Args:
            stats: MeasurementStats object with mean, std_dev, etc.
        """
        # Log formatted version to console/file
        self._logger.info(stats.format_for_console())

        # Send to stats widget callback
        if self.stats_callback:
            try:
                self.stats_callback(stats)
            except Exception:
                pass

    def student_error(
        self,
        title: str,
        message: str,
        causes: Optional[List[str]] = None,
        actions: Optional[List[str]] = None
    ) -> None:
        """
        Show an error dialog with actionable guidance.

        Every error students see should answer:
        1. What happened?
        2. Why might it have happened?
        3. What should I do?

        Args:
            title: Short error title
            message: Explanation of what went wrong
            causes: List of possible causes
            actions: List of suggested actions
        """
        causes = causes or []
        actions = actions or []

        # Log to file
        self._logger.error(f"{title}: {message}")
        for cause in causes:
            self._logger.error(f"  Possible cause: {cause}")
        for action in actions:
            self._logger.error(f"  Suggested action: {action}")

        # Show error dialog via callback
        if self.error_callback:
            try:
                self.error_callback(title, message, causes, actions)
            except Exception:
                pass

    # -------------------------------------------------------------------------
    # Tier 2: Console messages (INFO level)
    # -------------------------------------------------------------------------

    def info(self, message: str) -> None:
        """
        Log an informational message to console.

        Visible in terminal, appropriate for:
        - Device identification (model, serial)
        - Measurement timing
        - Parameters students control

        Args:
            message: Brief technical information
        """
        self._logger.info(message)

    def warning(self, message: str) -> None:
        """
        Log a warning message.

        Appears in console and file. Use for:
        - Measurement quality issues
        - Configuration warnings
        - Recoverable problems

        Args:
            message: Warning description
        """
        self._logger.warning(message)

    def error(self, message: str) -> None:
        """
        Log an error message (technical, for staff).

        For student-facing errors, use student_error() instead.

        Args:
            message: Technical error description
        """
        self._logger.error(message)

    # -------------------------------------------------------------------------
    # Tier 3: Debug messages (file only, unless staff mode)
    # -------------------------------------------------------------------------

    def debug(self, message: str) -> None:
        """
        Log a debug message.

        Only visible in:
        - Log file (always)
        - Console (only when staff debug mode enabled via Ctrl+Shift+D)

        Use for:
        - ADC configuration (timebases, ranges, coupling)
        - SDK calls and return values
        - Buffer sizes, sample counts
        - Algorithm parameters

        Args:
            message: Technical debug information
        """
        self._logger.debug(message)

    # -------------------------------------------------------------------------
    # Backward compatibility with MeasurementDataLogger
    # -------------------------------------------------------------------------

    def log(self, message: str, level: str = "INFO") -> None:
        """
        Backward-compatible log method.

        Maps to appropriate tier based on level:
        - ERROR/WARNING → warning/error (console + file)
        - INFO → info (console + file)
        - DEBUG → debug (file only, unless staff mode)

        Args:
            message: Message to log
            level: Log level (INFO, WARNING, ERROR, DEBUG)
        """
        level = level.upper()
        if level == "ERROR":
            self.error(message)
        elif level == "WARNING":
            self.warning(message)
        elif level == "DEBUG":
            self.debug(message)
        else:
            self.info(message)


# Convenience function for getting a logger
def get_logger(name: str) -> TieredLogger:
    """Get or create a TieredLogger instance."""
    return TieredLogger.get_logger(name)
