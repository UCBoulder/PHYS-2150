/**
 * Application Configuration Bridge
 *
 * Loads configuration from Python backend via QWebChannel API.
 * Config originates from defaults.json (fetched from GitHub, cached, or bundled).
 *
 * Usage:
 *   await LabConfig.load();  // Load config from Python
 *   const pixelRange = LabConfig.get('validation.pixel_range');
 */

// Configuration storage
let _config = null;
let _configReady = null;

/**
 * Load configuration from Python backend.
 *
 * @returns {Promise<Object>} The loaded configuration
 */
function loadConfig() {
    if (_configReady) return _configReady;

    _configReady = new Promise(async (resolve) => {
        const api = window.LabAPI ? window.LabAPI.get() : null;

        if (api && typeof api.get_ui_config === 'function') {
            try {
                api.get_ui_config(function(result) {
                    try {
                        _config = JSON.parse(result);
                        console.log('Loaded config from Python');
                        resolve(_config);
                    } catch (e) {
                        console.error('Failed to parse config JSON:', e);
                        _config = {};
                        resolve(_config);
                    }
                });
            } catch (e) {
                console.error('Failed to load config from Python:', e);
                _config = {};
                resolve(_config);
            }
        } else {
            console.error('Python API not available - config will be empty');
            _config = {};
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
};
