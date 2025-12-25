/**
 * Plotly Utilities
 *
 * Shared Plotly configuration and theming utilities for lab applications.
 * Provides consistent plot styling across JV and EQE apps.
 */

// ============================================
// Modebar Configuration
// ============================================

/**
 * Standard Plotly modebar configuration.
 * Hides logo and removes unnecessary tools.
 */
const plotConfig = {
    displayModeBar: true,
    modeBarButtonsToRemove: ['lasso2d', 'select2d', 'toImage'],
    displaylogo: false
};

// ============================================
// Theme Colors
// ============================================

/**
 * Get theme-aware colors for plots.
 *
 * @param {boolean} isDark - True for dark mode, false for light mode
 * @returns {Object} Color values for plot elements
 */
function getThemeColors(isDark) {
    return {
        text: isDark ? '#eeeeee' : '#1a1a1a',
        grid: isDark ? '#444444' : '#dddddd',
        zeroline: isDark ? '#666666' : '#999999',
        legendBg: isDark ? 'rgba(50,50,50,0.9)' : 'rgba(255,255,255,0.9)',
        paper: isDark ? 'rgba(0,0,0,0)' : 'rgba(0,0,0,0)',
        plot: isDark ? 'rgba(0,0,0,0)' : 'rgba(0,0,0,0)'
    };
}

/**
 * Get plot colors from CSS variables (for trace colors).
 * Should be called after DOM is ready.
 *
 * @returns {Object} Plot trace colors
 */
function getPlotColors() {
    const style = getComputedStyle(document.documentElement);
    return {
        blue: style.getPropertyValue('--plot-blue').trim() || '#4A90D9',
        green: style.getPropertyValue('--plot-green').trim() || '#66bb6a',
        orange: style.getPropertyValue('--plot-orange').trim() || '#ff9800',
        red: style.getPropertyValue('--plot-red').trim() || '#e57373',
        // Semantic aliases for JV
        jvForward: style.getPropertyValue('--plot-blue').trim() || '#4A90D9',
        jvReverse: style.getPropertyValue('--plot-red').trim() || '#e57373',
        // Semantic aliases for EQE
        power: style.getPropertyValue('--plot-blue').trim() || '#4A90D9',
        current: style.getPropertyValue('--plot-green').trim() || '#66bb6a',
        phaseMeasured: style.getPropertyValue('--plot-orange').trim() || '#ff9800',
        phaseFit: style.getPropertyValue('--plot-red').trim() || '#e57373',
    };
}

// ============================================
// Layout Generation
// ============================================

/**
 * Generate a Plotly layout with theme-aware styling.
 *
 * @param {boolean} isDark - True for dark mode
 * @param {Object} options - Layout options
 * @param {string} options.xLabel - X-axis title
 * @param {string} options.yLabel - Y-axis title
 * @param {Object} options.legend - Legend position override
 * @param {Object} options.margin - Margin override
 * @param {boolean} options.solidBackground - Use solid background (for EQE)
 * @returns {Object} Plotly layout object
 */
function getPlotLayout(isDark, options = {}) {
    const colors = getThemeColors(isDark);

    // Allow solid backgrounds for EQE-style plots
    if (options.solidBackground) {
        colors.paper = isDark ? '#2a2a2a' : '#f5f5f5';
        colors.plot = isDark ? '#2a2a2a' : '#f5f5f5';
    }

    // Default legend position (JV style: top-left)
    const defaultLegend = {
        font: { color: colors.text },
        bgcolor: colors.legendBg,
        x: 0.02,
        y: 0.98,
        xanchor: 'left',
        yanchor: 'top'
    };

    // Default margins
    const defaultMargin = { t: 20, r: 30, b: 60, l: 60 };

    return {
        xaxis: {
            title: options.xLabel || '',
            color: colors.text,
            gridcolor: colors.grid,
            zerolinecolor: colors.zeroline,
            zerolinewidth: 1
        },
        yaxis: {
            title: options.yLabel || '',
            color: colors.text,
            gridcolor: colors.grid,
            zerolinecolor: colors.zeroline,
            zerolinewidth: 1
        },
        paper_bgcolor: colors.paper,
        plot_bgcolor: colors.plot,
        font: { color: colors.text },
        legend: { ...defaultLegend, ...options.legend },
        margin: { ...defaultMargin, ...options.margin }
    };
}

/**
 * Create a JV-style layout (transparent background, top-left legend).
 *
 * @param {boolean} isDark - True for dark mode
 * @returns {Object} Plotly layout for JV plots
 */
function getJVLayout(isDark) {
    return getPlotLayout(isDark, {
        xLabel: 'Voltage (V)',
        yLabel: 'Current (mA)'
    });
}

/**
 * Create an EQE-style layout (solid background, top-right legend).
 *
 * @param {boolean} isDark - True for dark mode
 * @param {string} xLabel - X-axis title
 * @param {string} yLabel - Y-axis title
 * @returns {Object} Plotly layout for EQE plots
 */
function getEQELayout(isDark, xLabel, yLabel) {
    return getPlotLayout(isDark, {
        xLabel,
        yLabel,
        solidBackground: true,
        legend: {
            x: 1,
            y: 1,
            xanchor: 'right',
            yanchor: 'top',
            font: { size: 11 }
        },
        margin: { t: 20, r: 30, b: 95, l: 60 }
    });
}

// ============================================
// Theme Updates
// ============================================

/**
 * Update an existing plot's theme colors without re-rendering data.
 *
 * @param {string} plotId - The plot element ID
 * @param {boolean} isDark - True for dark mode
 * @param {boolean} solidBackground - Use solid background colors
 */
function updatePlotTheme(plotId, isDark, solidBackground = false) {
    const colors = getThemeColors(isDark);

    if (solidBackground) {
        colors.paper = isDark ? '#2a2a2a' : '#f5f5f5';
        colors.plot = isDark ? '#2a2a2a' : '#f5f5f5';
    }

    Plotly.relayout(plotId, {
        'xaxis.color': colors.text,
        'xaxis.gridcolor': colors.grid,
        'xaxis.zerolinecolor': colors.zeroline,
        'yaxis.color': colors.text,
        'yaxis.gridcolor': colors.grid,
        'yaxis.zerolinecolor': colors.zeroline,
        'font.color': colors.text,
        'legend.font.color': colors.text,
        'legend.bgcolor': colors.legendBg,
        'paper_bgcolor': colors.paper,
        'plot_bgcolor': colors.plot
    });
}

// ============================================
// Utility Functions
// ============================================

/**
 * Safely resize a plot if it exists.
 *
 * @param {string} plotId - The plot element ID
 */
function resizePlot(plotId) {
    const plotDiv = document.getElementById(plotId);
    if (plotDiv && plotDiv.data && typeof Plotly !== 'undefined') {
        Plotly.Plots.resize(plotId);
    }
}

/**
 * Safely resize multiple plots.
 *
 * @param {...string} plotIds - The plot element IDs
 */
function resizePlots(...plotIds) {
    plotIds.forEach(resizePlot);
}

/**
 * Check if a plot element has been initialized.
 *
 * @param {string} plotId - The plot element ID
 * @returns {boolean} True if plot has data
 */
function isPlotInitialized(plotId) {
    const plotDiv = document.getElementById(plotId);
    return plotDiv && plotDiv.data;
}

// ============================================
// Export
// ============================================

window.PlotlyUtils = {
    // Configuration
    config: plotConfig,

    // Colors
    getThemeColors,
    getPlotColors,

    // Layout generators
    getLayout: getPlotLayout,
    getJVLayout,
    getEQELayout,

    // Theme updates
    updateTheme: updatePlotTheme,

    // Utilities
    resize: resizePlot,
    resizeAll: resizePlots,
    isInitialized: isPlotInitialized
};
