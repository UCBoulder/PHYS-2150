/**
 * EQE Measurement Application (ES6 Module)
 *
 * Handles EQE spectral response measurements for solar cell characterization.
 * Uses ES6 module syntax to avoid global scope conflicts.
 */

import {
    getBaseLayout,
    getPlotConfig,
    PLOT_COLORS
} from './plotly-utils.js';

// ============================================
// State
// ============================================

const state = {
    activeTab: 'measurement',
    devices: {
        picoscope: { connected: false, message: '' },
        monochromator: { connected: false, message: '' },
        power_meter: { connected: false, message: '' }
    },
    offlineMode: false,
    measurementState: 'idle',
    currentPixel: null,
    cellNumber: '',
    wavelength: 0,
    shutterOpen: false,
    filter: 0,

    powerData: { x: [], y: [] },
    currentData: { x: [], y: [], stats: [] },
    phaseData: { x: [], y: [] },
    stats: null,

    stability: {
        testType: 'power',
        running: false,
        pixel: null,
        data: { times: [], values: [] },
        stats: null,
        startTime: null
    },

    analysis: {
        visible: false,
        powerData: null,
        currentData: null,
        eqeData: null,
        metrics: null,
        cellNumber: null,
        pixel: null,
        powerFile: null,
        currentFile: null
    },

    debugMode: false
};

// Console state
let consoleVisible = false;
const consoleMessages = [];
const MAX_CONSOLE_MESSAGES = 500;

// Live monitor state
let liveMonitorActive = false;

// Plot configuration (module-scoped, no global conflict)
const plotConfig = getPlotConfig();

// Physical constants for EQE calculation
const PLANCK = 6.62607015e-34;
const SPEED_OF_LIGHT = 2.99792458e8;
const ELECTRON_CHARGE = 1.602176634e-19;

// AM1.5G photon flux data
const AM15G_WAVELENGTHS = [
    300, 320, 340, 360, 380, 400, 420, 440, 460, 480,
    500, 520, 540, 560, 580, 600, 620, 640, 660, 680,
    700, 720, 740, 760, 780, 800, 820, 840, 860, 880,
    900, 920, 940, 960, 980, 1000, 1020, 1040, 1060, 1080, 1100
];
const AM15G_PHOTON_FLUX = [
    0.02, 0.20, 0.55, 0.95, 1.45, 2.10, 2.55, 2.70, 2.80, 2.90,
    3.00, 3.05, 3.05, 3.00, 2.95, 2.90, 2.85, 2.80, 2.75, 2.70,
    2.65, 2.60, 2.55, 2.50, 2.45, 2.40, 2.35, 2.30, 2.20, 2.10,
    2.00, 1.90, 1.50, 1.80, 1.75, 1.70, 1.65, 1.60, 1.55, 1.50, 1.45
].map(x => x * 1e18);

// ============================================
// Helper Functions
// ============================================

function extractCellPixelFromFilename(filename) {
    const cellMatch = filename.match(/cell(\d+)/i);
    const pixelMatch = filename.match(/pixel(\d+)/i);
    return {
        cell: cellMatch ? cellMatch[1] : null,
        pixel: pixelMatch ? parseInt(pixelMatch[1]) : null
    };
}

function getPlotLayout(isDark, xLabel, yLabel) {
    return getBaseLayout(isDark, xLabel, yLabel, {
        transparentBg: false,
        margin: { t: 20, r: 30, b: 95, l: 60 },
        legend: { x: 1, y: 1, xanchor: 'right', yanchor: 'top' }
    });
}

function interpolate(xArray, yArray, x) {
    if (x < xArray[0] || x > xArray[xArray.length - 1]) return null;
    for (let i = 0; i < xArray.length - 1; i++) {
        if (x >= xArray[i] && x <= xArray[i + 1]) {
            const t = (x - xArray[i]) / (xArray[i + 1] - xArray[i]);
            return yArray[i] + t * (yArray[i + 1] - yArray[i]);
        }
    }
    return null;
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// ============================================
// Initialization
// ============================================

/**
 * Populate form fields with defaults from config.
 * Called after config is loaded.
 */
function populateFormDefaults() {
    const defaults = LabConfig.get('defaults', {});
    const stability = LabConfig.get('stability', {});
    const validation = LabConfig.get('validation', {});

    // Wavelength measurement parameters
    if (defaults.start_wavelength !== undefined) {
        document.getElementById('start-wavelength').value = defaults.start_wavelength;
    }
    if (defaults.end_wavelength !== undefined) {
        document.getElementById('end-wavelength').value = defaults.end_wavelength;
    }
    if (defaults.step_size !== undefined) {
        document.getElementById('step-size').value = defaults.step_size;
    }

    // Stability test parameters
    const stabWl = document.getElementById('stability-wavelength');
    const stabDur = document.getElementById('stability-duration');
    const stabInt = document.getElementById('stability-interval');

    if (stabWl && stability.default_wavelength !== undefined) {
        stabWl.value = stability.default_wavelength;
    }
    if (stabDur) {
        if (stability.default_duration_min !== undefined) {
            stabDur.value = stability.default_duration_min;
        }
        if (stability.duration_range) {
            stabDur.min = stability.duration_range[0];
            stabDur.max = stability.duration_range[1];
        }
    }
    if (stabInt) {
        if (stability.default_interval_sec !== undefined) {
            stabInt.value = stability.default_interval_sec;
        }
        if (stability.interval_range) {
            stabInt.min = stability.interval_range[0];
            stabInt.max = stability.interval_range[1];
        }
    }

    // Pixel modal defaults
    const pixelInput = document.getElementById('pixel-input');
    const pixelLabel = document.querySelector('label[for="pixel-input"]');
    if (pixelInput && validation.pixel_range) {
        pixelInput.min = validation.pixel_range[0];
        pixelInput.max = validation.pixel_range[1];
        pixelInput.value = validation.pixel_range[0];
        if (pixelLabel) {
            pixelLabel.textContent = `Pixel Number (${validation.pixel_range[0]}-${validation.pixel_range[1]})`;
        }
    }
}

document.addEventListener('DOMContentLoaded', async () => {
    LabTheme.init();
    await LabAPI.init();
    await LabConfig.load();

    // Populate form defaults from config
    populateFormDefaults();

    setTimeout(() => {
        initPlots();
        // Ensure plots match current theme (handles theme passed from launcher)
        const isDark = LabTheme.isDark();
        window.dispatchEvent(new CustomEvent('themechange', { detail: { dark: isDark } }));
    }, 50);

    setTimeout(() => {
        const anyDeviceSet = state.devices.picoscope.message ||
                             state.devices.monochromator.message ||
                             state.devices.power_meter.message;
        if (!anyDeviceSet) {
            checkDeviceStatus();
        }
    }, 500);

    LabModals.init();
});

// Called by Python after window is shown
function showStartupCellModal() {
    LabModals.showCell((cellNumber) => {
        document.getElementById('cell-number').value = cellNumber;
        state.cellNumber = cellNumber;
    });
}

// ============================================
// Tab Navigation
// ============================================

function switchTab(tabName) {
    if (state.measurementState !== 'idle' && state.measurementState !== 'live_monitor') {
        LabModals.showError('Cannot Switch', 'Please stop the current measurement before switching tabs.');
        return;
    }
    if (state.stability.running) {
        LabModals.showError('Cannot Switch', 'Please stop the stability test before switching tabs.');
        return;
    }

    state.activeTab = tabName;

    document.querySelectorAll('.tab-btn').forEach(btn => {
        const btnTab = btn.getAttribute('onclick')?.match(/switchTab\('(\w+)'\)/)?.[1];
        btn.classList.toggle('active', btnTab === tabName);
    });

    document.querySelectorAll('.tab-content').forEach(content => {
        content.classList.toggle('active', content.id === 'tab-' + tabName);
    });

    if (tabName === 'stability') {
        setTimeout(() => initStabilityPlots(), 50);
    } else if (tabName === 'analysis') {
        setTimeout(() => {
            const plotDiv = document.getElementById('eqe-plot');
            if (!plotDiv.data) {
                initEQEPlot();
            } else {
                Plotly.Plots.resize('eqe-plot');
            }
            updateSessionDataButton();
        }, 50);
    } else {
        setTimeout(() => {
            Plotly.Plots.resize('power-plot');
            Plotly.Plots.resize('current-plot');
            Plotly.Plots.resize('phase-plot');
        }, 50);
    }
}

// ============================================
// Plots
// ============================================

function initPlots() {
    const isDark = LabTheme.isDark();

    Plotly.newPlot('power-plot',
        [{ x: [], y: [], mode: 'markers', type: 'scatter', name: 'Power',
           marker: { color: PLOT_COLORS.power, size: 8 } }],
        getPlotLayout(isDark, 'Wavelength (nm)', 'Power (µW)'),
        plotConfig
    );

    Plotly.newPlot('current-plot',
        [{ x: [], y: [], mode: 'markers', type: 'scatter', name: 'Current',
           marker: { color: PLOT_COLORS.current, size: 8 } }],
        getPlotLayout(isDark, 'Wavelength (nm)', 'Current (nA)'),
        plotConfig
    );

    Plotly.newPlot('phase-plot',
        [
            { x: [], y: [], mode: 'markers', type: 'scatter', name: 'Measured',
              marker: { color: PLOT_COLORS.phaseMeasured, size: 8 } },
            { x: [], y: [], mode: 'lines', type: 'scatter', name: 'Sine Fit',
              line: { color: PLOT_COLORS.phaseFit, width: 2 } }
        ],
        getPlotLayout(isDark, 'Phase (degrees)', 'Signal (V)'),
        plotConfig
    );
}

window.addEventListener('resize', () => {
    if (typeof Plotly !== 'undefined') {
        Plotly.Plots.resize('power-plot');
        Plotly.Plots.resize('current-plot');
        Plotly.Plots.resize('phase-plot');
    }
});

window.addEventListener('themechange', (e) => {
    const isDark = e.detail.dark;
    const plotIds = [
        'power-plot', 'current-plot', 'phase-plot',
        'stability-time-plot', 'stability-hist-plot',
        'eqe-plot'
    ];
    plotIds.forEach(id => {
        const plotDiv = document.getElementById(id);
        if (plotDiv && plotDiv.data) {
            const colors = {
                text: isDark ? '#eeeeee' : '#1a1a1a',
                grid: isDark ? '#444444' : '#dddddd',
                zeroline: isDark ? '#666666' : '#999999',
                paper: isDark ? '#2a2a2a' : '#f5f5f5',
                plot: isDark ? '#2a2a2a' : '#f5f5f5',
                legendBg: isDark ? 'rgba(50,50,50,0.8)' : 'rgba(245,245,245,0.9)'
            };
            Plotly.relayout(plotDiv, {
                'xaxis.color': colors.text, 'xaxis.gridcolor': colors.grid,
                'yaxis.color': colors.text, 'yaxis.gridcolor': colors.grid,
                'font.color': colors.text,
                'paper_bgcolor': colors.paper,
                'plot_bgcolor': colors.plot,
                'legend.font.color': colors.text,
                'legend.bgcolor': colors.legendBg
            });
        }
    });
});

// ============================================
// Device Status
// ============================================

async function checkDeviceStatus() {
    try {
        const api = LabAPI.get();
        if (api && api.get_device_status) {
            api.get_device_status((result) => {
                const status = JSON.parse(result);
                state.offlineMode = status.offline_mode;
                updateDeviceIndicator('picoscope', status.picoscope);
                updateDeviceIndicator('mono', status.monochromator);
                updateDeviceIndicator('power', status.power_meter);
                state.devices.picoscope = status.picoscope;
                state.devices.monochromator = status.monochromator;
                state.devices.power_meter = status.power_meter;
                updateButtonStates();
            });
        }
    } catch (error) {
        console.error('Device status check failed:', error);
    }
}

function updateDeviceIndicator(name, status) {
    const dot = document.getElementById(name + '-dot');
    const text = document.getElementById(name + '-status');

    const isOffline = state.offlineMode || (status.message && status.message.toUpperCase().includes('OFFLINE'));

    if (isOffline) {
        dot.className = 'device-dot warning';
        text.textContent = 'Offline Mode';
    } else if (status.connected) {
        dot.className = 'device-dot connected';
        text.textContent = 'Connected';
    } else {
        dot.className = 'device-dot disconnected';
        // Show simple "Not Connected" in status bar - details are in console
        text.textContent = 'Not Connected';
    }
}

function updateButtonStates() {
    const canMeasure = state.offlineMode ||
        (state.devices.picoscope.connected && state.devices.monochromator.connected);
    const canPower = state.offlineMode ||
        (state.devices.power_meter.connected && state.devices.monochromator.connected);

    document.getElementById('power-btn').disabled = !canPower;
    document.getElementById('current-btn').disabled = !canMeasure;
    document.getElementById('live-btn').disabled = !canMeasure;
}

function onDeviceStatusChanged(deviceName, connected, message) {
    const nameMap = { 'Thorlabs Power Meter': 'power', 'Monochromator': 'mono', 'PicoScope Lock-in': 'picoscope' };
    const stateKeyMap = { 'Thorlabs Power Meter': 'power_meter', 'Monochromator': 'monochromator', 'PicoScope Lock-in': 'picoscope' };
    const id = nameMap[deviceName];
    const stateKey = stateKeyMap[deviceName];
    if (id && stateKey) {
        if (message && message.includes('OFFLINE')) state.offlineMode = true;
        updateDeviceIndicator(id, { connected, message });
        state.devices[stateKey] = { connected, message };
        updateButtonStates();
    }
}

// ============================================
// Monochromator
// ============================================

function updateMonochromatorDisplay() {
    document.getElementById('mono-wavelength').textContent = state.wavelength.toFixed(1);
    const badge = document.getElementById('shutter-badge');
    const btn = document.getElementById('shutter-btn');
    if (state.shutterOpen) {
        badge.className = 'shutter-badge open';
        badge.textContent = 'Open';
        btn.textContent = 'Close';
    } else {
        badge.className = 'shutter-badge closed';
        badge.textContent = 'Closed';
        btn.textContent = 'Open';
    }
}

function goToWavelength() {
    const wavelength = parseFloat(document.getElementById('wavelength-input').value);
    // Get wavelength range from config, fallback to [200, 1200]
    const wlRange = LabConfig.get('devices.monochromator.wavelength_range', [200, 1200]);
    if (isNaN(wavelength) || wavelength < wlRange[0] || wavelength > wlRange[1]) {
        LabModals.showError('Invalid Wavelength', `Enter wavelength between ${wlRange[0]}-${wlRange[1]} nm`);
        return;
    }
    if (state.offlineMode) {
        state.wavelength = wavelength;
        updateMonochromatorDisplay();
        return;
    }
    const api = LabAPI.get();
    if (api && api.set_wavelength) {
        api.set_wavelength(wavelength, (result) => {
            const r = JSON.parse(result);
            if (!r.success) LabModals.showError('Error', r.message);
        });
    }
}

function toggleShutter() {
    if (state.offlineMode) {
        state.shutterOpen = !state.shutterOpen;
        updateMonochromatorDisplay();
        return;
    }
    const api = LabAPI.get();
    if (state.shutterOpen) {
        if (api && api.close_shutter) api.close_shutter(() => {});
    } else {
        if (api && api.open_shutter) api.open_shutter(() => {});
    }
}

function alignMonochromator() {
    if (state.offlineMode) {
        state.wavelength = 532;
        state.shutterOpen = true;
        updateMonochromatorDisplay();
        return;
    }
    const api = LabAPI.get();
    if (api && api.align_monochromator) {
        api.align_monochromator((result) => {
            const r = JSON.parse(result);
            if (!r.success) LabModals.showError('Error', r.message);
        });
    }
}

function onMonochromatorStateChanged(wavelength, shutterOpen, filterNumber) {
    state.wavelength = wavelength;
    state.shutterOpen = shutterOpen;
    state.filter = filterNumber;
    updateMonochromatorDisplay();

    if (liveMonitorActive) {
        document.getElementById('progress-status').textContent =
            'Live monitoring at ' + wavelength.toFixed(0) + ' nm';
    }
}

// ============================================
// Measurements
// ============================================

function getParams() {
    return {
        start_wavelength: parseFloat(document.getElementById('start-wavelength').value),
        end_wavelength: parseFloat(document.getElementById('end-wavelength').value),
        step_size: parseFloat(document.getElementById('step-size').value),
        cell_number: document.getElementById('cell-number').value || '000'
    };
}

function startPowerMeasurement() {
    const cell = document.getElementById('cell-number').value;
    if (!cell || !/^\d{3}$/.test(cell)) {
        LabModals.showCell((cellNumber) => {
            document.getElementById('cell-number').value = cellNumber;
            state.cellNumber = cellNumber;
            startPowerMeasurement();
        });
        return;
    }

    state.measurementState = 'power';
    state.powerData = { x: [], y: [] };
    clearPlot('power');
    setMeasuringState(true);
    updateProgress(0, 'Starting power measurement...');

    if (state.offlineMode) {
        mockPowerMeasurement();
        return;
    }

    const api = LabAPI.get();
    if (api && api.start_power_measurement) {
        api.start_power_measurement(JSON.stringify(getParams()), (result) => {
            const r = JSON.parse(result);
            if (!r.success) {
                LabModals.showError('Measurement Failed', r.message);
                setMeasuringState(false);
            }
        });
    }
}

function startCurrentMeasurement() {
    const cell = document.getElementById('cell-number').value;
    if (!cell || !/^\d{3}$/.test(cell)) {
        LabModals.showCell((cellNumber) => {
            document.getElementById('cell-number').value = cellNumber;
            state.cellNumber = cellNumber;
            LabModals.showPixel(startCurrentMeasurementWithPixel);
        });
        return;
    }
    LabModals.showPixel(startCurrentMeasurementWithPixel);
}

function startCurrentMeasurementWithPixel(pixel) {
    state.currentPixel = pixel;
    state.measurementState = 'phase';
    state.phaseData = { x: [], y: [] };
    state.currentData = { x: [], y: [], stats: [] };
    clearPlot('phase');
    clearPlot('current');
    setMeasuringState(true);
    updateProgress(0, 'Phase adjustment...');
    document.getElementById('pixel-label').textContent = 'Pixel: ' + pixel;
    document.getElementById('stats-row').classList.remove('hidden');
    setTimeout(() => {
        Plotly.Plots.resize('current-plot');
    }, 50);

    if (state.offlineMode) {
        mockPhaseThenCurrentMeasurement(pixel);
        return;
    }

    const params = { ...getParams(), pixel };
    const api = LabAPI.get();
    if (api && api.start_current_measurement) {
        api.start_current_measurement(JSON.stringify(params), (result) => {
            const r = JSON.parse(result);
            if (!r.success) {
                LabModals.showError('Measurement Failed', r.message);
                setMeasuringState(false);
            }
        });
    }
}

function stopMeasurement() {
    if (state.offlineMode) {
        state.measurementState = 'idle';
        setMeasuringState(false);
        return;
    }
    const api = LabAPI.get();
    if (api && api.stop_measurement) api.stop_measurement(() => {});
    state.measurementState = 'idle';
    setMeasuringState(false);
}

function setMeasuringState(measuring) {
    document.getElementById('power-btn').disabled = measuring;
    document.getElementById('current-btn').disabled = measuring;
    document.getElementById('stop-btn').disabled = !measuring;
    document.getElementById('live-btn').disabled = measuring;

    if (measuring) {
        document.getElementById('save-btn').disabled = true;
    }

    const inputs = document.querySelectorAll('.params-grid input, .mono-controls-inline input');
    inputs.forEach(input => input.disabled = measuring);

    const monoButtons = document.querySelectorAll('.mono-controls-inline .btn');
    monoButtons.forEach(btn => btn.disabled = measuring);

    if (!measuring) {
        updateButtonStates();
        document.getElementById('stats-row').classList.add('hidden');
        setTimeout(() => {
            Plotly.Plots.resize('power-plot');
            Plotly.Plots.resize('current-plot');
            Plotly.Plots.resize('phase-plot');
        }, 50);
    }
}

function updateProgress(percent, status) {
    document.getElementById('progress-fill').style.width = percent + '%';
    document.getElementById('progress-percent').textContent = Math.round(percent) + '%';
    document.getElementById('progress-status').textContent = status;
}

// ============================================
// Plot Updates (Python callbacks)
// ============================================

function onPowerProgress(wavelength, power, percent) {
    const powerUW = power * 1e6;
    state.powerData.x.push(wavelength);
    state.powerData.y.push(powerUW);

    const isDark = LabTheme.isDark();
    Plotly.newPlot('power-plot',
        [{ x: state.powerData.x, y: state.powerData.y, mode: 'markers', type: 'scatter',
           name: 'Power', marker: { color: PLOT_COLORS.power, size: 8 } }],
        getPlotLayout(isDark, 'Wavelength (nm)', 'Power (µW)'),
        plotConfig
    );
    updateProgress(percent, `Measuring at ${wavelength.toFixed(0)} nm`);
}

function onCurrentProgress(wavelength, current, percent) {
    const currentNA = current * 1e9;
    state.currentData.x.push(wavelength);
    state.currentData.y.push(currentNA);

    if (state.measurementState === 'phase') {
        state.measurementState = 'current';
    }

    const isDark = LabTheme.isDark();
    Plotly.newPlot('current-plot',
        [{ x: state.currentData.x, y: state.currentData.y, mode: 'markers', type: 'scatter',
           name: 'Current', marker: { color: PLOT_COLORS.current, size: 8 } }],
        getPlotLayout(isDark, 'Wavelength (nm)', 'Current (nA)'),
        plotConfig
    );
    updateProgress(percent, `Measuring at ${wavelength.toFixed(0)} nm`);
}

function onPhaseProgress(phase, signal) {
    state.phaseData.x.push(phase);
    state.phaseData.y.push(signal);

    const isDark = LabTheme.isDark();
    Plotly.newPlot('phase-plot',
        [
            { x: state.phaseData.x, y: state.phaseData.y, mode: 'markers', type: 'scatter',
              name: 'Measured', marker: { color: PLOT_COLORS.phaseMeasured, size: 8 } },
            { x: [], y: [], mode: 'lines', type: 'scatter', name: 'Sine Fit',
              line: { color: PLOT_COLORS.phaseFit, width: 2 } }
        ],
        getPlotLayout(isDark, 'Phase (degrees)', 'Signal (V)'),
        plotConfig
    );
    updateProgress(0, `Phase adjustment: ${phase.toFixed(0)}°`);
}

function onMeasurementComplete(success, message) {
    const completedMeasurement = state.measurementState;
    state.measurementState = 'idle';
    setMeasuringState(false);

    if (success) {
        updateProgress(100, 'Complete');
        document.getElementById('save-btn').disabled = false;
        if (completedMeasurement === 'power') savePowerData();
        else if (completedMeasurement === 'current') saveCurrentData();
    } else {
        updateProgress(0, 'Failed');
        if (message && message !== 'Stopped') {
            LabModals.showError('Measurement Failed', message);
        }
    }
}

function onMeasurementStats(stats) {
    state.stats = stats;
    state.currentData.stats.push({
        mean: stats.mean,
        std_dev: stats.std_dev,
        std_error: stats.std_error,
        n: stats.n,
        cv_percent: stats.cv_percent
    });
    document.getElementById('stats-n').textContent = `${stats.n}/${stats.total}`;

    // Format SD and SE in nanoamps for readability (current is in Amps)
    // SD = spread of measurements, SE = uncertainty in the mean
    const sdNanoamps = stats.std_dev * 1e9;
    const seNanoamps = stats.std_error * 1e9;
    document.getElementById('stats-sd').textContent = sdNanoamps.toFixed(2) + ' nA';
    document.getElementById('stats-se').textContent = seNanoamps.toFixed(2) + ' nA';

    document.getElementById('stats-cv').textContent = stats.cv_percent.toFixed(1) + '%';
    const badge = document.getElementById('stats-quality');
    badge.textContent = stats.quality;
    badge.className = 'quality-badge quality-' + stats.quality.toLowerCase();
}

function onPhaseAdjustmentComplete(data) {
    state.phaseData.x = data.phase_data || [];
    state.phaseData.y = data.signal_data || [];

    const fitX = data.fit_phases || [];
    const fitY = data.fit_signals || [];

    const isDark = LabTheme.isDark();
    Plotly.newPlot('phase-plot',
        [
            { x: state.phaseData.x, y: state.phaseData.y, mode: 'markers', type: 'scatter',
              name: 'Measured', marker: { color: PLOT_COLORS.phaseMeasured, size: 8 } },
            { x: fitX, y: fitY, mode: 'lines', type: 'scatter', name: 'Sine Fit',
              line: { color: PLOT_COLORS.phaseFit, width: 2 } }
        ],
        getPlotLayout(isDark, 'Phase (degrees)', 'Signal (V)'),
        plotConfig
    );

    updateProgress(0, `Phase: ${data.optimal_phase?.toFixed(1) || '--'}° (R² = ${data.r_squared?.toFixed(4) || '--'})`);
}

function clearPlot(type) {
    const isDark = LabTheme.isDark();
    if (type === 'power') {
        Plotly.newPlot('power-plot',
            [{ x: [], y: [], mode: 'markers', type: 'scatter', name: 'Power',
               marker: { color: PLOT_COLORS.power, size: 8 } }],
            getPlotLayout(isDark, 'Wavelength (nm)', 'Power (µW)'),
            plotConfig
        );
    } else if (type === 'current') {
        Plotly.newPlot('current-plot',
            [{ x: [], y: [], mode: 'markers', type: 'scatter', name: 'Current',
               marker: { color: PLOT_COLORS.current, size: 8 } }],
            getPlotLayout(isDark, 'Wavelength (nm)', 'Current (nA)'),
            plotConfig
        );
    } else if (type === 'phase') {
        Plotly.newPlot('phase-plot',
            [
                { x: [], y: [], mode: 'markers', type: 'scatter', name: 'Measured',
                  marker: { color: PLOT_COLORS.phaseMeasured, size: 8 } },
                { x: [], y: [], mode: 'lines', type: 'scatter', name: 'Sine Fit',
                  line: { color: PLOT_COLORS.phaseFit, width: 2 } }
            ],
            getPlotLayout(isDark, 'Phase (degrees)', 'Signal (V)'),
            plotConfig
        );
    }
}

// ============================================
// Live Monitor
// ============================================

function toggleLiveMonitor() {
    if (liveMonitorActive) {
        stopLiveMonitor();
    } else {
        startLiveMonitor();
    }
}

function startLiveMonitor() {
    liveMonitorActive = true;
    state.measurementState = 'live_monitor';
    document.getElementById('live-btn').textContent = 'Stop Monitor';
    document.getElementById('live-btn').className = 'btn btn-danger';
    document.getElementById('progress-bar-row').classList.add('hidden');
    document.getElementById('live-reading').classList.remove('hidden');
    document.getElementById('power-btn').disabled = true;
    document.getElementById('current-btn').disabled = true;
    document.getElementById('progress-status').textContent = 'Starting live monitor...';

    if (state.offlineMode) {
        mockLiveMonitor();
        return;
    }

    const api = LabAPI.get();
    if (api && api.start_live_monitor) api.start_live_monitor(() => {});
}

function stopLiveMonitor() {
    liveMonitorActive = false;
    state.measurementState = 'idle';
    document.getElementById('live-btn').textContent = 'Live Monitor';
    document.getElementById('live-btn').className = 'btn btn-secondary';
    document.getElementById('progress-bar-row').classList.remove('hidden');
    document.getElementById('live-reading').classList.add('hidden');
    updateButtonStates();
    updateProgress(0, 'Ready');

    if (!state.offlineMode) {
        const api = LabAPI.get();
        if (api && api.stop_live_monitor) api.stop_live_monitor(() => {});
    }
}

function onLiveSignalUpdate(currentNA) {
    document.getElementById('live-value').textContent = currentNA.toFixed(2);
}

// ============================================
// Data Export
// ============================================

function saveData() {
    const hasPower = state.powerData.x.length > 0;
    const hasCurrent = state.currentData.x.length > 0;

    if (!hasPower && !hasCurrent) {
        LabModals.showError('No Data', 'No measurement data to save');
        return;
    }

    LabModals.showSave({ hasPower, hasCurrent }, (type) => {
        if (type === 'power') {
            savePowerData();
        } else if (type === 'current') {
            saveCurrentData();
        }
    });
}

function savePowerData() {
    let csv = 'Wavelength (nm),Power (uW)\n';
    for (let i = 0; i < state.powerData.x.length; i++) {
        csv += `${state.powerData.x[i].toFixed(1)},${state.powerData.y[i].toFixed(6)}\n`;
    }
    const api = LabAPI.get();
    if (api && api.save_power_data) {
        api.save_power_data(csv, document.getElementById('cell-number').value, (result) => {
            const r = JSON.parse(result);
            if (r.success) console.log('Saved:', r.path);
            else if (r.message !== 'Cancelled') LabModals.showError('Save Failed', r.message);
        });
    }
}

function saveCurrentData() {
    let csv = 'Wavelength (nm),Current_mean (nA),Current_std (nA),Current_SE (nA),n,CV_percent\n';
    for (let i = 0; i < state.currentData.x.length; i++) {
        const wavelength = state.currentData.x[i];
        const current = state.currentData.y[i];
        const stats = state.currentData.stats[i] || {};
        const std_dev = stats.std_dev !== undefined ? (stats.std_dev * 1e9).toFixed(6) : '0';
        const std_error = stats.std_error !== undefined ? (stats.std_error * 1e9).toFixed(6) : '0';
        const n = stats.n || 0;
        const cv = stats.cv_percent !== undefined ? stats.cv_percent.toFixed(2) : '0';
        csv += `${wavelength.toFixed(1)},${current.toFixed(6)},${std_dev},${std_error},${n},${cv}\n`;
    }
    const api = LabAPI.get();
    if (api && api.save_current_data) {
        api.save_current_data(csv, document.getElementById('cell-number').value, state.currentPixel, (result) => {
            const r = JSON.parse(result);
            if (r.success) console.log('Saved:', r.path);
            else if (r.message !== 'Cancelled') LabModals.showError('Save Failed', r.message);
        });
    }
}

// ============================================
// Mock Measurements
// ============================================

function mockPowerMeasurement() {
    const params = getParams();
    let wavelength = params.start_wavelength;
    const end = params.end_wavelength;
    const step = params.step_size;
    const total = Math.ceil((end - wavelength) / step) + 1;
    let count = 0;

    state.shutterOpen = true;
    updateMonochromatorDisplay();

    const interval = setInterval(() => {
        if (state.measurementState !== 'power' || wavelength > end) {
            clearInterval(interval);
            if (state.measurementState === 'power') {
                state.shutterOpen = false;
                updateMonochromatorDisplay();
                onMeasurementComplete(true, 'Complete');
            }
            return;
        }
        const power = 2e-6 * Math.exp(-Math.pow((wavelength - 550) / 100, 2)) * (0.9 + 0.2 * Math.random());
        count++;

        state.wavelength = wavelength;
        updateMonochromatorDisplay();

        onPowerProgress(wavelength, power, (count / total) * 100);
        wavelength += step;
    }, 100);
}

function mockPhaseThenCurrentMeasurement(pixel) {
    state.wavelength = 532;
    state.shutterOpen = true;
    updateMonochromatorDisplay();

    const phaseData = [];
    const signalData = [];
    const optimalPhase = 45;
    const amplitude = 0.4;
    const offset = 0.5;

    for (let phase = 0; phase <= 360; phase += 15) {
        const signal = offset + amplitude * Math.sin((phase - optimalPhase) * Math.PI / 180) + 0.02 * (Math.random() - 0.5);
        phaseData.push(phase);
        signalData.push(signal);
        onPhaseProgress(phase, signal);
    }

    const fitPhases = [];
    const fitSignals = [];
    for (let phase = 0; phase <= 360; phase += 5) {
        fitPhases.push(phase);
        fitSignals.push(offset + amplitude * Math.sin((phase - optimalPhase) * Math.PI / 180));
    }

    setTimeout(() => {
        if (state.measurementState === 'idle') return;

        onPhaseAdjustmentComplete({
            phase_data: phaseData,
            signal_data: signalData,
            fit_phases: fitPhases,
            fit_signals: fitSignals,
            optimal_phase: optimalPhase,
            r_squared: 0.9876
        });

        state.measurementState = 'current';
        mockCurrentMeasurement();
    }, 500);
}

function mockCurrentMeasurement() {
    const params = getParams();
    let wavelength = params.start_wavelength;
    const end = params.end_wavelength;
    const step = params.step_size;
    const total = Math.ceil((end - wavelength) / step) + 1;
    let count = 0;

    const interval = setInterval(() => {
        if (state.measurementState !== 'current' || wavelength > end) {
            clearInterval(interval);
            if (state.measurementState === 'current') {
                state.shutterOpen = false;
                updateMonochromatorDisplay();
                onMeasurementComplete(true, 'Complete');
            }
            return;
        }
        const bandgap = 750;
        let current;
        if (wavelength < bandgap) {
            current = 2e-9 * (1 - Math.exp(-(wavelength - 350) / 50)) * (0.9 + 0.2 * Math.random());
        } else {
            current = 2e-9 * Math.exp(-(wavelength - bandgap) / 30) * (0.9 + 0.2 * Math.random());
        }
        count++;

        state.wavelength = wavelength;
        updateMonochromatorDisplay();

        const cv = 0.5 + Math.random() * 7.5;
        const std_dev = current * (cv / 100);
        const std_error = std_dev / Math.sqrt(5);  // SE = σ/√n
        const quality = cv < 1.0 ? 'Excellent' : cv < 5.0 ? 'Good' : cv < 10.0 ? 'Fair' : 'Check';
        onMeasurementStats({
            mean: current,
            std_dev: std_dev,
            std_error: std_error,
            n: 5, total: 5, outliers: 0,
            cv_percent: cv, quality: quality
        });

        onCurrentProgress(wavelength, current, (count / total) * 100);
        wavelength += step;
    }, 150);
}

function mockLiveMonitor() {
    state.wavelength = 532;
    state.shutterOpen = true;
    updateMonochromatorDisplay();
    document.getElementById('progress-status').textContent = 'Live monitoring at 532 nm';

    const mockInterval = setInterval(() => {
        if (!liveMonitorActive) {
            clearInterval(mockInterval);
            state.shutterOpen = false;
            updateMonochromatorDisplay();
            return;
        }
        onLiveSignalUpdate(1.5 + 0.5 * Math.random());
    }, 500);
}

// ============================================
// Stability Tests
// ============================================

function initStabilityPlots() {
    const isDark = LabTheme.isDark();

    Plotly.newPlot('stability-time-plot',
        [
            { x: [], y: [], mode: 'lines+markers', type: 'scatter', name: 'Measured',
              line: { color: PLOT_COLORS.power }, marker: { size: 6 } },
            { x: [], y: [], mode: 'lines', type: 'scatter', name: 'Mean',
              line: { color: PLOT_COLORS.phaseFit, dash: 'dash', width: 2 } },
            { x: [], y: [], mode: 'lines', type: 'scatter', name: '+1σ',
              line: { color: '#ffb74d', dash: 'dot', width: 1 }, showlegend: false },
            { x: [], y: [], mode: 'lines', type: 'scatter', name: '-1σ',
              line: { color: '#ffb74d', dash: 'dot', width: 1 }, showlegend: false }
        ],
        getPlotLayout(isDark, 'Time (s)', 'Value'),
        plotConfig
    );

    Plotly.newPlot('stability-hist-plot',
        [{ x: [], type: 'histogram', name: 'Distribution',
           marker: { color: PLOT_COLORS.power } }],
        {
            ...getPlotLayout(isDark, 'Value', 'Count'),
            bargap: 0.05
        },
        plotConfig
    );
}

function onStabilityTypeChange() {
    const testType = document.querySelector('input[name="stability-type"]:checked').value;
    state.stability.testType = testType;
}

function getStabilityParams() {
    return {
        type: state.stability.testType,
        wavelength: parseFloat(document.getElementById('stability-wavelength').value),
        duration: parseFloat(document.getElementById('stability-duration').value),
        interval: parseFloat(document.getElementById('stability-interval').value),
        pixel: state.stability.pixel || 1
    };
}

function startStabilityTest() {
    const testType = document.querySelector('input[name="stability-type"]:checked').value;
    state.stability.testType = testType;

    const wavelength = parseFloat(document.getElementById('stability-wavelength').value);
    // Get wavelength range from config, fallback to [200, 1200]
    const wlRange = LabConfig.get('devices.monochromator.wavelength_range', [200, 1200]);
    if (isNaN(wavelength) || wavelength < wlRange[0] || wavelength > wlRange[1]) {
        LabModals.showError('Invalid Wavelength', `Enter wavelength between ${wlRange[0]}-${wlRange[1]} nm`);
        return;
    }

    if (testType === 'current') {
        LabModals.showPixel(startStabilityTestWithPixel);
    } else {
        startStabilityTestWithPixel(null);
    }
}

function startStabilityTestWithPixel(pixel) {
    if (pixel !== null) {
        state.stability.pixel = pixel;
        document.getElementById('pixel-label').textContent = 'Pixel: ' + pixel;
    }

    const params = getStabilityParams();

    state.stability.running = true;
    state.stability.data = { times: [], values: [] };
    state.stability.stats = null;
    state.stability.startTime = Date.now();

    setStabilityTestState(true);
    updateStabilityProgress(0, 'Starting test...');
    clearStabilityStats();

    if (state.offlineMode) {
        mockStabilityTest(params);
        return;
    }

    const api = LabAPI.get();
    if (api && api.start_stability_test) {
        api.start_stability_test(JSON.stringify(params), (result) => {
            const r = JSON.parse(result);
            if (!r.success) {
                LabModals.showError('Test Failed', r.message);
                setStabilityTestState(false);
            } else if (r.phase === 'adjusting') {
                updateStabilityProgress(0, 'Adjusting phase (locking to chopper)...');
            }
        });
    }
}

function stopStabilityTest() {
    state.stability.running = false;

    if (!state.offlineMode) {
        const api = LabAPI.get();
        if (api && api.stop_stability_test) api.stop_stability_test(() => {});
    }

    setStabilityTestState(false);
    updateStabilityProgress(0, 'Stopped');
}

function setStabilityTestState(running) {
    document.getElementById('stability-start-btn').disabled = running;
    document.getElementById('stability-stop-btn').disabled = !running;

    const inputs = document.querySelectorAll('#tab-stability .config-field input, #tab-stability input[type="radio"]');
    inputs.forEach(input => input.disabled = running);

    document.getElementById('wavelength-input').disabled = running;
    document.querySelectorAll('.mono-controls-inline .btn').forEach(btn => btn.disabled = running);

    if (!running && state.stability.data.times.length > 0) {
        document.getElementById('stability-save-btn').disabled = false;
    }
}

function updateStabilityProgress(percent, status) {
    document.getElementById('stability-progress-fill').style.width = percent + '%';
    document.getElementById('stability-progress-percent').textContent = Math.round(percent) + '%';
    document.getElementById('stability-status').textContent = status;
}

function onStabilityProgress(timestamp, value) {
    state.stability.data.times.push(timestamp);
    state.stability.data.values.push(value);

    const stats = calculateStabilityStats(state.stability.data.values);
    state.stability.stats = stats;

    updateStabilityPlots();
    updateStabilityStatsDisplay(stats);

    const params = getStabilityParams();
    const elapsed = timestamp;
    const total = params.duration * 60;
    const percent = Math.min(100, (elapsed / total) * 100);
    updateStabilityProgress(percent, `Measuring... (${state.stability.data.times.length} points)`);
}

function calculateStabilityStats(values) {
    if (values.length === 0) return null;

    const n = values.length;
    const mean = values.reduce((a, b) => a + b, 0) / n;
    const variance = values.reduce((sum, v) => sum + Math.pow(v - mean, 2), 0) / n;
    const std = Math.sqrt(variance);
    const min = Math.min(...values);
    const max = Math.max(...values);

    return {
        mean: mean,
        std: std,
        cv_percent: (std / Math.abs(mean)) * 100,
        min: min,
        max: max,
        range: max - min,
        count: n
    };
}

function updateStabilityPlots() {
    const isDark = LabTheme.isDark();
    const times = state.stability.data.times;
    const rawValues = state.stability.data.values;
    const stats = state.stability.stats;

    const isPower = state.stability.testType === 'power';
    const multiplier = isPower ? 1e6 : 1e9;
    const values = rawValues.map(v => v * multiplier);

    let meanLine = [], plusSigma = [], minusSigma = [];
    if (stats && times.length > 0) {
        const meanVal = stats.mean * multiplier;
        const stdVal = stats.std * multiplier;
        meanLine = [{ x: [times[0], times[times.length - 1]], y: [meanVal, meanVal] }];
        plusSigma = [{ x: [times[0], times[times.length - 1]], y: [meanVal + stdVal, meanVal + stdVal] }];
        minusSigma = [{ x: [times[0], times[times.length - 1]], y: [meanVal - stdVal, meanVal - stdVal] }];
    }

    const yLabel = isPower ? 'Power (µW)' : 'Current (nA)';

    const timeLayout = getPlotLayout(isDark, 'Time (s)', yLabel);
    timeLayout.yaxis.tickformat = '.2f';

    Plotly.react('stability-time-plot',
        [
            { x: times, y: values, mode: 'lines+markers', type: 'scatter', name: 'Measured',
              line: { color: PLOT_COLORS.power }, marker: { size: 6 } },
            { x: meanLine[0]?.x || [], y: meanLine[0]?.y || [], mode: 'lines', type: 'scatter', name: 'Mean',
              line: { color: PLOT_COLORS.phaseFit, dash: 'dash', width: 2 } },
            { x: plusSigma[0]?.x || [], y: plusSigma[0]?.y || [], mode: 'lines', type: 'scatter', name: '±1σ',
              line: { color: '#ffb74d', dash: 'dot', width: 1 } },
            { x: minusSigma[0]?.x || [], y: minusSigma[0]?.y || [], mode: 'lines', type: 'scatter', name: '-1σ',
              line: { color: '#ffb74d', dash: 'dot', width: 1 }, showlegend: false }
        ],
        timeLayout,
        plotConfig
    );

    const histLayout = getPlotLayout(isDark, yLabel, 'Count');
    histLayout.xaxis.tickformat = '.2f';
    histLayout.margin = { ...histLayout.margin, b: 60, l: 50 };
    histLayout.bargap = 0.05;

    Plotly.react('stability-hist-plot',
        [{ x: values, type: 'histogram', name: 'Distribution',
           marker: { color: PLOT_COLORS.power },
           nbinsx: Math.min(20, Math.max(5, Math.floor(values.length / 2))) }],
        histLayout,
        plotConfig
    );
}

function updateStabilityStatsDisplay(stats) {
    if (!stats) return;

    const isPower = state.stability.testType === 'power';
    const unit = isPower ? ' µW' : ' nA';
    const multiplier = isPower ? 1e6 : 1e9;

    document.getElementById('stability-mean').textContent =
        (stats.mean * multiplier).toFixed(3) + unit;
    document.getElementById('stability-std').textContent =
        (stats.std * multiplier).toFixed(3) + unit;

    const cvEl = document.getElementById('stability-cv');
    cvEl.textContent = stats.cv_percent.toFixed(2) + '%';
    cvEl.className = 'stability-stat-value cv';
    if (stats.cv_percent < 1.0) cvEl.classList.add('excellent');
    else if (stats.cv_percent < 3.0) cvEl.classList.add('good');
    else cvEl.classList.add('poor');

    document.getElementById('stability-count').textContent = stats.count;
    document.getElementById('stability-range').textContent =
        (stats.min * multiplier).toFixed(3) + ' - ' + (stats.max * multiplier).toFixed(3) + unit;
}

function clearStabilityStats() {
    document.getElementById('stability-mean').textContent = '--';
    document.getElementById('stability-std').textContent = '--';
    document.getElementById('stability-cv').textContent = '--%';
    document.getElementById('stability-cv').className = 'stability-stat-value cv';
    document.getElementById('stability-count').textContent = '0';
    document.getElementById('stability-range').textContent = '--';

    initStabilityPlots();
}

function onStabilityComplete(success, message) {
    state.stability.running = false;
    setStabilityTestState(false);

    if (success) {
        const count = state.stability.data.times.length;
        updateStabilityProgress(100, `Complete (${count} measurements)`);
    } else {
        updateStabilityProgress(0, message || 'Failed');
        if (message && message !== 'Stopped') {
            LabModals.showError('Test Failed', message);
        }
    }
}

function saveStabilityData() {
    const stats = state.stability.stats;
    const params = getStabilityParams();
    const isPower = state.stability.testType === 'power';
    const unit = isPower ? 'W' : 'A';
    const unitDisplay = isPower ? 'uW' : 'nA';
    const multiplier = isPower ? 1e6 : 1e9;

    let csv = `# Stability Test Results\n`;
    csv += `# Type: ${state.stability.testType}\n`;
    csv += `# Wavelength: ${params.wavelength} nm\n`;
    csv += `# Duration: ${params.duration} min\n`;
    csv += `# Interval: ${params.interval} sec\n`;
    if (stats) {
        csv += `# Mean: ${(stats.mean * multiplier).toFixed(6)} ${unitDisplay}\n`;
        csv += `# Std Dev: ${(stats.std * multiplier).toFixed(6)} ${unitDisplay}\n`;
        csv += `# CV: ${stats.cv_percent.toFixed(4)}%\n`;
        csv += `# Count: ${stats.count}\n`;
    }
    csv += `#\n`;
    csv += `Time (s),Value (${unit}),Value (${unitDisplay})\n`;

    for (let i = 0; i < state.stability.data.times.length; i++) {
        const t = state.stability.data.times[i];
        const v = state.stability.data.values[i];
        csv += `${t.toFixed(2)},${v.toExponential(6)},${(v * multiplier).toFixed(6)}\n`;
    }

    const api = LabAPI.get();
    if (api && api.save_stability_data) {
        api.save_stability_data(csv, params.wavelength, state.stability.testType, (result) => {
            const r = JSON.parse(result);
            if (r.success) console.log('Saved:', r.path);
            else if (r.message !== 'Cancelled') LabModals.showError('Save Failed', r.message);
        });
    }
}

function mockStabilityTest(params) {
    const intervalMs = params.interval * 1000;
    const durationMs = params.duration * 60 * 1000;
    const isPower = params.type === 'power';

    const baseValue = isPower ? 2.5e-6 : 1.8e-9;
    const noiseLevel = baseValue * 0.02;

    state.wavelength = params.wavelength;
    state.shutterOpen = true;
    updateMonochromatorDisplay();

    let elapsed = 0;

    const mockInterval = setInterval(() => {
        if (!state.stability.running || elapsed >= durationMs) {
            clearInterval(mockInterval);
            state.shutterOpen = false;
            updateMonochromatorDisplay();
            if (state.stability.running) {
                onStabilityComplete(true, 'Complete');
            }
            return;
        }

        elapsed += intervalMs;
        const timestamp = elapsed / 1000;
        const value = baseValue + (Math.random() - 0.5) * 2 * noiseLevel;

        onStabilityProgress(timestamp, value);
    }, intervalMs);
}

// ============================================
// EQE Analysis (Staff Mode)
// ============================================

function calculateJsc(eqeWavelengths, eqeValues) {
    let integral = 0;

    for (let i = 0; i < eqeWavelengths.length - 1; i++) {
        const wl1 = eqeWavelengths[i];
        const wl2 = eqeWavelengths[i + 1];
        const eqe1 = eqeValues[i] / 100;
        const eqe2 = eqeValues[i + 1] / 100;

        const phi1 = interpolate(AM15G_WAVELENGTHS, AM15G_PHOTON_FLUX, wl1);
        const phi2 = interpolate(AM15G_WAVELENGTHS, AM15G_PHOTON_FLUX, wl2);

        if (phi1 === null || phi2 === null) continue;

        const avgEQE = (eqe1 + eqe2) / 2;
        const avgPhi = (phi1 + phi2) / 2;
        const dLambda = wl2 - wl1;

        integral += avgEQE * avgPhi * dLambda;
    }

    const jscAm2 = ELECTRON_CHARGE * integral;
    const jscMaCm2 = jscAm2 * 0.1;

    return jscMaCm2;
}

function toggleAnalysisPanel() {
    state.analysis.visible = !state.analysis.visible;
    const tabBtn = document.getElementById('analysis-tab-btn');

    if (state.analysis.visible) {
        tabBtn.style.display = '';
        switchTab('analysis');
    } else {
        tabBtn.style.display = 'none';
        switchTab('measurement');
    }
}

function initEQEPlot() {
    const isDark = LabTheme.isDark();
    Plotly.newPlot('eqe-plot',
        [
            { x: [], y: [], mode: 'lines+markers', type: 'scatter', name: 'EQE',
              line: { color: PLOT_COLORS.power, width: 2 }, marker: { size: 6 } },
            { x: [], y: [], mode: 'lines', type: 'scatter', name: 'Peak',
              line: { color: PLOT_COLORS.phaseFit, dash: 'dash', width: 1 } }
        ],
        {
            ...getPlotLayout(isDark, 'Wavelength (nm)', 'EQE (%)'),
            yaxis: {
                ...getPlotLayout(isDark, '', '').yaxis,
                title: 'EQE (%)',
                range: [0, 100]
            }
        },
        plotConfig
    );
}

function updateSessionDataButton() {
    const hasPower = state.powerData.x.length > 0;
    const hasCurrent = state.currentData.x.length > 0;
    document.getElementById('use-power-session-btn').disabled = !hasPower;
    document.getElementById('use-current-session-btn').disabled = !hasCurrent;
}

function updateCalculateButton() {
    const hasPower = state.analysis.powerData !== null;
    const hasCurrent = state.analysis.currentData !== null;
    document.getElementById('calculate-eqe-btn').disabled = !(hasPower && hasCurrent);
}

function usePowerSession() {
    if (state.powerData.x.length === 0) {
        setAnalysisStatus('No power data in session', 'error');
        return;
    }

    state.analysis.powerData = {
        wavelengths: [...state.powerData.x],
        values: state.powerData.y.map(p => p * 1e-6)
    };

    document.getElementById('power-file-status').textContent = `Session (${state.powerData.x.length} pts)`;
    document.getElementById('power-file-status').classList.add('loaded');

    updateCalculateButton();
    setAnalysisStatus('Power data loaded from session');
}

function useCurrentSession() {
    if (state.currentData.x.length === 0) {
        setAnalysisStatus('No current data in session', 'error');
        return;
    }

    state.analysis.currentData = {
        wavelengths: [...state.currentData.x],
        values: state.currentData.y.map(c => c * 1e-9)
    };

    document.getElementById('current-file-status').textContent = `Session (${state.currentData.x.length} pts)`;
    document.getElementById('current-file-status').classList.add('loaded');

    updateCalculateButton();
    setAnalysisStatus('Current data loaded from session');
}

function loadPowerCSV() {
    const input = document.getElementById('power-file-input');
    input.value = '';
    input.click();
}

function loadCurrentCSV() {
    const input = document.getElementById('current-file-input');
    input.value = '';
    input.click();
}

function onPowerFileSelected(event) {
    const file = event.target.files[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (e) => {
        try {
            const data = parseCSV(e.target.result);
            state.analysis.powerData = data;
            state.analysis.powerFile = file.name;
            document.getElementById('power-file-status').textContent = file.name;
            document.getElementById('power-file-status').classList.add('loaded');
            updateCalculateButton();
            setAnalysisStatus(`Power data loaded (${data.wavelengths.length} points)`, 'success');
        } catch (err) {
            setAnalysisStatus('Failed to parse power CSV: ' + err.message, 'error');
        }
    };
    reader.readAsText(file);
}

function onCurrentFileSelected(event) {
    const file = event.target.files[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (e) => {
        try {
            const data = parseCSV(e.target.result);
            state.analysis.currentData = data;
            state.analysis.currentFile = file.name;

            const extracted = extractCellPixelFromFilename(file.name);
            state.analysis.cellNumber = extracted.cell;
            state.analysis.pixel = extracted.pixel;

            document.getElementById('current-file-status').textContent = file.name;
            document.getElementById('current-file-status').classList.add('loaded');
            updateCalculateButton();
            setAnalysisStatus(`Current data loaded (${data.wavelengths.length} points)`, 'success');
        } catch (err) {
            setAnalysisStatus('Failed to parse current CSV: ' + err.message, 'error');
        }
    };
    reader.readAsText(file);
}

function parseCSV(content) {
    const lines = content.trim().split('\n');
    const wavelengths = [];
    const values = [];

    for (let i = 0; i < lines.length; i++) {
        const line = lines[i].trim();
        if (!line || line.startsWith('#') || line.startsWith('Wavelength')) continue;

        const parts = line.split(',');
        if (parts.length >= 2) {
            const wl = parseFloat(parts[0]);
            const val = parseFloat(parts[1]);
            if (!isNaN(wl) && !isNaN(val)) {
                wavelengths.push(wl);
                values.push(val);
            }
        }
    }

    if (wavelengths.length === 0) {
        throw new Error('No valid data found');
    }

    return { wavelengths, values };
}

function calculateEQE() {
    const power = state.analysis.powerData;
    const current = state.analysis.currentData;

    if (!power || !current) {
        setAnalysisStatus('Missing power or current data', 'error');
        return;
    }

    try {
        const eqeWavelengths = [];
        const eqeValues = [];

        for (let i = 0; i < current.wavelengths.length; i++) {
            const wl = current.wavelengths[i];
            const I = current.values[i];

            const P = interpolate(power.wavelengths, power.values, wl);
            if (P === null || P <= 0) continue;

            const lambda_m = wl * 1e-9;
            const eqe = (Math.abs(I) * PLANCK * SPEED_OF_LIGHT) / (ELECTRON_CHARGE * P * lambda_m);
            const eqePercent = eqe * 100;

            if (eqePercent >= 0 && eqePercent <= 150) {
                eqeWavelengths.push(wl);
                eqeValues.push(eqePercent);
            }
        }

        if (eqeWavelengths.length === 0) {
            setAnalysisStatus('No valid EQE values calculated', 'error');
            return;
        }

        state.analysis.eqeData = { wavelengths: eqeWavelengths, eqe: eqeValues };

        const peakEQE = Math.max(...eqeValues);
        const peakIndex = eqeValues.indexOf(peakEQE);
        const peakWavelength = eqeWavelengths[peakIndex];

        const threshold = peakEQE * 0.5;
        let bandgapWavelength = null;
        for (let i = peakIndex; i < eqeWavelengths.length - 1; i++) {
            if (eqeValues[i] >= threshold && eqeValues[i + 1] < threshold) {
                const x1 = eqeWavelengths[i], x2 = eqeWavelengths[i + 1];
                const y1 = eqeValues[i], y2 = eqeValues[i + 1];
                bandgapWavelength = x1 + (threshold - y1) * (x2 - x1) / (y2 - y1);
                break;
            }
        }

        const jsc = calculateJsc(eqeWavelengths, eqeValues);

        state.analysis.metrics = {
            peakEQE: peakEQE,
            peakWavelength: peakWavelength,
            bandgapWavelength: bandgapWavelength,
            bandgapEV: bandgapWavelength ? 1240 / bandgapWavelength : null,
            integratedJsc: jsc,
            dataPoints: eqeWavelengths.length
        };

        updateEQEPlot();
        updateMetricsDisplay();

        setAnalysisStatus('EQE calculated successfully', 'success');
        document.getElementById('btn-save-analysis').disabled = false;

    } catch (err) {
        setAnalysisStatus('Calculation error: ' + err.message, 'error');
    }
}

function updateEQEPlot() {
    const isDark = LabTheme.isDark();
    const data = state.analysis.eqeData;
    const metrics = state.analysis.metrics;

    const peakX = data.wavelengths.length > 0 ?
        [data.wavelengths[0], data.wavelengths[data.wavelengths.length - 1]] : [];
    const peakY = metrics ? [metrics.peakEQE, metrics.peakEQE] : [];

    Plotly.react('eqe-plot',
        [
            { x: data.wavelengths, y: data.eqe, mode: 'lines+markers', type: 'scatter', name: 'EQE',
              line: { color: PLOT_COLORS.power, width: 2 }, marker: { size: 6 } },
            { x: peakX, y: peakY, mode: 'lines', type: 'scatter', name: `Peak: ${metrics?.peakEQE?.toFixed(1)}%`,
              line: { color: PLOT_COLORS.phaseFit, dash: 'dash', width: 1 } }
        ],
        {
            ...getPlotLayout(isDark, 'Wavelength (nm)', 'EQE (%)'),
            yaxis: {
                ...getPlotLayout(isDark, '', '').yaxis,
                title: 'EQE (%)',
                range: [0, Math.max(100, (metrics?.peakEQE || 0) * 1.1)]
            }
        },
        plotConfig
    );
}

function updateMetricsDisplay() {
    const m = state.analysis.metrics;
    if (!m) return;

    document.getElementById('metric-peak-eqe').textContent = m.peakEQE.toFixed(1) + '%';
    document.getElementById('metric-peak-wavelength').textContent = `at ${m.peakWavelength.toFixed(0)} nm`;

    if (m.bandgapWavelength) {
        document.getElementById('metric-bandgap').textContent = `~${m.bandgapWavelength.toFixed(0)} nm`;
        document.getElementById('metric-bandgap-ev').textContent = `(${m.bandgapEV.toFixed(2)} eV)`;
    } else {
        document.getElementById('metric-bandgap').textContent = 'N/A';
        document.getElementById('metric-bandgap-ev').textContent = '';
    }

    document.getElementById('metric-datapoints').textContent = m.dataPoints;

    if (m.integratedJsc !== null && m.integratedJsc !== undefined) {
        document.getElementById('metric-jsc').textContent = m.integratedJsc.toFixed(2) + ' mA/cm²';
    } else {
        document.getElementById('metric-jsc').textContent = 'N/A';
    }
}

function setAnalysisStatus(message, type) {
    const el = document.getElementById('analysis-status');
    el.textContent = message;
    el.className = 'progress-status analysis-status-text' + (type ? ' ' + type : '');
}

function saveAnalysisResults() {
    const data = state.analysis.eqeData;
    const m = state.analysis.metrics;
    if (!data || !m) return;

    let csv = '# EQE Analysis Results\n';
    const now = new Date();
    const localISO = `${now.getFullYear()}-${String(now.getMonth()+1).padStart(2,'0')}-${String(now.getDate()).padStart(2,'0')} ${String(now.getHours()).padStart(2,'0')}:${String(now.getMinutes()).padStart(2,'0')}:${String(now.getSeconds()).padStart(2,'0')}`;
    csv += `# Generated: ${localISO}\n`;
    if (state.analysis.cellNumber) csv += `# Cell: ${state.analysis.cellNumber}\n`;
    if (state.analysis.pixel) csv += `# Pixel: ${state.analysis.pixel}\n`;
    if (state.analysis.powerFile) csv += `# Power File: ${state.analysis.powerFile}\n`;
    if (state.analysis.currentFile) csv += `# Current File: ${state.analysis.currentFile}\n`;
    csv += '#\n';
    csv += `# Peak EQE: ${m.peakEQE.toFixed(2)}% at ${m.peakWavelength.toFixed(0)} nm\n`;
    if (m.bandgapWavelength) {
        csv += `# Bandgap Edge: ${m.bandgapWavelength.toFixed(0)} nm (${m.bandgapEV.toFixed(2)} eV)\n`;
    }
    csv += `# Integrated Jsc: ${m.integratedJsc.toFixed(2)} mA/cm^2 (AM1.5G)\n`;
    csv += `# Data Points: ${m.dataPoints}\n`;
    csv += '#\n';
    csv += 'Wavelength (nm),EQE (%)\n';

    for (let i = 0; i < data.wavelengths.length; i++) {
        csv += `${data.wavelengths[i]},${data.eqe[i].toFixed(4)}\n`;
    }

    const api = LabAPI.get();
    if (api && api.save_analysis_data) {
        api.save_analysis_data(csv, (result) => {
            const r = JSON.parse(result);
            if (r.success) {
                setAnalysisStatus('Results saved', 'success');
            } else if (r.message !== 'Cancelled') {
                setAnalysisStatus('Save failed: ' + r.message, 'error');
            }
        });
    }
}

// ============================================
// Console Panel
// ============================================

function toggleConsole() {
    consoleVisible = !consoleVisible;
    const panel = document.getElementById('console-panel');
    panel.classList.toggle('visible', consoleVisible);
}

function clearConsole() {
    consoleMessages.length = 0;
    const output = document.getElementById('console-output');
    output.innerHTML = '<div class="console-empty">Console cleared.</div>';
}

function copyConsole() {
    if (consoleMessages.length === 0) {
        return;
    }

    const text = consoleMessages.map(msg =>
        `${msg.time} [${msg.level.toUpperCase()}] ${msg.message}`
    ).join('\n');

    // Use fallback method for Qt WebEngine compatibility
    const textarea = document.createElement('textarea');
    textarea.value = text;
    textarea.style.position = 'fixed';
    textarea.style.opacity = '0';
    document.body.appendChild(textarea);
    textarea.select();

    try {
        document.execCommand('copy');
        // Brief visual feedback on the Copy button
        const btns = document.querySelectorAll('.console-actions .console-btn');
        const copyBtn = btns[0]; // Copy is the first button
        if (copyBtn) {
            const original = copyBtn.textContent;
            copyBtn.textContent = 'Copied!';
            setTimeout(() => { copyBtn.textContent = original; }, 1000);
        }
    } catch (err) {
        console.error('Failed to copy:', err);
    }

    document.body.removeChild(textarea);
}

// Console resize functionality
let isResizing = false;
let startY = 0;
let startHeight = 0;

function initConsoleResize() {
    const handle = document.getElementById('console-resize-handle');
    const panel = document.getElementById('console-panel');

    if (!handle || !panel) return;

    handle.addEventListener('mousedown', (e) => {
        isResizing = true;
        startY = e.clientY;
        startHeight = panel.offsetHeight;
        handle.classList.add('dragging');
        document.body.style.cursor = 'ns-resize';
        document.body.style.userSelect = 'none';
        e.preventDefault();
    });

    document.addEventListener('mousemove', (e) => {
        if (!isResizing) return;

        const deltaY = startY - e.clientY;
        const newHeight = Math.min(Math.max(100, startHeight + deltaY), window.innerHeight - 100);
        panel.style.height = newHeight + 'px';
    });

    document.addEventListener('mouseup', () => {
        if (isResizing) {
            isResizing = false;
            const handle = document.getElementById('console-resize-handle');
            if (handle) handle.classList.remove('dragging');
            document.body.style.cursor = '';
            document.body.style.userSelect = '';
        }
    });
}

// Initialize resize on DOMContentLoaded
document.addEventListener('DOMContentLoaded', initConsoleResize);

function addConsoleMessage(level, message) {
    const now = new Date();
    const time = now.toTimeString().split(' ')[0];

    consoleMessages.push({ time, level, message });
    if (consoleMessages.length > MAX_CONSOLE_MESSAGES) {
        consoleMessages.shift();
    }

    renderConsole();
}

function renderConsole() {
    const output = document.getElementById('console-output');
    if (consoleMessages.length === 0) {
        output.innerHTML = '<div class="console-empty">No log messages yet.</div>';
        return;
    }

    output.innerHTML = consoleMessages.map(msg => `
        <div class="console-line">
            <span class="console-time">${msg.time}</span>
            <span class="console-level ${msg.level}">${msg.level}</span>
            <span class="console-message">${escapeHtml(msg.message)}</span>
        </div>
    `).join('');

    output.scrollTop = output.scrollHeight;
}

function onLogMessage(level, message) {
    addConsoleMessage(level, message);
}

function toggleDebugMode() {
    const api = LabAPI.get();
    if (api && api.toggle_debug_mode) {
        api.toggle_debug_mode((result) => {
            const r = JSON.parse(result);
            state.debugMode = r.enabled;
            if (r.enabled) {
                addConsoleMessage('info', 'Print capture ENABLED');
                LabModals.showInfo('Print Capture ENABLED',
                    'print() statements are now visible in the terminal panel.\n\nThis captures debug output that normally only appears in the system console.\n\nPress Ctrl+Shift+D again to disable.');
            } else {
                addConsoleMessage('info', 'Print capture DISABLED');
                LabModals.showInfo('Print Capture DISABLED', 'Print statements no longer captured to terminal.');
            }
        });
    } else if (state.offlineMode) {
        state.debugMode = !state.debugMode;
        if (state.debugMode) {
            addConsoleMessage('info', 'Print capture ENABLED (offline - no effect)');
            LabModals.showInfo('Print Capture ENABLED', 'Offline mode - no print statements to capture.');
        } else {
            addConsoleMessage('info', 'Print capture DISABLED');
            LabModals.showInfo('Print Capture DISABLED', 'Print capture turned off.');
        }
    }
}

// ============================================
// Keyboard Shortcuts
// ============================================

document.addEventListener('keydown', (e) => {
    if (e.ctrlKey && e.shiftKey && e.key === 'T') {
        e.preventDefault();
        toggleConsole();
    }
    else if (e.ctrlKey && e.shiftKey && e.key === 'E') {
        e.preventDefault();
        toggleAnalysisPanel();
    }
    else if (e.ctrlKey && e.shiftKey && e.key === 'D') {
        e.preventDefault();
        toggleDebugMode();
    }
});

// ============================================
// Global Exports for Python WebChannel
// ============================================

window.onDeviceStatusChanged = onDeviceStatusChanged;
window.onMonochromatorStateChanged = onMonochromatorStateChanged;
window.onPowerProgress = onPowerProgress;
window.onCurrentProgress = onCurrentProgress;
window.onPhaseProgress = onPhaseProgress;
window.onPhaseAdjustmentComplete = onPhaseAdjustmentComplete;
window.onMeasurementComplete = onMeasurementComplete;
window.onMeasurementStats = onMeasurementStats;
window.onLiveSignalUpdate = onLiveSignalUpdate;
window.onStabilityProgress = onStabilityProgress;
window.onStabilityComplete = onStabilityComplete;
window.onLogMessage = onLogMessage;
window.showStartupCellModal = showStartupCellModal;

// Global exports for onclick handlers in HTML
window.switchTab = switchTab;
window.toggleTheme = () => LabTheme.toggle();
window.goToWavelength = goToWavelength;
window.toggleShutter = toggleShutter;
window.alignMonochromator = alignMonochromator;
window.startPowerMeasurement = startPowerMeasurement;
window.startCurrentMeasurement = startCurrentMeasurement;
window.stopMeasurement = stopMeasurement;
window.saveData = saveData;
window.toggleLiveMonitor = toggleLiveMonitor;
window.onStabilityTypeChange = onStabilityTypeChange;
window.startStabilityTest = startStabilityTest;
window.stopStabilityTest = stopStabilityTest;
window.saveStabilityData = saveStabilityData;
window.usePowerSession = usePowerSession;
window.useCurrentSession = useCurrentSession;
window.loadPowerCSV = loadPowerCSV;
window.loadCurrentCSV = loadCurrentCSV;
window.onPowerFileSelected = onPowerFileSelected;
window.onCurrentFileSelected = onCurrentFileSelected;
window.calculateEQE = calculateEQE;
window.saveAnalysisResults = saveAnalysisResults;
window.toggleConsole = toggleConsole;
window.clearConsole = clearConsole;
window.copyConsole = copyConsole;
