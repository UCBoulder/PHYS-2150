/**
 * J-V Measurement Application (ES6 Module)
 *
 * Handles I-V curve measurements for solar cell characterization.
 * Uses ES6 module syntax to avoid global scope conflicts.
 */

import {
    getBaseLayout,
    getPlotConfig,
    updatePlotTheme,
    PLOT_COLORS
} from './plotly-utils.js';

// ============================================
// State
// ============================================

let isMeasuring = false;
let currentPixel = null;
let forwardData = { x: [], y: [], stats: [] };
let reverseData = { x: [], y: [], stats: [] };
let isOfflineMode = false;
let isDeviceConnected = false;
let activeTab = 'measurement';

// Stability test state
let stabilityTestRunning = false;
let stabilityData = {
    timestamps: [],
    voltages: [],
    currents: []
};
let stabilityStartTime = null;
let stabilityDuration = 0; // minutes

// Analysis state
const analysisState = {
    visible: false,
    forwardData: null,  // { voltages: [], currents: [] }
    reverseData: null,
    metrics: null,
    cellNumber: null,
    pixel: null,
    sourceFile: null
};

// Console state
let consoleVisible = false;
const consoleMessages = [];
const MAX_CONSOLE_MESSAGES = 500;

// Plot configuration (module-scoped, no global conflict)
const plotConfig = getPlotConfig();

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

function getPlotLayout(isDark) {
    return getBaseLayout(isDark, 'Voltage (V)', 'Current (mA)', {
        transparentBg: true,
        legend: { x: 0.02, y: 0.98, xanchor: 'left', yanchor: 'top' }
    });
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
    const validation = LabConfig.get('validation', {});

    // Voltage parameters
    if (defaults.start_voltage !== undefined) {
        document.getElementById('start-voltage').value = defaults.start_voltage;
    }
    if (defaults.stop_voltage !== undefined) {
        document.getElementById('stop-voltage').value = defaults.stop_voltage;
    }
    if (defaults.step_voltage !== undefined) {
        document.getElementById('step-voltage').value = defaults.step_voltage;
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
    LabModals.init();
    await LabAPI.init();
    await LabConfig.load();

    // Populate form defaults from config
    populateFormDefaults();

    // Small delay to ensure Plotly is ready
    setTimeout(() => {
        initPlot();
        initStabilityPlot();
        // Ensure plots match current theme (handles theme passed from launcher)
        const isDark = LabTheme.isDark();
        window.dispatchEvent(new CustomEvent('themechange', { detail: { dark: isDark } }));

        checkDeviceStatus();

        // Prompt for cell number on startup
        LabModals.showCell((cellNumber) => {
            document.getElementById('cell-number').value = cellNumber;
        });
    }, 50);
});

// ============================================
// Tab Navigation
// ============================================

function switchTab(tabName) {
    // Prevent switching during active measurements
    if (isMeasuring) {
        LabModals.showError('Cannot Switch', 'Please stop the current measurement before switching tabs.');
        return;
    }

    // Prevent switching during active stability test
    if (stabilityTestRunning) {
        LabModals.showError('Cannot Switch', 'Please stop the stability test before switching tabs.');
        return;
    }

    activeTab = tabName;

    // Update tab buttons
    document.querySelectorAll('.tab-btn').forEach(btn => {
        const btnTab = btn.getAttribute('onclick')?.match(/switchTab\('(\w+)'\)/)?.[1];
        btn.classList.toggle('active', btnTab === tabName);
    });

    // Update tab content visibility
    document.querySelectorAll('.tab-content').forEach(content => {
        content.classList.toggle('active', content.id === 'tab-' + tabName);
    });

    // Initialize plots for the new tab
    if (tabName === 'analysis') {
        setTimeout(() => {
            const plotDiv = document.getElementById('iv-analysis-plot');
            if (!plotDiv.data) {
                initAnalysisPlot();
            } else {
                Plotly.Plots.resize('iv-analysis-plot');
            }
            updateSessionButton();
        }, 50);
    } else if (tabName === 'stability') {
        // Sync cell number from measurement tab if stability field is empty
        const mainCellNumber = document.getElementById('cell-number').value;
        const stabilityCellNumber = document.getElementById('stability-cell-number');
        if (mainCellNumber && !stabilityCellNumber.value) {
            stabilityCellNumber.value = mainCellNumber;
        }
        setTimeout(() => {
            Plotly.Plots.resize('stability-plot');
        }, 50);
    } else {
        setTimeout(() => {
            Plotly.Plots.resize('jv-plot');
        }, 50);
    }
}

function toggleAnalysisPanel() {
    analysisState.visible = !analysisState.visible;
    const tabBtn = document.getElementById('analysis-tab-btn');

    if (analysisState.visible) {
        tabBtn.style.display = '';
        switchTab('analysis');
    } else {
        tabBtn.style.display = 'none';
        switchTab('measurement');
    }
}

// ============================================
// Measurement Tab Functions
// ============================================

function initPlot() {
    clearPlot();
}

window.addEventListener('resize', () => {
    if (typeof Plotly !== 'undefined') {
        if (activeTab === 'measurement') {
            Plotly.Plots.resize('jv-plot');
        } else if (activeTab === 'stability') {
            Plotly.Plots.resize('stability-plot');
        } else if (activeTab === 'analysis') {
            Plotly.Plots.resize('iv-analysis-plot');
        }
    }
});

window.addEventListener('themechange', (e) => {
    const plotDiv = document.getElementById('jv-plot');
    if (typeof Plotly !== 'undefined' && plotDiv && plotDiv.data) {
        updatePlotTheme('jv-plot', e.detail.dark, { transparentBg: true });
    }
    const stabilityPlot = document.getElementById('stability-plot');
    if (typeof Plotly !== 'undefined' && stabilityPlot && stabilityPlot.data) {
        updatePlotTheme('stability-plot', e.detail.dark, { transparentBg: true });
    }
    const analysisPlot = document.getElementById('iv-analysis-plot');
    if (typeof Plotly !== 'undefined' && analysisPlot && analysisPlot.data) {
        updatePlotTheme('iv-analysis-plot', e.detail.dark, { transparentBg: true });
    }
});

async function checkDeviceStatus() {
    try {
        const api = LabAPI.get();
        if (api && api.get_device_status) {
            api.get_device_status((result) => {
                const status = JSON.parse(result);
                isOfflineMode = status.offline_mode;
                isDeviceConnected = status.connected;
                updateDeviceStatus(status.connected, status.message, status.offline_mode);
            });
        } else {
            isOfflineMode = true;
            isDeviceConnected = false;
            updateDeviceStatus(false, 'Development mode', true);
        }
    } catch (error) {
        updateDeviceStatus(false, 'Connection failed', false);
    }
}

function updateDeviceStatus(connected, message, offlineMode) {
    const dot = document.getElementById('status-dot');
    const text = document.getElementById('status-text');
    const btn = document.getElementById('measure-btn');

    // Also update stability tab device status
    const stabilityDot = document.getElementById('stability-status-dot');
    const stabilityText = document.getElementById('stability-status-text');

    isDeviceConnected = connected;
    isOfflineMode = offlineMode;

    if (connected) {
        dot.className = 'device-dot connected';
        text.textContent = message || 'Connected';
        btn.disabled = false;
        if (stabilityDot) stabilityDot.className = 'device-dot connected';
        if (stabilityText) stabilityText.textContent = message || 'Connected';
    } else if (offlineMode) {
        dot.className = 'device-dot warning';
        text.textContent = message || 'Offline mode';
        btn.disabled = false;
        if (stabilityDot) stabilityDot.className = 'device-dot warning';
        if (stabilityText) stabilityText.textContent = message || 'Offline mode';
    } else {
        dot.className = 'device-dot disconnected';
        text.textContent = message || 'Not connected';
        btn.disabled = true;
        if (stabilityDot) stabilityDot.className = 'device-dot disconnected';
        if (stabilityText) stabilityText.textContent = message || 'Not connected';
    }
}

function toggleMeasurement() {
    if (isMeasuring) {
        stopMeasurement();
    } else {
        const cellNumber = document.getElementById('cell-number').value;
        if (!cellNumber || !/^\d{3}$/.test(cellNumber)) {
            LabModals.showCell((cell) => {
                document.getElementById('cell-number').value = cell;
                LabModals.showPixel(startMeasurement);
            });
            return;
        }
        LabModals.showPixel(startMeasurement);
    }
}

async function startMeasurement(pixel) {
    currentPixel = pixel;
    isMeasuring = true;
    updateMeasuringState(true);
    updateProgress(0, 'Starting forward sweep...');

    forwardData = { x: [], y: [], stats: [] };
    reverseData = { x: [], y: [], stats: [] };
    document.getElementById('save-btn').disabled = true;
    clearPlot();
    resetStatsBar();
    updatePixelLabel(pixel);

    const params = {
        start_voltage: parseFloat(document.getElementById('start-voltage').value),
        stop_voltage: parseFloat(document.getElementById('stop-voltage').value),
        step_voltage: parseFloat(document.getElementById('step-voltage').value),
        cell_number: document.getElementById('cell-number').value,
        pixel: pixel
    };

    if (isDeviceConnected) {
        console.log('Starting hardware measurement with params:', params);
        const api = LabAPI.get();
        if (api && api.start_measurement) {
            api.start_measurement(JSON.stringify(params), (result) => {
                const response = JSON.parse(result);
                if (!response.success) {
                    LabModals.showError('Measurement Failed', response.message);
                    isMeasuring = false;
                    updateMeasuringState(false);
                }
            });
        }
    } else if (isOfflineMode) {
        console.log('Starting mock measurement with params:', params);
        mockMeasurement(params);
    } else {
        LabModals.showError('No Device', 'No device connected. Use --offline flag for testing.');
        isMeasuring = false;
        updateMeasuringState(false);
    }
}

function stopMeasurement() {
    isMeasuring = false;
    updateMeasuringState(false);
    updateProgress(0, 'Stopped');

    const api = LabAPI.get();
    if (api && api.stop_measurement) {
        api.stop_measurement(() => {});
    }
}

function updateMeasuringState(measuring) {
    const btn = document.getElementById('measure-btn');
    const inputs = document.querySelectorAll('#tab-measurement .params-panel input');

    if (measuring) {
        btn.textContent = 'Stop Measurement';
        btn.className = 'btn btn-danger';
        inputs.forEach(input => input.disabled = true);
    } else {
        btn.textContent = 'Start Measurement';
        btn.className = 'btn btn-primary';
        inputs.forEach(input => input.disabled = false);
    }
}

function updateProgress(percent, message) {
    document.getElementById('progress-fill').style.width = percent + '%';
    document.getElementById('progress-percent').textContent = Math.round(percent) + '%';
    if (message) {
        document.getElementById('status-message').textContent = message;
    }
}

function updatePixelLabel(pixel) {
    document.getElementById('pixel-label').textContent = `Pixel: ${pixel}`;
}

// Called from Python via WebChannel
function onMeasurementPoint(direction, voltage, current) {
    if (direction === 'forward') {
        forwardData.x.push(voltage);
        forwardData.y.push(current);
    } else {
        reverseData.x.push(voltage);
        reverseData.y.push(current);
    }
    updatePlot();
}

function onMeasurementComplete(success) {
    isMeasuring = false;
    updateMeasuringState(false);

    if (success) {
        updateProgress(100, 'Complete');
        document.getElementById('save-btn').disabled = false;
        console.log('Measurement complete');
        saveData();
    } else {
        updateProgress(0, 'Failed');
    }
}

// ============================================
// Stability Test Functions
// ============================================

function initStabilityPlot() {
    const plotDiv = document.getElementById('stability-plot');
    const isDark = LabTheme.isDark();

    const trace = {
        x: [],
        y: [],
        mode: 'lines+markers',
        type: 'scatter',
        name: 'Current',
        line: { color: PLOT_COLORS.jvForward, width: 2 },
        marker: { size: 5, color: PLOT_COLORS.jvForward }
    };

    const layout = getBaseLayout(isDark, 'Time (s)', 'Current (mA)', {
        transparentBg: true,
        title: 'Current Stability vs Time',
        showlegend: false
    });

    Plotly.newPlot(plotDiv, [trace], layout, plotConfig);
}

function startStabilityTest() {
    // Validate test parameters first
    const targetVoltage = parseFloat(document.getElementById('stability-target-voltage').value);
    const duration = parseFloat(document.getElementById('stability-duration').value);
    const interval = parseFloat(document.getElementById('stability-interval').value);

    if (isNaN(targetVoltage) || isNaN(duration) || isNaN(interval)) {
        LabModals.showError('Invalid Input', 'Please enter valid test parameters');
        return;
    }

    // Check cell number, prompt if needed
    const cellNumber = document.getElementById('stability-cell-number').value;
    if (!cellNumber || !/^\d{3}$/.test(cellNumber)) {
        LabModals.showCell((cell) => {
            document.getElementById('stability-cell-number').value = cell;
            LabModals.showPixel(executeStabilityTest);
        });
        return;
    }

    // Prompt for pixel number
    LabModals.showPixel(executeStabilityTest);
}

function executeStabilityTest(pixel) {
    currentPixel = pixel;

    const targetVoltage = parseFloat(document.getElementById('stability-target-voltage').value);
    const duration = parseFloat(document.getElementById('stability-duration').value);
    const interval = parseFloat(document.getElementById('stability-interval').value);
    const cellNumber = document.getElementById('stability-cell-number').value;

    // Clear previous data
    stabilityData.timestamps = [];
    stabilityData.voltages = [];
    stabilityData.currents = [];
    stabilityStartTime = null;
    stabilityDuration = duration;

    // Reset plot
    Plotly.deleteTraces('stability-plot', 0);
    Plotly.addTraces('stability-plot', {
        x: [],
        y: [],
        mode: 'lines+markers',
        type: 'scatter',
        line: { color: PLOT_COLORS.jvForward, width: 2 },
        marker: { size: 5, color: PLOT_COLORS.jvForward }
    });

    // Reset stats
    updateStabilityStats();

    // Update UI
    stabilityTestRunning = true;
    document.getElementById('stability-start-btn').disabled = true;
    document.getElementById('stability-stop-btn').disabled = false;
    document.getElementById('stability-save-btn').disabled = true;

    // Call API
    const params = {
        target_voltage: targetVoltage,
        duration: duration,
        interval: interval,
        pixel: pixel,
        cell_number: cellNumber
    };

    const api = LabAPI.get();
    api.start_stability_test(JSON.stringify(params), (result) => {
        const response = JSON.parse(result);
        if (!response.success) {
            LabModals.showError('Stability Test Failed', response.message);
            resetStabilityUI();
        } else {
            stabilityStartTime = Date.now() / 1000;
        }
    });
}

function stopStabilityTest() {
    const api = LabAPI.get();
    api.stop_stability_test((result) => {
        // UI will be reset in onStabilityComplete callback
    });
}

function saveStabilityData() {
    if (stabilityData.timestamps.length === 0) {
        LabModals.showError('No Data', 'No data to save');
        return;
    }

    // Generate CSV
    const headers = ['Timestamp (s)', 'Voltage (V)', 'Current (mA)'];
    let csv = headers.join(',') + '\n';

    for (let i = 0; i < stabilityData.timestamps.length; i++) {
        csv += `${stabilityData.timestamps[i].toFixed(2)},`;
        csv += `${stabilityData.voltages[i].toFixed(2)},`;
        csv += `${stabilityData.currents[i].toFixed(5)}\n`;
    }

    // Call save API
    const api = LabAPI.get();
    api.save_stability_data(csv, (result) => {
        const response = JSON.parse(result);
        if (response.success) {
            console.log('Stability data saved to:', response.path);
        } else {
            console.error('Save failed:', response.message);
        }
    });
}

function resetStabilityUI() {
    stabilityTestRunning = false;
    document.getElementById('stability-start-btn').disabled = false;
    document.getElementById('stability-stop-btn').disabled = true;
    document.getElementById('stability-save-btn').disabled = false;
    document.getElementById('stability-progress-fill').style.width = '0%';
    document.getElementById('stability-progress-percent').textContent = '0%';
}

// Callback from Python: new measurement point
function onStabilityMeasurement(timestamp, voltage, current) {
    stabilityData.timestamps.push(timestamp);
    stabilityData.voltages.push(voltage);
    stabilityData.currents.push(current);

    // Update plot
    Plotly.extendTraces('stability-plot', {
        x: [[timestamp]],
        y: [[current]]
    }, [0]);

    // Update stats
    updateStabilityStats();

    // Update progress bar
    if (stabilityDuration > 0) {
        const progress = Math.min(100, (timestamp / (stabilityDuration * 60)) * 100);
        document.getElementById('stability-progress-fill').style.width = progress + '%';
        document.getElementById('stability-progress-percent').textContent = Math.round(progress) + '%';
    }
}

// Callback from Python: test complete
function onStabilityComplete(success) {
    resetStabilityUI();

    if (success) {
        document.getElementById('stability-status').textContent = 'Test complete';
    } else {
        document.getElementById('stability-status').textContent = 'Test stopped';
    }
}

// Callback from Python: error
function onStabilityError(errorMessage) {
    console.error('Stability test error:', errorMessage);
    LabModals.showError('Stability Test Error', errorMessage);
    resetStabilityUI();
    document.getElementById('stability-status').textContent = 'Error: ' + errorMessage;
}

// Callback from Python: status update
function onStabilityStatus(statusMessage) {
    document.getElementById('stability-status').textContent = statusMessage;
}

function updateStabilityStats() {
    if (stabilityData.currents.length === 0) {
        document.getElementById('stability-mean').textContent = '--';
        document.getElementById('stability-std').textContent = '--';
        document.getElementById('stability-cv').textContent = '--';
        document.getElementById('stability-count').textContent = '0';
        return;
    }

    // Calculate statistics
    const currents = stabilityData.currents;
    const n = currents.length;
    const mean = currents.reduce((a, b) => a + b, 0) / n;

    let std = 0;
    if (n > 1) {
        const variance = currents.reduce((sum, val) => sum + Math.pow(val - mean, 2), 0) / (n - 1);
        std = Math.sqrt(variance);
    }

    const cv = mean !== 0 ? (std / Math.abs(mean)) * 100 : 0;

    // Update display
    document.getElementById('stability-mean').textContent = mean.toFixed(5) + ' mA';
    document.getElementById('stability-std').textContent = std.toFixed(5) + ' mA';
    document.getElementById('stability-cv').textContent = cv.toFixed(2) + '%';
    document.getElementById('stability-count').textContent = n.toString();
}

// ============================================
// Measurement Data Export
// ============================================

function saveData() {
    const cellNumber = document.getElementById('cell-number').value || '000';
    const pixel = currentPixel || 1;

    // Get headers from config (raw format with Direction, Voltage, Current, Std, n)
    const headersRaw = LabConfig.get('export.headers_raw', {
        direction: 'Direction',
        voltage: 'Voltage (V)',
        current: 'Current (mA)',
        std: 'Std (mA)',
        n: 'n'
    });
    let csv = `${headersRaw.direction},${headersRaw.voltage},${headersRaw.current},${headersRaw.std},${headersRaw.n}\n`;

    for (let i = 0; i < forwardData.x.length; i++) {
        const std = forwardData.stats[i] ? forwardData.stats[i].std_dev.toFixed(6) : '0';
        const n = forwardData.stats[i] ? forwardData.stats[i].n : '1';
        csv += `Forward,${forwardData.x[i].toFixed(4)},${forwardData.y[i].toFixed(6)},${std},${n}\n`;
    }

    for (let i = 0; i < reverseData.x.length; i++) {
        const std = reverseData.stats[i] ? reverseData.stats[i].std_dev.toFixed(6) : '0';
        const n = reverseData.stats[i] ? reverseData.stats[i].n : '1';
        csv += `Reverse,${reverseData.x[i].toFixed(4)},${reverseData.y[i].toFixed(6)},${std},${n}\n`;
    }

    const api = LabAPI.get();
    if (api && api.save_csv_data) {
        api.save_csv_data(csv, cellNumber, pixel, (result) => {
            const response = JSON.parse(result);
            if (response.success) {
                console.log('Data saved to:', response.path);
            } else if (response.message !== 'Cancelled') {
                LabModals.showError('Save Failed', response.message);
            }
        });
    } else {
        console.error('Save API not available');
    }
}

function clearPlot() {
    const plotDiv = document.getElementById('jv-plot');
    const layout = getPlotLayout(LabTheme.isDark());
    const traces = [
        { x: [], y: [], mode: 'markers', type: 'scatter', name: 'Forward', marker: { color: PLOT_COLORS.jvForward, size: 8 } },
        { x: [], y: [], mode: 'markers', type: 'scatter', name: 'Reverse', marker: { color: PLOT_COLORS.jvReverse, size: 8 } }
    ];
    Plotly.newPlot(plotDiv, traces, layout, plotConfig).then(() => attachJVPlotHover());
}

function updatePlot() {
    const plotDiv = document.getElementById('jv-plot');
    const layout = getPlotLayout(LabTheme.isDark());
    const traces = [
        { x: forwardData.x, y: forwardData.y, mode: 'markers', type: 'scatter', name: 'Forward', marker: { color: PLOT_COLORS.jvForward, size: 8 } },
        { x: reverseData.x, y: reverseData.y, mode: 'markers', type: 'scatter', name: 'Reverse', marker: { color: PLOT_COLORS.jvReverse, size: 8 } }
    ];
    Plotly.newPlot(plotDiv, traces, layout, plotConfig).then(() => attachJVPlotHover());
}

// Mock measurement for offline mode
function mockMeasurement(params) {
    const start = params.start_voltage;
    const stop = params.stop_voltage;
    const step = params.step_voltage;
    const totalSteps = Math.ceil((stop - start) / step);
    let stepCount = 0;

    let voltage = start;
    const interval = setInterval(() => {
        if (!isMeasuring || voltage > stop) {
            clearInterval(interval);
            if (isMeasuring) {
                updateProgress(50, 'Reverse sweep...');
                mockReverseSweep(stop, start, step, totalSteps);
            }
            return;
        }

        const current = 0.01 * (Math.exp(voltage / 0.026) - 1) + (Math.random() - 0.5) * 0.001;
        onMeasurementPoint('forward', voltage, current * 1000);
        stepCount++;
        const progress = (stepCount / totalSteps) * 50;
        updateProgress(progress, `Forward: ${voltage.toFixed(2)} V`);
        voltage += step;
    }, 50);
}

function mockReverseSweep(start, stop, step, totalSteps) {
    let stepCount = 0;
    let voltage = start;
    const interval = setInterval(() => {
        if (!isMeasuring || voltage < stop) {
            clearInterval(interval);
            onMeasurementComplete(true);
            return;
        }

        const current = 0.01 * (Math.exp(voltage / 0.026) - 1) + (Math.random() - 0.5) * 0.001;
        onMeasurementPoint('reverse', voltage, current * 1000);
        stepCount++;
        const progress = 50 + (stepCount / totalSteps) * 50;
        updateProgress(progress, `Reverse: ${voltage.toFixed(2)} V`);
        voltage -= step;
    }, 50);
}

function onMeasurementProgress(percent, message) {
    updateProgress(percent, message);
}

/**
 * Handle measurement statistics from Python.
 * Updates the stats bar with current measurement quality info.
 */
function onMeasurementStats(stats) {
    // Store stats for hover interaction
    const statsData = {
        voltage: stats.voltage,
        mean: stats.mean,
        std_dev: stats.std_dev,
        n: stats.n,
        quality: stats.quality,
        unit: stats.unit
    };

    if (stats.direction === 'forward') {
        forwardData.stats.push(statsData);
    } else {
        reverseData.stats.push(statsData);
    }

    // Update stats bar display
    displayStats(statsData);
}

/**
 * Display stats in the stats bar.
 */
function displayStats(stats) {
    document.getElementById('jv-stats-n').textContent = stats.n;
    document.getElementById('jv-stats-voltage').textContent = stats.voltage.toFixed(2) + ' V';
    document.getElementById('jv-stats-mean').textContent = stats.mean.toFixed(4) + ' ' + stats.unit;
    document.getElementById('jv-stats-std').textContent = stats.std_dev.toFixed(4) + ' ' + stats.unit;
}

/**
 * Reset stats bar to initial state.
 */
function resetStatsBar() {
    document.getElementById('jv-stats-n').textContent = '--';
    document.getElementById('jv-stats-voltage').textContent = '--';
    document.getElementById('jv-stats-mean').textContent = '--';
    document.getElementById('jv-stats-std').textContent = '--';
}

/**
 * Attach hover event listener to the JV plot for interactive stats display.
 */
function attachJVPlotHover() {
    const jvPlot = document.getElementById('jv-plot');
    jvPlot.on('plotly_hover', function(data) {
        const traceIndex = data.points[0].curveNumber;  // 0=forward, 1=reverse
        const pointIndex = data.points[0].pointIndex;
        const statsArray = traceIndex === 0 ? forwardData.stats : reverseData.stats;
        if (statsArray && statsArray[pointIndex]) {
            displayStats(statsArray[pointIndex]);
        }
    });
}

// ============================================
// Analysis Tab Functions
// ============================================

function initAnalysisPlot() {
    const plotDiv = document.getElementById('iv-analysis-plot');
    const layout = getPlotLayout(LabTheme.isDark());
    const traces = [
        { x: [], y: [], mode: 'lines+markers', type: 'scatter', name: 'Forward', line: { color: PLOT_COLORS.jvForward }, marker: { size: 6 } },
        { x: [], y: [], mode: 'lines+markers', type: 'scatter', name: 'Reverse', line: { color: PLOT_COLORS.jvReverse }, marker: { size: 6 } },
        { x: [], y: [], mode: 'markers', type: 'scatter', name: 'Voc', marker: { color: PLOT_COLORS.markerVoc, size: 12, symbol: 'diamond' } },
        { x: [], y: [], mode: 'markers', type: 'scatter', name: 'Isc', marker: { color: PLOT_COLORS.markerIsc, size: 12, symbol: 'diamond' } },
        { x: [], y: [], mode: 'markers', type: 'scatter', name: 'MPP', marker: { color: PLOT_COLORS.markerMPP, size: 14, symbol: 'star' } }
    ];
    Plotly.newPlot(plotDiv, traces, layout, plotConfig);
}

function updateSessionButton() {
    const btn = document.getElementById('use-session-btn');
    btn.disabled = forwardData.x.length === 0 && reverseData.x.length === 0;
}

function useSessionData() {
    if (forwardData.x.length === 0 && reverseData.x.length === 0) {
        setAnalysisStatus('No session data', 'error');
        return;
    }

    if (forwardData.x.length > 0) {
        analysisState.forwardData = {
            voltages: [...forwardData.x],
            currents: [...forwardData.y]
        };
    }
    if (reverseData.x.length > 0) {
        analysisState.reverseData = {
            voltages: [...reverseData.x],
            currents: [...reverseData.y]
        };
    }

    // Get cell/pixel from measurement tab
    analysisState.cellNumber = document.getElementById('cell-number').value || null;
    analysisState.pixel = currentPixel;
    analysisState.sourceFile = 'Session';

    const fwdPts = forwardData.x.length;
    const revPts = reverseData.x.length;
    const statusEl = document.getElementById('data-file-status');
    statusEl.textContent = `Session (${fwdPts}/${revPts} pts)`;
    statusEl.classList.add('loaded');
    updateCalculateButton();
    setAnalysisStatus('Session data loaded', 'success');
}

function loadCSVFile() {
    const input = document.getElementById('csv-file-input');
    input.value = '';
    input.click();
}

function onCSVFileSelected(event) {
    const file = event.target.files[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (e) => {
        try {
            const result = parseIVCSV(e.target.result);
            analysisState.forwardData = result.forward;
            analysisState.reverseData = result.reverse;

            // Extract cell/pixel from filename
            const extracted = extractCellPixelFromFilename(file.name);
            analysisState.cellNumber = extracted.cell;
            analysisState.pixel = extracted.pixel;
            analysisState.sourceFile = file.name;

            const fwdPts = result.forward ? result.forward.voltages.length : 0;
            const revPts = result.reverse ? result.reverse.voltages.length : 0;

            const statusEl = document.getElementById('data-file-status');
            statusEl.textContent = `${file.name} (${fwdPts}/${revPts})`;
            statusEl.classList.add('loaded');
            updateCalculateButton();
            setAnalysisStatus(`Loaded: ${fwdPts} fwd, ${revPts} rev points`, 'success');
        } catch (err) {
            setAnalysisStatus('Failed to parse: ' + err.message, 'error');
        }
    };
    reader.readAsText(file);
}

function parseIVCSV(content) {
    const lines = content.trim().split('\n');
    const forward = { voltages: [], currents: [] };
    const reverse = { voltages: [], currents: [] };

    for (let i = 0; i < lines.length; i++) {
        const line = lines[i].trim();
        if (!line || line.startsWith('#') || line.toLowerCase().startsWith('direction') ||
            line.toLowerCase().startsWith('voltage')) continue;

        const parts = line.split(',');

        if (parts.length >= 3 && (parts[0] === 'Forward' || parts[0] === 'Reverse')) {
            // Format: Direction,Voltage,Current
            const v = parseFloat(parts[1]);
            const c = parseFloat(parts[2]);
            if (!isNaN(v) && !isNaN(c)) {
                if (parts[0] === 'Forward') {
                    forward.voltages.push(v);
                    forward.currents.push(c);
                } else {
                    reverse.voltages.push(v);
                    reverse.currents.push(c);
                }
            }
        } else if (parts.length >= 2) {
            // Format: Voltage,Current (assume forward only)
            const v = parseFloat(parts[0]);
            const c = parseFloat(parts[1]);
            if (!isNaN(v) && !isNaN(c)) {
                forward.voltages.push(v);
                forward.currents.push(c);
            }
        }
    }

    if (forward.voltages.length === 0 && reverse.voltages.length === 0) {
        throw new Error('No valid data found');
    }

    return {
        forward: forward.voltages.length > 0 ? forward : null,
        reverse: reverse.voltages.length > 0 ? reverse : null
    };
}

function updateCalculateButton() {
    const sweepType = document.querySelector('input[name="sweep-select"]:checked').value;
    const hasData = (sweepType === 'forward' && analysisState.forwardData) ||
                   (sweepType === 'reverse' && analysisState.reverseData);
    document.getElementById('calculate-params-btn').disabled = !hasData;
}

function setAnalysisStatus(message, type = '') {
    const el = document.getElementById('analysis-status');
    el.textContent = message;
    el.className = 'analysis-status-text';
    if (type) {
        el.classList.add(type);
    }
}

function calculateParameters() {
    const sweepType = document.querySelector('input[name="sweep-select"]:checked').value;
    const data = sweepType === 'forward' ? analysisState.forwardData : analysisState.reverseData;

    if (!data) {
        setAnalysisStatus(`No ${sweepType} data loaded`, 'error');
        return;
    }

    try {
        const voltages = data.voltages;
        const currents = data.currents;

        // Sort by voltage for consistent analysis
        const sorted = sortByVoltage(voltages, currents);

        // Calculate parameters
        const isc = interpolateAtX(sorted.v, sorted.i, 0);  // I at V=0
        const voc = findVoc(sorted.v, sorted.i);  // V at I=0

        // Find max power point
        let pmax = 0, vmpp = 0, impp = 0;
        for (let j = 0; j < sorted.v.length; j++) {
            const power = -sorted.v[j] * sorted.i[j];
            if (power > pmax) {
                pmax = power;
                vmpp = sorted.v[j];
                impp = sorted.i[j];
            }
        }

        // Fill factor
        const ff = (voc > 0 && isc !== 0) ? pmax / (Math.abs(isc) * voc) : 0;

        // Resistances
        const rs = calculateRs(sorted.v, sorted.i, voc);
        const rsh = calculateRsh(sorted.v, sorted.i);

        // Optional: Jsc and PCE if area is provided
        const areaInput = document.getElementById('cell-area').value;
        const area = parseFloat(areaInput);
        let jsc = null, pce = null;
        if (!isNaN(area) && area > 0) {
            jsc = Math.abs(isc) / area;  // mA/cm^2
            pce = (pmax / (area * 100)) * 100;  // % (assuming 100 mW/cm^2 AM1.5G)
        }

        // Store metrics
        analysisState.metrics = {
            voc, isc, pmax, vmpp, impp, ff, rs, rsh, jsc, pce,
            sweepType,
            dataPoints: voltages.length
        };

        // Update display
        updateMetricsDisplay();
        updateAnalysisPlot(sorted.v, sorted.i, sweepType, voc, isc, vmpp, impp);
        setAnalysisStatus('Analysis complete', 'success');
        document.getElementById('btn-save-analysis').disabled = false;

    } catch (err) {
        setAnalysisStatus('Calculation error: ' + err.message, 'error');
        console.error(err);
    }
}

function sortByVoltage(voltages, currents) {
    const pairs = voltages.map((v, i) => ({ v, i: currents[i] }));
    pairs.sort((a, b) => a.v - b.v);
    return {
        v: pairs.map(p => p.v),
        i: pairs.map(p => p.i)
    };
}

function interpolateAtX(xArr, yArr, targetX) {
    for (let i = 0; i < xArr.length - 1; i++) {
        if ((xArr[i] <= targetX && xArr[i + 1] >= targetX) ||
            (xArr[i] >= targetX && xArr[i + 1] <= targetX)) {
            const x1 = xArr[i], x2 = xArr[i + 1];
            const y1 = yArr[i], y2 = yArr[i + 1];
            return y1 + (targetX - x1) * (y2 - y1) / (x2 - x1);
        }
    }
    if (targetX <= xArr[0]) return yArr[0];
    return yArr[yArr.length - 1];
}

function findVoc(voltages, currents) {
    for (let i = 0; i < currents.length - 1; i++) {
        if ((currents[i] <= 0 && currents[i + 1] >= 0) ||
            (currents[i] >= 0 && currents[i + 1] <= 0)) {
            const v1 = voltages[i], v2 = voltages[i + 1];
            const i1 = currents[i], i2 = currents[i + 1];
            return v1 + (0 - i1) * (v2 - v1) / (i2 - i1);
        }
    }
    let minIdx = 0, minAbs = Math.abs(currents[0]);
    for (let i = 1; i < currents.length; i++) {
        if (Math.abs(currents[i]) < minAbs) {
            minAbs = Math.abs(currents[i]);
            minIdx = i;
        }
    }
    return voltages[minIdx];
}

function calculateRs(voltages, currents, voc) {
    const nearVoc = [];
    for (let i = 0; i < voltages.length; i++) {
        if (Math.abs(voltages[i] - voc) < 0.1) {
            nearVoc.push({ v: voltages[i], i: currents[i] });
        }
    }
    if (nearVoc.length < 2) return null;

    const n = nearVoc.length;
    let sumV = 0, sumI = 0, sumVI = 0, sumI2 = 0;
    for (const p of nearVoc) {
        sumV += p.v;
        sumI += p.i;
        sumVI += p.v * p.i;
        sumI2 += p.i * p.i;
    }
    const denom = n * sumI2 - sumI * sumI;
    if (Math.abs(denom) < 1e-10) return null;
    const slope = (n * sumVI - sumV * sumI) / denom;
    return Math.abs(slope) * 1000;
}

function calculateRsh(voltages, currents) {
    const nearZero = [];
    for (let i = 0; i < voltages.length; i++) {
        if (Math.abs(voltages[i]) < 0.1) {
            nearZero.push({ v: voltages[i], i: currents[i] });
        }
    }
    if (nearZero.length < 2) return null;

    const n = nearZero.length;
    let sumV = 0, sumI = 0, sumVI = 0, sumI2 = 0;
    for (const p of nearZero) {
        sumV += p.v;
        sumI += p.i;
        sumVI += p.v * p.i;
        sumI2 += p.i * p.i;
    }
    const denom = n * sumI2 - sumI * sumI;
    if (Math.abs(denom) < 1e-10) return null;
    const slope = (n * sumVI - sumV * sumI) / denom;
    return Math.abs(slope) * 1000;
}

function updateMetricsDisplay() {
    const m = analysisState.metrics;
    if (!m) return;

    const pceGroup = document.getElementById('pce-metric-group');
    if (m.pce !== null) {
        pceGroup.style.display = '';
        document.getElementById('metric-pce').textContent = m.pce.toFixed(2) + ' %';
    } else {
        pceGroup.style.display = 'none';
    }

    const jscGroup = document.getElementById('jsc-metric-group');
    const iscGroup = document.getElementById('isc-metric-group');
    const jscEl = document.getElementById('metric-jsc');
    const iscEl = document.getElementById('metric-isc');

    if (m.jsc !== null) {
        jscGroup.style.display = '';
        iscGroup.style.display = '';
        jscEl.textContent = m.jsc.toFixed(2) + ' mA/cm²';
        iscEl.textContent = m.isc.toFixed(3) + ' mA';
    } else {
        jscGroup.style.display = 'none';
        iscGroup.style.display = '';
        iscEl.textContent = m.isc.toFixed(3) + ' mA';
    }

    document.getElementById('metric-voc').textContent = m.voc.toFixed(3) + ' V';
    document.getElementById('metric-ff').textContent = (m.ff * 100).toFixed(1) + ' %';
    document.getElementById('metric-pmax').textContent = m.pmax.toFixed(3) + ' mW';

    document.getElementById('metric-vmpp').textContent = m.vmpp.toFixed(3) + ' V';
    document.getElementById('metric-impp').textContent = m.impp.toFixed(3) + ' mA';

    document.getElementById('metric-rs').textContent = m.rs !== null ? m.rs.toFixed(1) + ' Ω' : '-- Ω';
    document.getElementById('metric-rsh').textContent = m.rsh !== null ? m.rsh.toFixed(0) + ' Ω' : '-- Ω';
}

function updateAnalysisPlot(voltages, currents, sweepType, voc, isc, vmpp, impp) {
    const plotDiv = document.getElementById('iv-analysis-plot');
    const layout = getPlotLayout(LabTheme.isDark());

    const fwdTrace = {
        x: sweepType === 'forward' ? voltages : [],
        y: sweepType === 'forward' ? currents : [],
        mode: 'lines+markers',
        type: 'scatter',
        name: 'Forward',
        line: { color: PLOT_COLORS.jvForward },
        marker: { size: 6 }
    };
    const revTrace = {
        x: sweepType === 'reverse' ? voltages : [],
        y: sweepType === 'reverse' ? currents : [],
        mode: 'lines+markers',
        type: 'scatter',
        name: 'Reverse',
        line: { color: PLOT_COLORS.jvReverse },
        marker: { size: 6 }
    };

    const vocTrace = {
        x: [voc],
        y: [0],
        mode: 'markers',
        type: 'scatter',
        name: `Voc (${voc.toFixed(3)} V)`,
        marker: { color: PLOT_COLORS.markerVoc, size: 12, symbol: 'diamond' }
    };
    const iscTrace = {
        x: [0],
        y: [isc],
        mode: 'markers',
        type: 'scatter',
        name: `Isc (${isc.toFixed(3)} mA)`,
        marker: { color: PLOT_COLORS.markerIsc, size: 12, symbol: 'diamond' }
    };
    const mppTrace = {
        x: [vmpp],
        y: [impp],
        mode: 'markers',
        type: 'scatter',
        name: `MPP (${(vmpp * Math.abs(impp)).toFixed(3)} mW)`,
        marker: { color: PLOT_COLORS.markerMPP, size: 14, symbol: 'star' }
    };

    Plotly.newPlot(plotDiv, [fwdTrace, revTrace, vocTrace, iscTrace, mppTrace], layout, plotConfig);
}

function saveAnalysisResults() {
    const m = analysisState.metrics;
    if (!m) return;

    let csv = '# I-V Analysis Results\n';
    const now = new Date();
    const timestamp = now.toISOString().replace('T', ' ').split('.')[0];
    csv += `# Generated: ${timestamp}\n`;
    if (analysisState.cellNumber) csv += `# Cell: ${analysisState.cellNumber}\n`;
    if (analysisState.pixel) csv += `# Pixel: ${analysisState.pixel}\n`;
    if (analysisState.sourceFile) csv += `# Source: ${analysisState.sourceFile}\n`;
    csv += `# Sweep: ${m.sweepType}\n`;
    csv += `# Data Points: ${m.dataPoints}\n`;
    csv += '#\n';
    csv += `# Voc: ${m.voc.toFixed(4)} V\n`;
    csv += `# Isc: ${m.isc.toFixed(4)} mA\n`;
    if (m.jsc !== null) csv += `# Jsc: ${m.jsc.toFixed(4)} mA/cm^2\n`;
    csv += `# Fill Factor: ${(m.ff * 100).toFixed(2)} %\n`;
    csv += `# Pmax: ${m.pmax.toFixed(4)} mW\n`;
    if (m.pce !== null) csv += `# PCE: ${m.pce.toFixed(2)} %\n`;
    csv += `# Vmpp: ${m.vmpp.toFixed(4)} V\n`;
    csv += `# Impp: ${m.impp.toFixed(4)} mA\n`;
    if (m.rs !== null) csv += `# Rs: ${m.rs.toFixed(2)} ohms\n`;
    if (m.rsh !== null) csv += `# Rsh: ${m.rsh.toFixed(2)} ohms\n`;
    csv += '#\n';

    const data = m.sweepType === 'forward' ? analysisState.forwardData : analysisState.reverseData;
    // Get headers from config (use raw format headers for simple V-I export)
    const headersRaw = LabConfig.get('export.headers_raw', {
        voltage: 'Voltage (V)',
        current: 'Current (mA)'
    });
    csv += `${headersRaw.voltage},${headersRaw.current}\n`;
    for (let i = 0; i < data.voltages.length; i++) {
        csv += `${data.voltages[i].toFixed(4)},${data.currents[i].toFixed(6)}\n`;
    }

    const api = LabAPI.get();
    if (api && api.save_analysis_data) {
        api.save_analysis_data(csv, (result) => {
            const r = JSON.parse(result);
            if (r.success) {
                setAnalysisStatus('Results saved to ' + r.path, 'success');
            } else if (r.message !== 'Cancelled') {
                setAnalysisStatus('Save failed: ' + r.message, 'error');
            }
        });
    }
}

// Listen for sweep selector changes
document.querySelectorAll('input[name="sweep-select"]').forEach(radio => {
    radio.addEventListener('change', updateCalculateButton);
});

// ============================================
// Console Panel Functions
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

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function onLogMessage(level, message) {
    addConsoleMessage(level, message);
}

// ============================================
// Keyboard Shortcuts
// ============================================

document.addEventListener('keydown', (e) => {
    // Use Ctrl (Windows/Linux) or Cmd (Mac) + Shift + key
    // Use e.code for reliable cross-platform detection
    const modifierKey = e.ctrlKey || e.metaKey;

    // Ctrl/Cmd+Shift+T - Toggle console panel
    if (modifierKey && e.shiftKey && e.code === 'KeyT') {
        e.preventDefault();
        toggleConsole();
    }
    // Ctrl/Cmd+Shift+D - Toggle print capture
    else if (modifierKey && e.shiftKey && e.code === 'KeyD') {
        e.preventDefault();
        const api = LabAPI.get();
        if (api && api.toggle_debug_mode) {
            api.toggle_debug_mode((result) => {
                const response = JSON.parse(result);
                if (response.enabled) {
                    addConsoleMessage('info', 'Print capture ENABLED');
                    LabModals.showInfo(
                        'Print Capture ENABLED',
                        'print() statements are now visible in the terminal panel.\n\nThis captures debug output that normally only appears in the system console.\n\nPress Ctrl+Shift+D again to disable.'
                    );
                } else {
                    addConsoleMessage('info', 'Print capture DISABLED');
                    LabModals.showInfo('Print Capture DISABLED', 'Print statements no longer captured to terminal.');
                }
            });
        }
    }
    // Ctrl/Cmd+Shift+E - Toggle analysis panel (staff mode)
    else if (modifierKey && e.shiftKey && e.code === 'KeyE') {
        e.preventDefault();
        toggleAnalysisPanel();
    }
});

// ============================================
// Global Exports for Python WebChannel
// ============================================

window.onMeasurementPoint = onMeasurementPoint;
window.onMeasurementComplete = onMeasurementComplete;
window.onMeasurementProgress = onMeasurementProgress;
window.onMeasurementStats = onMeasurementStats;
window.updateDeviceStatus = updateDeviceStatus;
window.onLogMessage = onLogMessage;

// Global exports for onclick handlers in HTML
window.switchTab = switchTab;
window.toggleMeasurement = toggleMeasurement;
window.saveData = saveData;
window.useSessionData = useSessionData;
window.loadCSVFile = loadCSVFile;
window.onCSVFileSelected = onCSVFileSelected;
window.calculateParameters = calculateParameters;
window.saveAnalysisResults = saveAnalysisResults;
window.toggleConsole = toggleConsole;
window.clearConsole = clearConsole;
window.copyConsole = copyConsole;
window.toggleTheme = () => LabTheme.toggle();

// Stability test exports
window.startStabilityTest = startStabilityTest;
window.stopStabilityTest = stopStabilityTest;
window.saveStabilityData = saveStabilityData;
window.onStabilityMeasurement = onStabilityMeasurement;
window.onStabilityComplete = onStabilityComplete;
window.onStabilityError = onStabilityError;
window.onStabilityStatus = onStabilityStatus;
