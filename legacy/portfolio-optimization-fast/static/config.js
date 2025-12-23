/**
 * Advanced Configuration Module
 *
 * This module provides advanced configuration options for the portfolio optimization
 * quickstart, including presets and configurable solver parameters.
 *
 * NOTE: This is an optional enhancement. The core quickstart works without this module.
 * To use it, include this script after app.js and call initAdvancedConfig().
 */

// =============================================================================
// Configuration Presets
// =============================================================================

const PRESETS = {
    conservative: {
        targetStocks: 30,
        maxSector: 15,
        solverTime: 60,
        description: "Max diversification: 30 stocks, tight sector limits, longer solve time."
    },
    balanced: {
        targetStocks: 20,
        maxSector: 25,
        solverTime: 30,
        description: "Balanced settings for typical portfolio optimization."
    },
    aggressive: {
        targetStocks: 10,
        maxSector: 40,
        solverTime: 30,
        description: "Concentrated bets: fewer stocks, looser sector limits."
    },
    quick: {
        targetStocks: 20,
        maxSector: 25,
        solverTime: 10,
        description: "Fast iteration: same as balanced but 10s solve time."
    }
};

// Current configuration state
let currentConfig = { ...PRESETS.balanced };

// =============================================================================
// Initialization
// =============================================================================

/**
 * Initialize advanced configuration UI and event handlers.
 * Call this after the DOM is ready.
 */
function initAdvancedConfig() {
    // Preset selector
    $("#presetSelector").change(function() {
        const preset = $(this).val();
        if (preset !== "custom" && PRESETS[preset]) {
            // Use Object.assign to mutate in place - preserves window.currentConfig reference
            Object.assign(currentConfig, PRESETS[preset]);
            updateConfigSliders();
            updatePresetDescription(preset);
            applyConfigToLoadedPlan();
        }
    });

    // Target stocks slider
    $("#targetStocksSlider").on("input", function() {
        currentConfig.targetStocks = parseInt(this.value);
        $("#targetStocksValue").text(this.value);
        markAsCustom();
        applyConfigToLoadedPlan();
    });

    // Max sector slider
    $("#maxSectorSlider").on("input", function() {
        currentConfig.maxSector = parseInt(this.value);
        $("#maxSectorValue").text(this.value + "%");
        markAsCustom();
        applyConfigToLoadedPlan();
    });

    // Solver time slider
    $("#solverTimeSlider").on("input", function() {
        currentConfig.solverTime = parseInt(this.value);
        $("#solverTimeValue").text(formatSolverTime(this.value));
        markAsCustom();
        applyConfigToLoadedPlan();
    });
}

// =============================================================================
// Configuration UI Updates
// =============================================================================

function updateConfigSliders() {
    $("#targetStocksSlider").val(currentConfig.targetStocks);
    $("#targetStocksValue").text(currentConfig.targetStocks);

    $("#maxSectorSlider").val(currentConfig.maxSector);
    $("#maxSectorValue").text(currentConfig.maxSector + "%");

    $("#solverTimeSlider").val(currentConfig.solverTime);
    $("#solverTimeValue").text(formatSolverTime(currentConfig.solverTime));
}

function formatSolverTime(seconds) {
    if (seconds >= 60) {
        const mins = Math.floor(seconds / 60);
        const secs = seconds % 60;
        return secs > 0 ? `${mins}m ${secs}s` : `${mins}m`;
    }
    return `${seconds}s`;
}

function markAsCustom() {
    // Check if current settings match any preset
    for (const [name, preset] of Object.entries(PRESETS)) {
        if (preset.targetStocks === currentConfig.targetStocks &&
            preset.maxSector === currentConfig.maxSector &&
            preset.solverTime === currentConfig.solverTime) {
            $("#presetSelector").val(name);
            updatePresetDescription(name);
            return;
        }
    }
    // No match - mark as custom
    $("#presetSelector").val("custom");
    updatePresetDescription("custom");
}

function updatePresetDescription(preset) {
    const descriptions = {
        conservative: PRESETS.conservative.description,
        balanced: PRESETS.balanced.description,
        aggressive: PRESETS.aggressive.description,
        quick: PRESETS.quick.description,
        custom: "Custom configuration. Adjust sliders to your needs."
    };
    $("#presetDescription").text(descriptions[preset] || descriptions.custom);
}

// =============================================================================
// Apply Configuration to Plan
// =============================================================================

/**
 * Apply current configuration to the loaded plan.
 * This updates the plan object that will be sent to the solver.
 */
function applyConfigToLoadedPlan() {
    // loadedPlan is defined in app.js
    if (typeof loadedPlan !== 'undefined' && loadedPlan) {
        loadedPlan.targetPositionCount = currentConfig.targetStocks;
        loadedPlan.maxSectorPercentage = currentConfig.maxSector / 100;
        loadedPlan.solverConfig = {
            terminationSeconds: currentConfig.solverTime
        };
    }
}

/**
 * Get the current configuration.
 * @returns {Object} Current configuration with targetStocks, maxSector, solverTime
 */
function getCurrentConfig() {
    return { ...currentConfig };
}

/**
 * Get target stock count from current configuration.
 * Used by app.js for KPI display.
 */
function getTargetStockCount() {
    return currentConfig.targetStocks;
}

// Export for use in app.js
window.PRESETS = PRESETS;
window.currentConfig = currentConfig;
window.initAdvancedConfig = initAdvancedConfig;
window.applyConfigToLoadedPlan = applyConfigToLoadedPlan;
window.getCurrentConfig = getCurrentConfig;
window.getTargetStockCount = getTargetStockCount;
