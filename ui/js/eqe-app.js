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

    powerData: { x: [], y: [], stats: [], colors: [], pendingQuality: null },
    currentData: { x: [], y: [], stats: [], colors: [], pendingQuality: null },
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
        powerData: null,      // { wavelengths: [], values: [], stats: [] }
        currentData: null,    // { wavelengths: [], values: [], stats: [] }
        eqeData: null,        // { wavelengths: [], eqe: [], uncertainty: [] }
        metrics: null,
        cellNumber: null,
        pixel: null,
        powerFile: null,
        currentFile: null,
        showErrorBars: true   // Toggle for error bar display
    },

    lockinlab: {
        numCycles: 10,
        noiseLevel: 30,
        phaseOffset: 0,
        // User-controlled signal parameters (for synthetic data)
        userAmplitude: 150,   // mV - what students set
        userDcOffset: 100,    // mV - what students set
        // Actual data properties
        rawSignal: [],
        rawReference: [],
        timeAxis: [],
        signalAmplitude: 0,   // Actual amplitude in data (V)
        dcOffset: 0,          // Actual DC offset in data (V)
        samplesPerCycle: 50,
        displayCycles: 15,
        hasData: false,
        useSimulated: false,
        isSynthetic: true,
        steps: {
            showRaw: true,
            removeDC: false,
            multiply: false,
            average: false
        }
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
    const defaults = LabConfig.get('defaults');
    const stability = LabConfig.get('stability');
    const validation = LabConfig.get('validation');

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

    // Cell input configuration from config
    const cellInput = validation.cell_input || {};
    const cellInputEl = document.getElementById('cell-input');
    const cellLabel = document.querySelector('label[for="cell-input"]');
    const cellError = document.getElementById('cell-input-error');
    if (cellInputEl && cellInput.pattern) {
        cellInputEl.pattern = cellInput.pattern;
        cellInputEl.placeholder = cellInput.placeholder;
    }
    if (cellLabel && cellInput.example) {
        cellLabel.textContent = `Cell Number (e.g., ${cellInput.example})`;
    }
    if (cellError && cellInput.error) {
        cellError.textContent = cellInput.error;
    }

    // Main form cell number input - set placeholder from config
    const cellNumberEl = document.getElementById('cell-number');
    const cellExample = cellInput.example;
    if (cellNumberEl) {
        cellNumberEl.placeholder = `e.g. ${cellExample}`;
    }

    // Pixel modal defaults
    const pixelInput = document.getElementById('pixel-input');
    const pixelLabel = document.querySelector('label[for="pixel-input"]');
    const pixelError = document.getElementById('pixel-input-error');
    if (pixelInput && validation.pixel_range) {
        pixelInput.min = validation.pixel_range[0];
        pixelInput.max = validation.pixel_range[1];
        pixelInput.value = validation.pixel_range[0];
        if (pixelLabel) {
            pixelLabel.textContent = `Pixel Number (${validation.pixel_range[0]}-${validation.pixel_range[1]})`;
        }
        if (pixelError) {
            pixelError.textContent = `Pixel must be between ${validation.pixel_range[0]} and ${validation.pixel_range[1]}`;
        }
    }

    // Lock-in Lab defaults and ranges from config
    const lockinlab = LabConfig.get('lockinlab');
    const lockinDefaults = lockinlab.defaults || {};
    const lockinRanges = lockinlab.ranges || {};

    // Update state with config defaults
    if (lockinDefaults.amplitude_mv !== undefined) state.lockinlab.userAmplitude = lockinDefaults.amplitude_mv;
    if (lockinDefaults.dcoffset_mv !== undefined) state.lockinlab.userDcOffset = lockinDefaults.dcoffset_mv;
    if (lockinDefaults.noise_percent !== undefined) state.lockinlab.noiseLevel = lockinDefaults.noise_percent;
    if (lockinDefaults.phase_offset !== undefined) state.lockinlab.phaseOffset = lockinDefaults.phase_offset;
    if (lockinDefaults.cycles !== undefined) state.lockinlab.numCycles = lockinDefaults.cycles;

    // Set slider ranges and values
    const ampSlider = document.getElementById('lockinlab-amplitude');
    const dcSlider = document.getElementById('lockinlab-dcoffset');
    const noiseSlider = document.getElementById('lockinlab-noise');
    const phaseSlider = document.getElementById('lockinlab-phase');
    const cyclesSlider = document.getElementById('lockinlab-cycles');

    if (ampSlider && lockinRanges.amplitude) {
        ampSlider.min = lockinRanges.amplitude[0];
        ampSlider.max = lockinRanges.amplitude[1];
        ampSlider.value = lockinDefaults.amplitude_mv;
        document.getElementById('lockinlab-amplitude-value').textContent = `${ampSlider.value} mV`;
    }
    if (dcSlider && lockinRanges.dcoffset) {
        dcSlider.min = lockinRanges.dcoffset[0];
        dcSlider.max = lockinRanges.dcoffset[1];
        dcSlider.value = lockinDefaults.dcoffset_mv;
        document.getElementById('lockinlab-dcoffset-value').textContent = `${dcSlider.value} mV`;
    }
    if (noiseSlider && lockinRanges.noise) {
        noiseSlider.min = lockinRanges.noise[0];
        noiseSlider.max = lockinRanges.noise[1];
        noiseSlider.value = lockinDefaults.noise_percent;
        document.getElementById('lockinlab-noise-value').textContent = `${noiseSlider.value}%`;
    }
    if (phaseSlider && lockinRanges.phase) {
        phaseSlider.min = lockinRanges.phase[0];
        phaseSlider.max = lockinRanges.phase[1];
        phaseSlider.value = lockinDefaults.phase_offset;
        document.getElementById('lockinlab-phase-value').textContent = `${phaseSlider.value}°`;
    }
    if (cyclesSlider && lockinRanges.cycles) {
        cyclesSlider.min = lockinRanges.cycles[0];
        cyclesSlider.max = lockinRanges.cycles[1];
        cyclesSlider.value = lockinDefaults.cycles;
        document.getElementById('lockinlab-cycles-value').textContent = cyclesSlider.value;
    }

    // Update chopper frequency label from config
    const chopperFreq = LabConfig.get('devices.picoscope_lockin.default_chopper_freq');
    const refLegend = document.querySelector('.legend-item.reference');
    if (refLegend) {
        refLegend.textContent = `Reference (${chopperFreq} Hz)`;
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

// Helper to get error messages from config
function getErrorMsg(key) {
    return LabConfig.get(`error_messages.${key}`);
}

function switchTab(tabName) {
    if (state.measurementState !== 'idle' && state.measurementState !== 'live_monitor') {
        LabModals.showError(getErrorMsg('cannot_switch_title'), getErrorMsg('cannot_switch_measurement'));
        return;
    }
    if (state.stability.running) {
        LabModals.showError(getErrorMsg('cannot_switch_title'), getErrorMsg('cannot_switch_stability'));
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
    } else if (tabName === 'lockinlab') {
        setTimeout(() => initLockinLabPlots(), 50);
    } else {
        setTimeout(() => {
            Plotly.Plots.resize('power-plot');
            Plotly.Plots.resize('current-plot');
        }, 50);
    }
}

// ============================================
// Plots
// ============================================

function attachPowerPlotHover() {
    const powerPlot = document.getElementById('power-plot');
    powerPlot.on('plotly_hover', function(data) {
        const pointIndex = data.points[0].pointIndex;
        if (state.powerData.stats && state.powerData.stats[pointIndex]) {
            displayPowerStats(state.powerData.stats[pointIndex]);
        }
    });
}

function attachCurrentPlotHover() {
    const currentPlot = document.getElementById('current-plot');
    currentPlot.on('plotly_hover', function(data) {
        const pointIndex = data.points[0].pointIndex;
        if (state.currentData.stats && state.currentData.stats[pointIndex]) {
            displayCurrentStats(state.currentData.stats[pointIndex]);
        }
    });
}

function initPlots() {
    const isDark = LabTheme.isDark();

    Plotly.newPlot('power-plot',
        [{ x: [], y: [], mode: 'markers', type: 'scatter', name: 'Power',
           marker: { color: PLOT_COLORS.power, size: 8 } }],
        getPlotLayout(isDark, 'Wavelength (nm)', 'Power (µW)'),
        plotConfig
    ).then(() => attachPowerPlotHover());

    Plotly.newPlot('current-plot',
        [{ x: [], y: [], mode: 'markers', type: 'scatter', name: 'Current',
           marker: { color: PLOT_COLORS.current, size: 8 } }],
        getPlotLayout(isDark, 'Wavelength (nm)', 'Current (nA)'),
        plotConfig
    ).then(() => attachCurrentPlotHover());
}

function displayPowerStats(stats) {
    document.getElementById('power-stats-n').textContent = stats.n;
    document.getElementById('power-stats-wavelength').textContent = `${stats.wavelength.toFixed(0)} nm`;
    const meanMicroWatts = stats.mean * 1e6;
    const sdMicroWatts = stats.std_dev * 1e6;
    document.getElementById('power-stats-mean').textContent = `${meanMicroWatts.toFixed(3)} µW`;
    document.getElementById('power-stats-std').textContent = `${sdMicroWatts.toFixed(3)} µW`;
    const badge = document.getElementById('power-stats-quality');
    badge.textContent = stats.quality;
    badge.className = 'quality-badge quality-' + stats.quality.toLowerCase();
}

function displayCurrentStats(stats) {
    document.getElementById('current-stats-n').textContent = stats.n;
    document.getElementById('current-stats-wavelength').textContent = `${stats.wavelength.toFixed(0)} nm`;
    const meanNanoamps = stats.mean * 1e9;
    const sdNanoamps = stats.std_dev * 1e9;
    document.getElementById('current-stats-mean').textContent = `${meanNanoamps.toFixed(2)} nA`;
    document.getElementById('current-stats-std').textContent = `${sdNanoamps.toFixed(2)} nA`;
    const badge = document.getElementById('current-stats-quality');
    badge.textContent = stats.quality;
    badge.className = 'quality-badge quality-' + stats.quality.toLowerCase();
}

window.addEventListener('resize', () => {
    if (typeof Plotly !== 'undefined') {
        const plotIds = [
            'power-plot', 'current-plot',
            'stability-time-plot', 'stability-hist-plot',
            'eqe-plot', 'lockinlab-plot'
        ];
        plotIds.forEach(id => {
            const el = document.getElementById(id);
            if (el && el.data) Plotly.Plots.resize(el);
        });
    }
});

window.addEventListener('themechange', (e) => {
    const isDark = e.detail.dark;
    const plotIds = [
        'power-plot', 'current-plot',
        'stability-time-plot', 'stability-hist-plot',
        'eqe-plot', 'lockinlab-plot'
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
    const wlRange = LabConfig.get('devices.monochromator.wavelength_range');
    if (isNaN(wavelength) || wavelength < wlRange[0] || wavelength > wlRange[1]) {
        LabModals.showError(getErrorMsg('invalid_wavelength_title'), getErrorMsg('invalid_wavelength_message').replace('{min}', wlRange[0]).replace('{max}', wlRange[1]));
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
            if (!r.success) LabModals.showError(getErrorMsg('error_title'), r.message);
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
            if (!r.success) LabModals.showError(getErrorMsg('error_title'), r.message);
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
    const cellPattern = new RegExp(LabConfig.get('validation.cell_number'));
    if (!cell || !cellPattern.test(cell)) {
        LabModals.showCell((cellNumber) => {
            document.getElementById('cell-number').value = cellNumber;
            state.cellNumber = cellNumber;
            startPowerMeasurement();
        });
        return;
    }

    state.measurementState = 'power';
    state.powerData = { x: [], y: [], stats: [], colors: [], pendingQuality: null };
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
                LabModals.showError(getErrorMsg('measurement_failed_title'), r.message);
                setMeasuringState(false);
            }
        });
    }
}

function startCurrentMeasurement() {
    const cell = document.getElementById('cell-number').value;
    const cellPattern = new RegExp(LabConfig.get('validation.cell_number'));
    if (!cell || !cellPattern.test(cell)) {
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
    state.measurementState = 'current';
    state.currentData = { x: [], y: [], stats: [], colors: [], pendingQuality: null };
    clearPlot('current');
    setMeasuringState(true);
    updateProgress(0, 'Validating chopper...');
    document.getElementById('pixel-label').textContent = 'Pixel: ' + pixel;

    if (state.offlineMode) {
        mockCurrentMeasurement(pixel);
        return;
    }

    const params = { ...getParams(), pixel };
    const api = LabAPI.get();
    if (api && api.start_current_measurement) {
        api.start_current_measurement(JSON.stringify(params), (result) => {
            const r = JSON.parse(result);
            if (!r.success) {
                LabModals.showError(getErrorMsg('measurement_failed_title'), r.message);
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
        // Stats persist after measurement - no reset needed
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

    // Determine point color from pending quality (stats arrive before progress)
    const qualityColorMap = {
        'Excellent': PLOT_COLORS.qualityExcellent,
        'Good': PLOT_COLORS.qualityGood,
        'Fair': PLOT_COLORS.qualityFair,
        'Check measurement': PLOT_COLORS.qualityPoor,
        'Check': PLOT_COLORS.qualityPoor
    };
    const pointColor = qualityColorMap[state.powerData.pendingQuality] || PLOT_COLORS.power;
    state.powerData.colors.push(pointColor);
    state.powerData.pendingQuality = null;

    const isDark = LabTheme.isDark();
    Plotly.newPlot('power-plot',
        [{ x: state.powerData.x, y: state.powerData.y, mode: 'markers', type: 'scatter',
           name: 'Power', marker: { color: state.powerData.colors, size: 8 } }],
        getPlotLayout(isDark, 'Wavelength (nm)', 'Power (µW)'),
        plotConfig
    ).then(() => attachPowerPlotHover());
    updateProgress(percent, `Measuring at ${wavelength.toFixed(0)} nm`);
}

function onCurrentProgress(wavelength, current, percent) {
    const currentNA = current * 1e9;
    state.currentData.x.push(wavelength);
    state.currentData.y.push(currentNA);

    // Determine point color from pending quality (stats arrive before progress in Python)
    // Maps quality strings from Python's tiered_logger.py
    const qualityColorMap = {
        'Excellent': PLOT_COLORS.qualityExcellent,
        'Good': PLOT_COLORS.qualityGood,
        'Fair': PLOT_COLORS.qualityFair,
        'Check measurement': PLOT_COLORS.qualityPoor,
        'Check': PLOT_COLORS.qualityPoor  // alias for mock mode
    };
    const pointColor = qualityColorMap[state.currentData.pendingQuality] || PLOT_COLORS.current;
    state.currentData.colors.push(pointColor);
    state.currentData.pendingQuality = null;  // Clear after use

    const isDark = LabTheme.isDark();
    Plotly.newPlot('current-plot',
        [{ x: state.currentData.x, y: state.currentData.y, mode: 'markers', type: 'scatter',
           name: 'Current', marker: { color: state.currentData.colors, size: 8 } }],
        getPlotLayout(isDark, 'Wavelength (nm)', 'Current (nA)'),
        plotConfig
    ).then(() => attachCurrentPlotHover());
    updateProgress(percent, `Measuring at ${wavelength.toFixed(0)} nm`);
}

function onPhaseProgress(phase, signal) {
    // Used by stability test phase adjustment - just update progress
    // (phase plot removed from Measurement tab)
    state.phaseData.x.push(phase);
    state.phaseData.y.push(signal);
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
            LabModals.showError(getErrorMsg('measurement_failed_title'), message);
        }
    }
}

function onMeasurementStats(stats) {
    state.stats = stats;

    const measurementType = stats.measurement_type || 'current';
    const wavelength = stats.wavelength_nm || state.wavelength;

    if (measurementType === 'power') {
        // Calculate quality from CV% (same thresholds as current)
        const cv = stats.cv_percent || ((stats.std_dev / stats.mean) * 100);
        const quality = stats.quality || (cv < 1.0 ? 'Excellent' : cv < 5.0 ? 'Good' : cv < 10.0 ? 'Fair' : 'Check');

        // Store stats for this wavelength (for hover interaction)
        if (!state.powerData.stats) state.powerData.stats = [];
        state.powerData.stats.push({
            wavelength: wavelength,
            mean: stats.mean,
            std_dev: stats.std_dev,
            n: stats.n,
            quality: quality
        });

        // Update power stats row - just show number of readings, not n/total
        document.getElementById('power-stats-n').textContent = stats.n;
        document.getElementById('power-stats-wavelength').textContent = `${wavelength.toFixed(0)} nm`;

        // Format power in µW
        const meanMicroWatts = stats.mean * 1e6;
        const sdMicroWatts = stats.std_dev * 1e6;
        document.getElementById('power-stats-mean').textContent = `${meanMicroWatts.toFixed(3)} µW`;
        document.getElementById('power-stats-std').textContent = `${sdMicroWatts.toFixed(3)} µW`;

        // Quality badge
        const badge = document.getElementById('power-stats-quality');
        badge.textContent = quality;
        badge.className = 'quality-badge quality-' + quality.toLowerCase();

        // Store quality for the upcoming data point (stats arrive before progress)
        // onPowerProgress will use this to set the point color
        state.powerData.pendingQuality = quality;

    } else {
        // Store stats for this wavelength (for hover interaction)
        state.currentData.stats.push({
            wavelength: wavelength,
            mean: stats.mean,
            std_dev: stats.std_dev,
            n: stats.n,
            quality: stats.quality
        });

        // Update current stats row - just show number of readings, not n/total
        document.getElementById('current-stats-n').textContent = stats.n;
        document.getElementById('current-stats-wavelength').textContent = `${wavelength.toFixed(0)} nm`;

        // Format current in nA
        const meanNanoamps = stats.mean * 1e9;
        const sdNanoamps = stats.std_dev * 1e9;
        document.getElementById('current-stats-mean').textContent = `${meanNanoamps.toFixed(2)} nA`;
        document.getElementById('current-stats-std').textContent = `${sdNanoamps.toFixed(2)} nA`;

        // Quality badge based on CV%
        const badge = document.getElementById('current-stats-quality');
        badge.textContent = stats.quality;
        badge.className = 'quality-badge quality-' + stats.quality.toLowerCase();

        // Store quality for the upcoming data point (stats arrive before progress in Python)
        // onCurrentProgress will use this to set the point color
        state.currentData.pendingQuality = stats.quality;
    }
}

function onPhaseAdjustmentComplete(data) {
    // Used by stability test phase adjustment - just update progress and store data
    // (phase plot removed from Measurement tab)
    state.phaseData.x = data.phase_data || [];
    state.phaseData.y = data.signal_data || [];
    updateProgress(0, `Phase: ${data.optimal_phase?.toFixed(1) || '--'}° (R² = ${data.r_squared?.toFixed(4) || '--'})`);
}

function clearPlot(type) {
    const isDark = LabTheme.isDark();
    if (type === 'power') {
        state.powerData.stats = [];
        Plotly.newPlot('power-plot',
            [{ x: [], y: [], mode: 'markers', type: 'scatter', name: 'Power',
               marker: { color: PLOT_COLORS.power, size: 8 } }],
            getPlotLayout(isDark, 'Wavelength (nm)', 'Power (µW)'),
            plotConfig
        ).then(() => attachPowerPlotHover());
        resetPowerStatsDisplay();
    } else if (type === 'current') {
        state.currentData.stats = [];
        Plotly.newPlot('current-plot',
            [{ x: [], y: [], mode: 'markers', type: 'scatter', name: 'Current',
               marker: { color: PLOT_COLORS.current, size: 8 } }],
            getPlotLayout(isDark, 'Wavelength (nm)', 'Current (nA)'),
            plotConfig
        ).then(() => attachCurrentPlotHover());
        resetCurrentStatsDisplay();
    }
}

function resetPowerStatsDisplay() {
    document.getElementById('power-stats-n').textContent = '--';
    document.getElementById('power-stats-wavelength').textContent = '--';
    document.getElementById('power-stats-mean').textContent = '--';
    document.getElementById('power-stats-std').textContent = '--';
    const badge = document.getElementById('power-stats-quality');
    badge.textContent = '--';
    badge.className = 'quality-badge';
}

function resetCurrentStatsDisplay() {
    document.getElementById('current-stats-n').textContent = '--';
    document.getElementById('current-stats-wavelength').textContent = '--';
    document.getElementById('current-stats-mean').textContent = '--';
    document.getElementById('current-stats-std').textContent = '--';
    const badge = document.getElementById('current-stats-quality');
    badge.textContent = '--';
    badge.className = 'quality-badge';
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
        LabModals.showError(getErrorMsg('no_data_title'), getErrorMsg('no_measurement_data'));
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
    // Get headers from config (single source of truth)
    // Use power_with_stats since we collect stats for each measurement
    const headers = LabConfig.get('export.headers.power_with_stats');
    let csv = headers.join(',') + '\n';
    for (let i = 0; i < state.powerData.x.length; i++) {
        const wavelength = state.powerData.x[i];
        const power = state.powerData.y[i];  // Already in µW
        const stats = state.powerData.stats[i] || {};
        // stats.std_dev is in Watts, convert to µW
        const std_dev = stats.std_dev !== undefined ? (stats.std_dev * 1e6).toFixed(3) : '0';
        const n = stats.n || 0;
        csv += `${wavelength.toFixed(1)},${power.toFixed(3)},${std_dev},${n}\n`;
    }
    const api = LabAPI.get();
    if (api && api.save_power_data) {
        api.save_power_data(csv, document.getElementById('cell-number').value, (result) => {
            const r = JSON.parse(result);
            if (r.success) console.log('Saved:', r.path);
            else if (r.message !== 'Cancelled') LabModals.showError(getErrorMsg('save_failed_title'), r.message);
        });
    }
}

function saveCurrentData() {
    // Get headers from config (single source of truth)
    // Use current_with_stats since offline mode generates mock stats
    const headers = LabConfig.get('export.headers.current_with_stats');
    let csv = headers.join(',') + '\n';
    for (let i = 0; i < state.currentData.x.length; i++) {
        const wavelength = state.currentData.x[i];
        const current = state.currentData.y[i];
        const stats = state.currentData.stats[i] || {};
        const std_dev = stats.std_dev !== undefined ? (stats.std_dev * 1e9).toFixed(2) : '0';
        const n = stats.n || 0;
        csv += `${wavelength.toFixed(1)},${current.toFixed(2)},${std_dev},${n}\n`;
    }
    const api = LabAPI.get();
    if (api && api.save_current_data) {
        api.save_current_data(csv, document.getElementById('cell-number').value, state.currentPixel, (result) => {
            const r = JSON.parse(result);
            if (r.success) console.log('Saved:', r.path);
            else if (r.message !== 'Cancelled') LabModals.showError(getErrorMsg('save_failed_title'), r.message);
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
        const std_dev = power * 0.02 * Math.random();  // ~2% noise for mock
        count++;

        state.wavelength = wavelength;
        updateMonochromatorDisplay();

        // Emit power stats before progress (mimics real behavior)
        // Shows readings per wavelength (200/200), not wavelength progress
        onMeasurementStats({
            mean: power,
            std_dev: std_dev,
            n: 200,
            total: 200,
            wavelength_nm: wavelength,
            cv_percent: (std_dev / power) * 100,
            quality: 'Good',
            measurement_type: 'power'
        });

        onPowerProgress(wavelength, power, (count / total) * 100);
        wavelength += step;
    }, 100);
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

        // Call stats first (stores pending quality - matches Python order)
        const cv = 0.5 + Math.random() * 11.5;  // 0.5-12% range covers all quality levels
        const std_dev = current * (cv / 100);
        const std_error = std_dev / Math.sqrt(5);  // SE = σ/√n
        const quality = cv < 1.0 ? 'Excellent' : cv < 5.0 ? 'Good' : cv < 10.0 ? 'Fair' : 'Check';
        onMeasurementStats({
            mean: current,
            std_dev: std_dev,
            std_error: std_error,
            n: 5, total: 5, outliers: 0,
            cv_percent: cv, quality: quality,
            wavelength_nm: wavelength,
            measurement_type: 'current'
        });

        // Then call progress (adds point with quality-based color)
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
    const wlRange = LabConfig.get('devices.monochromator.wavelength_range');
    if (isNaN(wavelength) || wavelength < wlRange[0] || wavelength > wlRange[1]) {
        LabModals.showError(getErrorMsg('invalid_wavelength_title'), getErrorMsg('invalid_wavelength_message').replace('{min}', wlRange[0]).replace('{max}', wlRange[1]));
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
                LabModals.showError(getErrorMsg('test_failed_title'), r.message);
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

    document.getElementById('stability-count').textContent = stats.count;
    document.getElementById('stability-range').textContent =
        (stats.min * multiplier).toFixed(3) + ' - ' + (stats.max * multiplier).toFixed(3) + unit;
}

function clearStabilityStats() {
    document.getElementById('stability-mean').textContent = '--';
    document.getElementById('stability-std').textContent = '--';
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
            LabModals.showError(getErrorMsg('test_failed_title'), message);
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
            else if (r.message !== 'Cancelled') LabModals.showError(getErrorMsg('save_failed_title'), r.message);
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
// Lock-in Lab (Deconstructed Algorithm)
// ============================================

const LOCKINLAB_EXPLANATIONS = {
    initial: '<p>Click <strong>Capture New Data</strong> to start, then enable each processing step to see how <strong>phase-sensitive detection</strong> (PSD) extracts your signal from noise.</p>' +
             '<p>This is the technique used in lock-in amplifiers: multiply by a reference, then average.</p>',

    raw: '<p>The <span style="color:#2196F3"><strong>blue trace</strong></span> is your photocurrent - it goes up when light hits the cell (chopper open) and down when blocked.</p>' +
         '<p>The <span style="color:#FF9800"><strong>orange trace</strong></span> is the reference from the chopper wheel at {chopper_freq} Hz. It\'s a square wave that switches between <strong>+1</strong> and <strong>-1</strong> (see right axis).</p>' +
         '<p>Notice the signal has a <strong>DC offset</strong> (not centered at zero) - we need to remove this first.</p>',

    removeDC: '<p>We <strong>subtract the mean</strong> to center the signal at zero.</p>' +
              '<p>This is different from the baseline DC offset - here we\'re ensuring the AC component oscillates symmetrically around zero.</p>' +
              '<p><strong>Why?</strong> Without centering, the product would have a large offset unrelated to our modulated signal.</p>',

    multiply: '<p>Now we <strong>multiply</strong> signal × reference (±1). This is the heart of <strong>phase-sensitive detection</strong>.</p>' +
              '<p>Since the reference is <strong>+1</strong> or <strong>-1</strong>, multiplying <em>preserves</em> the signal when ref=+1 and <em>inverts</em> it when ref=-1.</p>' +
              '<p>Look at the <span style="color:#4CAF50"><strong>green product trace</strong></span> - when signal and reference have the same sign, the product is <strong>positive</strong>. When in phase, the product stays mostly positive!</p>' +
              '<p><strong>Try it:</strong> Adjust the phase slider to see what happens when they are out of sync.</p>',

    average: '<p>Finally, we <strong>average over time</strong> to complete the phase-sensitive detection.</p>' +
             '<p>The <span style="color:#9C27B0"><strong>purple line</strong></span> shows the running average converging to your signal.</p>' +
             '<p>Noise at other frequencies produces positive and negative products that <strong>cancel out</strong>. Only signal at the reference frequency accumulates!</p>' +
             '<p><strong>Try it:</strong> Increase integration cycles to average longer and watch the result stabilize.</p>',

    liveMode: '<p>Now apply what you learned to <strong>real data</strong> from your solar cell.</p>' +
              '<p>Enable each processing step and observe how phase-sensitive detection extracts the signal from your actual measurement.</p>'
};

function initLockinLabPlots() {
    const isDark = LabTheme.isDark();

    // Initial empty plot with clean axes - no dual y-axis until data is captured
    const layout = {
        ...getBaseLayout(isDark),
        xaxis: {
            title: 'Cycles',
            gridcolor: isDark ? '#333' : '#eee',
            range: [0, 10]
        },
        yaxis: {
            title: 'Signal (V)',
            gridcolor: isDark ? '#333' : '#eee',
            range: [-0.5, 0.5]
        },
        showlegend: false,
        margin: { l: 60, r: 50, t: 20, b: 50 },
        annotations: [{
            text: 'Click "Capture New Data" to begin',
            xref: 'paper',
            yref: 'paper',
            x: 0.5,
            y: 0.5,
            showarrow: false,
            font: {
                size: 14,
                color: isDark ? '#888' : '#666'
            }
        }]
    };

    Plotly.newPlot('lockinlab-plot', [], layout, plotConfig);

    // Clear the legend initially
    updateLockinLegend([]);

    // Initialize toggle switches with click handlers
    initLockinToggles();

    // Initialize synthetic slider states (disabled by default since simulated is off)
    updateSyntheticSliderStates(state.lockinlab.useSimulated);
}

function initLockinToggles() {
    const toggles = document.querySelectorAll('.lockinlab-steps .toggle-switch');
    toggles.forEach(label => {
        const checkbox = label.querySelector('input[type="checkbox"]');
        const slider = label.querySelector('.toggle-slider');

        if (!checkbox || !slider) return;

        // Set initial state
        if (checkbox.checked) {
            slider.classList.add('active');
        }

        // Handle clicks on the slider
        slider.addEventListener('click', function(e) {
            e.preventDefault();
            e.stopPropagation();
            checkbox.checked = !checkbox.checked;
            slider.classList.toggle('active', checkbox.checked);
            onLockinStepChange();
        });

        // Handle clicks on the label text too
        const labelText = label.querySelector('.toggle-label');
        if (labelText) {
            labelText.addEventListener('click', function(e) {
                e.preventDefault();
                e.stopPropagation();
                checkbox.checked = !checkbox.checked;
                slider.classList.toggle('active', checkbox.checked);
                onLockinStepChange();
            });
        }
    });

    // Initialize the data source toggle separately
    const dataSourceToggle = document.querySelector('.data-source-toggle');
    if (dataSourceToggle) {
        const checkbox = dataSourceToggle.querySelector('input[type="checkbox"]');
        const slider = dataSourceToggle.querySelector('.toggle-slider');
        const labelText = dataSourceToggle.querySelector('.toggle-label');

        if (checkbox && slider) {
            // In offline mode, force simulated and disable toggle
            if (state.offlineMode) {
                checkbox.checked = true;
                checkbox.disabled = true;
                slider.classList.add('active');
                state.lockinlab.useSimulated = true;
            }

            slider.addEventListener('click', function(e) {
                if (state.offlineMode) return;  // Don't allow change in offline mode
                e.preventDefault();
                e.stopPropagation();
                checkbox.checked = !checkbox.checked;
                slider.classList.toggle('active', checkbox.checked);
                onLockinDataSourceChange();
            });

            if (labelText) {
                labelText.addEventListener('click', function(e) {
                    if (state.offlineMode) return;
                    e.preventDefault();
                    e.stopPropagation();
                    checkbox.checked = !checkbox.checked;
                    slider.classList.toggle('active', checkbox.checked);
                    onLockinDataSourceChange();
                });
            }
        }
    }
}

async function captureLockinData() {
    const btn = document.getElementById('lockinlab-capture-btn');
    if (!btn) return;

    btn.disabled = true;
    btn.textContent = 'Capturing...';

    try {
        // Use simulated data if: offline mode OR user toggled "Use Simulated Data"
        if (state.offlineMode || state.lockinlab.useSimulated) {
            generateSyntheticLockinData();
        } else {
            await fetchRealLockinData();
        }

        applyLockinProcessingSteps();
        updateLockinExplanation();
        updateExpectedValue();
    } catch (e) {
        console.error('Failed to capture lock-in data:', e);
    } finally {
        btn.disabled = false;
        btn.textContent = 'Capture New Data';
    }
}

/**
 * Shift a waveform by a phase offset using linear interpolation.
 * This preserves the actual waveform shape (important for real PicoScope data).
 *
 * @param {number[]} waveform - The waveform to shift
 * @param {number} phaseDegrees - Phase offset in degrees
 * @param {number} samplesPerCycle - Number of samples per cycle
 * @returns {number[]} - Shifted waveform
 */
function shiftWaveformByPhase(waveform, phaseDegrees, samplesPerCycle) {
    const n = waveform.length;
    if (n === 0 || phaseDegrees === 0) return [...waveform];

    // Convert phase to fractional samples
    const phaseShift = (phaseDegrees / 360) * samplesPerCycle;

    // Use linear interpolation for sub-sample accuracy
    const shifted = [];
    for (let i = 0; i < n; i++) {
        // Calculate source position (with wraparound)
        let srcPos = i - phaseShift;
        while (srcPos < 0) srcPos += n;
        while (srcPos >= n) srcPos -= n;

        // Linear interpolation between adjacent samples
        const idx0 = Math.floor(srcPos);
        const idx1 = (idx0 + 1) % n;
        const frac = srcPos - idx0;

        shifted.push(waveform[idx0] * (1 - frac) + waveform[idx1] * frac);
    }

    return shifted;
}

function generateSyntheticLockinData() {
    const chopperFreq = 81;
    const maxCycles = 200;  // Always generate 200 cycles of data
    const samplesPerCycle = 50;  // 50 samples per chopper cycle for smooth waveforms
    const numSamples = maxCycles * samplesPerCycle;  // 10000 samples total
    const duration = maxCycles / chopperFreq;  // About 2.5 seconds

    // Use student-controlled values (convert mV to V)
    const signalAmplitude = state.lockinlab.userAmplitude / 1000;  // mV to V
    const dcOffset = state.lockinlab.userDcOffset / 1000;          // mV to V

    const time = [];
    const signal = [];
    const reference = [];

    for (let i = 0; i < numSamples; i++) {
        const t = i * duration / numSamples;
        time.push(t * 1000); // Convert to ms

        // Reference: square wave at chopper frequency (+1 when open, -1 when closed)
        // Add tiny offset to avoid sampling exactly at zero crossings where Math.sign(0)=0
        const phase = 2 * Math.PI * chopperFreq * t + 0.0001;
        const refValue = Math.sign(Math.sin(phase));
        reference.push(refValue);

        // Signal: photocurrent that's LOW when chopper blocks light, HIGH when open
        // Physically realistic: signal is always positive (dcOffset to dcOffset + amplitude)
        const squareComponent = Math.sign(Math.sin(phase));

        const cleanSignal = dcOffset + signalAmplitude * (squareComponent + 1) / 2;
        signal.push(cleanSignal);
    }

    state.lockinlab.rawSignal = signal;
    state.lockinlab.rawReference = reference;
    state.lockinlab.timeAxis = time;
    state.lockinlab.signalAmplitude = signalAmplitude;
    state.lockinlab.dcOffset = dcOffset;
    state.lockinlab.samplesPerCycle = samplesPerCycle;
    state.lockinlab.isSynthetic = true;  // Flag for phase offset handling
    state.lockinlab.hasData = true;

    // Generate and store noise array (values between -1 and 1)
    // This is scaled by noise level slider when applied
    const noiseArray = [];
    for (let i = 0; i < numSamples; i++) {
        noiseArray.push((Math.random() - 0.5) * 2);
    }
    state.lockinlab.noiseArray = noiseArray;

    // Calculate fixed y-axis range that works for both raw and DC-removed views
    // Raw signal formula: dcOffset + signalAmplitude * (smoothed+1)/2
    //   → range is [dcOffset, dcOffset + signalAmplitude] = [0.15, 0.45]
    // DC-removed: centered at 0, so roughly ±signalAmplitude/2
    // Need symmetric range around zero that fits both
    const rawMax = dcOffset + signalAmplitude;  // 0.45
    const rawMin = dcOffset;                     // 0.15
    const maxExtent = Math.max(Math.abs(rawMax), Math.abs(rawMin));
    const yMax = maxExtent * 1.3;  // 30% padding for noise headroom
    state.lockinlab.yAxisRange = [-yMax, yMax];
}

async function fetchRealLockinData() {
    const api = LabAPI.get();
    if (!api) {
        generateSyntheticLockinData();
        return;
    }

    try {
        // Capture enough cycles to support full slider range (max 50)
        const response = await api.lockinlab_measure(50);
        const result = JSON.parse(response);
        if (result.success && result.signal_waveform) {
            state.lockinlab.rawSignal = result.signal_waveform;
            state.lockinlab.rawReference = result.reference_waveform;
            state.lockinlab.timeAxis = result.time_axis;
            state.lockinlab.signalAmplitude = result.R;
            state.lockinlab.isSynthetic = false;  // Real data - use interpolation for phase
            state.lockinlab.hasData = true;

            // Estimate samples per cycle from time axis and chopper frequency
            const duration = result.time_axis[result.time_axis.length - 1] / 1000;  // ms to seconds
            const numSamples = result.signal_waveform.length;
            const chopperFreq = result.freq || getChopperFreq();
            state.lockinlab.samplesPerCycle = numSamples / (duration * chopperFreq);

            // Generate and store noise array for real data too
            const noiseArray = [];
            for (let i = 0; i < numSamples; i++) {
                noiseArray.push((Math.random() - 0.5) * 2);
            }
            state.lockinlab.noiseArray = noiseArray;

            // Calculate fixed y-axis range from actual signal data
            // Must accommodate both raw signal (with DC offset) and DC-removed signal
            const signalMax = Math.max(...result.signal_waveform);
            const signalMin = Math.min(...result.signal_waveform);
            const maxExtent = Math.max(Math.abs(signalMax), Math.abs(signalMin));
            const yMax = maxExtent * 1.3;  // 30% padding for noise headroom
            state.lockinlab.yAxisRange = [-yMax, yMax];
        } else {
            generateSyntheticLockinData();
        }
    } catch (e) {
        console.error('Failed to fetch real data:', e);
        generateSyntheticLockinData();
    }
}

function onLockinParamChange() {
    // Update slider displays
    const noiseSlider = document.getElementById('lockinlab-noise');
    const phaseSlider = document.getElementById('lockinlab-phase');
    const cyclesSlider = document.getElementById('lockinlab-cycles');

    document.getElementById('lockinlab-noise-value').textContent = `${noiseSlider.value}%`;
    document.getElementById('lockinlab-phase-value').textContent = `${phaseSlider.value}°`;
    document.getElementById('lockinlab-cycles-value').textContent = cyclesSlider.value;

    state.lockinlab.noiseLevel = parseInt(noiseSlider.value);
    state.lockinlab.phaseOffset = parseInt(phaseSlider.value);
    state.lockinlab.numCycles = parseInt(cyclesSlider.value);

    // Reapply processing if we have data
    if (state.lockinlab.hasData) {
        applyLockinProcessingSteps();
    }
}

function onLockinSignalParamChange() {
    // Update slider displays for signal parameters
    const ampSlider = document.getElementById('lockinlab-amplitude');
    const dcSlider = document.getElementById('lockinlab-dcoffset');

    document.getElementById('lockinlab-amplitude-value').textContent = `${ampSlider.value} mV`;
    document.getElementById('lockinlab-dcoffset-value').textContent = `${dcSlider.value} mV`;

    state.lockinlab.userAmplitude = parseInt(ampSlider.value);
    state.lockinlab.userDcOffset = parseInt(dcSlider.value);

    // Update expected value display
    updateExpectedValue();

    // Regenerate synthetic data if using simulated mode
    if (state.lockinlab.isSynthetic && state.lockinlab.hasData) {
        generateSyntheticLockinData();
        applyLockinProcessingSteps();
    }
}

function updateExpectedValue() {
    // Signal goes from dcOffset (blocked) to dcOffset + modulation (open)
    // After DC removal: ±modulation/2
    // Lock-in output = modulation/2 = AC amplitude
    const expectedEl = document.getElementById('lockinlab-expected');
    if (expectedEl) {
        if (state.lockinlab.isSynthetic) {
            const acAmplitude = state.lockinlab.userAmplitude / 2;
            expectedEl.textContent = `${acAmplitude.toFixed(1)} mV`;
        } else {
            // For real data, we don't know the expected value
            expectedEl.textContent = '-- mV';
        }
    }
}

function onLockinDataSourceChange() {
    const useSimulated = document.getElementById('lockinlab-simulated').checked;
    state.lockinlab.useSimulated = useSimulated;

    // Update toggle visual state
    const toggle = document.querySelector('.data-source-toggle .toggle-slider');
    if (toggle) {
        toggle.classList.toggle('active', useSimulated);
    }

    // Enable/disable synthetic-only sliders (modulation, DC offset, noise)
    // These only apply to simulated data - real data shows what we captured
    updateSyntheticSliderStates(useSimulated);

    // If we have data, recapture with new source
    if (state.lockinlab.hasData) {
        captureLockinData();
    }
}

function updateSyntheticSliderStates(enabled) {
    const syntheticSliders = ['lockinlab-amplitude', 'lockinlab-dcoffset', 'lockinlab-noise'];
    syntheticSliders.forEach(id => {
        const slider = document.getElementById(id);
        if (slider) {
            slider.disabled = !enabled;
            // Also dim the label
            const field = slider.closest('.param-field');
            if (field) {
                field.classList.toggle('disabled', !enabled);
            }
        }
    });
}

function onLockinStepChange() {
    state.lockinlab.steps.showRaw = document.getElementById('step-raw').checked;
    state.lockinlab.steps.removeDC = document.getElementById('step-removedc').checked;
    state.lockinlab.steps.multiply = document.getElementById('step-multiply').checked;
    state.lockinlab.steps.average = document.getElementById('step-average').checked;

    if (state.lockinlab.hasData) {
        applyLockinProcessingSteps();
    }

    updateLockinExplanation();
}

function applyLockinProcessingSteps() {
    if (!state.lockinlab.hasData) return;

    const rawSignal = state.lockinlab.rawSignal;
    const rawReference = state.lockinlab.rawReference;
    const time = state.lockinlab.timeAxis;

    // Display based on numCycles setting - show what we're averaging over
    const samplesPerCycle = state.lockinlab.samplesPerCycle || 50;
    const numCycles = state.lockinlab.numCycles;
    const displaySamples = Math.min(numCycles * samplesPerCycle, rawSignal.length);

    // Create cycle-based X axis (shows cycles, not time)
    const cycleAxis = [];
    for (let i = 0; i < displaySamples; i++) {
        cycleAxis.push(i / samplesPerCycle);  // X-axis in cycles
    }

    // Apply stored noise to signal (noise array generated once at capture time)
    const noiseLevel = state.lockinlab.noiseLevel / 100;
    const signalRange = Math.max(...rawSignal) - Math.min(...rawSignal);
    const noiseArray = state.lockinlab.noiseArray || [];
    const signalWithNoise = rawSignal.map((v, i) => v + noiseArray[i] * noiseLevel * signalRange);

    // Apply phase offset to reference
    const phaseOffset = state.lockinlab.phaseOffset;
    let reference;

    if (state.lockinlab.isSynthetic) {
        // For synthetic data: regenerate square wave with phase offset
        // This gives smooth phase control instead of discrete steps
        // Add tiny offset (0.0001) to avoid sampling at zero crossings where Math.sign(0)=0
        const phaseRad = phaseOffset * Math.PI / 180;
        reference = [];
        for (let i = 0; i < rawReference.length; i++) {
            const cyclePhase = (i / samplesPerCycle) * 2 * Math.PI + 0.0001;
            reference.push(Math.sign(Math.sin(cyclePhase + phaseRad)));
        }
    } else {
        // For real data: shift waveform using linear interpolation
        // This preserves the actual reference shape from the PicoScope
        reference = shiftWaveformByPhase(rawReference, phaseOffset, samplesPerCycle);
    }

    const traces = [];
    const isDark = LabTheme.isDark();
    const legendItems = [];

    // Determine which signal to use based on DC removal step
    let signal = signalWithNoise.slice(0, displaySamples);
    let signalForDisplay = signal;

    // Step 2: Subtract mean to center signal at zero
    if (state.lockinlab.steps.removeDC) {
        const mean = signal.reduce((a, b) => a + b, 0) / signal.length;
        signal = signal.map(v => v - mean);
        signalForDisplay = signal;
    }

    // Step 1: Show raw signals (or DC-removed if that step is enabled)
    if (state.lockinlab.steps.showRaw) {
        traces.push({
            x: cycleAxis,
            y: signalForDisplay,
            mode: 'lines',
            name: 'Signal',
            line: { color: '#2196F3', width: 1.5 },
            yaxis: 'y'
        });
        // Reference on secondary y-axis at true ±1 scale
        traces.push({
            x: cycleAxis,
            y: reference.slice(0, displaySamples),
            mode: 'lines',
            name: 'Reference (±1)',
            line: { color: '#FF9800', width: 1.5 },
            yaxis: 'y2'
        });
        legendItems.push('signal', 'reference');
    }

    // Step 3: Multiply signal × reference
    let product = [];
    if (state.lockinlab.steps.multiply) {
        product = signal.map((s, i) => s * reference.slice(0, displaySamples)[i]);
        traces.push({
            x: cycleAxis,
            y: product,
            mode: 'lines',
            name: 'Product',
            line: { color: '#4CAF50', width: 1.5 }
        });
        legendItems.push('product');
    }

    // Step 4: Average - averages whatever the current pipeline produces
    // This is "live" - if multiply is off, it averages the signal directly
    let finalResult = 0;
    if (state.lockinlab.steps.average) {
        // Determine what to average based on pipeline state
        const dataToAverage = state.lockinlab.steps.multiply ? product : signal;

        if (dataToAverage.length > 0) {
            // Compute running average
            const runningAvg = [];
            let sum = 0;

            for (let i = 0; i < dataToAverage.length; i++) {
                sum += dataToAverage[i];
                runningAvg.push(sum / (i + 1));
            }

            finalResult = runningAvg[runningAvg.length - 1];

            traces.push({
                x: cycleAxis,
                y: runningAvg,
                mode: 'lines',
                name: 'Average',
                line: { color: '#9C27B0', width: 2.5 }
            });
            legendItems.push('average');
        }
    }

    // Update plot with dual y-axes and fixed range
    const yRange = state.lockinlab.yAxisRange || [-0.2, 0.2];
    const layout = {
        ...getBaseLayout(isDark),
        xaxis: {
            title: 'Cycles',
            gridcolor: isDark ? '#333' : '#eee'
        },
        yaxis: {
            title: 'Signal (V)',
            gridcolor: isDark ? '#333' : '#eee',
            range: yRange,  // Fixed range based on captured data
            fixedrange: false
        },
        yaxis2: {
            title: 'Reference',
            overlaying: 'y',
            side: 'right',
            range: [-1.3, 1.3],  // Fixed ±1 range with padding
            gridcolor: 'transparent',
            showgrid: false,
            tickvals: [-1, 0, 1],
            ticktext: ['-1', '0', '+1'],
            titlefont: { color: '#FF9800' },
            tickfont: { color: '#FF9800' }
        },
        showlegend: false,
        margin: { l: 60, r: 50, t: 20, b: 50 },
        annotations: []  // Clear placeholder text
    };

    Plotly.react('lockinlab-plot', traces, layout, plotConfig);

    // Update legend
    updateLockinLegend(legendItems);

    // Update result display
    if (state.lockinlab.steps.average) {
        document.getElementById('lockinlab-result').textContent = `${(finalResult * 1000).toFixed(2)} mV`;
    } else {
        document.getElementById('lockinlab-result').textContent = '-- mV';
    }
}

function updateLockinLegend(items) {
    const legend = document.getElementById('lockinlab-legend');
    const chopperFreq = getChopperFreq();
    legend.innerHTML = items.map(item => {
        const labels = {
            signal: 'Signal',
            reference: `Reference (${chopperFreq} Hz)`,
            product: 'Product (signal × ref)',
            average: 'Running Average'
        };
        return `<span class="legend-item ${item}">${labels[item]}</span>`;
    }).join('');
}

function getChopperFreq() {
    return LabConfig.get('devices.picoscope_lockin.default_chopper_freq');
}

function applyConfigPlaceholders(text) {
    return text.replace(/{chopper_freq}/g, getChopperFreq());
}

function updateLockinExplanation() {
    const textEl = document.getElementById('lockinlab-explanation-text');
    const panel = document.querySelector('.lockinlab-explanation');

    // In live mode, show static message and dim the panel
    const isLiveMode = state.lockinlab.hasData && !state.lockinlab.isSynthetic;
    if (panel) {
        panel.classList.toggle('live-mode', isLiveMode);
    }

    if (isLiveMode) {
        textEl.innerHTML = applyConfigPlaceholders(LOCKINLAB_EXPLANATIONS.liveMode);
        return;
    }

    if (!state.lockinlab.hasData) {
        textEl.innerHTML = applyConfigPlaceholders(LOCKINLAB_EXPLANATIONS.initial);
        return;
    }

    // Show explanation for highest enabled step (simulated mode only)
    if (state.lockinlab.steps.average) {
        textEl.innerHTML = applyConfigPlaceholders(LOCKINLAB_EXPLANATIONS.average);
    } else if (state.lockinlab.steps.multiply) {
        textEl.innerHTML = applyConfigPlaceholders(LOCKINLAB_EXPLANATIONS.multiply);
    } else if (state.lockinlab.steps.removeDC) {
        textEl.innerHTML = applyConfigPlaceholders(LOCKINLAB_EXPLANATIONS.removeDC);
    } else if (state.lockinlab.steps.showRaw) {
        textEl.innerHTML = applyConfigPlaceholders(LOCKINLAB_EXPLANATIONS.raw);
    } else {
        textEl.innerHTML = applyConfigPlaceholders(LOCKINLAB_EXPLANATIONS.initial);
    }
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

    // Convert µW to W for EQE calculation, include stats for uncertainty
    const stats = state.powerData.stats.map(s => ({
        std_dev: s.std_dev * 1e-6,  // µW to W
        n: s.n
    }));

    state.analysis.powerData = {
        wavelengths: [...state.powerData.x],
        values: state.powerData.y.map(p => p * 1e-6),  // µW to W
        stats: stats
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

    // Convert nA to A for EQE calculation, include stats for uncertainty
    const stats = state.currentData.stats.map(s => ({
        std_dev: s.std_dev * 1e-9,  // nA to A
        n: s.n
    }));

    state.analysis.currentData = {
        wavelengths: [...state.currentData.x],
        values: state.currentData.y.map(c => c * 1e-9),  // nA to A
        stats: stats
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
            // CSV stores power in µW, but EQE calculation expects Watts (SI units)
            // Convert µW to W, and stats if available
            const stats = data.stats ? data.stats.map(s => s ? {
                std_dev: s.std_dev * 1e-6,  // µW to W
                n: s.n
            } : null) : null;

            state.analysis.powerData = {
                wavelengths: data.wavelengths,
                values: data.values.map(v => v * 1e-6),
                stats: stats
            };
            state.analysis.powerFile = file.name;
            document.getElementById('power-file-status').textContent = file.name;
            document.getElementById('power-file-status').classList.add('loaded');
            updateCalculateButton();
            const statsMsg = stats ? ' (with uncertainty)' : '';
            setAnalysisStatus(`Power data loaded (${data.wavelengths.length} points${statsMsg})`, 'success');
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
            // CSV stores current in nA, but EQE calculation expects Amps (SI units)
            // Convert nA to A, and stats if available
            const stats = data.stats ? data.stats.map(s => s ? {
                std_dev: s.std_dev * 1e-9,  // nA to A
                n: s.n
            } : null) : null;

            state.analysis.currentData = {
                wavelengths: data.wavelengths,
                values: data.values.map(v => v * 1e-9),
                stats: stats
            };
            state.analysis.currentFile = file.name;

            const extracted = extractCellPixelFromFilename(file.name);
            state.analysis.cellNumber = extracted.cell;
            state.analysis.pixel = extracted.pixel;

            document.getElementById('current-file-status').textContent = file.name;
            document.getElementById('current-file-status').classList.add('loaded');
            updateCalculateButton();
            const statsMsg = stats ? ' (with uncertainty)' : '';
            setAnalysisStatus(`Current data loaded (${data.wavelengths.length} points${statsMsg})`, 'success');
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
    const stats = [];
    let hasStats = false;

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

                // Check for stats columns (std_dev, n)
                if (parts.length >= 4) {
                    const std_dev = parseFloat(parts[2]);
                    const n = parseInt(parts[3], 10);
                    if (!isNaN(std_dev) && !isNaN(n)) {
                        stats.push({ std_dev, n });
                        hasStats = true;
                    } else {
                        stats.push(null);
                    }
                } else {
                    stats.push(null);
                }
            }
        }
    }

    if (wavelengths.length === 0) {
        throw new Error('No valid data found');
    }

    return { wavelengths, values, stats: hasStats ? stats : null };
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
        const eqeUncertainty = [];

        // Check if we have stats for uncertainty calculation
        const hasCurrentStats = current.stats && current.stats.length === current.values.length;
        const hasPowerStats = power.stats && power.stats.length === power.values.length;
        const canCalculateUncertainty = hasCurrentStats && hasPowerStats;

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

                // Calculate propagated uncertainty if stats are available
                if (canCalculateUncertainty) {
                    const currentStat = current.stats[i];
                    const powerStat = interpolateStats(power.wavelengths, power.stats, wl);

                    if (currentStat && powerStat && currentStat.n > 1 && powerStat.n > 1) {
                        // Standard error = std_dev / sqrt(n)
                        const se_I = currentStat.std_dev / Math.sqrt(currentStat.n);
                        const se_P = powerStat.std_dev / Math.sqrt(powerStat.n);

                        // Relative uncertainties
                        const rel_I = se_I / Math.abs(I);
                        const rel_P = se_P / P;

                        // Propagated relative uncertainty: δEQE/EQE = sqrt[(δI/I)² + (δP/P)²]
                        const rel_EQE = Math.sqrt(rel_I * rel_I + rel_P * rel_P);

                        // Absolute uncertainty in EQE (%)
                        const uncertaintyPercent = eqePercent * rel_EQE;
                        eqeUncertainty.push(uncertaintyPercent);
                    } else {
                        eqeUncertainty.push(null);
                    }
                } else {
                    eqeUncertainty.push(null);
                }
            }
        }

        if (eqeWavelengths.length === 0) {
            setAnalysisStatus('No valid EQE values calculated', 'error');
            return;
        }

        state.analysis.eqeData = {
            wavelengths: eqeWavelengths,
            eqe: eqeValues,
            uncertainty: canCalculateUncertainty ? eqeUncertainty : null
        };

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

        const hasValidUncertainty = eqeUncertainty.some(u => u !== null);
        const uncertaintyMsg = hasValidUncertainty ? ' with uncertainty' : '';
        setAnalysisStatus(`EQE calculated successfully${uncertaintyMsg}`, 'success');
        document.getElementById('btn-save-analysis').disabled = false;

    } catch (err) {
        setAnalysisStatus('Calculation error: ' + err.message, 'error');
    }
}

// Interpolate stats at a given wavelength
function interpolateStats(xArray, statsArray, x) {
    if (!statsArray || statsArray.length === 0) return null;

    // Find surrounding points
    for (let i = 0; i < xArray.length - 1; i++) {
        if (xArray[i] <= x && xArray[i + 1] >= x) {
            const stat1 = statsArray[i];
            const stat2 = statsArray[i + 1];

            if (!stat1 || !stat2) return null;

            // Linear interpolation factor
            const t = (x - xArray[i]) / (xArray[i + 1] - xArray[i]);

            // Interpolate std_dev and use average n
            return {
                std_dev: stat1.std_dev + t * (stat2.std_dev - stat1.std_dev),
                n: Math.round((stat1.n + stat2.n) / 2)
            };
        }
    }

    // Check exact match at boundaries
    const firstIdx = xArray.indexOf(x);
    if (firstIdx !== -1 && statsArray[firstIdx]) {
        return statsArray[firstIdx];
    }

    return null;
}

function updateEQEPlot() {
    const isDark = LabTheme.isDark();
    const data = state.analysis.eqeData;
    const metrics = state.analysis.metrics;

    const peakX = data.wavelengths.length > 0 ?
        [data.wavelengths[0], data.wavelengths[data.wavelengths.length - 1]] : [];
    const peakY = metrics ? [metrics.peakEQE, metrics.peakEQE] : [];

    // Check if we have uncertainty data and error bars are enabled
    const hasUncertainty = data.uncertainty && data.uncertainty.some(u => u !== null);
    const showErrorBars = hasUncertainty && state.analysis.showErrorBars;

    // Show/hide error bar toggle based on uncertainty data availability
    const toggleContainer = document.getElementById('error-bar-toggle-container');
    if (toggleContainer) {
        toggleContainer.style.display = hasUncertainty ? 'flex' : 'none';
    }

    // Build the EQE trace with optional error bars
    const eqeTrace = {
        x: data.wavelengths,
        y: data.eqe,
        mode: 'lines+markers',
        type: 'scatter',
        name: 'EQE',
        line: { color: PLOT_COLORS.power, width: 2 },
        marker: { size: 6 }
    };

    // Add error bars if available and enabled
    if (showErrorBars) {
        eqeTrace.error_y = {
            type: 'data',
            array: data.uncertainty.map(u => u !== null ? u : 0),
            visible: true,
            color: PLOT_COLORS.power,
            thickness: 1.5,
            width: 3
        };
    }

    Plotly.react('eqe-plot',
        [
            eqeTrace,
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

function toggleErrorBars() {
    state.analysis.showErrorBars = document.getElementById('error-bar-toggle').checked;
    if (state.analysis.eqeData) {
        updateEQEPlot();
    }
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
    // Use Ctrl (Windows/Linux) or Cmd (Mac) + Shift + key
    // Use e.code for reliable cross-platform detection
    const modifierKey = e.ctrlKey || e.metaKey;

    if (modifierKey && e.shiftKey && e.code === 'KeyT') {
        e.preventDefault();
        toggleConsole();
    }
    else if (modifierKey && e.shiftKey && e.code === 'KeyE') {
        e.preventDefault();
        toggleAnalysisPanel();
    }
    else if (modifierKey && e.shiftKey && e.code === 'KeyD') {
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
window.toggleErrorBars = toggleErrorBars;
window.toggleConsole = toggleConsole;
window.clearConsole = clearConsole;
window.copyConsole = copyConsole;
window.captureLockinData = captureLockinData;
window.onLockinParamChange = onLockinParamChange;
window.onLockinSignalParamChange = onLockinSignalParamChange;
window.onLockinStepChange = onLockinStepChange;
