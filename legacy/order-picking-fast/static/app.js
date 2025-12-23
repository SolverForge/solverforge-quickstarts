/**
 * Order Picking Optimization - Frontend Application
 *
 * This application demonstrates real-time constraint optimization for warehouse
 * order picking. It uses SolverForge (a constraint solver) to optimize which
 * trolley picks which items and in what order, minimizing total travel distance
 * while respecting capacity constraints.
 *
 * Architecture:
 * - Backend: FastAPI server with SolverForge solver
 * - Frontend: jQuery + Canvas for visualization
 * - Communication: REST API with 250ms polling for real-time updates
 *
 * Key concepts:
 * - Planning entities: TrolleySteps (items to pick)
 * - Planning variable: Which trolley picks each step
 * - Constraints: Bucket capacity (hard), minimize distance (soft)
 */

// =============================================================================
// Application State
// =============================================================================

/** Current solution data from the solver */
let loadedSchedule = null;

/** Active problem ID when solving (null when not solving) */
let currentProblemId = null;

/** Interval ID for polling updates during solving */
let autoRefreshIntervalId = null;

/** Last score string for detecting improvements */
let lastScore = null;

/** Cached distances per trolley (Map<trolleyId, distance>) */
let distances = new Map();

/** Tracks user intent to solve (prevents race condition with solver startup) */
let userRequestedSolving = false;

// =============================================================================
// Initialization
// =============================================================================

/**
 * Initialize the application when the DOM is ready.
 * Sets up event handlers and loads initial demo data.
 */
$(document).ready(function() {
    // Add SolverForge header and footer branding
    replaceQuickstartSolverForgeAutoHeaderFooter();

    // Initialize the isometric 3D warehouse canvas
    initWarehouseCanvas();

    // Load default demo data to show something immediately
    loadDemoData();

    // Wire up button click handlers
    $("#solveButton").click(solve);
    $("#stopSolvingButton").click(stopSolving);
    $("#analyzeButton").click(analyze);
    $("#generateButton").click(generateNewData);

    // Update displayed values when sliders change
    $("#ordersCountSlider").on("input", function() {
        $("#ordersCountValue").text($(this).val());
    });
    $("#trolleysCountSlider").on("input", function() {
        $("#trolleysCountValue").text($(this).val());
    });
    $("#bucketsCountSlider").on("input", function() {
        $("#bucketsCountValue").text($(this).val());
    });

    // Redraw warehouse on window resize
    window.addEventListener('resize', () => {
        initWarehouseCanvas();
        if (loadedSchedule) {
            renderWarehouse(loadedSchedule);
        }
    });
});

// =============================================================================
// Data Loading
// =============================================================================

/**
 * Load the default demo dataset from the server.
 * This provides a starting point with pre-configured orders and trolleys.
 */
function loadDemoData() {
    fetch('/demo-data/DEFAULT')
        .then(r => r.json())
        .then(solution => {
            loadedSchedule = solution;
            currentProblemId = null;
            updateUI(solution, false);
        })
        .catch(error => {
            showError("Failed to load demo data", error);
        });
}

/**
 * Generate new random demo data based on slider settings.
 * Allows testing with different problem sizes.
 */
function generateNewData() {
    // Read configuration from UI sliders
    const config = {
        ordersCount: parseInt($("#ordersCountSlider").val()),
        trolleysCount: parseInt($("#trolleysCountSlider").val()),
        bucketCount: parseInt($("#bucketsCountSlider").val())
    };

    // Show loading state
    const btn = $("#generateButton");
    btn.prop('disabled', true).html('<i class="fas fa-spinner fa-spin"></i> Generating...');

    fetch('/demo-data/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config)
    })
    .then(r => {
        if (!r.ok) {
            return r.text().then(text => {
                throw new Error(`Server error ${r.status}: ${text}`);
            });
        }
        return r.json();
    })
    .then(solution => {
        loadedSchedule = solution;
        currentProblemId = null;
        distances.clear();
        updateUI(solution, false);
        $("#settingsPanel").collapse('hide');
        showSuccess(`Generated ${config.ordersCount} orders with ${config.trolleysCount} trolleys`);
    })
    .catch(error => {
        console.error("Generate error:", error);
        showError("Failed to generate data: " + error.message, error);
    })
    .finally(() => {
        btn.prop('disabled', false).html('<i class="fas fa-sync-alt"></i> Generate New');
    });
}

// =============================================================================
// Solving - Start/Stop Optimization
// =============================================================================

/**
 * Start the optimization solver.
 *
 * Flow:
 * 1. POST current schedule to /schedules to start solving
 * 2. Server returns a problemId for tracking
 * 3. Start polling every 250ms for solution updates
 * 4. Update UI in real-time as solver finds better solutions
 */
function solve() {
    lastScore = null;
    userRequestedSolving = true;

    // Show solving state immediately for user feedback
    setSolving(true);

    // Submit the problem to the solver
    fetch('/schedules', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(loadedSchedule)
    })
    .then(r => r.text())
    .then(problemId => {
        // Store problem ID for subsequent API calls
        currentProblemId = problemId.replace(/"/g, '');

        // Start animation from first poll response, not stale loadedSchedule
        ISO.isSolving = true;

        // Poll for updates every 250ms for smooth real-time visualization
        autoRefreshIntervalId = setInterval(refreshSchedule, 250);

        // Trigger immediate first poll to get real data ASAP
        refreshSchedule();
    })
    .catch(error => {
        showError("Failed to start solving", error);
        setSolving(false);
        stopWarehouseAnimation();
    });
}

/**
 * Stop the optimization solver early.
 * Returns the best solution found so far.
 */
function stopSolving() {
    if (!currentProblemId) return;
    userRequestedSolving = false;

    // Stop polling immediately
    if (autoRefreshIntervalId) {
        clearInterval(autoRefreshIntervalId);
        autoRefreshIntervalId = null;
    }

    // Update UI immediately - don't wait for server
    setSolving(false);
    stopWarehouseAnimation();

    // Tell the server to terminate solving
    fetch(`/schedules/${currentProblemId}`, { method: 'DELETE' })
        .then(r => r.ok ? r.json() : Promise.reject(`HTTP ${r.status}`))
        .then(solution => {
            loadedSchedule = solution;
            updateUI(solution, false);
        })
        .catch(error => showError("Failed to stop solving", error));
}

// =============================================================================
// Real-Time Polling
// =============================================================================

/**
 * Fetch the latest solution and status from the server.
 * Called every 250ms during solving to provide real-time updates.
 *
 * Why polling instead of WebSockets/SSE?
 * - Simpler implementation and debugging
 * - Works reliably across all environments
 * - 250ms is fast enough for smooth visualization
 * - Proven pattern used across SolverForge quickstarts
 */
function refreshSchedule() {
    if (!currentProblemId) return;
    if (!userRequestedSolving) return;  // Don't process if user stopped

    // Fetch solution and status in parallel for efficiency
    Promise.all([
        fetch(`/schedules/${currentProblemId}`).then(r => r.json()),
        fetch(`/schedules/${currentProblemId}/status`).then(r => r.json())
    ])
    .then(([solution, status]) => {
        // Double-check user hasn't stopped while fetch was in-flight
        if (!userRequestedSolving) return;

        // CRITICAL: Sync animation state IMMEDIATELY before any rendering
        // This prevents race conditions where animation loop uses stale data
        if (typeof ISO !== 'undefined') {
            ISO.currentSolution = solution;
        }

        // Update distance cache from status response
        distances = new Map(Object.entries(status.distances || {}));

        // Detect score improvements and trigger visual feedback
        const newScoreStr = `${status.score.hardScore}hard/${status.score.softScore}soft`;
        if (lastScore && newScoreStr !== lastScore) {
            flashScoreImprovement();
        }
        lastScore = newScoreStr;

        // Update application state
        loadedSchedule = solution;
        const isSolving = status.solverStatus !== 'NOT_SOLVING' && status.solverStatus != null;
        updateUI(solution, isSolving);

        // Update animation paths when solution changes
        if (userRequestedSolving) {
            if (ISO.trolleyAnimations.size === 0) {
                startWarehouseAnimation(solution);
            }
            updateWarehouseAnimation(solution);
        }

        // Auto-stop polling when solver finishes (with valid score) or user stopped
        const solverSaysNotSolving = status.solverStatus === 'NOT_SOLVING';
        const solverActuallyFinished = solverSaysNotSolving && solution.score !== null;
        const shouldStop = !userRequestedSolving || solverActuallyFinished;

        if (shouldStop) {
            if (autoRefreshIntervalId) {
                clearInterval(autoRefreshIntervalId);
                autoRefreshIntervalId = null;
            }
            userRequestedSolving = false;
            setSolving(false);
            stopWarehouseAnimation();
        }
    })
    .catch(error => {
        console.error("Refresh error:", error);
    });
}

// =============================================================================
// UI Updates
// =============================================================================

/**
 * Update all UI components with the current solution state.
 *
 * @param {Object} solution - The current solution from the solver
 * @param {boolean} solving - Whether the solver is currently running
 */
function updateUI(solution, solving) {
    updateScore(solution);
    updateStats(solution);
    updateLegend(solution, distances);
    updateTrolleyCards(solution);
    renderWarehouse(solution);
    setSolving(solving && solution.solverStatus !== 'NOT_SOLVING');
}

/**
 * Update the score display.
 * Score format: "{hardScore}hard/{softScore}soft"
 * - Hard score: Constraint violations (must be 0 for valid solution)
 * - Soft score: Optimization objective (minimize distance)
 */
function updateScore(solution) {
    const score = solution.score;
    if (!score) {
        $("#score").text("?");
    } else if (typeof score === 'string') {
        $("#score").text(score);
    } else {
        $("#score").text(`${score.hardScore}hard/${score.softScore}soft`);
    }
}

/**
 * Update statistics cards showing problem metrics.
 * Calculates totals from the solution data structure.
 */
function updateStats(solution) {
    const orderIds = new Set();
    let totalItems = 0;
    let activeTrolleys = 0;
    let totalDistance = 0;

    // Build lookup for resolving step references
    const stepLookup = new Map();
    for (const step of solution.trolleySteps || []) {
        stepLookup.set(step.id, step);
    }

    // Aggregate statistics from all trolleys
    for (const trolley of solution.trolleys || []) {
        // Resolve step references (may be IDs or objects)
        const steps = (trolley.steps || []).map(ref =>
            typeof ref === 'string' ? stepLookup.get(ref) : ref
        ).filter(s => s);

        if (steps.length > 0) {
            activeTrolleys++;
            totalItems += steps.length;

            // Track unique orders
            for (const step of steps) {
                if (step.orderItem) {
                    orderIds.add(step.orderItem.orderId);
                }
            }
        }

        // Sum distances from cache
        const dist = distances.get(trolley.id) || 0;
        totalDistance += dist;
    }

    // Update UI with animations
    animateValue("#totalOrders", orderIds.size);
    animateValue("#totalItems", totalItems);
    animateValue("#activeTrolleys", activeTrolleys);
    animateValue("#totalDistance", Math.round(totalDistance / 100)); // cm -> m
}

/**
 * Animate a value change with a brief highlight effect.
 */
function animateValue(selector, newValue) {
    const el = $(selector);
    const oldValue = parseInt(el.text()) || 0;
    if (oldValue !== newValue) {
        el.text(newValue);
        el.addClass('value-changed');
        setTimeout(() => el.removeClass('value-changed'), 500);
    }
}

/**
 * Render the trolley assignment cards showing items per trolley.
 * Updates in place to avoid flicker.
 */
function updateTrolleyCards(solution) {
    const container = $("#trolleyCardsContainer");

    // Build step lookup for reference resolution
    const stepLookup = new Map();
    for (const step of solution.trolleySteps || []) {
        stepLookup.set(step.id, step);
    }

    const trolleys = solution.trolleys || [];

    // Create cards if needed (first time or count changed)
    if (container.children().length !== trolleys.length) {
        container.empty();
        for (const trolley of trolleys) {
            const color = getTrolleyColor(trolley.id);
            const card = $(`
                <div class="trolley-card" data-trolley-id="${trolley.id}">
                    <div class="trolley-card-header">
                        <div class="trolley-color-badge" style="background: ${color}"></div>
                        <div class="trolley-card-info">
                            <div class="trolley-card-title">Trolley ${trolley.id}</div>
                            <div class="trolley-card-stats"></div>
                        </div>
                        <div class="trolley-capacity-bar">
                            <div class="trolley-capacity-fill"></div>
                        </div>
                    </div>
                    <div class="trolley-card-body"></div>
                </div>
            `);
            container.append(card);
        }
    }

    // Update each card in place
    for (const trolley of trolleys) {
        const card = container.find(`[data-trolley-id="${trolley.id}"]`);
        if (!card.length) continue;

        const steps = (trolley.steps || []).map(ref =>
            typeof ref === 'string' ? stepLookup.get(ref) : ref
        ).filter(s => s);

        const itemCount = steps.length;

        // Calculate capacity
        let totalVolume = 0;
        const bucketCapacity = 50000;
        const bucketCount = trolley.bucketCount || 6;
        const maxCapacity = bucketCapacity * bucketCount;
        for (const step of steps) {
            if (step.orderItem?.product?.volume) {
                totalVolume += step.orderItem.product.volume;
            }
        }
        const capacityPercent = Math.min(100, Math.round((totalVolume / maxCapacity) * 100));
        const capacityClass = capacityPercent > 90 ? 'high' : capacityPercent > 70 ? 'medium' : 'low';

        // Update stats
        card.find('.trolley-card-stats').text(`${itemCount} items`);

        // Update capacity bar
        const fill = card.find('.trolley-capacity-fill');
        fill.css('width', `${capacityPercent}%`);
        fill.removeClass('low medium high').addClass(capacityClass);

        // Update items list
        const body = card.find('.trolley-card-body');
        if (itemCount > 0) {
            body.html(`
                <div class="trolley-items-list">
                    ${steps.map((step, i) => `
                        <div class="trolley-item">
                            <span class="trolley-item-number">${i + 1}</span>
                            ${step.orderItem?.product?.name?.substring(0, 15) || 'Item'}
                        </div>
                    `).join('')}
                </div>
            `);
        } else {
            body.html('<div class="trolley-empty">No items assigned</div>');
        }
    }
}

/**
 * Update UI to reflect solving/not-solving state.
 */
function setSolving(solving) {
    if (solving) {
        $("#solveButton").hide();
        $("#stopSolvingButton").show();
        $("#solvingIndicator").show();
        $("#generateButton").prop('disabled', true);
    } else {
        $("#solveButton").show();
        $("#stopSolvingButton").hide();
        $("#solvingIndicator").hide();
        $("#generateButton").prop('disabled', false);
    }
}

/**
 * Flash the score display to indicate improvement.
 */
function flashScoreImprovement() {
    const display = $("#scoreDisplay");
    display.addClass('improved');
    setTimeout(() => display.removeClass('improved'), 500);
}

// =============================================================================
// Score Analysis
// =============================================================================

/**
 * Fetch and display detailed constraint analysis.
 * Shows which constraints are satisfied/violated and their contribution to score.
 */
function analyze() {
    if (!currentProblemId) {
        showError("No active solution to analyze");
        return;
    }

    // Show loading state
    const btn = $("#analyzeButton");
    btn.prop('disabled', true).html('<i class="fas fa-spinner fa-spin"></i>');

    fetch(`/schedules/${currentProblemId}/score-analysis`)
        .then(r => r.json())
        .then(analysis => {
            showScoreAnalysis(analysis);
        })
        .catch(error => {
            showError("Failed to load score analysis", error);
        })
        .finally(() => {
            btn.prop('disabled', false).html('<i class="fas fa-chart-bar"></i>');
        });
}

/**
 * Display score analysis in a modal dialog.
 */
function showScoreAnalysis(analysis) {
    const content = $("#scoreAnalysisModalContent");
    content.empty();

    if (!analysis || !analysis.constraints) {
        content.html('<p>No constraint data available.</p>');
    } else {
        for (const constraint of analysis.constraints) {
            const score = constraint.score || '0';
            const isHard = score.includes('hard');

            const group = $(`
                <div class="constraint-group">
                    <div class="constraint-header">
                        <span class="constraint-name">${constraint.name}</span>
                        <span class="constraint-score ${isHard ? 'hard' : 'soft'}">${score}</span>
                    </div>
                </div>
            `);
            content.append(group);
        }
    }

    // Use getOrCreateInstance to avoid stacking modal instances
    const modalEl = document.getElementById('scoreAnalysisModal');
    bootstrap.Modal.getOrCreateInstance(modalEl).show();
}

// =============================================================================
// Notifications
// =============================================================================

/**
 * Display an error notification that auto-dismisses.
 */
function showError(message, error) {
    console.error(message, error);
    const alert = $(`
        <div class="alert alert-danger alert-dismissible fade show">
            <i class="fas fa-exclamation-circle me-2"></i>
            <strong>Error:</strong> ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        </div>
    `);
    $("#notificationPanel").append(alert);
    setTimeout(() => alert.alert('close'), 5000);
}

/**
 * Display a success notification that auto-dismisses.
 */
function showSuccess(message) {
    const alert = $(`
        <div class="alert alert-success alert-dismissible fade show">
            <i class="fas fa-check-circle me-2"></i>${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        </div>
    `);
    $("#notificationPanel").append(alert);
    setTimeout(() => alert.alert('close'), 3000);
}

// =============================================================================
// SolverForge Branding
// =============================================================================

/**
 * Add SolverForge header and footer branding.
 * Matches the pattern used in other SolverForge quickstarts.
 */
function replaceQuickstartSolverForgeAutoHeaderFooter() {
    const header = $("header#solverforge-auto-header");
    if (header.length) {
        header.css("background-color", "#ffffff");
        header.append($(`
            <div class="container-fluid">
                <nav class="navbar sticky-top navbar-expand-lg shadow-sm mb-3" style="background-color: #ffffff;">
                    <a class="navbar-brand" href="https://www.solverforge.org">
                        <img src="/webjars/solverforge/img/solverforge-horizontal.svg" alt="SolverForge logo" width="400">
                    </a>
                </nav>
            </div>
        `));
    }

    const footer = $("footer#solverforge-auto-footer");
    if (footer.length) {
        footer.append($(`
            <footer class="bg-black text-white-50">
                <div class="container">
                    <div class="hstack gap-3 p-4">
                        <div class="ms-auto"><a class="text-white" href="https://www.solverforge.org">SolverForge</a></div>
                        <div class="vr"></div>
                        <div><a class="text-white" href="https://www.solverforge.org/docs">Documentation</a></div>
                        <div class="vr"></div>
                        <div><a class="text-white" href="https://github.com/SolverForge/solverforge-legacy">Code</a></div>
                        <div class="vr"></div>
                        <div class="me-auto"><a class="text-white" href="mailto:info@solverforge.org">Support</a></div>
                    </div>
                </div>
            </footer>
        `));
    }
}
