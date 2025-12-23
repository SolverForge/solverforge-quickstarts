/**
 * Portfolio Optimization Quickstart - Frontend Application
 */

// =============================================================================
// Global State
// =============================================================================

let autoRefreshIntervalId = null;
let demoDataId = "SMALL";
let scheduleId = null;
let loadedPlan = null;

// Chart instances
let sectorChart = null;
let returnsChart = null;

// Sorting state for stock table
let sortColumn = 'predictedReturn';
let sortDirection = 'desc';

// Sector colors (consistent across charts and badges)
const SECTOR_COLORS = {
    'Technology': '#3b82f6',
    'Healthcare': '#10b981',
    'Finance': '#eab308',
    'Energy': '#ef4444',
    'Consumer': '#a855f7'
};

// =============================================================================
// Initialization
// =============================================================================

$(document).ready(function() {
    // Initialize header/footer with nav tabs
    replaceQuickstartSolverForgeAutoHeaderFooter();

    // Initialize Bootstrap tooltips
    const tooltipTriggerList = document.querySelectorAll('[data-bs-toggle="tooltip"]');
    [...tooltipTriggerList].map(el => new bootstrap.Tooltip(el));

    // Load initial data
    loadDemoData();

    // Event handlers
    $("#solveButton").click(solve);
    $("#stopSolvingButton").click(stopSolving);
    $("#analyzeButton").click(analyze);
    $("#dataSelector").change(function() {
        demoDataId = $(this).val();
        loadDemoData();
    });
    $("#showSelectedOnly").change(renderAllStocksTable);

    // Sortable table headers
    $("#allStocksTable").closest("table").find("th[data-sort]").click(function() {
        const column = $(this).data("sort");
        if (sortColumn === column) {
            sortDirection = sortDirection === 'asc' ? 'desc' : 'asc';
        } else {
            sortColumn = column;
            sortDirection = 'desc';
        }
        updateSortIndicators();
        renderAllStocksTable();
    });

    // Initialize advanced configuration if available (from config.js)
    if (typeof initAdvancedConfig === 'function') {
        initAdvancedConfig();
    }
});

// =============================================================================
// jQuery AJAX Extensions
// =============================================================================

$.ajaxSetup({
    contentType: "application/json",
    accepts: {
        json: "application/json"
    }
});

$.put = function(url, data) {
    return $.ajax({
        url: url,
        type: "PUT",
        data: JSON.stringify(data),
        contentType: "application/json"
    });
};

$.delete = function(url) {
    return $.ajax({
        url: url,
        type: "DELETE"
    });
};

// =============================================================================
// Data Loading
// =============================================================================

function loadDemoData() {
    $.getJSON("/demo-data/" + demoDataId)
        .done(function(data) {
            loadedPlan = data;
            scheduleId = null;
            // Apply advanced config if available (from config.js)
            if (typeof applyConfigToLoadedPlan === 'function') {
                applyConfigToLoadedPlan();
            }
            refreshUI();
            updateScore("Score: ?");
        })
        .fail(function(xhr) {
            showError("Failed to load demo data", xhr);
        });
}

// =============================================================================
// Solving
// =============================================================================

function solve() {
    if (!loadedPlan) {
        showSimpleError("Please load demo data first");
        return;
    }

    $.ajax({
        url: "/portfolios",
        type: "POST",
        data: JSON.stringify(loadedPlan),
        contentType: "application/json"
    })
    .done(function(data) {
        scheduleId = data;
        refreshSolvingButtons(true);
    })
    .fail(function(xhr) {
        showError("Failed to start solver", xhr);
    });
}

function stopSolving() {
    if (!scheduleId) return;

    $.delete("/portfolios/" + scheduleId)
        .done(function(data) {
            loadedPlan = data;
            refreshSolvingButtons(false);
            refreshUI();
        })
        .fail(function(xhr) {
            showError("Failed to stop solver", xhr);
        });
}

function refreshSolvingButtons(solving) {
    if (solving) {
        $("#solveButton").hide();
        $("#stopSolvingButton").show();
        $("#solvingSpinner").addClass("active");
        $(".kpi-value").addClass("solving-pulse");

        if (autoRefreshIntervalId == null) {
            autoRefreshIntervalId = setInterval(refreshSchedule, 2000);
        }
    } else {
        $("#solveButton").show();
        $("#stopSolvingButton").hide();
        $("#solvingSpinner").removeClass("active");
        $(".kpi-value").removeClass("solving-pulse");

        if (autoRefreshIntervalId != null) {
            clearInterval(autoRefreshIntervalId);
            autoRefreshIntervalId = null;
        }
    }
}

function refreshSchedule() {
    if (!scheduleId) return;

    $.getJSON("/portfolios/" + scheduleId)
        .done(function(data) {
            loadedPlan = data;
            refreshUI();

            // Check if solver is done
            if (data.solverStatus === "NOT_SOLVING") {
                refreshSolvingButtons(false);
            }
        })
        .fail(function(xhr) {
            showError("Failed to refresh solution", xhr);
            refreshSolvingButtons(false);
        });
}

// =============================================================================
// Score Analysis
// =============================================================================

function analyze() {
    if (!loadedPlan) {
        showSimpleError("Please load demo data first");
        return;
    }

    $.put("/portfolios/analyze", loadedPlan)
        .done(function(data) {
            showConstraintAnalysis(data);
        })
        .fail(function(xhr) {
            showError("Failed to analyze constraints", xhr);
        });
}

function showConstraintAnalysis(analysis) {
    const tbody = $("#weightModalContent tbody");
    tbody.empty();

    // Update modal label with score
    const score = loadedPlan.score || "?";
    $("#weightModalLabel").text(score);

    // Sort constraints: hard first, then by score impact
    const constraints = analysis.constraints || [];
    constraints.sort((a, b) => {
        if (a.type !== b.type) {
            return a.type === "HARD" ? -1 : 1;
        }
        return Math.abs(b.score) - Math.abs(a.score);
    });

    constraints.forEach(function(c) {
        const icon = c.score === 0
            ? '<i class="fas fa-check-circle text-success"></i>'
            : '<i class="fas fa-exclamation-triangle text-danger"></i>';

        const typeClass = c.type === "HARD" ? "text-danger" : "text-warning";
        const scoreClass = c.score === 0 ? "text-success" : "text-danger";

        tbody.append(`
            <tr>
                <td>${icon}</td>
                <td>${c.name}</td>
                <td><span class="${typeClass}">${c.type}</span></td>
                <td>${c.weight || '-'}</td>
                <td>${c.matchCount || 0}</td>
                <td class="${scoreClass}">${c.score}</td>
            </tr>
        `);
    });

    // Show modal
    const modal = new bootstrap.Modal(document.getElementById('weightModal'));
    modal.show();
}

// =============================================================================
// UI Refresh
// =============================================================================

function refreshUI() {
    updateKPIs();
    updateScore();
    updateCharts();
    renderSelectedStocksTable();
    renderAllStocksTable();
}

function updateKPIs() {
    if (!loadedPlan || !loadedPlan.stocks) {
        resetKPIs();
        return;
    }

    const stocks = loadedPlan.stocks;
    const selected = stocks.filter(s => s.selected);
    const selectedCount = selected.length;

    // Get target from plan, config module, or default to 20
    let targetCount = loadedPlan.targetPositionCount || 20;
    if (typeof getTargetStockCount === 'function') {
        targetCount = getTargetStockCount();
    }

    // Selected stocks count (show target)
    const selectedEl = $("#selectedCount");
    selectedEl.text(selectedCount + "/" + targetCount);
    if (selectedCount === targetCount) {
        selectedEl.removeClass("text-warning").addClass("text-success");
    } else if (selectedCount > 0) {
        selectedEl.removeClass("text-success").addClass("text-warning");
    } else {
        selectedEl.removeClass("text-success text-warning");
    }
    $("#selectedBadge").text(selectedCount + " selected");

    // Stock count badge
    $("#stockCountBadge").text(stocks.length + " stocks");

    // Use metrics from backend if available
    if (loadedPlan.metrics) {
        updateKPIsFromMetrics(loadedPlan.metrics);
    } else {
        // Fallback: calculate locally
        updateKPIsLocally(selected, selectedCount);
    }
}

function resetKPIs() {
    $("#selectedCount").text("0/20");
    $("#expectedReturn").text("0.00%").removeClass("positive negative");
    $("#sectorCount").text("0");
    $("#diversificationScore").text("0%").removeClass("text-success text-warning text-danger");
    $("#maxSectorExposure").text("0%");
    $("#returnVolatility").text("0.00%");
    $("#sharpeProxy").text("0.00");
    $("#herfindahlIndex").text("0.000");
    $("#selectedBadge").text("0 selected");
}

function updateKPIsFromMetrics(metrics) {
    // Expected return
    const returnEl = $("#expectedReturn");
    returnEl.text((metrics.expectedReturn * 100).toFixed(2) + "%");
    returnEl.removeClass("positive negative");
    returnEl.addClass(metrics.expectedReturn >= 0 ? "positive" : "negative");

    // Sector count
    $("#sectorCount").text(metrics.sectorCount);

    // Diversification score (0-100%)
    const divScore = (metrics.diversificationScore * 100).toFixed(0);
    const divEl = $("#diversificationScore");
    divEl.text(divScore + "%");
    divEl.removeClass("text-success text-warning text-danger");
    if (metrics.diversificationScore >= 0.7) {
        divEl.addClass("text-success");
    } else if (metrics.diversificationScore >= 0.5) {
        divEl.addClass("text-warning");
    } else {
        divEl.addClass("text-danger");
    }

    // Max sector exposure
    $("#maxSectorExposure").text((metrics.maxSectorExposure * 100).toFixed(1) + "%");

    // Return volatility
    $("#returnVolatility").text((metrics.returnVolatility * 100).toFixed(2) + "%");

    // Sharpe proxy
    const sharpeEl = $("#sharpeProxy");
    sharpeEl.text(metrics.sharpeProxy.toFixed(2));
    sharpeEl.removeClass("text-success text-warning text-danger");
    if (metrics.sharpeProxy >= 1.0) {
        sharpeEl.addClass("text-success");
    } else if (metrics.sharpeProxy >= 0.5) {
        sharpeEl.addClass("text-warning");
    }

    // HHI (Herfindahl-Hirschman Index)
    const hhiEl = $("#herfindahlIndex");
    hhiEl.text(metrics.herfindahlIndex.toFixed(3));
    hhiEl.removeClass("text-success text-warning text-danger");
    if (metrics.herfindahlIndex < 0.15) {
        hhiEl.addClass("text-success");
    } else if (metrics.herfindahlIndex < 0.25) {
        hhiEl.addClass("text-warning");
    } else {
        hhiEl.addClass("text-danger");
    }
}

function updateKPIsLocally(selected, selectedCount) {
    // Expected return (weighted average)
    const expectedReturn = selectedCount > 0
        ? selected.reduce((sum, s) => sum + s.predictedReturn, 0) / selectedCount
        : 0;
    const returnEl = $("#expectedReturn");
    returnEl.text((expectedReturn * 100).toFixed(2) + "%");
    returnEl.removeClass("positive negative");
    returnEl.addClass(expectedReturn >= 0 ? "positive" : "negative");

    // Sector count
    const sectors = new Set(selected.map(s => s.sector));
    $("#sectorCount").text(sectors.size);

    if (selectedCount > 0) {
        // Calculate sector weights and HHI locally
        const sectorCounts = {};
        selected.forEach(s => {
            sectorCounts[s.sector] = (sectorCounts[s.sector] || 0) + 1;
        });

        const sectorWeights = Object.values(sectorCounts).map(c => c / selectedCount);
        const hhi = sectorWeights.reduce((sum, w) => sum + w * w, 0);
        const divScore = ((1 - hhi) * 100).toFixed(0);
        const maxSector = Math.max(...sectorWeights) * 100;

        $("#diversificationScore").text(divScore + "%");
        $("#maxSectorExposure").text(maxSector.toFixed(1) + "%");
        $("#herfindahlIndex").text(hhi.toFixed(3));

        // Calculate volatility locally
        const returns = selected.map(s => s.predictedReturn);
        const meanReturn = returns.reduce((a, b) => a + b, 0) / returns.length;
        const variance = returns.reduce((sum, r) => sum + Math.pow(r - meanReturn, 2), 0) / returns.length;
        const volatility = Math.sqrt(variance);

        $("#returnVolatility").text((volatility * 100).toFixed(2) + "%");
        $("#sharpeProxy").text(volatility > 0 ? (expectedReturn / volatility).toFixed(2) : "0.00");
    } else {
        $("#diversificationScore").text("0%");
        $("#maxSectorExposure").text("0%");
        $("#returnVolatility").text("0.00%");
        $("#sharpeProxy").text("0.00");
        $("#herfindahlIndex").text("0.000");
    }
}

function updateScore() {
    if (!loadedPlan || !loadedPlan.score) {
        $("#score").text("Score: ?");
        return;
    }

    const score = loadedPlan.score;
    const match = score.match(/(-?\d+)hard\/(-?\d+)soft/);

    if (match) {
        const hard = parseInt(match[1]);
        const soft = parseInt(match[2]);
        const isFeasible = hard === 0;

        const scoreHtml = `
            <span class="score-badge ${isFeasible ? 'score-feasible' : 'score-infeasible'}">
                ${hard}hard
            </span>
            <span class="score-badge score-soft ms-1">
                ${soft}soft
            </span>
        `;
        $("#score").html(scoreHtml);
    } else {
        $("#score").text("Score: " + score);
    }
}

// =============================================================================
// Charts
// =============================================================================

function updateCharts() {
    updateSectorChart();
    updateReturnsChart();
}

function updateSectorChart() {
    const ctx = document.getElementById('sectorChart');
    if (!ctx) return;

    if (!loadedPlan || !loadedPlan.stocks) {
        if (sectorChart) {
            sectorChart.destroy();
            sectorChart = null;
        }
        return;
    }

    const selected = loadedPlan.stocks.filter(s => s.selected);

    if (selected.length === 0) {
        if (sectorChart) {
            sectorChart.destroy();
            sectorChart = null;
        }
        return;
    }

    // Calculate sector counts
    const sectorCounts = {};
    selected.forEach(s => {
        sectorCounts[s.sector] = (sectorCounts[s.sector] || 0) + 1;
    });

    const labels = Object.keys(sectorCounts);
    const data = labels.map(s => (sectorCounts[s] / selected.length) * 100);
    const colors = labels.map(s => SECTOR_COLORS[s] || '#64748b');

    if (sectorChart) {
        sectorChart.destroy();
    }

    sectorChart = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: labels,
            datasets: [{
                data: data,
                backgroundColor: colors,
                borderWidth: 3,
                borderColor: '#fff',
                hoverOffset: 8
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            cutout: '60%',
            plugins: {
                legend: {
                    position: 'right',
                    labels: {
                        padding: 16,
                        usePointStyle: true,
                        pointStyle: 'circle'
                    }
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            const value = context.raw.toFixed(1);
                            const count = sectorCounts[context.label];
                            return `${context.label}: ${value}% (${count} stocks)`;
                        }
                    }
                }
            }
        }
    });
}

function updateReturnsChart() {
    const ctx = document.getElementById('returnsChart');
    if (!ctx) return;

    if (!loadedPlan || !loadedPlan.stocks) {
        if (returnsChart) {
            returnsChart.destroy();
            returnsChart = null;
        }
        return;
    }

    const selected = loadedPlan.stocks.filter(s => s.selected);

    if (selected.length === 0) {
        if (returnsChart) {
            returnsChart.destroy();
            returnsChart = null;
        }
        return;
    }

    // Sort by return and take top 10
    const top10 = [...selected]
        .sort((a, b) => b.predictedReturn - a.predictedReturn)
        .slice(0, 10);

    const labels = top10.map(s => s.stockId);
    const data = top10.map(s => s.predictedReturn * 100);
    const colors = top10.map(s => SECTOR_COLORS[s.sector] || '#64748b');

    if (returnsChart) {
        returnsChart.destroy();
    }

    returnsChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: 'Predicted Return (%)',
                data: data,
                backgroundColor: colors,
                borderRadius: 6,
                borderSkipped: false
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            indexAxis: 'y',
            plugins: {
                legend: {
                    display: false
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            const stock = top10[context.dataIndex];
                            return `${stock.stockName}: ${context.raw.toFixed(2)}%`;
                        }
                    }
                }
            },
            scales: {
                x: {
                    beginAtZero: true,
                    grid: {
                        display: true,
                        color: 'rgba(0,0,0,0.05)'
                    },
                    title: {
                        display: true,
                        text: 'Predicted Return (%)',
                        color: '#64748b'
                    }
                },
                y: {
                    grid: {
                        display: false
                    }
                }
            }
        }
    });
}

// =============================================================================
// Tables
// =============================================================================

function renderSelectedStocksTable() {
    const tbody = $("#selectedStocksTable");

    if (!loadedPlan || !loadedPlan.stocks) {
        tbody.html(`
            <tr>
                <td colspan="5" class="text-center text-muted py-4">
                    <i class="fas fa-info-circle me-2"></i>No data loaded
                </td>
            </tr>
        `);
        return;
    }

    const selected = loadedPlan.stocks
        .filter(s => s.selected)
        .sort((a, b) => b.predictedReturn - a.predictedReturn);

    if (selected.length === 0) {
        tbody.html(`
            <tr>
                <td colspan="5" class="text-center text-muted py-4">
                    <i class="fas fa-info-circle me-2"></i>No stocks selected yet
                </td>
            </tr>
        `);
        return;
    }

    const weightPerStock = 100 / selected.length;

    tbody.html(selected.map(stock => {
        const returnClass = stock.predictedReturn >= 0 ? 'return-positive' : 'return-negative';
        const returnSign = stock.predictedReturn >= 0 ? '+' : '';

        return `
            <tr class="stock-selected">
                <td><strong>${stock.stockId}</strong></td>
                <td>${stock.stockName}</td>
                <td><span class="sector-badge sector-${stock.sector}">${stock.sector}</span></td>
                <td class="${returnClass}">${returnSign}${(stock.predictedReturn * 100).toFixed(2)}%</td>
                <td>${weightPerStock.toFixed(2)}%</td>
            </tr>
        `;
    }).join(''));
}

function renderAllStocksTable() {
    const tbody = $("#allStocksTable");
    const showSelectedOnly = $("#showSelectedOnly").is(":checked");

    if (!loadedPlan || !loadedPlan.stocks) {
        tbody.html(`
            <tr>
                <td colspan="6" class="text-center text-muted py-4">
                    <i class="fas fa-database me-2"></i>No data loaded
                </td>
            </tr>
        `);
        return;
    }

    let stocks = loadedPlan.stocks;

    // Filter if needed
    if (showSelectedOnly) {
        stocks = stocks.filter(s => s.selected);
    }

    // Sort
    stocks = [...stocks].sort((a, b) => {
        let aVal = a[sortColumn];
        let bVal = b[sortColumn];

        // Handle boolean (selected)
        if (sortColumn === 'selected') {
            aVal = a.selected ? 1 : 0;
            bVal = b.selected ? 1 : 0;
        }

        // Handle strings
        if (typeof aVal === 'string') {
            aVal = aVal.toLowerCase();
            bVal = bVal.toLowerCase();
        }

        if (aVal < bVal) return sortDirection === 'asc' ? -1 : 1;
        if (aVal > bVal) return sortDirection === 'asc' ? 1 : -1;
        return 0;
    });

    if (stocks.length === 0) {
        tbody.html(`
            <tr>
                <td colspan="6" class="text-center text-muted py-4">
                    <i class="fas fa-filter me-2"></i>No stocks match the filter
                </td>
            </tr>
        `);
        return;
    }

    // Calculate weight per stock
    const selectedCount = loadedPlan.stocks.filter(s => s.selected).length;
    const weightPerStock = selectedCount > 0 ? (100 / selectedCount) : 0;

    tbody.html(stocks.map(stock => {
        const returnClass = stock.predictedReturn >= 0 ? 'return-positive' : 'return-negative';
        const returnSign = stock.predictedReturn >= 0 ? '+' : '';
        const rowClass = stock.selected ? 'stock-selected' : '';
        const weight = stock.selected ? weightPerStock.toFixed(2) : '0.00';

        return `
            <tr class="${rowClass}">
                <td>
                    <span class="badge ${stock.selected ? 'bg-success' : 'bg-secondary'}">
                        ${stock.selected ? 'Yes' : 'No'}
                    </span>
                </td>
                <td><strong>${stock.stockId}</strong></td>
                <td>${stock.stockName}</td>
                <td><span class="sector-badge sector-${stock.sector}">${stock.sector}</span></td>
                <td class="${returnClass}">${returnSign}${(stock.predictedReturn * 100).toFixed(2)}%</td>
                <td>${weight}%</td>
            </tr>
        `;
    }).join(''));
}

function updateSortIndicators() {
    const table = $("#allStocksTable").closest("table");
    table.find("th").removeClass("sorted");
    table.find("th i").removeClass("fa-sort-up fa-sort-down").addClass("fa-sort");

    const th = table.find(`th[data-sort="${sortColumn}"]`);
    th.addClass("sorted");
    th.find("i")
        .removeClass("fa-sort")
        .addClass(sortDirection === 'asc' ? 'fa-sort-up' : 'fa-sort-down');
}

// =============================================================================
// Header/Footer with Nav Tabs
// =============================================================================

function replaceQuickstartSolverForgeAutoHeaderFooter() {
    const solverforgeHeader = $("header#solverforge-auto-header");
    if (solverforgeHeader != null) {
        solverforgeHeader.css("background-color", "#ffffff");
        solverforgeHeader.append(
            $(`<div class="container-fluid">
                <nav class="navbar sticky-top navbar-expand-lg shadow-sm mb-3" style="background-color: #ffffff;">
                    <a class="navbar-brand" href="https://www.solverforge.org">
                        <img src="/webjars/solverforge/img/solverforge-horizontal.svg" alt="SolverForge logo" width="300">
                    </a>
                    <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#navbarNav" aria-controls="navbarNav" aria-expanded="false" aria-label="Toggle navigation">
                        <span class="navbar-toggler-icon"></span>
                    </button>
                    <div class="collapse navbar-collapse" id="navbarNav">
                        <ul class="nav nav-pills ms-4">
                            <li class="nav-item">
                                <button class="nav-link active" data-bs-toggle="pill" data-bs-target="#demo" type="button" style="color: #1f2937;">
                                    <i class="fas fa-chart-pie me-1"></i> Demo
                                </button>
                            </li>
                            <li class="nav-item">
                                <button class="nav-link" data-bs-toggle="pill" data-bs-target="#rest" type="button" style="color: #1f2937;">
                                    <i class="fas fa-book me-1"></i> Guide
                                </button>
                            </li>
                            <li class="nav-item">
                                <button class="nav-link" data-bs-toggle="pill" data-bs-target="#openapi" type="button" style="color: #1f2937;">
                                    <i class="fas fa-code me-1"></i> REST API
                                </button>
                            </li>
                        </ul>
                    </div>
                </nav>
            </div>`)
        );
    }

    const solverforgeFooter = $("footer#solverforge-auto-footer");
    if (solverforgeFooter != null) {
        solverforgeFooter.append(
            $(`<footer class="bg-black text-white-50">
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
            </footer>`)
        );
    }
}

// =============================================================================
// Utility Functions
// =============================================================================

function copyCode(button) {
    const codeBlock = $(button).closest('.code-block').find('code');
    const text = codeBlock.text();

    navigator.clipboard.writeText(text).then(function() {
        const originalHtml = $(button).html();
        $(button).html('<i class="fas fa-check"></i> Copied!');
        setTimeout(function() {
            $(button).html(originalHtml);
        }, 2000);
    });
}

// Make copyCode available globally
window.copyCode = copyCode;
