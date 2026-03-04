/**
 * Plotly Utilities (ES6 Module)
 *
 * Shared Plotly configuration and helpers for lab applications.
 * Uses ES6 module syntax to avoid global scope conflicts.
 */

/**
 * Get theme-appropriate colors for plots.
 * @param {boolean} isDark - Whether dark mode is active
 * @returns {Object} Color values for plot elements
 */
export function getThemeColors(isDark) {
    return {
        text: isDark ? '#eeeeee' : '#1a1a1a',
        grid: isDark ? '#444444' : '#dddddd',
        zeroline: isDark ? '#666666' : '#999999',
        legendBg: isDark ? 'rgba(50,50,50,0.9)' : 'rgba(255,255,255,0.9)',
        paper: isDark ? '#2a2a2a' : '#f5f5f5',
        plot: isDark ? '#2a2a2a' : '#f5f5f5'
    };
}

/**
 * Save a plot as an image file via Python backend.
 * @param {string} plotId - The DOM element ID of the plot
 * @param {string|function} nameOrFn - Filename (without extension) or function that returns filename
 */
export function savePlotImage(plotId, nameOrFn = 'plot') {
    const plotDiv = document.getElementById(plotId);
    if (!plotDiv) {
        console.error('Plot not found:', plotId);
        return;
    }

    // Resolve filename (call function if provided, otherwise use string)
    const defaultName = typeof nameOrFn === 'function' ? nameOrFn() : nameOrFn;

    Plotly.toImage(plotDiv, { format: 'png', scale: 2 }).then(function(dataUrl) {
        const api = window.LabAPI ? window.LabAPI.get() : null;
        if (api && api.save_plot_image) {
            api.save_plot_image(dataUrl, defaultName + '.png', function(result) {
                const r = JSON.parse(result);
                if (r.success) {
                    console.log('Plot saved:', r.path);
                } else if (r.message !== 'Cancelled') {
                    console.error('Save failed:', r.message);
                }
            });
        } else {
            // Fallback: trigger browser download
            const link = document.createElement('a');
            link.download = defaultName + '.png';
            link.href = dataUrl;
            link.click();
        }
    });
}

/**
 * Create a custom save button for the Plotly modebar.
 * @param {string} plotId - The DOM element ID of the plot
 * @param {string|function} nameOrFn - Filename (without extension) or function that returns filename
 * @returns {Object} Modebar button configuration
 */
export function createSaveButton(plotId, nameOrFn = 'plot') {
    return {
        name: 'Save as PNG',
        icon: Plotly.Icons.camera,
        click: function() {
            savePlotImage(plotId, nameOrFn);
        }
    };
}

/**
 * Get the standard Plotly modebar configuration.
 * @param {string} plotId - Optional plot ID for custom save button
 * @param {string|function} nameOrFn - Filename or function returning filename for save
 * @returns {Object} Plotly config object
 */
export function getPlotConfig(plotId = null, nameOrFn = 'plot') {
    const config = {
        displayModeBar: true,
        modeBarButtonsToRemove: ['lasso2d', 'select2d', 'toImage'],
        displaylogo: false
    };

    // Add custom save button if plotId provided
    if (plotId) {
        config.modeBarButtonsToAdd = [createSaveButton(plotId, nameOrFn)];
    }

    return config;
}

/**
 * Get a base layout for plots with theme-appropriate colors.
 * @param {boolean} isDark - Whether dark mode is active
 * @param {string} xLabel - X-axis label
 * @param {string} yLabel - Y-axis label
 * @param {Object} options - Additional layout options
 * @param {boolean} options.transparentBg - Use transparent background (JV style)
 * @param {Object} options.margin - Custom margin values
 * @param {Object} options.legend - Custom legend position
 * @returns {Object} Plotly layout object
 */
export function getBaseLayout(isDark, xLabel, yLabel, options = {}) {
    const colors = getThemeColors(isDark);
    const useTransparentBg = options.transparentBg || false;

    return {
        xaxis: {
            title: xLabel,
            color: colors.text,
            gridcolor: colors.grid,
            zerolinecolor: colors.zeroline,
            zerolinewidth: 1
        },
        yaxis: {
            title: yLabel,
            color: colors.text,
            gridcolor: colors.grid,
            zerolinecolor: colors.zeroline,
            zerolinewidth: 1
        },
        paper_bgcolor: useTransparentBg ? 'rgba(0,0,0,0)' : colors.paper,
        plot_bgcolor: useTransparentBg ? 'rgba(0,0,0,0)' : colors.plot,
        font: { color: colors.text },
        legend: {
            font: { color: colors.text, size: options.legend?.fontSize || 11 },
            bgcolor: colors.legendBg,
            x: options.legend?.x ?? 0.02,
            y: options.legend?.y ?? 0.98,
            xanchor: options.legend?.xanchor || 'left',
            yanchor: options.legend?.yanchor || 'top'
        },
        margin: options.margin || { t: 20, r: 30, b: 60, l: 60 }
    };
}

/**
 * Update a plot's theme colors.
 * @param {string} plotId - The DOM element ID of the plot
 * @param {boolean} isDark - Whether dark mode is active
 * @param {Object} options - Additional options
 * @param {boolean} options.transparentBg - Use transparent background
 */
export function updatePlotTheme(plotId, isDark, options = {}) {
    const plotDiv = document.getElementById(plotId);
    if (!plotDiv || !plotDiv.data) return;

    const colors = getThemeColors(isDark);
    const useTransparentBg = options.transparentBg || false;

    const updates = {
        'xaxis.color': colors.text,
        'xaxis.gridcolor': colors.grid,
        'xaxis.zerolinecolor': colors.zeroline,
        'yaxis.color': colors.text,
        'yaxis.gridcolor': colors.grid,
        'yaxis.zerolinecolor': colors.zeroline,
        'font.color': colors.text,
        'legend.font.color': colors.text,
        'legend.bgcolor': colors.legendBg
    };

    if (!useTransparentBg) {
        updates['paper_bgcolor'] = colors.paper;
        updates['plot_bgcolor'] = colors.plot;
    }

    Plotly.relayout(plotDiv, updates);
}

/**
 * Standard plot colors used across applications.
 */
export const PLOT_COLORS = {
    // JV app colors
    jvForward: '#4A90D9',
    jvReverse: '#e57373',

    // EQE app colors
    power: '#4A90D9',
    current: '#66bb6a',
    phaseMeasured: '#ff9800',
    phaseFit: '#e57373',

    // Analysis markers
    markerVoc: '#00C853',
    markerIsc: '#FF6D00',
    markerMPP: '#AA00FF',

    // Quality-based colors for current measurement points
    // Subtle variations that convey quality without being alarming
    qualityExcellent: '#66bb6a',  // Standard green (CV < 2%)
    qualityGood: '#2e7d32',       // Dark green (CV < 5%)
    qualityFair: '#f9a825',       // Amber (CV < 10%)
    qualityPoor: '#e57373'        // Muted red (CV >= 10%)
};
