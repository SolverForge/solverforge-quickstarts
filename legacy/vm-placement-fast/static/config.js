/**
 * VM Placement Configuration Module
 *
 * Provides configurable infrastructure and workload settings for the VM placement
 * quickstart, including sliders for racks, servers, VMs, and solver time.
 */

// =============================================================================
// Configuration State
// =============================================================================

let currentConfig = {
    rackCount: 3,
    serversPerRack: 4,
    vmCount: 20,
    solverTime: 30
};

// =============================================================================
// Initialization
// =============================================================================

/**
 * Initialize configuration UI and event handlers.
 * Called automatically when the script loads.
 */
function initConfig() {
    // Rack count slider
    $("#rackCountSlider").on("input", function() {
        currentConfig.rackCount = parseInt(this.value);
        $("#rackCountValue").text(this.value);
        updateConfigSummary();
    });

    // Servers per rack slider
    $("#serversPerRackSlider").on("input", function() {
        currentConfig.serversPerRack = parseInt(this.value);
        $("#serversPerRackValue").text(this.value);
        updateConfigSummary();
    });

    // VM count slider
    $("#vmCountSlider").on("input", function() {
        currentConfig.vmCount = parseInt(this.value);
        $("#vmCountValue").text(this.value);
        updateConfigSummary();
    });

    // Solver time slider
    $("#solverTimeSlider").on("input", function() {
        currentConfig.solverTime = parseInt(this.value);
        $("#solverTimeValue").text(formatSolverTime(this.value));
    });

    // Generate button
    $("#generateDataBtn").click(function() {
        generateCustomData();
    });

    // Initialize summary
    updateConfigSummary();
}

// =============================================================================
// UI Updates
// =============================================================================

function updateConfigSummary() {
    const totalServers = currentConfig.rackCount * currentConfig.serversPerRack;
    $("#configSummary").text(
        `${totalServers} servers across ${currentConfig.rackCount} rack${currentConfig.rackCount > 1 ? 's' : ''}, ` +
        `${currentConfig.vmCount} VMs to place`
    );
}

function formatSolverTime(seconds) {
    if (seconds >= 60) {
        const mins = Math.floor(seconds / 60);
        const secs = seconds % 60;
        return secs > 0 ? `${mins}m ${secs}s` : `${mins}m`;
    }
    return `${seconds}s`;
}

// =============================================================================
// Data Generation
// =============================================================================

function generateCustomData() {
    const btn = $("#generateDataBtn");
    const originalHtml = btn.html();

    // Show loading state
    btn.prop("disabled", true);
    btn.html('<i class="fas fa-spinner fa-spin me-1"></i> Generating...');

    $.ajax({
        url: "/demo-data/generate",
        type: "POST",
        data: JSON.stringify({
            rack_count: currentConfig.rackCount,
            servers_per_rack: currentConfig.serversPerRack,
            vm_count: currentConfig.vmCount
        }),
        contentType: "application/json"
    })
    .done(function(placement) {
        // Reset animation state for new data
        isFirstRender = true;
        vmPositionCache = {};
        previousScore = null;
        placementId = null;

        // Store and render new data
        loadedPlacement = placement;
        renderPlacement(placement);

        // Flash success
        btn.html('<i class="fas fa-check me-1"></i> Generated!');
        btn.removeClass("btn-primary").addClass("btn-success");

        setTimeout(() => {
            btn.html(originalHtml);
            btn.removeClass("btn-success").addClass("btn-primary");
            btn.prop("disabled", false);
        }, 1500);
    })
    .fail(function(xhr) {
        showError("Failed to generate custom data", xhr);
        btn.html(originalHtml);
        btn.prop("disabled", false);
    });
}

// =============================================================================
// Solver Time Integration
// =============================================================================

/**
 * Get the current solver time setting.
 * Can be used by app.js to configure solver termination.
 */
function getSolverTime() {
    return currentConfig.solverTime;
}

/**
 * Get the current configuration.
 */
function getCurrentConfig() {
    return { ...currentConfig };
}

// Export for use in app.js
window.currentConfig = currentConfig;
window.getSolverTime = getSolverTime;
window.getCurrentConfig = getCurrentConfig;
window.initConfig = initConfig;

// Initialize when DOM is ready
$(document).ready(function() {
    initConfig();
});
