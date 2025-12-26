/**
 * Modal Management
 *
 * Shared modal components for lab applications.
 * Handles cell number input, pixel selection, and generic modal logic.
 */

// ==================== Generic Modal Helpers ====================

/**
 * Show a modal by adding the 'active' class.
 * @param {string} modalId - The modal element ID
 */
function showModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.classList.add('active');
    }
}

/**
 * Hide a modal by removing the 'active' class.
 * @param {string} modalId - The modal element ID
 */
function hideModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.classList.remove('active');
    }
}

// ==================== Cell Number Modal ====================

let _cellNumberCallback = null;

/**
 * Show the cell number modal.
 * @param {Function} onConfirm - Callback with cell number when confirmed
 */
function showCellModal(onConfirm) {
    _cellNumberCallback = onConfirm;
    showModal('cell-modal');
    // Wait for modal transition (200ms) to complete before focusing
    setTimeout(() => {
        const input = document.getElementById('cell-input');
        if (input) {
            input.focus();
            input.select();
        }
    }, 250);
}

/**
 * Hide the cell number modal.
 */
function closeCellModal() {
    hideModal('cell-modal');
    _cellNumberCallback = null;
}

/**
 * Validate and confirm the cell number.
 * Called by the Confirm/Continue button.
 */
function confirmCellNumber() {
    const input = document.getElementById('cell-input');
    const error = document.getElementById('cell-input-error');
    const value = input.value.trim();

    if (!/^\d{3}$/.test(value)) {
        input.classList.add('error');
        if (error) error.classList.add('visible');
        input.focus();
        return;
    }

    // Clear error state
    input.classList.remove('error');
    if (error) error.classList.remove('visible');

    // Call the callback with the cell number
    if (_cellNumberCallback) {
        _cellNumberCallback(value);
    }

    closeCellModal();
}

/**
 * Initialize cell modal event listeners.
 * Call this after DOM is ready.
 */
function initCellModal() {
    const input = document.getElementById('cell-input');
    const error = document.getElementById('cell-input-error');

    if (input) {
        // Enter key to confirm
        input.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                confirmCellNumber();
            }
        });

        // Clear error on typing
        input.addEventListener('input', () => {
            input.classList.remove('error');
            if (error) error.classList.remove('visible');
        });
    }
}

// ==================== Pixel Selection Modal ====================

let _pixelCallback = null;

/**
 * Show the pixel selection modal.
 * @param {Function} onConfirm - Callback with pixel number when confirmed
 */
function showPixelModal(onConfirm) {
    _pixelCallback = onConfirm;
    showModal('pixel-modal');
    // Wait for modal transition (200ms) to complete before focusing
    setTimeout(() => {
        const input = document.getElementById('pixel-input');
        if (input) {
            input.focus();
            input.select();
        }
    }, 250);
}

/**
 * Hide the pixel selection modal.
 */
function closePixelModal() {
    hideModal('pixel-modal');
    _pixelCallback = null;
}

/**
 * Validate and confirm the pixel number.
 * Called by the Start button.
 */
function confirmPixel() {
    const input = document.getElementById('pixel-input');
    const pixel = parseInt(input.value);

    // Get pixel range from config, fallback to [1, 8]
    const pixelRange = LabConfig.get('validation.pixel_range', [1, 8]);
    const minPixel = pixelRange[0];
    const maxPixel = pixelRange[1];

    if (isNaN(pixel) || pixel < minPixel || pixel > maxPixel) {
        alert(`Pixel must be between ${minPixel} and ${maxPixel}`);
        input.focus();
        return;
    }

    // Call the callback with the pixel number
    if (_pixelCallback) {
        _pixelCallback(pixel);
    }

    closePixelModal();
}

/**
 * Initialize pixel modal event listeners.
 * Call this after DOM is ready.
 */
function initPixelModal() {
    const input = document.getElementById('pixel-input');

    if (input) {
        // Enter key to confirm
        input.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                confirmPixel();
            }
        });
    }
}

// ==================== Save Data Modal ====================

let _saveCallback = null;

/**
 * Show the save data modal.
 * @param {Object} options - Available data options
 * @param {boolean} options.hasPower - Whether power data is available
 * @param {boolean} options.hasCurrent - Whether current data is available
 * @param {Function} onSave - Callback with 'power' or 'current' when confirmed
 */
function showSaveModal(options, onSave) {
    _saveCallback = onSave;

    // Update button states based on available data
    const powerBtn = document.getElementById('save-power-btn');
    const currentBtn = document.getElementById('save-current-btn');

    if (powerBtn) powerBtn.disabled = !options.hasPower;
    if (currentBtn) currentBtn.disabled = !options.hasCurrent;

    showModal('save-modal');
}

/**
 * Hide the save data modal.
 */
function closeSaveModal() {
    hideModal('save-modal');
    _saveCallback = null;
}

/**
 * Confirm saving power data.
 */
function confirmSavePower() {
    if (_saveCallback) {
        _saveCallback('power');
    }
    closeSaveModal();
}

/**
 * Confirm saving current data.
 */
function confirmSaveCurrent() {
    if (_saveCallback) {
        _saveCallback('current');
    }
    closeSaveModal();
}

// ==================== Log Viewer Modal ====================

let _logViewerOpen = false;

/**
 * Toggle the log viewer modal (Ctrl+Shift+L).
 */
async function toggleLogViewer() {
    if (_logViewerOpen) {
        closeLogViewer();
    } else {
        await showLogViewer();
    }
}

/**
 * Show the log viewer modal with recent logs.
 */
async function showLogViewer() {
    const api = getApi();
    if (!api) {
        console.warn('API not available for log viewer');
        return;
    }

    // Show modal first with loading state
    const logsContent = document.getElementById('log-viewer-content');
    const logsPath = document.getElementById('log-viewer-path');
    if (logsContent) {
        logsContent.textContent = 'Loading logs...';
    }
    showModal('log-viewer-modal');
    _logViewerOpen = true;

    // Fetch logs from Python
    try {
        api.get_recent_logs(500, function(result) {
            try {
                const response = JSON.parse(result);
                if (response.success) {
                    if (logsContent) {
                        logsContent.textContent = response.logs || '(No log entries)';
                        // Scroll to bottom to show most recent
                        logsContent.scrollTop = logsContent.scrollHeight;
                    }
                    if (logsPath) {
                        logsPath.textContent = response.path || '';
                    }
                } else {
                    if (logsContent) {
                        logsContent.textContent = `Error: ${response.message}`;
                    }
                }
            } catch (e) {
                if (logsContent) {
                    logsContent.textContent = `Error parsing response: ${e}`;
                }
            }
        });
    } catch (e) {
        if (logsContent) {
            logsContent.textContent = `Error fetching logs: ${e}`;
        }
    }
}

/**
 * Close the log viewer modal.
 */
function closeLogViewer() {
    hideModal('log-viewer-modal');
    _logViewerOpen = false;
}

/**
 * Refresh logs in the log viewer.
 */
async function refreshLogs() {
    const api = getApi();
    if (!api) return;

    const logsContent = document.getElementById('log-viewer-content');
    if (logsContent) {
        logsContent.textContent = 'Refreshing...';
    }

    api.get_recent_logs(500, function(result) {
        try {
            const response = JSON.parse(result);
            if (response.success && logsContent) {
                logsContent.textContent = response.logs || '(No log entries)';
                logsContent.scrollTop = logsContent.scrollHeight;
            }
        } catch (e) {
            console.error('Error refreshing logs:', e);
        }
    });
}

/**
 * Copy log content to clipboard.
 */
function copyLogs() {
    const logsContent = document.getElementById('log-viewer-content');
    if (logsContent) {
        navigator.clipboard.writeText(logsContent.textContent).then(() => {
            // Brief visual feedback
            const copyBtn = document.getElementById('log-copy-btn');
            if (copyBtn) {
                const originalText = copyBtn.textContent;
                copyBtn.textContent = 'Copied!';
                setTimeout(() => { copyBtn.textContent = originalText; }, 1500);
            }
        }).catch(err => {
            console.error('Failed to copy logs:', err);
        });
    }
}

/**
 * Get the HTML for the log viewer modal.
 * @returns {string} Modal HTML
 */
function getLogViewerModalHTML() {
    return `
    <div class="modal-overlay" id="log-viewer-modal">
        <div class="modal log-viewer-modal">
            <div class="modal-title">
                Debug Logs
                <span class="modal-subtitle" id="log-viewer-path"></span>
            </div>
            <div class="modal-body log-viewer-body">
                <pre class="log-viewer-content" id="log-viewer-content">Loading...</pre>
            </div>
            <div class="modal-footer">
                <button class="btn btn-secondary" id="log-copy-btn" onclick="LabModals.copyLogs()">Copy</button>
                <button class="btn btn-secondary" onclick="LabModals.refreshLogs()">Refresh</button>
                <button class="btn btn-primary" onclick="LabModals.closeLogViewer()">Close</button>
            </div>
        </div>
    </div>`;
}

/**
 * Initialize log viewer keyboard shortcuts.
 * Ctrl+Shift+L toggles the log viewer.
 * Escape closes it when open.
 */
function initLogViewerShortcut() {
    document.addEventListener('keydown', (e) => {
        if (e.ctrlKey && e.shiftKey && e.key === 'L') {
            e.preventDefault();
            toggleLogViewer();
        }
        // Escape closes the log viewer if open
        if (e.key === 'Escape' && _logViewerOpen) {
            e.preventDefault();
            closeLogViewer();
        }
    });
}

// ==================== Error Modal ====================

/**
 * Show the error modal with a message.
 * @param {string} title - The error title
 * @param {string} message - The error message
 */
function showErrorModal(title, message) {
    const titleEl = document.getElementById('error-modal-title');
    const messageEl = document.getElementById('error-modal-message');

    if (titleEl) titleEl.textContent = title;
    if (messageEl) messageEl.textContent = message;

    showModal('error-modal');

    // Focus OK button after modal transition so Enter dismisses it
    setTimeout(() => {
        const okBtn = document.querySelector('#error-modal .btn-primary');
        if (okBtn) okBtn.focus();
    }, 250);
}

/**
 * Hide the error modal.
 */
function closeErrorModal() {
    hideModal('error-modal');
}

// ==================== Info Modal ====================

/**
 * Show an info/notification modal with a message.
 * @param {string} title - The modal title
 * @param {string} message - The modal message
 */
function showInfoModal(title, message) {
    const titleEl = document.getElementById('info-modal-title');
    const messageEl = document.getElementById('info-modal-message');

    if (titleEl) titleEl.textContent = title;
    if (messageEl) messageEl.textContent = message;

    showModal('info-modal');

    // Focus OK button after modal transition so Enter dismisses it
    setTimeout(() => {
        const okBtn = document.querySelector('#info-modal .btn-primary');
        if (okBtn) okBtn.focus();
    }, 250);
}

/**
 * Hide the info modal.
 */
function closeInfoModal() {
    hideModal('info-modal');
}

// ==================== HTML Templates ====================

/**
 * Get the HTML for a cell number modal.
 * @returns {string} Modal HTML
 */
function getCellModalHTML() {
    return `
    <div class="modal-overlay" id="cell-modal">
        <div class="modal">
            <div class="modal-title">Enter Cell Number</div>
            <div class="modal-body">
                <div class="input-group mb-0">
                    <label for="cell-input">Cell Number (e.g., 195)</label>
                    <input type="text" id="cell-input" pattern="[0-9]{3}" maxlength="3" placeholder="000">
                    <span class="input-error" id="cell-input-error">Please enter a 3-digit cell number</span>
                </div>
            </div>
            <div class="modal-footer">
                <button class="btn btn-primary" onclick="LabModals.confirmCell()">Continue</button>
            </div>
        </div>
    </div>`;
}

/**
 * Get the HTML for a pixel selection modal.
 * @param {Object} options - Configuration options
 * @param {number} options.min - Minimum pixel number (default from config)
 * @param {number} options.max - Maximum pixel number (default from config)
 * @param {boolean} options.showCancel - Show cancel button (default: true)
 * @returns {string} Modal HTML
 */
function getPixelModalHTML(options = {}) {
    // Get pixel range from config, fallback to [1, 8]
    const pixelRange = LabConfig.get('validation.pixel_range', [1, 8]);
    const min = options.min || pixelRange[0];
    const max = options.max || pixelRange[1];
    const showCancel = options.showCancel !== false;

    return `
    <div class="modal-overlay" id="pixel-modal">
        <div class="modal">
            <div class="modal-title">Select Pixel</div>
            <div class="modal-body">
                <div class="input-group mb-0">
                    <label for="pixel-input">Pixel Number (${min}-${max})</label>
                    <input type="number" id="pixel-input" min="${min}" max="${max}" value="1">
                </div>
            </div>
            <div class="modal-footer">
                ${showCancel ? '<button class="btn btn-secondary" onclick="LabModals.closePixel()">Cancel</button>' : ''}
                <button class="btn btn-primary" onclick="LabModals.confirmPixel()">Start</button>
            </div>
        </div>
    </div>`;
}

/**
 * Get the HTML for a save data modal.
 * @returns {string} Modal HTML
 */
function getSaveModalHTML() {
    return `
    <div class="modal-overlay" id="save-modal">
        <div class="modal">
            <div class="modal-title">Save Data</div>
            <div class="modal-body">
                <p style="margin-bottom: 16px; color: var(--text-secondary);">Which data would you like to save?</p>
                <div class="save-options">
                    <button class="btn btn-primary btn-block" id="save-power-btn" onclick="LabModals.confirmSavePower()" style="margin-bottom: 8px;">
                        Save Power Data
                    </button>
                    <button class="btn btn-primary btn-block" id="save-current-btn" onclick="LabModals.confirmSaveCurrent()">
                        Save Current Data
                    </button>
                </div>
            </div>
            <div class="modal-footer">
                <button class="btn btn-secondary" onclick="LabModals.closeSave()">Cancel</button>
            </div>
        </div>
    </div>`;
}

/**
 * Get the HTML for an error modal.
 * @returns {string} Modal HTML
 */
function getErrorModalHTML() {
    return `
    <div class="modal-overlay" id="error-modal">
        <div class="modal">
            <div class="modal-title" id="error-modal-title">Error</div>
            <div class="modal-body">
                <p id="error-modal-message" style="color: var(--text-secondary);"></p>
            </div>
            <div class="modal-footer">
                <button class="btn btn-primary" onclick="LabModals.closeError()">OK</button>
            </div>
        </div>
    </div>`;
}

/**
 * Get the HTML for an info modal.
 * @returns {string} Modal HTML
 */
function getInfoModalHTML() {
    return `
    <div class="modal-overlay" id="info-modal">
        <div class="modal">
            <div class="modal-title" id="info-modal-title">Info</div>
            <div class="modal-body">
                <p id="info-modal-message" style="color: var(--text-secondary); white-space: pre-line;"></p>
            </div>
            <div class="modal-footer">
                <button class="btn btn-primary" onclick="LabModals.closeInfo()">OK</button>
            </div>
        </div>
    </div>`;
}

/**
 * Initialize all modal event listeners.
 * Call this after DOM is ready.
 */
function initModals() {
    initCellModal();
    initPixelModal();
    initLogViewerShortcut();
}

// Export for use in other modules
window.LabModals = {
    // Generic
    show: showModal,
    hide: hideModal,
    init: initModals,

    // Cell modal
    showCell: showCellModal,
    closeCell: closeCellModal,
    confirmCell: confirmCellNumber,
    initCell: initCellModal,
    getCellHTML: getCellModalHTML,

    // Pixel modal
    showPixel: showPixelModal,
    closePixel: closePixelModal,
    confirmPixel: confirmPixel,
    initPixel: initPixelModal,
    getPixelHTML: getPixelModalHTML,

    // Save modal
    showSave: showSaveModal,
    closeSave: closeSaveModal,
    confirmSavePower: confirmSavePower,
    confirmSaveCurrent: confirmSaveCurrent,
    getSaveHTML: getSaveModalHTML,

    // Error modal
    showError: showErrorModal,
    closeError: closeErrorModal,
    getErrorHTML: getErrorModalHTML,

    // Info modal
    showInfo: showInfoModal,
    closeInfo: closeInfoModal,
    getInfoHTML: getInfoModalHTML,

    // Log viewer modal
    showLogViewer: showLogViewer,
    closeLogViewer: closeLogViewer,
    toggleLogViewer: toggleLogViewer,
    refreshLogs: refreshLogs,
    copyLogs: copyLogs,
    getLogViewerHTML: getLogViewerModalHTML,
};

// Also expose individual functions globally for onclick handlers
window.showCellModal = showCellModal;
window.closeCellModal = closeCellModal;
window.confirmCellNumber = confirmCellNumber;
window.showPixelModal = showPixelModal;
window.closePixelModal = closePixelModal;
window.confirmPixel = confirmPixel;
window.closeSaveModal = closeSaveModal;
window.confirmSavePower = confirmSavePower;
window.confirmSaveCurrent = confirmSaveCurrent;
