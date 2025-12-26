/**
 * Theme Management
 *
 * Handles light/dark mode toggling with localStorage persistence.
 * Reusable across all lab applications.
 */

let _isDarkMode = true;

/**
 * Initialize theme from saved preference.
 * Call this on page load.
 */
function initTheme() {
    const savedTheme = localStorage.getItem('theme');
    _isDarkMode = savedTheme !== 'light';
    applyTheme(_isDarkMode);
}

/**
 * Toggle between light and dark mode.
 */
function toggleTheme() {
    _isDarkMode = !_isDarkMode;
    applyTheme(_isDarkMode);
}

/**
 * Apply a specific theme.
 *
 * @param {boolean} dark - True for dark mode, false for light mode
 */
function applyTheme(dark) {
    const body = document.body;

    if (dark) {
        body.classList.add('dark-mode');
        body.classList.remove('light-mode');
    } else {
        body.classList.add('light-mode');
        body.classList.remove('dark-mode');
    }

    localStorage.setItem('theme', dark ? 'dark' : 'light');

    // Dispatch event for components that need to react to theme changes
    window.dispatchEvent(new CustomEvent('themechange', { detail: { dark } }));
}

/**
 * Check if currently in dark mode.
 * Reads directly from localStorage to ensure consistency with Python-set themes.
 *
 * @returns {boolean} True if dark mode is active
 */
function isDarkMode() {
    const savedTheme = localStorage.getItem('theme');
    return savedTheme !== 'light';
}

/**
 * Create the theme toggle button HTML.
 * Returns SVG icons for sun/moon.
 */
function createThemeToggle() {
    return `
        <button class="theme-toggle" onclick="toggleTheme()" title="Toggle theme (Ctrl+Shift+C)" aria-label="Toggle light/dark theme">
            <svg id="sun-icon" class="theme-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="12" r="5"/>
                <line x1="12" y1="1" x2="12" y2="3"/>
                <line x1="12" y1="21" x2="12" y2="23"/>
                <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/>
                <line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/>
                <line x1="1" y1="12" x2="3" y2="12"/>
                <line x1="21" y1="12" x2="23" y2="12"/>
                <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/>
                <line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>
            </svg>
            <svg id="moon-icon" class="theme-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
            </svg>
        </button>
    `;
}

// Keyboard shortcut: Ctrl+Shift+C
document.addEventListener('keydown', function(e) {
    if (e.ctrlKey && e.shiftKey && e.key === 'C') {
        e.preventDefault();
        toggleTheme();
    }
});

/**
 * Get plot colors from CSS variables.
 * Call this after DOM is ready.
 *
 * @returns {Object} Plot color values
 */
function getPlotColors() {
    const style = getComputedStyle(document.documentElement);
    return {
        blue: style.getPropertyValue('--plot-blue').trim() || '#4A90D9',
        green: style.getPropertyValue('--plot-green').trim() || '#66bb6a',
        orange: style.getPropertyValue('--plot-orange').trim() || '#ff9800',
        red: style.getPropertyValue('--plot-red').trim() || '#e57373',
        // Semantic aliases
        power: style.getPropertyValue('--plot-blue').trim() || '#4A90D9',
        current: style.getPropertyValue('--plot-green').trim() || '#66bb6a',
        phaseMeasured: style.getPropertyValue('--plot-orange').trim() || '#ff9800',
        phaseFit: style.getPropertyValue('--plot-red').trim() || '#e57373',
        jvForward: style.getPropertyValue('--plot-blue').trim() || '#4A90D9',
        jvReverse: style.getPropertyValue('--plot-red').trim() || '#e57373',
    };
}

// Export for use in other modules
window.LabTheme = {
    init: initTheme,
    toggle: toggleTheme,
    apply: applyTheme,
    isDark: isDarkMode,
    createToggle: createThemeToggle,
    getPlotColors: getPlotColors,
};
