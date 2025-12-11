// VM Placement Optimizer - Frontend Application with Real-Time Animations

let autoRefreshIntervalId = null;
let demoDataId = null;
let placementId = null;
let loadedPlacement = null;

// Animation state tracking
let vmPositionCache = {}; // { vmId: serverId | null }
let isFirstRender = true;
let previousScore = null;
let serverLookup = {}; // For quick server access during animations

$(document).ready(function () {
    let initialized = false;

    function safeInitialize() {
        if (!initialized) {
            initialized = true;
            initializeApp();
        }
    }

    $(window).on('load', safeInitialize);
    setTimeout(safeInitialize, 100);
});

function initializeApp() {
    replaceQuickstartSolverForgeAutoHeaderFooter();

    $("#solveButton").click(function () {
        solve();
    });
    $("#stopSolvingButton").click(function () {
        stopSolving();
    });
    $("#analyzeButton").click(function () {
        analyze();
    });

    // View toggle
    $('input[name="viewToggle"]').change(function() {
        if ($('#rackView').is(':checked')) {
            $('#rackViewContainer').show();
            $('#cardViewContainer').hide();
        } else {
            $('#rackViewContainer').hide();
            $('#cardViewContainer').show();
        }
    });

    setupAjax();
    fetchDemoData();
}

function setupAjax() {
    $.ajaxSetup({
        headers: {
            'Content-Type': 'application/json',
            'Accept': 'application/json,text/plain',
        }
    });
    jQuery.each(["put", "delete"], function (i, method) {
        jQuery[method] = function (url, data, callback, type) {
            if (jQuery.isFunction(data)) {
                type = type || callback;
                callback = data;
                data = undefined;
            }
            return jQuery.ajax({
                url: url,
                type: method,
                dataType: type,
                data: data,
                success: callback
            });
        };
    });
}

function fetchDemoData() {
    $.get("/demo-data", function (data) {
        data.forEach(item => {
            $("#testDataButton").append($('<a id="' + item + 'TestData" class="dropdown-item" href="#">' + item + '</a>'));
            $("#" + item + "TestData").click(function () {
                switchDataDropDownItemActive(item);
                placementId = null;
                demoDataId = item;
                // Reset animation state for new dataset
                isFirstRender = true;
                vmPositionCache = {};
                previousScore = null;
                refreshPlacement();
            });
        });
        if (data.length > 0) {
            demoDataId = data[0];
            switchDataDropDownItemActive(demoDataId);
            refreshPlacement();
        }
    }).fail(function (xhr, ajaxOptions, thrownError) {
        let $demo = $("#demo");
        $demo.empty();
        $demo.html("<h1><p align=\"center\">No test data available</p></h1>");
    });
}

function switchDataDropDownItemActive(newItem) {
    const activeCssClass = "active";
    $("#testDataButton > a." + activeCssClass).removeClass(activeCssClass);
    $("#" + newItem + "TestData").addClass(activeCssClass);
}

function refreshPlacement() {
    let path = "/placements/" + placementId;
    if (placementId === null) {
        if (demoDataId === null) {
            showSimpleError("Please select a test data set.");
            return;
        }
        path = "/demo-data/" + demoDataId;
    }
    $.getJSON(path, function (placement) {
        loadedPlacement = placement;
        renderPlacement(placement);
    }).fail(function (xhr, ajaxOptions, thrownError) {
        showError("Getting the placement has failed.", xhr);
        refreshSolvingButtons(false);
    });
}

function renderPlacement(placement) {
    if (!placement) {
        console.error('No placement data provided');
        return;
    }

    const isSolving = placement.solverStatus != null && placement.solverStatus !== "NOT_SOLVING";
    refreshSolvingButtons(isSolving);

    // Update score with animation
    const newScore = placement.score == null ? "?" : placement.score;
    const scoreEl = $("#score");
    if (previousScore !== newScore) {
        scoreEl.text("Score: " + newScore);
        if (previousScore !== null && newScore !== "?") {
            scoreEl.addClass("updated");
            setTimeout(() => scoreEl.removeClass("updated"), 300);
        }
        previousScore = newScore;
    }

    // Update summary cards with change detection
    updateSummaryCard("#totalServers", placement.servers ? placement.servers.length : 0);
    updateSummaryCard("#activeServers", placement.activeServers || 0);
    updateSummaryCard("#totalVms", placement.vms ? placement.vms.length : 0);
    updateSummaryCard("#unassignedVms", placement.unassignedVms || 0);
    updateSummaryCard("#cpuUtil", Math.round((placement.totalCpuUtilization || 0) * 100) + "%");
    updateSummaryCard("#memUtil", Math.round((placement.totalMemoryUtilization || 0) * 100) + "%");

    // Update unassigned card styling
    const unassignedCard = $("#unassignedCard");
    const unassignedVms = placement.unassignedVms || 0;
    unassignedCard.removeClass("warning danger");
    if (unassignedVms > 0) {
        unassignedCard.addClass(unassignedVms > 5 ? "danger" : "warning");
    }

    if (!placement.servers || !placement.vms) {
        return;
    }

    // Create VM and server lookups
    const vmById = {};
    placement.vms.forEach(vm => vmById[vm.id] = vm);

    serverLookup = {};
    placement.servers.forEach(s => serverLookup[s.id] = s);

    if (isFirstRender) {
        // Full render on first load
        renderRackView(placement, vmById);
        renderCardView(placement, vmById);
        renderUnassignedVMs(placement.vms);
        vmPositionCache = buildPositionCache(placement);
        isFirstRender = false;
        return;
    }

    // Incremental animated update
    const newPositions = buildPositionCache(placement);
    const changes = diffPositions(vmPositionCache, newPositions);

    if (changes.length > 0) {
        console.log(`Detected ${changes.length} VM position changes:`, changes.slice(0, 5));
        animateVmChanges(changes, placement, vmById);
    }

    // Always update utilization bars smoothly
    updateUtilizationBars(placement);

    // Update unassigned list
    updateUnassignedList(placement.vms, vmById);

    vmPositionCache = newPositions;
}

function updateSummaryCard(selector, newValue) {
    const el = $(selector);
    const oldValue = el.text();
    if (oldValue !== String(newValue)) {
        el.text(newValue);
        el.addClass("changed");
        setTimeout(() => el.removeClass("changed"), 300);
    }
}

function buildPositionCache(placement) {
    const cache = {};
    placement.vms.forEach(vm => {
        cache[vm.id] = vm.server || null;
    });
    // Debug: log sample of cache
    const sample = Object.entries(cache).slice(0, 3);
    console.log('Position cache sample:', sample);
    return cache;
}

function diffPositions(oldCache, newCache) {
    const changes = [];
    for (const vmId in newCache) {
        const oldServer = oldCache[vmId];
        const newServer = newCache[vmId];
        if (oldServer !== newServer) {
            changes.push({ vmId, from: oldServer, to: newServer });
        }
    }
    return changes;
}

function animateVmChanges(changes, placement, vmById) {
    changes.forEach(({ vmId, from, to }) => {
        const vm = vmById[vmId];
        if (!vm) return;

        // Get source and target elements
        let sourceEl, targetEl;
        let sourceChipEl = null; // The actual chip element to hide during animation

        if (from) {
            sourceEl = $(`#server-blade-${from} .vm-chips`);
            sourceChipEl = $(`#server-blade-${from} #vm-chip-${vmId}`);
            // Highlight sending server
            $(`#server-blade-${from}`).addClass('sending');
            setTimeout(() => $(`#server-blade-${from}`).removeClass('sending'), 200);
        } else {
            // VM is coming from unassigned list
            sourceEl = $(`#unassigned-${vmId}`);
            sourceChipEl = sourceEl;
        }

        if (to) {
            targetEl = $(`#server-blade-${to} .vm-chips`);
            // Highlight receiving server
            $(`#server-blade-${to}`).addClass('receiving');
            setTimeout(() => $(`#server-blade-${to}`).removeClass('receiving'), 300);
        } else {
            targetEl = $('#unassignedList');
        }

        // If elements not found, just update DOM directly
        if (!sourceEl.length || !targetEl.length) {
            console.log(`Animation fallback: sourceEl=${sourceEl.length}, targetEl=${targetEl.length} for VM ${vmId}`);
            updateVmPosition(vmId, from, to, vm);
            return;
        }

        // Create flying clone
        const flyingChip = createVmChip(vm);
        flyingChip.addClass('flying-vm');

        // Get positions
        const sourceRect = sourceEl[0].getBoundingClientRect();
        const targetRect = targetEl[0].getBoundingClientRect();

        // Position at source
        flyingChip.css({
            left: sourceRect.left + 'px',
            top: sourceRect.top + 'px',
            transform: 'translate(0, 0)'
        });

        $('body').append(flyingChip);

        // Hide original element during animation
        if (sourceChipEl && sourceChipEl.length) {
            sourceChipEl.css('opacity', '0');
        }

        // Trigger fly animation (use double RAF for reliable animation start)
        requestAnimationFrame(() => {
            requestAnimationFrame(() => {
                flyingChip.addClass('animate');
                flyingChip.css({
                    transform: `translate(${targetRect.left - sourceRect.left}px, ${targetRect.top - sourceRect.top}px)`
                });
            });
        });

        // Clean up and update DOM after animation
        setTimeout(() => {
            flyingChip.remove();
            updateVmPosition(vmId, from, to, vm);
        }, 220); // Slightly longer than animation duration to ensure completion
    });
}

function updateVmPosition(vmId, from, to, vm) {
    // Remove from source
    if (from) {
        $(`#server-blade-${from} #vm-chip-${vmId}`).remove();
    } else {
        $(`#unassigned-${vmId}`).remove();
    }

    // Add to target
    if (to) {
        let vmChipsContainer = $(`#server-blade-${to} .vm-chips`);
        if (!vmChipsContainer.length) {
            // Create vm-chips container if it doesn't exist
            vmChipsContainer = $('<div class="vm-chips"></div>');
            $(`#server-blade-${to}`).append(vmChipsContainer);
        }
        const newChip = createVmChip(vm);
        newChip.attr('id', `vm-chip-${vm.id}`);
        vmChipsContainer.append(newChip);

        // Update server blade state (empty/not empty)
        $(`#server-blade-${to}`).removeClass('empty');
    }

    // Update source server empty state
    if (from) {
        const sourceChips = $(`#server-blade-${from} .vm-chips`).children();
        if (sourceChips.length === 0) {
            $(`#server-blade-${from}`).addClass('empty');
        }
    }
}

function updateUtilizationBars(placement) {
    placement.servers.forEach(server => {
        const cpuBar = $(`#util-${server.id}-cpu`);
        const memBar = $(`#util-${server.id}-mem`);
        const stoBar = $(`#util-${server.id}-sto`);

        const updates = [
            { bar: cpuBar, util: server.cpuUtilization || 0 },
            { bar: memBar, util: server.memoryUtilization || 0 },
            { bar: stoBar, util: server.storageUtilization || 0 }
        ];

        updates.forEach(({ bar, util }) => {
            if (bar.length) {
                const newPct = Math.min(util * 100, 100);
                const oldPct = parseFloat(bar[0].style.width) || 0;

                bar.css('width', newPct + '%');
                bar.removeClass('low medium high over').addClass(getUtilClass(util));

                if (Math.abs(oldPct - newPct) > 1) {
                    bar.addClass('changed');
                    setTimeout(() => bar.removeClass('changed'), 300);
                }
            }
        });

        // Update server blade empty/overcommitted state
        const blade = $(`#server-blade-${server.id}`);
        const hasVms = server.vms && server.vms.length > 0;
        const isOvercommitted = (server.cpuUtilization || 0) > 1 ||
                                (server.memoryUtilization || 0) > 1 ||
                                (server.storageUtilization || 0) > 1;

        blade.toggleClass('empty', !hasVms);
        blade.toggleClass('overcommitted', isOvercommitted);
    });
}

function updateUnassignedList(vms, vmById) {
    const container = $("#unassignedList");
    const unassigned = vms.filter(vm => !vm.server);

    if (unassigned.length === 0) {
        if (!container.find('.all-assigned').length) {
            container.empty();
            container.append(`
                <div class="all-assigned">
                    <i class="fas fa-check-circle"></i>
                    <strong>All VMs assigned!</strong>
                </div>
            `);
        }
        return;
    }

    // Remove "all assigned" message if present
    container.find('.all-assigned').remove();

    // Update existing or add new unassigned VMs
    unassigned.sort((a, b) => (b.priority || 1) - (a.priority || 1));

    unassigned.forEach(vm => {
        if (!$(`#unassigned-${vm.id}`).length) {
            const vmDiv = createUnassignedVmElement(vm);
            container.append(vmDiv);
        }
    });
}

function createUnassignedVmElement(vm) {
    return $(`
        <div id="unassigned-${vm.id}" class="unassigned-vm">
            <div class="name">
                ${vm.name}
                ${vm.affinityGroup ? `<span class="constraint-marker affinity">${vm.affinityGroup}</span>` : ''}
                ${vm.antiAffinityGroup ? `<span class="constraint-marker anti-affinity">${vm.antiAffinityGroup}</span>` : ''}
            </div>
            <div class="details">
                <i class="fas fa-microchip"></i> ${vm.cpuCores}c
                <i class="fas fa-memory ms-2"></i> ${vm.memoryGb}GB
                <i class="fas fa-hdd ms-2"></i> ${vm.storageGb}GB
                <span class="ms-2 badge bg-${getPriorityBadgeClass(vm.priority)}">P${vm.priority || 1}</span>
            </div>
        </div>
    `);
}

function renderRackView(placement, vmById) {
    const container = $("#rackViewContainer");
    container.empty();

    // Group servers by rack
    const rackGroups = {};
    placement.servers.forEach(server => {
        const rack = server.rack || "Unracked";
        if (!rackGroups[rack]) {
            rackGroups[rack] = [];
        }
        rackGroups[rack].push(server);
    });

    // Sort racks alphabetically
    const sortedRacks = Object.keys(rackGroups).sort();

    sortedRacks.forEach(rackName => {
        const servers = rackGroups[rackName];
        servers.sort((a, b) => a.name.localeCompare(b.name));

        const rackDiv = $('<div class="rack"></div>');
        const rackHeader = $(`
            <div class="rack-header">
                <i class="fas fa-server"></i>
                <span>${rackName}</span>
                <span class="ms-auto badge bg-secondary">${servers.length} servers</span>
            </div>
        `);
        rackDiv.append(rackHeader);

        servers.forEach(server => {
            const blade = createServerBlade(server, vmById);
            rackDiv.append(blade);
        });

        container.append(rackDiv);
    });
}

function createServerBlade(server, vmById) {
    const cpuUtil = server.cpuUtilization || 0;
    const memUtil = server.memoryUtilization || 0;
    const storageUtil = server.storageUtilization || 0;
    const isEmpty = !server.vms || server.vms.length === 0;
    const isOvercommitted = cpuUtil > 1 || memUtil > 1 || storageUtil > 1;

    let bladeClass = "server-blade";
    if (isEmpty) bladeClass += " empty";
    if (isOvercommitted) bladeClass += " overcommitted";

    const blade = $(`<div id="server-blade-${server.id}" class="${bladeClass}"></div>`);

    // Header
    const header = $(`
        <div class="server-blade-header">
            <span class="server-name">${server.name}</span>
            <span class="server-specs">${server.cpuCores}c / ${server.memoryGb}GB / ${server.storageGb}GB</span>
        </div>
    `);
    blade.append(header);

    // Utilization bars with IDs for animation
    const utilBars = $('<div class="utilization-mini"></div>');
    utilBars.append(createMiniUtilBar(cpuUtil, "CPU", `util-${server.id}-cpu`));
    utilBars.append(createMiniUtilBar(memUtil, "MEM", `util-${server.id}-mem`));
    utilBars.append(createMiniUtilBar(storageUtil, "STO", `util-${server.id}-sto`));
    blade.append(utilBars);

    // VM chips with IDs for animation
    const vmChips = $('<div class="vm-chips"></div>');
    if (server.vms && server.vms.length > 0) {
        server.vms.forEach(vmId => {
            const vm = vmById[vmId];
            if (vm) {
                const chip = createVmChip(vm);
                chip.attr('id', `vm-chip-${vm.id}`);
                vmChips.append(chip);
            }
        });
    }
    blade.append(vmChips);

    // Click handler for details
    blade.click(function(e) {
        if (!$(e.target).hasClass('vm-chip')) {
            showServerDetails(server, vmById);
        }
    });

    return blade;
}

function createMiniUtilBar(value, label, id) {
    const percentage = Math.min(value * 100, 100);
    const utilClass = getUtilClass(value);

    return $(`
        <div class="util-mini-bar" title="${label}: ${Math.round(value * 100)}%">
            <div id="${id}" class="util-mini-fill ${utilClass}" style="width: ${percentage}%"></div>
        </div>
    `);
}

function createVmChip(vm) {
    const priority = vm.priority || 1;
    let chipClass = `vm-chip priority-${priority}`;
    if (vm.affinityGroup) chipClass += " affinity";
    if (vm.antiAffinityGroup) chipClass += " anti-affinity";

    let tooltip = vm.name;
    tooltip += `\nCPU: ${vm.cpuCores} cores`;
    tooltip += `\nMemory: ${vm.memoryGb} GB`;
    tooltip += `\nStorage: ${vm.storageGb} GB`;
    tooltip += `\nPriority: ${priority}`;
    if (vm.affinityGroup) tooltip += `\nAffinity: ${vm.affinityGroup}`;
    if (vm.antiAffinityGroup) tooltip += `\nAnti-Affinity: ${vm.antiAffinityGroup}`;

    return $(`<span class="${chipClass}" title="${tooltip}">${vm.name}</span>`);
}

function renderCardView(placement, vmById) {
    const container = $("#cardViewContainer");
    container.empty();

    const sortedServers = [...placement.servers].sort((a, b) => {
        const aVms = a.vms ? a.vms.length : 0;
        const bVms = b.vms ? b.vms.length : 0;
        if (bVms !== aVms) return bVms - aVms;
        return a.name.localeCompare(b.name);
    });

    sortedServers.forEach(server => {
        const card = createServerCard(server, vmById);
        container.append(card);
    });
}

function createServerCard(server, vmById) {
    const cpuUtil = server.cpuUtilization || 0;
    const memUtil = server.memoryUtilization || 0;
    const storageUtil = server.storageUtilization || 0;
    const isEmpty = !server.vms || server.vms.length === 0;

    const cardWrapper = $('<div class="col-md-6 col-lg-4"></div>');
    const card = $(`
        <div class="card h-100 ${isEmpty ? 'opacity-50' : ''}">
            <div class="card-header d-flex justify-content-between align-items-center">
                <strong>${server.name}</strong>
                ${server.rack ? `<span class="badge bg-secondary">${server.rack}</span>` : ''}
            </div>
            <div class="card-body">
                <div class="mb-3">
                    ${createUtilRow("CPU", cpuUtil, server.cpuCores + " cores")}
                    ${createUtilRow("Memory", memUtil, server.memoryGb + " GB")}
                    ${createUtilRow("Storage", storageUtil, server.storageGb + " GB")}
                </div>
                <div class="vm-chips">
                    ${(server.vms || []).map(vmId => {
                        const vm = vmById[vmId];
                        if (vm) {
                            const priority = vm.priority || 1;
                            let chipClass = `vm-chip priority-${priority}`;
                            if (vm.affinityGroup) chipClass += " affinity";
                            if (vm.antiAffinityGroup) chipClass += " anti-affinity";
                            return `<span class="${chipClass}" title="${vm.name}">${vm.name}</span>`;
                        }
                        return '';
                    }).join('')}
                </div>
            </div>
        </div>
    `);
    cardWrapper.append(card);
    return cardWrapper;
}

function createUtilRow(label, value, capacity) {
    const percentage = Math.min(value * 100, 100);
    const displayPercentage = Math.round(value * 100);
    const utilClass = getUtilClass(value);

    const bgClass = {
        'low': 'bg-success',
        'medium': 'bg-warning',
        'high': 'bg-danger',
        'over': 'bg-danger'
    }[utilClass];

    return `
        <div class="mb-2">
            <div class="d-flex justify-content-between small">
                <span>${label}</span>
                <span class="text-muted">${capacity} (${displayPercentage}%)</span>
            </div>
            <div class="progress" style="height: 6px;">
                <div class="progress-bar ${bgClass}" style="width: ${percentage}%"></div>
            </div>
        </div>
    `;
}

function renderUnassignedVMs(vms) {
    const container = $("#unassignedList");
    container.empty();

    const unassigned = vms.filter(vm => !vm.server);

    if (unassigned.length === 0) {
        container.append(`
            <div class="all-assigned">
                <i class="fas fa-check-circle"></i>
                <strong>All VMs assigned!</strong>
            </div>
        `);
        return;
    }

    unassigned.sort((a, b) => (b.priority || 1) - (a.priority || 1));

    unassigned.forEach(vm => {
        const vmDiv = createUnassignedVmElement(vm);
        container.append(vmDiv);
    });
}

function getPriorityBadgeClass(priority) {
    switch(priority) {
        case 5: return "danger";
        case 4: return "primary";
        case 3: return "success";
        case 2: return "secondary";
        default: return "light text-dark";
    }
}

function showServerDetails(server, vmById) {
    const modal = new bootstrap.Modal("#serverDetailModal");
    const content = $("#serverDetailModalContent");
    $("#serverDetailModalLabel").html(`<i class="fas fa-server me-2"></i>${server.name}`);

    const cpuUtil = server.cpuUtilization || 0;
    const memUtil = server.memoryUtilization || 0;
    const storageUtil = server.storageUtilization || 0;

    content.html(`
        <div class="mb-3">
            <h6>Specifications</h6>
            <table class="table table-sm">
                <tr><td>Rack</td><td>${server.rack || 'Unracked'}</td></tr>
                <tr><td>CPU Cores</td><td>${server.cpuCores}</td></tr>
                <tr><td>Memory</td><td>${server.memoryGb} GB</td></tr>
                <tr><td>Storage</td><td>${server.storageGb} GB</td></tr>
            </table>
        </div>
        <div class="mb-3">
            <h6>Utilization</h6>
            ${createUtilRow("CPU", cpuUtil, `${server.usedCpu || 0}/${server.cpuCores} cores`)}
            ${createUtilRow("Memory", memUtil, `${server.usedMemory || 0}/${server.memoryGb} GB`)}
            ${createUtilRow("Storage", storageUtil, `${server.usedStorage || 0}/${server.storageGb} GB`)}
        </div>
        <div>
            <h6>Assigned VMs (${server.vms ? server.vms.length : 0})</h6>
            ${server.vms && server.vms.length > 0 ? `
                <table class="table table-sm">
                    <thead>
                        <tr>
                            <th>Name</th>
                            <th>CPU</th>
                            <th>Memory</th>
                            <th>Storage</th>
                            <th>Priority</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${server.vms.map(vmId => {
                            const vm = vmById[vmId];
                            if (vm) {
                                return `
                                    <tr>
                                        <td>${vm.name}</td>
                                        <td>${vm.cpuCores}</td>
                                        <td>${vm.memoryGb} GB</td>
                                        <td>${vm.storageGb} GB</td>
                                        <td><span class="badge bg-${getPriorityBadgeClass(vm.priority)}">P${vm.priority || 1}</span></td>
                                    </tr>
                                `;
                            }
                            return '';
                        }).join('')}
                    </tbody>
                </table>
            ` : '<p class="text-muted">No VMs assigned</p>'}
        </div>
    `);

    modal.show();
}

function getUtilClass(value) {
    if (value > 1) return 'over';
    if (value > 0.8) return 'high';
    if (value > 0.5) return 'medium';
    return 'low';
}

function solve() {
    if (!loadedPlacement) {
        showSimpleError("No placement data loaded. Please wait for the data to load or refresh the page.");
        return;
    }

    // Reset animation state for solving - capture current positions before solving modifies them
    vmPositionCache = buildPositionCache(loadedPlacement);
    console.log('Solve started. Initial position cache size:', Object.keys(vmPositionCache).length);

    $.post("/placements", JSON.stringify(loadedPlacement), function (data) {
        placementId = data;
        refreshSolvingButtons(true);
    }).fail(function (xhr, ajaxOptions, thrownError) {
        showError("Start solving failed.", xhr);
        refreshSolvingButtons(false);
    }, "text");
}

function stopSolving() {
    $.delete(`/placements/${placementId}`, function () {
        refreshSolvingButtons(false);
        // Do a final full render to ensure accuracy
        isFirstRender = true;
        refreshPlacement();
    }).fail(function (xhr, ajaxOptions, thrownError) {
        showError("Stop solving failed.", xhr);
    });
}

function analyze() {
    const modal = new bootstrap.Modal("#scoreAnalysisModal");
    modal.show();

    const scoreAnalysisModalContent = $("#scoreAnalysisModalContent");
    scoreAnalysisModalContent.empty();

    if (!loadedPlacement || loadedPlacement.score == null) {
        scoreAnalysisModalContent.text("No score to analyze yet, please first press the 'Solve' button.");
        return;
    }

    $('#scoreAnalysisScoreLabel').text(`(${loadedPlacement.score})`);

    $.put("/placements/analyze", JSON.stringify(loadedPlacement), function (scoreAnalysis) {
        let constraints = scoreAnalysis.constraints;

        constraints.sort((a, b) => {
            let aComponents = getScoreComponents(a.score);
            let bComponents = getScoreComponents(b.score);
            if (aComponents.hard < 0 && bComponents.hard > 0) return -1;
            if (aComponents.hard > 0 && bComponents.soft < 0) return 1;
            if (Math.abs(aComponents.hard) > Math.abs(bComponents.hard)) {
                return -1;
            } else {
                if (Math.abs(aComponents.soft) > Math.abs(bComponents.soft)) {
                    return -1;
                }
                return Math.abs(bComponents.soft) - Math.abs(aComponents.soft);
            }
        });

        constraints = constraints.map((e) => {
            let components = getScoreComponents(e.weight);
            e.type = components.hard !== 0 ? 'hard' : 'soft';
            e.weight = components[e.type];
            let scores = getScoreComponents(e.score);
            e.implicitScore = scores.hard !== 0 ? scores.hard : scores.soft;
            return e;
        });

        scoreAnalysisModalContent.empty();

        const analysisTable = $(`<table class="table"/>`).css({textAlign: 'center'});
        const analysisTHead = $(`<thead/>`).append($(`<tr/>`)
            .append($(`<th></th>`))
            .append($(`<th>Constraint</th>`).css({textAlign: 'left'}))
            .append($(`<th>Type</th>`))
            .append($(`<th># Matches</th>`))
            .append($(`<th>Weight</th>`))
            .append($(`<th>Score</th>`)));
        analysisTable.append(analysisTHead);

        const analysisTBody = $(`<tbody/>`);
        $.each(constraints, (index, constraintAnalysis) => {
            let icon = constraintAnalysis.type === "hard" && constraintAnalysis.implicitScore < 0
                ? '<span class="fas fa-exclamation-triangle text-danger"></span>'
                : '';
            if (!icon) {
                icon = constraintAnalysis.matches.length === 0
                    ? '<span class="fas fa-check-circle text-success"></span>'
                    : '';
            }

            let row = $(`<tr/>`);
            row.append($(`<td/>`).html(icon))
                .append($(`<td/>`).text(constraintAnalysis.name).css({textAlign: 'left'}))
                .append($(`<td/>`).html(`<span class="badge bg-${constraintAnalysis.type === 'hard' ? 'danger' : 'warning'}">${constraintAnalysis.type}</span>`))
                .append($(`<td/>`).html(`<b>${constraintAnalysis.matches.length}</b>`))
                .append($(`<td/>`).text(constraintAnalysis.weight))
                .append($(`<td/>`).text(constraintAnalysis.implicitScore));
            analysisTBody.append(row);
        });
        analysisTable.append(analysisTBody);
        scoreAnalysisModalContent.append(analysisTable);
    }).fail(function (xhr, ajaxOptions, thrownError) {
        showError("Analyze failed.", xhr);
    }, "text");
}

function getScoreComponents(score) {
    let components = {hard: 0, soft: 0};
    if (!score) return components;

    $.each([...score.matchAll(/(-?\d*\.?\d+)(hard|soft)/g)], (i, parts) => {
        components[parts[2]] = parseFloat(parts[1]);
    });

    return components;
}

function refreshSolvingButtons(solving) {
    if (solving) {
        $("#solveButton").hide();
        $("#stopSolvingButton").show();
        $("#solvingSpinner").addClass("active");
        if (autoRefreshIntervalId == null) {
            // 250ms polling for smooth real-time animations
            autoRefreshIntervalId = setInterval(refreshPlacement, 250);
        }
    } else {
        $("#solveButton").show();
        $("#stopSolvingButton").hide();
        $("#solvingSpinner").removeClass("active");
        if (autoRefreshIntervalId != null) {
            clearInterval(autoRefreshIntervalId);
            autoRefreshIntervalId = null;
        }
    }
}

function replaceQuickstartSolverForgeAutoHeaderFooter() {
    const solverforgeHeader = $("header#solverforge-auto-header");
    if (solverforgeHeader != null) {
        solverforgeHeader.css("background-color", "#ffffff");
        solverforgeHeader.append(
            $(`<div class="container-fluid">
        <nav class="navbar sticky-top navbar-expand-lg shadow-sm mb-3" style="background-color: #ffffff;">
          <a class="navbar-brand" href="https://www.solverforge.org">
            <img src="/webjars/solverforge/img/solverforge-horizontal.svg" alt="SolverForge logo" width="400">
          </a>
          <button class="navbar-toggler" type="button" data-toggle="collapse" data-target="#navbarNav" aria-controls="navbarNav" aria-expanded="false" aria-label="Toggle navigation">
            <span class="navbar-toggler-icon"></span>
          </button>
          <div class="collapse navbar-collapse" id="navbarNav">
            <ul class="nav nav-pills">
              <li class="nav-item active" id="navUIItem">
                <button class="nav-link active" id="navUI" data-bs-toggle="pill" data-bs-target="#demo" type="button" style="color: #1f2937;">Demo UI</button>
              </li>
              <li class="nav-item" id="navRestItem">
                <button class="nav-link" id="navRest" data-bs-toggle="pill" data-bs-target="#rest" type="button" style="color: #1f2937;">Guide</button>
              </li>
              <li class="nav-item" id="navOpenApiItem">
                <button class="nav-link" id="navOpenApi" data-bs-toggle="pill" data-bs-target="#openapi" type="button" style="color: #1f2937;">REST API</button>
              </li>
            </ul>
          </div>
          <div class="ms-auto">
              <div class="dropdown">
                  <button class="btn dropdown-toggle" type="button" id="dropdownMenuButton" data-bs-toggle="dropdown" aria-haspopup="true" aria-expanded="false" style="background-color: #10b981; color: #ffffff; border-color: #10b981;">
                      Data
                  </button>
                  <div id="testDataButton" class="dropdown-menu" aria-labelledby="dropdownMenuButton"></div>
              </div>
          </div>
        </nav>
      </div>`));
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
             </footer>`));
    }
}

function copyTextToClipboard(elementId) {
    const element = document.getElementById(elementId);
    if (element) {
        navigator.clipboard.writeText(element.textContent).then(() => {
            // Optional: show feedback
        }).catch(err => {
            console.error('Failed to copy text: ', err);
        });
    }
}
