/**
 * I-V Measurement Application
 *
 * ES6 module for the J-V characterization interface.
 * Uses shared modules: LabAPI, LabTheme, LabModals (loaded via global scripts)
 */

// ============================================
// State
// ============================================

const state = {
    isMeasuring: false,
    currentPixel: null,
    forwardData: { x: [], y: [] },
    reverseData: { x: [], y: [] },
    isOfflineMode: false,
    isDeviceConnected: false,
    activeTab: 'measurement',

    // Analysis state
    analysis: {
        visible: false,
        forwardData: null,  // { voltages: [], currents: [] }
        reverseData: null,
        metrics: null,
        cellNumber: null,
        pixel: null,
        sourceFile: null
    }
};

// ============================================
// Plot Configuration (uses PlotlyUtils)
// ============================================

// Convenience aliases for PlotlyUtils
const plotConfig = PlotlyUtils.config;

function getPlotLayout(isDark) {
    return PlotlyUtils.getJVLayout(isDark);
}

function updatePlotTheme(plotId, isDark) {
    PlotlyUtils.updateTheme(plotId, isDark);
}

// ============================================
// Initialization
// ============================================

async function init() {
    LabTheme.init();
    LabModals.init();
    await LabAPI.init();

    // Small delay to ensure Plotly is ready
    setTimeout(() => {
        initPlot();
        checkDeviceStatus();

        // Prompt for cell number on startup
        LabModals.showCell((cellNumber) => {
            document.getElementById('cell-number').value = cellNumber;
        });
    }, 50);
}

// ============================================
// Tab Navigation
// ============================================

function switchTab(tabName) {
    // Prevent switching during active measurements
    if (state.isMeasuring) {
        LabModals.showError('Cannot Switch', 'Please stop the current measurement before switching tabs.');
        return;
    }

    state.activeTab = tabName;

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
    } else {
        setTimeout(() => {
            Plotly.Plots.resize('jv-plot');
        }, 50);
    }
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

// ============================================
// Measurement Tab Functions
// ============================================

function initPlot() {
    clearPlot();
}

function clearPlot() {
    const plotDiv = document.getElementById('jv-plot');
    const layout = getPlotLayout(LabTheme.isDark());
    const traces = [
        { x: [], y: [], mode: 'markers', type: 'scatter', name: 'Forward', marker: { color: '#4A90D9', size: 8 } },
        { x: [], y: [], mode: 'markers', type: 'scatter', name: 'Reverse', marker: { color: '#e57373', size: 8 } }
    ];
    Plotly.newPlot(plotDiv, traces, layout, plotConfig);
}

function updatePlot() {
    const plotDiv = document.getElementById('jv-plot');
    const layout = getPlotLayout(LabTheme.isDark());
    const traces = [
        { x: state.forwardData.x, y: state.forwardData.y, mode: 'markers', type: 'scatter', name: 'Forward', marker: { color: '#4A90D9', size: 8 } },
        { x: state.reverseData.x, y: state.reverseData.y, mode: 'markers', type: 'scatter', name: 'Reverse', marker: { color: '#e57373', size: 8 } }
    ];
    Plotly.newPlot(plotDiv, traces, layout, plotConfig);
}

async function checkDeviceStatus() {
    try {
        const api = LabAPI.get();
        if (api && api.get_device_status) {
            api.get_device_status((result) => {
                const status = JSON.parse(result);
                state.isOfflineMode = status.offline_mode;
                state.isDeviceConnected = status.connected;
                updateDeviceStatus(status.connected, status.message, status.offline_mode);
            });
        } else {
            state.isOfflineMode = true;
            state.isDeviceConnected = false;
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

    state.isDeviceConnected = connected;
    state.isOfflineMode = offlineMode;

    if (connected) {
        dot.className = 'device-dot connected';
        text.textContent = message || 'Connected';
        btn.disabled = false;
    } else if (offlineMode) {
        dot.className = 'device-dot warning';
        text.textContent = message || 'Offline mode';
        btn.disabled = false;
    } else {
        dot.className = 'device-dot disconnected';
        text.textContent = message || 'Not connected';
        btn.disabled = true;
    }
}

function toggleMeasurement() {
    if (state.isMeasuring) {
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
    state.currentPixel = pixel;
    state.isMeasuring = true;
    updateMeasuringState(true);
    updateProgress(0, 'Starting forward sweep...');

    state.forwardData = { x: [], y: [] };
    state.reverseData = { x: [], y: [] };
    document.getElementById('save-btn').disabled = true;
    clearPlot();
    updatePixelLabel(pixel);

    const params = {
        start_voltage: parseFloat(document.getElementById('start-voltage').value),
        stop_voltage: parseFloat(document.getElementById('stop-voltage').value),
        step_voltage: parseFloat(document.getElementById('step-voltage').value),
        cell_number: document.getElementById('cell-number').value,
        pixel: pixel
    };

    if (state.isDeviceConnected) {
        console.log('Starting hardware measurement with params:', params);
        const api = LabAPI.get();
        if (api && api.start_measurement) {
            api.start_measurement(JSON.stringify(params), (result) => {
                const response = JSON.parse(result);
                if (!response.success) {
                    LabModals.showError('Measurement Failed', response.message);
                    state.isMeasuring = false;
                    updateMeasuringState(false);
                }
            });
        }
    } else if (state.isOfflineMode) {
        console.log('Starting mock measurement with params:', params);
        mockMeasurement(params);
    } else {
        LabModals.showError('No Device', 'No device connected. Use --offline flag for testing.');
        state.isMeasuring = false;
        updateMeasuringState(false);
    }
}

function stopMeasurement() {
    state.isMeasuring = false;
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
        state.forwardData.x.push(voltage);
        state.forwardData.y.push(current);
    } else {
        state.reverseData.x.push(voltage);
        state.reverseData.y.push(current);
    }
    updatePlot();
}

function onMeasurementComplete(success) {
    state.isMeasuring = false;
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

function onMeasurementProgress(percent, message) {
    updateProgress(percent, message);
}

function saveData() {
    const cellNumber = document.getElementById('cell-number').value || '000';
    const pixel = state.currentPixel || 1;

    let csv = 'Direction,Voltage (V),Current (mA)\n';

    for (let i = 0; i < state.forwardData.x.length; i++) {
        csv += `Forward,${state.forwardData.x[i].toFixed(4)},${state.forwardData.y[i].toFixed(6)}\n`;
    }

    for (let i = 0; i < state.reverseData.x.length; i++) {
        csv += `Reverse,${state.reverseData.x[i].toFixed(4)},${state.reverseData.y[i].toFixed(6)}\n`;
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

// ============================================
// Mock Measurement (Offline Mode)
// ============================================

function mockMeasurement(params) {
    const start = params.start_voltage;
    const stop = params.stop_voltage;
    const step = params.step_voltage;
    const totalSteps = Math.ceil((stop - start) / step);
    let stepCount = 0;

    let voltage = start;
    const interval = setInterval(() => {
        if (!state.isMeasuring || voltage > stop) {
            clearInterval(interval);
            if (state.isMeasuring) {
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
        if (!state.isMeasuring || voltage < stop) {
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

// ============================================
// Analysis Tab Functions
// ============================================

function initAnalysisPlot() {
    const plotDiv = document.getElementById('iv-analysis-plot');
    const layout = getPlotLayout(LabTheme.isDark());
    const traces = [
        { x: [], y: [], mode: 'lines+markers', type: 'scatter', name: 'Forward', line: { color: '#4A90D9' }, marker: { size: 6 } },
        { x: [], y: [], mode: 'lines+markers', type: 'scatter', name: 'Reverse', line: { color: '#e57373' }, marker: { size: 6 } },
        { x: [], y: [], mode: 'markers', type: 'scatter', name: 'Voc', marker: { color: '#00C853', size: 12, symbol: 'diamond' } },
        { x: [], y: [], mode: 'markers', type: 'scatter', name: 'Isc', marker: { color: '#FF6D00', size: 12, symbol: 'diamond' } },
        { x: [], y: [], mode: 'markers', type: 'scatter', name: 'MPP', marker: { color: '#AA00FF', size: 14, symbol: 'star' } }
    ];
    Plotly.newPlot(plotDiv, traces, layout, plotConfig);
}

function updateSessionButton() {
    const btn = document.getElementById('use-session-btn');
    btn.disabled = state.forwardData.x.length === 0 && state.reverseData.x.length === 0;
}

function useSessionData() {
    if (state.forwardData.x.length === 0 && state.reverseData.x.length === 0) {
        setAnalysisStatus('No session data', 'error');
        return;
    }

    if (state.forwardData.x.length > 0) {
        state.analysis.forwardData = {
            voltages: [...state.forwardData.x],
            currents: [...state.forwardData.y]
        };
    }
    if (state.reverseData.x.length > 0) {
        state.analysis.reverseData = {
            voltages: [...state.reverseData.x],
            currents: [...state.reverseData.y]
        };
    }

    // Get cell/pixel from measurement tab
    state.analysis.cellNumber = document.getElementById('cell-number').value || null;
    state.analysis.pixel = state.currentPixel;
    state.analysis.sourceFile = 'Session';

    const fwdPts = state.forwardData.x.length;
    const revPts = state.reverseData.x.length;
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
            state.analysis.forwardData = result.forward;
            state.analysis.reverseData = result.reverse;

            // Extract cell/pixel from filename
            const extracted = extractCellPixelFromFilename(file.name);
            state.analysis.cellNumber = extracted.cell;
            state.analysis.pixel = extracted.pixel;
            state.analysis.sourceFile = file.name;

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

function extractCellPixelFromFilename(filename) {
    const cellMatch = filename.match(/cell(\d+)/i);
    const pixelMatch = filename.match(/pixel(\d+)/i);
    return {
        cell: cellMatch ? cellMatch[1] : null,
        pixel: pixelMatch ? parseInt(pixelMatch[1]) : null
    };
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
    const hasData = (sweepType === 'forward' && state.analysis.forwardData) ||
                   (sweepType === 'reverse' && state.analysis.reverseData);
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
    const data = sweepType === 'forward' ? state.analysis.forwardData : state.analysis.reverseData;

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
            jsc = Math.abs(isc) / area;  // mA/cm²
            pce = (pmax / (area * 100)) * 100;  // % (assuming 100 mW/cm² AM1.5G)
        }

        // Store metrics
        state.analysis.metrics = {
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
    const m = state.analysis.metrics;
    if (!m) return;

    // PCE - headline metric (only show if area was provided)
    const pceGroup = document.getElementById('pce-metric-group');
    if (m.pce !== null) {
        pceGroup.style.display = '';
        document.getElementById('metric-pce').textContent = m.pce.toFixed(2) + ' %';
    } else {
        pceGroup.style.display = 'none';
    }

    // Jsc/Isc
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

    // Voc, FF, Pmax
    document.getElementById('metric-voc').textContent = m.voc.toFixed(3) + ' V';
    document.getElementById('metric-ff').textContent = (m.ff * 100).toFixed(1) + ' %';
    document.getElementById('metric-pmax').textContent = m.pmax.toFixed(3) + ' mW';

    // MPP values
    document.getElementById('metric-vmpp').textContent = m.vmpp.toFixed(3) + ' V';
    document.getElementById('metric-impp').textContent = m.impp.toFixed(3) + ' mA';

    // Resistances
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
        line: { color: '#4A90D9' },
        marker: { size: 6 }
    };
    const revTrace = {
        x: sweepType === 'reverse' ? voltages : [],
        y: sweepType === 'reverse' ? currents : [],
        mode: 'lines+markers',
        type: 'scatter',
        name: 'Reverse',
        line: { color: '#e57373' },
        marker: { size: 6 }
    };

    const vocTrace = {
        x: [voc],
        y: [0],
        mode: 'markers',
        type: 'scatter',
        name: `Voc (${voc.toFixed(3)} V)`,
        marker: { color: '#00C853', size: 12, symbol: 'diamond' }
    };
    const iscTrace = {
        x: [0],
        y: [isc],
        mode: 'markers',
        type: 'scatter',
        name: `Isc (${isc.toFixed(3)} mA)`,
        marker: { color: '#FF6D00', size: 12, symbol: 'diamond' }
    };
    const mppTrace = {
        x: [vmpp],
        y: [impp],
        mode: 'markers',
        type: 'scatter',
        name: `MPP (${(vmpp * Math.abs(impp)).toFixed(3)} mW)`,
        marker: { color: '#AA00FF', size: 14, symbol: 'star' }
    };

    Plotly.newPlot(plotDiv, [fwdTrace, revTrace, vocTrace, iscTrace, mppTrace], layout, plotConfig);
}

function saveAnalysisResults() {
    const m = state.analysis.metrics;
    if (!m) return;

    let csv = '# I-V Analysis Results\n';
    const now = new Date();
    const timestamp = now.toISOString().replace('T', ' ').split('.')[0];
    csv += `# Generated: ${timestamp}\n`;
    if (state.analysis.cellNumber) csv += `# Cell: ${state.analysis.cellNumber}\n`;
    if (state.analysis.pixel) csv += `# Pixel: ${state.analysis.pixel}\n`;
    if (state.analysis.sourceFile) csv += `# Source: ${state.analysis.sourceFile}\n`;
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

    const data = m.sweepType === 'forward' ? state.analysis.forwardData : state.analysis.reverseData;
    csv += 'Voltage (V),Current (mA)\n';
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

// ============================================
// Console Panel Functions
// ============================================

let consoleVisible = false;
const consoleMessages = [];
const MAX_CONSOLE_MESSAGES = 500;

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

function setupKeyboardShortcuts() {
    document.addEventListener('keydown', (e) => {
        // Ctrl+Shift+T - Toggle console panel
        if (e.ctrlKey && e.shiftKey && e.key === 'T') {
            e.preventDefault();
            toggleConsole();
        }
        // Ctrl+Shift+D - Toggle debug mode
        else if (e.ctrlKey && e.shiftKey && e.key === 'D') {
            e.preventDefault();
            const api = LabAPI.get();
            if (api && api.toggle_debug_mode) {
                api.toggle_debug_mode((result) => {
                    const response = JSON.parse(result);
                    if (response.enabled) {
                        addConsoleMessage('info', 'Debug mode ENABLED - verbose output now visible');
                        LabModals.showInfo(
                            'Debug Mode Enabled',
                            'Technical debug output is now visible in the console.\n\nPress Ctrl+Shift+D again to disable.'
                        );
                    } else {
                        addConsoleMessage('info', 'Debug mode DISABLED');
                        LabModals.showInfo('Debug Mode Disabled', 'Technical debug output is now hidden.');
                    }
                });
            }
        }
        // Ctrl+Shift+E - Toggle analysis panel (staff mode)
        else if (e.ctrlKey && e.shiftKey && e.key === 'E') {
            e.preventDefault();
            toggleAnalysisPanel();
        }
    });
}

// ============================================
// Event Listeners
// ============================================

function setupEventListeners() {
    // Resize handler
    window.addEventListener('resize', () => {
        if (typeof Plotly !== 'undefined') {
            if (state.activeTab === 'measurement') {
                Plotly.Plots.resize('jv-plot');
            } else if (state.activeTab === 'analysis') {
                Plotly.Plots.resize('iv-analysis-plot');
            }
        }
    });

    // Theme change handler
    window.addEventListener('themechange', (e) => {
        const plotDiv = document.getElementById('jv-plot');
        if (typeof Plotly !== 'undefined' && plotDiv && plotDiv.data) {
            updatePlotTheme('jv-plot', e.detail.dark);
        }
        const analysisPlot = document.getElementById('iv-analysis-plot');
        if (typeof Plotly !== 'undefined' && analysisPlot && analysisPlot.data) {
            updatePlotTheme('iv-analysis-plot', e.detail.dark);
        }
    });

    // Sweep selector changes
    document.querySelectorAll('input[name="sweep-select"]').forEach(radio => {
        radio.addEventListener('change', updateCalculateButton);
    });

    setupKeyboardShortcuts();
}

// ============================================
// Global Exports (for Python WebChannel callbacks)
// ============================================

window.onMeasurementPoint = onMeasurementPoint;
window.onMeasurementComplete = onMeasurementComplete;
window.onMeasurementProgress = onMeasurementProgress;
window.updateDeviceStatus = updateDeviceStatus;
window.onLogMessage = onLogMessage;

// Exports for onclick handlers in HTML
window.toggleMeasurement = toggleMeasurement;
window.saveData = saveData;
window.switchTab = switchTab;
window.toggleConsole = toggleConsole;
window.clearConsole = clearConsole;
window.useSessionData = useSessionData;
window.loadCSVFile = loadCSVFile;
window.onCSVFileSelected = onCSVFileSelected;
window.calculateParameters = calculateParameters;
window.saveAnalysisResults = saveAnalysisResults;

// ============================================
// Initialize on DOM Ready
// ============================================

document.addEventListener('DOMContentLoaded', () => {
    setupEventListeners();
    init();
});
