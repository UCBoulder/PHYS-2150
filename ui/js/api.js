/**
 * Qt WebChannel API Connection
 *
 * Provides a promise-based wrapper around Qt WebChannel for cleaner async code.
 * Reusable across all lab applications.
 */

// Global API reference
let _api = null;
let _apiReady = null;

/**
 * Initialize the Qt WebChannel connection.
 * Call this once on page load.
 *
 * @returns {Promise} Resolves with the API object when connected
 */
function initApi() {
    if (_apiReady) return _apiReady;

    _apiReady = new Promise((resolve, reject) => {
        if (typeof QWebChannel === 'undefined') {
            console.warn('QWebChannel not available - running in standalone browser mode');
            // Create mock API for development/testing
            _api = createMockApi();
            resolve(_api);
            return;
        }

        try {
            new QWebChannel(qt.webChannelTransport, function(channel) {
                _api = channel.objects.api;
                console.log('Connected to Qt WebChannel');
                resolve(_api);
            });
        } catch (error) {
            reject(error);
        }
    });

    return _apiReady;
}

/**
 * Get the API object (must call initApi first).
 *
 * @returns {Object|null} The API object or null if not initialized
 */
function getApi() {
    return _api;
}

/**
 * Call an API method with promise wrapper.
 * Converts Qt's callback-based API to promises.
 *
 * @param {string} method - Method name to call
 * @param {...any} args - Arguments to pass to the method
 * @returns {Promise} Resolves with the parsed JSON response
 */
function apiCall(method, ...args) {
    return new Promise((resolve, reject) => {
        if (!_api) {
            reject(new Error('API not initialized'));
            return;
        }

        if (typeof _api[method] !== 'function') {
            reject(new Error(`Unknown API method: ${method}`));
            return;
        }

        // Add callback as last argument
        _api[method](...args, function(result) {
            try {
                const response = JSON.parse(result);
                if (response.success === false) {
                    reject(new Error(response.message || 'API call failed'));
                } else {
                    resolve(response);
                }
            } catch (e) {
                // If not JSON, return raw result
                resolve(result);
            }
        });
    });
}

/**
 * Create a mock API for development/testing without Qt.
 * Override this in individual apps for app-specific mocks.
 */
function createMockApi() {
    return {
        // Default mock methods - override per app
        get_version: (callback) => callback('"1.0.0"'),
    };
}

// Export for use in other modules
window.LabAPI = {
    init: initApi,
    get: getApi,
    call: apiCall,
};
