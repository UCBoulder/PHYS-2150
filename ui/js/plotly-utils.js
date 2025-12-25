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
 * Get the standard Plotly modebar configuration.
 * @returns {Object} Plotly config object
 */
export function getPlotConfig() {
    return {
        displayModeBar: true,
        modeBarButtonsToRemove: ['lasso2d', 'select2d', 'toImage'],
        displaylogo: false
    };
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
    markerMPP: '#AA00FF'
};
