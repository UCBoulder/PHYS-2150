/**
 * Application Configuration Bridge
 *
 * Loads configuration from Python backend via QWebChannel API.
 * Provides fallback defaults for offline/browser-only mode.
 *
 * Usage:
 *   await LabConfig.load();  // Load config from Python
 *   const pixelRange = LabConfig.get('validation.pixel_range');
 */

// Configuration storage
let _config = null;
let _configReady = null;

// Fallback defaults for offline/browser mode
// These should mirror the Python config files
const FALLBACK_DEFAULTS = {
    // Common validation patterns (both JV and EQE)
    validation: {
        cell_number: '^\\d{3}$',
        pixel_range: [1, 8],
    },

    // JV-specific defaults
    jv: {
        defaults: {
            start_voltage: -0.2,
            stop_voltage: 1.5,
            step_voltage: 0.02,
            cell_number: '',
            pixel_number: 1,
        },
        voltage_bounds: {
            min_start: -1.0,
            max_stop: 2.0,
            min_step: 0.001,
            max_step: 0.5,
        },
        export: {
            headers: {
                voltage: 'Voltage (V)',
                forward_current: 'Forward Scan (mA)',
                reverse_current: 'Reverse Scan (mA)',
            },
            headers_raw: {
                direction: 'Direction',
                voltage: 'Voltage (V)',
                current: 'Current (mA)',
            },
        },
    },

    // EQE-specific defaults
    eqe: {
        defaults: {
            start_wavelength: 350.0,
            end_wavelength: 750.0,
            step_size: 10.0,
            cell_number: '',
            pixel_number: 1,
        },
        devices: {
            monochromator: {
                wavelength_range: [200, 1200],
            },
            picoscope: {
                default_chopper_freq: 81,
            },
        },
        stability: {
            default_wavelength: 550,
            default_duration_min: 5,
            duration_range: [1, 60],
            default_interval_sec: 2,
            interval_range: [1, 60],
        },
        phase: {
            alignment_wavelength: 532,
        },
        export: {
            headers: {
                power: ['Wavelength (nm)', 'Power (W)'],
                current: ['Wavelength (nm)', 'Current (nA)'],
                current_with_stats: ['Wavelength (nm)', 'Current_mean (nA)', 'Current_std (nA)', 'n'],
            },
            include_measurement_stats: true,
        },
    },
};

/**
 * Get app-specific fallback config based on current page.
 * Returns a flat structure matching what Python API would return.
 */
function getAppFallback() {
    const isJV = document.title.includes('I-V') || window.location.href.includes('jv');
    const isEQE = document.title.includes('EQE') || window.location.href.includes('eqe');

    if (isJV) {
        return {
            defaults: FALLBACK_DEFAULTS.jv.defaults,
            validation: FALLBACK_DEFAULTS.validation,
            measurement: FALLBACK_DEFAULTS.jv.voltage_bounds,
            export: FALLBACK_DEFAULTS.jv.export,
        };
    } else if (isEQE) {
        return {
            defaults: FALLBACK_DEFAULTS.eqe.defaults,
            validation: FALLBACK_DEFAULTS.validation,
            devices: FALLBACK_DEFAULTS.eqe.devices,
            stability: FALLBACK_DEFAULTS.eqe.stability,
            phase: FALLBACK_DEFAULTS.eqe.phase,
            export: FALLBACK_DEFAULTS.eqe.export,
        };
    }
    // Default: return full structure for unknown pages
    return FALLBACK_DEFAULTS;
}

/**
 * Load configuration from Python backend.
 * Falls back to defaults if API is not available.
 *
 * @returns {Promise<Object>} The loaded configuration
 */
function loadConfig() {
    if (_configReady) return _configReady;

    _configReady = new Promise(async (resolve) => {
        const api = window.LabAPI ? window.LabAPI.get() : null;

        if (api && typeof api.get_ui_config === 'function') {
            try {
                // Call Python API to get config
                api.get_ui_config(function(result) {
                    try {
                        _config = JSON.parse(result);
                        console.log('Loaded config from Python:', _config);
                        resolve(_config);
                    } catch (e) {
                        console.warn('Failed to parse config JSON, using fallbacks:', e);
                        _config = getAppFallback();
                        resolve(_config);
                    }
                });
            } catch (e) {
                console.warn('Failed to load config from Python, using fallbacks:', e);
                _config = getAppFallback();
                resolve(_config);
            }
        } else {
            console.log('API not available, using fallback config');
            _config = getAppFallback();
            resolve(_config);
        }
    });

    return _configReady;
}

/**
 * Get a configuration value by dot-notation path.
 *
 * @param {string} path - Dot-notation path (e.g., 'validation.pixel_range')
 * @param {any} defaultValue - Default if path not found
 * @returns {any} The configuration value
 */
function getConfig(path, defaultValue = undefined) {
    if (!_config) {
        console.warn('Config not loaded yet, returning default');
        return defaultValue;
    }

    const parts = path.split('.');
    let value = _config;

    for (const part of parts) {
        if (value && typeof value === 'object' && part in value) {
            value = value[part];
        } else {
            return defaultValue;
        }
    }

    return value;
}

/**
 * Get the full configuration object.
 *
 * @returns {Object|null} The configuration object
 */
function getFullConfig() {
    return _config;
}

/**
 * Check if config has been loaded.
 *
 * @returns {boolean} True if config is loaded
 */
function isConfigLoaded() {
    return _config !== null;
}

// Export for use in other modules
window.LabConfig = {
    load: loadConfig,
    get: getConfig,
    getAll: getFullConfig,
    isLoaded: isConfigLoaded,
    FALLBACK_DEFAULTS: FALLBACK_DEFAULTS,
};
