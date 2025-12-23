const TROLLEY_PATHS = new Map();
let TROLLEY_TRAVEL_DISTANCE = new Map();
let autoRefreshIntervalId = null;
let loadedSchedule = null;
let currentProblemId = null;
let solverWasNeverStarted = true;
let sseConnection = null;
let lastScore = null;

// Build a lookup map for trolleySteps by ID to resolve step references
function buildStepLookup(orderPickingSolution) {
    const lookup = new Map();
    for (const step of orderPickingSolution.trolleySteps) {
        lookup.set(step.id, step);
    }
    return lookup;
}

// Get trolley steps from the trolley.steps list (Python uses PlanningListVariable)
function getTrolleySteps(trolley, stepLookup) {
    if (!trolley.steps || trolley.steps.length === 0) {
        return [];
    }
    // Steps can be IDs (strings) or full objects
    return trolley.steps.map(stepRef => {
        if (typeof stepRef === 'string') {
            return stepLookup.get(stepRef);
        }
        return stepRef;
    }).filter(step => step != null);
}

function refreshSolution() {
    if (!currentProblemId) {
        // Load demo data initially
        loadDemoData();
        return;
    }

    Promise.all([
        fetch(`/schedules/${currentProblemId}`).then(r => r.json()),
        fetch(`/schedules/${currentProblemId}/distances`).then(r => r.json())
    ]).then(([solution, distances]) => {
        TROLLEY_TRAVEL_DISTANCE = new Map(Object.entries(distances.distance_to_travel_by_trolley || distances.distanceToTravelByTrolley || {}));
        updateWelcomeMessage(solverWasNeverStarted);
        printSolutionScore(solution);
        printSolutionTable(solution);
        printTrolleysMap(solution);
        loadedSchedule = solution;
        const solving = solution.solverStatus != null && solution.solverStatus !== "NOT_SOLVING";
        refreshSolvingButtons(solving);
        updateLogiSimView();
    }).catch(function (error) {
        const err = "Internal error: " + error;
        showError("An error was produced during solution refresh.", err);
    });
}

function loadDemoData() {
    fetch('/demo-data/DEFAULT')
        .then(r => r.json())
        .then(solution => {
            updateWelcomeMessage(true);
            printSolutionScore(solution);
            printSolutionTable(solution);
            printTrolleysMap(solution);
            loadedSchedule = solution;
            refreshSolvingButtons(false);
            updateLogiSimView();
        })
        .catch(function (error) {
            showError("Failed to load demo data.", error);
        });
}

// refresh solution to resize the canvas
window.addEventListener('resize', e => refreshSolution());
refreshSolution();

function printSolutionScore(orderPickingSolution) {
    const score = orderPickingSolution.score;
    if (score == null) {
        $("#score").text("Score: ?");
    } else if (typeof score === 'string') {
        // Python returns score as string like "0hard/0soft"
        $("#score").text(`Score: ${score}`);
    } else {
        $("#score").text(`Score: ${score.hardScore}hard/${score.softScore}soft`);
    }
}

function updateWelcomeMessage(neverStarted) {
    const welcomeMessageContainer = $('#welcomeMessageContainer');
    if (neverStarted) {
        welcomeMessageContainer.show();
    } else {
        welcomeMessageContainer.empty();
    }
}

function printSolutionTable(orderPickingSolution) {
    const container = $('#pickingPlanContainer');
    container.empty();

    const stepLookup = buildStepLookup(orderPickingSolution);
    const unassignedOrderItemsAndOrdersSpreading = findUnassignedOrderItemsAndOrdersSpreading(orderPickingSolution);
    const unassignedItemsByOrder = unassignedOrderItemsAndOrdersSpreading[0];
    const trolleysByOrder = unassignedOrderItemsAndOrdersSpreading[1];
    const unassignedTrolleys = [];

    // Create trolley cards container
    const cardsContainer = $('<div class="trolley-cards-container">').appendTo(container);

    for (const trolley of orderPickingSolution.trolleys) {
        const trolleySteps = getTrolleySteps(trolley, stepLookup);
        if (trolleySteps.length > 0) {
            const travelDistance = TROLLEY_TRAVEL_DISTANCE.get(trolley.id) || 0;
            printTrolleyCard(cardsContainer, trolley, trolleySteps, travelDistance, unassignedItemsByOrder, trolleysByOrder);
        } else {
            unassignedTrolleys.push(trolley);
        }
    }

    // Add waiting trolleys section if any
    if (unassignedTrolleys.length > 0) {
        const waitingSection = $(`
            <div class="waiting-trolleys">
                <div class="waiting-header">
                    <i class="fas fa-clock"></i>
                    <span>${unassignedTrolleys.length} trolleys waiting for assignments</span>
                </div>
            </div>
        `).appendTo(cardsContainer);
    }

    printUnassignedEntities(unassignedTrolleys, unassignedItemsByOrder);
}

function printTrolleyCard(container, trolley, trolleySteps, travelDistance, unassignedItemsByOrder, trolleysByOrder) {
    const trolleyId = trolley.id;
    const color = trolleyColor(trolleyId);

    // Calculate capacity usage
    let totalVolume = 0;
    const orderVolumes = new Map();
    for (const step of trolleySteps) {
        const volume = step.orderItem.product.volume;
        totalVolume += volume;
        const orderId = step.orderItem.orderId;
        orderVolumes.set(orderId, (orderVolumes.get(orderId) || 0) + volume);
    }

    const totalCapacity = trolley.bucketCount * trolley.bucketCapacity;
    const capacityPercent = Math.min(100, Math.round((totalVolume / totalCapacity) * 100));
    const capacityClass = capacityPercent >= 90 ? 'critical' : (capacityPercent >= 70 ? 'warning' : '');

    // Unique orders
    const uniqueOrders = new Set(trolleySteps.map(s => s.orderItem.orderId));

    const card = $(`
        <div class="trolley-card fade-in" data-trolley="${trolleyId}">
            <div class="trolley-card-header" data-bs-toggle="collapse" data-bs-target="#trolleyDetail${trolleyId}">
                <div class="trolley-icon" style="border: 2px solid ${color};">
                    <i class="fas fa-cart-plus"></i>
                </div>
                <div class="trolley-info">
                    <div class="trolley-name">Trolley ${trolleyId}</div>
                    <div class="trolley-stats">
                        ${trolleySteps.length} items &bull; ${uniqueOrders.size} orders &bull; ${travelDistance}m
                    </div>
                </div>
                <div class="capacity-indicator">
                    <div class="capacity-bar">
                        <div class="capacity-bar-fill ${capacityClass}" style="width: ${capacityPercent}%"></div>
                    </div>
                    <span class="capacity-text">${capacityPercent}%</span>
                </div>
                <i class="fas fa-chevron-down expand-icon"></i>
            </div>
            <div class="collapse" id="trolleyDetail${trolleyId}">
                <div class="trolley-card-body">
                    <!-- Steps table will be added here -->
                </div>
            </div>
        </div>
    `);

    // Build steps table inside card body
    const cardBody = card.find('.trolley-card-body');
    const stepsTable = $('<table class="steps-table">').appendTo(cardBody);
    const thead = $(`
        <thead>
            <tr>
                <th>Step</th>
                <th>Order</th>
                <th>Product</th>
                <th>Location</th>
                <th>Volume</th>
            </tr>
        </thead>
    `).appendTo(stepsTable);
    const tbody = $('<tbody>').appendTo(stepsTable);

    let stepNumber = 1;
    for (const step of trolleySteps) {
        const orderItem = step.orderItem;
        const product = orderItem.product;
        const location = product.location;
        const orderId = orderItem.orderId;
        const orderColorVal = orderColor(orderId);

        const row = $(`
            <tr>
                <td><span class="step-number">${stepNumber}</span></td>
                <td><span class="order-badge" style="background-color: ${orderColorVal}; color: white;">Order ${orderId}</span></td>
                <td>${product.name}</td>
                <td><code>${location.shelvingId} ${location.side} R${location.row}</code></td>
                <td>${formatVolume(product.volume)}</td>
            </tr>
        `);
        tbody.append(row);
        stepNumber++;
    }

    // Add bucket visualization
    const bucketViz = buildBucketVisualization(trolley, orderVolumes);
    cardBody.append(bucketViz);

    container.append(card);
}

function formatVolume(volume) {
    if (volume >= 1000) {
        return (volume / 1000).toFixed(1) + 'L';
    }
    return volume + 'cm³';
}

function buildBucketVisualization(trolley, orderVolumes) {
    const container = $('<div class="bucket-viz">');
    const header = $('<div class="bucket-viz-header">Bucket Allocation</div>').appendTo(container);
    const bucketsRow = $('<div class="buckets-row">').appendTo(container);

    const sortedOrders = Array.from(orderVolumes.entries()).sort((a, b) => b[1] - a[1]);

    let availableBuckets = trolley.bucketCount;
    let bucketNum = 0;

    for (const [orderId, volume] of sortedOrders) {
        const requiredBuckets = Math.ceil(volume / trolley.bucketCapacity);
        const orderColorVal = orderColor(orderId);

        for (let b = 0; b < requiredBuckets && bucketNum < trolley.bucketCount; b++) {
            const isLastBucket = b === requiredBuckets - 1;
            const bucketVolume = isLastBucket
                ? volume - (b * trolley.bucketCapacity)
                : trolley.bucketCapacity;
            const fillPercent = Math.round((bucketVolume / trolley.bucketCapacity) * 100);

            const bucket = $(`
                <div class="bucket" title="Order ${orderId}: ${fillPercent}% full">
                    <div class="bucket-fill" style="height: ${fillPercent}%; background-color: ${orderColorVal};"></div>
                    <span class="bucket-label">${orderId}</span>
                </div>
            `);
            bucketsRow.append(bucket);
            bucketNum++;
            availableBuckets--;
        }
    }

    // Empty buckets
    for (let i = 0; i < availableBuckets; i++) {
        const bucket = $(`
            <div class="bucket empty" title="Empty bucket">
                <span class="bucket-label">-</span>
            </div>
        `);
        bucketsRow.append(bucket);
    }

    return container;
}

function printUnassignedEntities(unassignedTrolleys, unAssignedItemsByOrder) {
    const unassignedEntitiesContainer = $('#unassignedEntitiesContainer');
    unassignedEntitiesContainer.empty();

    const unassignedEntitiesNav = $('<nav>').appendTo(unassignedEntitiesContainer);
    const unassignedEntitiesTabs = $('<div class="nav nav-tabs" id="unassignedEntitiesTabList" role="tablist">').appendTo(unassignedEntitiesNav);
    const unassignedEntitiesTabListContent = $('<div class="tab-content" id="unassignedEntitiesTabListContent">').appendTo(unassignedEntitiesContainer);

    printUnassignedTrolleys(unassignedTrolleys, unassignedEntitiesTabs, unassignedEntitiesTabListContent);
    printUnassignedOrders(unAssignedItemsByOrder, unassignedEntitiesTabs, unassignedEntitiesTabListContent);
}

function printTabNavLink(navTabs, active, tabId, tabPaneId, name) {
    const activeValue = active ? 'active' : '';
    return $(`<a class="nav-link ${activeValue}" id="${tabId}" data-bs-toggle="tab" href="#${tabPaneId}" role="tab" aria-controls="${tabId}" aria-selected="true">${name}</a>`).appendTo(navTabs);
}

function printTabPane(navTabsContainer, active, show, tabPaneId, tabId) {
    const activeValue = active ? 'active' : '';
    const showValue = show ? 'show' : '';
    return $(`<div class="tab-pane fade ${showValue} ${activeValue}" id="${tabPaneId}" role="tabpanel" aria-labelledby="${tabId}"></div>`).appendTo(navTabsContainer);
}

function printUnassignedTrolleys(trolleys, unassignedEntitiesTabs, unassignedEntitiesTabListContent) {
    printTabNavLink(unassignedEntitiesTabs, true, 'unassignedTrolleys', 'unassignedTrolleysTab', 'Trolleys');
    const tabPane = printTabPane(unassignedEntitiesTabListContent, true, true, 'unassignedTrolleysTab', 'unassignedTrolleys');
    const unassignedTrolleysTable = $(`<table class="table table-striped" id="unassignedTrolleysTable">`).appendTo(tabPane);
    printUnassignedTrolleysTableHeader(unassignedTrolleysTable);
    const unassignedTrolleysTableBody = $('<tbody>').appendTo(unassignedTrolleysTable);
    for (const trolley of trolleys) {
        const location = trolley.location;
        printUnassignedTrolleyRow(unassignedTrolleysTableBody, trolley, location);
    }
}

function printUnassignedTrolleysTableHeader(unassignedTrolleysTable) {
    const header = $('<thead class="table-dark">').appendTo(unassignedTrolleysTable);
    const headerTr = $('<tr>').appendTo(header);
    $('<th scope="col">#Trolley</th>').appendTo(headerTr);
    $('<th scope="col">Start location</th>').appendTo(headerTr);
    $('<th scope="col">Buckets</th>').appendTo(headerTr);
    $('<th scope="col">Bucket capacity</th>').appendTo(headerTr);
}

function printUnassignedTrolleyRow(unassignedTrolleysTableBody, trolley, location) {
    const trolleyRow = $('<tr>').appendTo(unassignedTrolleysTableBody);
    trolleyRow.append($(`<th scope="row">${trolley.id}</th>`));
    trolleyRow.append($(`<td>${location.shelvingId}, ${location.side}, ${location.row}</td>`));
    trolleyRow.append($(`<td>${trolley.bucketCount}</td>`));
    trolleyRow.append($(`<td>${trolley.bucketCapacity}</td>`));
}

function printUnassignedOrders(unAssignedItemsByOrder, unassignedEntitiesTabs, unassignedEntitiesTabListContent) {
    const orderIds = Array.from(unAssignedItemsByOrder.keys());
    orderIds.sort((a, b) => a - b);
    for (const orderId of orderIds) {
        const unassignedItems = unAssignedItemsByOrder.get(orderId);
        if (unassignedItems.length > 0) {
            unassignedItems.sort((item1, item2) => item1.id - item2.id);
            printUnassignedOrder(orderId, unassignedItems, unassignedEntitiesTabs, unassignedEntitiesTabListContent);
        }
    }
}

function printUnassignedOrder(orderId, unassignedItems, unassignedEntitiesTabs, unassignedEntitiesTabListContent) {
    const name = 'Order_' + orderId;
    const tabId = 'unassignedOrder_' + orderId;
    const tabPaneId = "unassignedOrderTab_" + orderId;

    printTabNavLink(unassignedEntitiesTabs, false, tabId, tabPaneId, name);
    const tabPane = printTabPane(unassignedEntitiesTabListContent, false, false, tabPaneId, tabId);
    const unassignedOrderTable = $('<table class="table table-striped">').appendTo(tabPane);
    printUnassignedOrderTableHeader(unassignedOrderTable);
    const unassignedOrderTableBody = $('<tbody>').appendTo(unassignedOrderTable);
    for (const orderItem of unassignedItems) {
        printUnassignedOrderRow(unassignedOrderTableBody, orderItem);
    }
}

function printUnassignedOrderTableHeader(unassignedOrderTable) {
    const header = $('<thead class="table-dark">').appendTo(unassignedOrderTable);
    const headerTr = $('<tr>').appendTo(header);
    $('<th scope="col">#Order item</th>').appendTo(headerTr);
    $('<th scope="col">Warehouse location</th>').appendTo(headerTr);
    $('<th scope="col">Name</th>').appendTo(headerTr);
    $('<th scope="col">Volume</th>').appendTo(headerTr);
}

function printUnassignedOrderRow(unassignedOrderTableBody, orderItem) {
    const itemRow = $('<tr>').appendTo(unassignedOrderTableBody);
    const product = orderItem.product;
    const location = product.location;
    itemRow.append($(`<th scope="row">${orderItem.id}</th>`));
    itemRow.append($(`<td>${location.shelvingId}, ${location.side}, ${location.row}</td>`));
    itemRow.append($(`<td>${product.name}</td>`));
    itemRow.append($(`<td>${product.volume}</td>`));
}

/**
 * Calculates the unassigned items and the occupied trolleys by each order.
 */
function findUnassignedOrderItemsAndOrdersSpreading(orderPickingSolution) {
    const unassignedItemsByOrder = new Map();
    const trolleysByOrder = new Map();
    for (const trolleyStep of orderPickingSolution.trolleySteps) {
        const orderItem = trolleyStep.orderItem;
        const orderId = orderItem.orderId;
        const trolleyId = trolleyStep.trolleyId || trolleyStep.trolley;
        if (trolleyId === null || trolleyId === undefined) {
            let unassignedItems = unassignedItemsByOrder.get(orderId);
            if (unassignedItems === undefined) {
                unassignedItems = [];
                unassignedItemsByOrder.set(orderId, unassignedItems);
            }
            unassignedItems.push(orderItem);
        } else {
            let trolleys = trolleysByOrder.get(orderId);
            if (trolleys === undefined) {
                trolleys = new Set();
                trolleysByOrder.set(orderId, trolleys);
            }
            trolleys.add(typeof trolleyId === 'string' ? trolleyId : trolleyId.id || trolleyId);
        }
    }
    return [unassignedItemsByOrder, trolleysByOrder];
}

function printTrolley(tableBody, trolley, trolleySteps, travelDistance, unAssignedItemsByOrder, trolleysByOrder) {
    const trolleyId = 'Trolley_' + trolley.id;
    const trolleyIcon = 'fa-cart-plus';
    const trolleyRow = $('<tr class="agent-row">').appendTo(tableBody);
    const trolleyTd = $('<td style="width:15%;">').appendTo(trolleyRow);
    const trolleyCard = $('<div class="card" style="background-color:#f7ecd5">').appendTo(trolleyTd);
    const trolleyCardBody = $('<div class="card-body p-1">').appendTo(trolleyCard);
    const trolleyCardRow = $(`<div class="row flex-nowrap">
                <div class="col-1">
                    <i class="fas ${trolleyIcon}"></i>
                </div>
                <div class="col-11">
                    <span style="font-size:1em" title="${trolleySteps.length} order items assigned to this Trolley, with a travel distance of ${travelDistance} meters."><a id="${trolleyId}">${trolleyId}&nbsp;&nbsp;(${trolleySteps.length} items, ${travelDistance} m)</a></span>
                </div>
            </div>`).appendTo(trolleyCardBody);

    printTrolleyDetail(trolleyCardBody, trolley, trolleySteps, unAssignedItemsByOrder, trolleysByOrder);

    const stepsTd = $('<td style="flex-flow:row; display: flex;">').appendTo(trolleyRow);
    printTrolleySteps(stepsTd, trolleySteps);
}

function printTrolleyDetail(detailContainer, trolley, trolleySteps, unAssignedItemsByOrder, trolleysByOrder) {
    const orderVolumes = new Map();
    for (const trolleyStep of trolleySteps) {
        const orderItem = trolleyStep.orderItem;
        const orderId = orderItem.orderId;
        let orderVolume = orderVolumes.get(orderId);
        if (orderVolume === undefined) {
            orderVolume = orderItem.product.volume;
        } else {
            orderVolume = orderVolume + orderItem.product.volume;
        }
        orderVolumes.set(orderId, orderVolume);
    }

    const sortedEntries = Array.from(orderVolumes.entries());
    sortedEntries.sort((e1, e2) => e2[1] - e1[1]);

    const bucketWidth = 50;
    const trolleyBucketsContainer = $('<div class="row">').appendTo(detailContainer);
    const bucketsDiv = $('<div style="padding-left: 15px; padding-top: 15px;">').appendTo(trolleyBucketsContainer);
    const bucketsTable = $('<table>').appendTo(bucketsDiv);
    let bucketsRow;
    let bucketTd;
    let bucketTdNumber = 0;
    let availableBuckets = trolley.bucketCount;
    let orderCount = 0;
    const ordersDetail = [];

    for (const entry of sortedEntries) {
        const orderNumber = entry[0];
        const orderTotalVolume = entry[1];
        const orderRequiredBuckets = Math.ceil(orderTotalVolume / trolley.bucketCapacity);
        const bucketColor = orderColor(orderNumber);
        ordersDetail.push([orderNumber, bucketColor, orderTotalVolume, orderRequiredBuckets]);
        for (let orderBucket = 1; orderBucket <= orderRequiredBuckets; orderBucket++) {
            if (bucketTdNumber % 2 === 0) {
                bucketsRow = $('<tr>').appendTo(bucketsTable);
            }
            bucketTdNumber++;
            let bucketDivWidth = bucketWidth;
            let bucketOccupancyPercent = 100;
            if (orderBucket === orderRequiredBuckets) {
                const lastBucketVolume = orderTotalVolume - ((orderBucket - 1) * trolley.bucketCapacity);
                bucketDivWidth = (bucketDivWidth / trolley.bucketCapacity) * lastBucketVolume;
                bucketOccupancyPercent = Math.ceil((100 * bucketDivWidth) / bucketWidth);
            }
            bucketTd = $(`<td style="border: 1px solid; border-color: black; padding: 1px; width:${bucketWidth};" title="${bucketOccupancyPercent}% of the bucket reserved for order #${orderNumber}">`).appendTo(bucketsRow);
            $(`<div style="background-color: ${bucketColor}; width:${bucketDivWidth}px; height:${bucketWidth}px;"></div>`).appendTo(bucketTd);
            availableBuckets--;
        }
    }

    if (availableBuckets > 0) {
        for (let i = 0; i < availableBuckets; i++) {
            if (bucketTdNumber % 2 === 0) {
                bucketsRow = $('<tr>').appendTo(bucketsTable);
            }
            bucketTdNumber++;
            bucketTd = $(`<td style="border: 1px solid; border-color: black; padding: 1px; width:${bucketWidth};" title="Free bucket">`).appendTo(bucketsRow);
            $(`<div style="width:${bucketWidth}px; height:${bucketWidth}px;"></div>`).appendTo(bucketTd);
        }
    } else if (availableBuckets < 0) {
        $(`<div><strong>Over constrained problem!! with the configured number of trolleys and buckets it's not possible to complete the orders, please check the configuration parameters.</strong></div>`).appendTo(bucketsDiv);
    }

    const trolleyOrdersDetailContainer = $('<div class="row" style="padding-left: 15px; padding-top: 15px; padding-right: 15px;">').appendTo(detailContainer);
    printTrolleyOrdersDetail(trolleyOrdersDetailContainer, trolley, ordersDetail);

    const trolleyOrdersSplitDetailContainer = $('<div class="row" style="padding-left: 15px; padding-top: 15px; padding-right: 15px;">').appendTo(detailContainer);
    printTrolleyOrdersSplitDetail(trolleyOrdersSplitDetailContainer, trolley, ordersDetail, unAssignedItemsByOrder, trolleysByOrder);
}

function printTrolleyOrdersDetail(ordersDetailContainer, trolley, ordersDetail) {
    const orderDetailsTable = $('<table class="table table-striped">').appendTo(ordersDetailContainer);
    printOrdersDetailTableHeader(orderDetailsTable);
    const ordersDetailTableBody = $('<tbody>').appendTo(orderDetailsTable);
    for (let orderDetail of ordersDetail) {
        const orderNumber = orderDetail[0];
        const bucketColor = orderDetail[1];
        const orderTotalVolume = orderDetail[2];
        const orderRequiredBuckets = orderDetail[3];
        printOrdersDetailRow(ordersDetailTableBody, orderNumber, bucketColor, orderTotalVolume, orderRequiredBuckets);
    }
    $(`<div>Bucket capacity ${trolley.bucketCapacity}</div>`).appendTo(ordersDetailContainer);
}

function printOrdersDetailTableHeader(ordersDetailTable) {
    const header = $('<thead class="table-dark">').appendTo(ordersDetailTable);
    const headerTr = $('<tr>').appendTo(header);
    $('<th scope="col">#Order</th>').appendTo(headerTr);
    $('<th scope="col">Volume</th>').appendTo(headerTr);
    $('<th scope="col">Buckets</th>').appendTo(headerTr);
}

function printOrdersDetailRow(ordersDetailTableBody, orderNumber, bucketColor, orderTotalVolume, orderRequiredBuckets) {
    const orderDetailRow = $('<tr>').appendTo(ordersDetailTableBody);
    orderDetailRow.append($(`<th scope="row"><div style="background-color: ${bucketColor}">${orderNumber}</div></th>`));
    orderDetailRow.append($(`<td>${orderTotalVolume}</td>`));
    orderDetailRow.append($(`<td>${orderRequiredBuckets}</td>`));
}

function printTrolleyOrdersSplitDetail(ordersDetailContainer, trolley, ordersDetail, unAssignedItemsByOrder, trolleysByOrder) {
    for (const orderDetail of ordersDetail) {
        const orderNumber = orderDetail[0];
        let anotherTrolleys = trolleysByOrder.get(orderNumber);
        if (anotherTrolleys !== undefined && anotherTrolleys.size > 1) {
            const anotherTrolleysDiv = $(`<div><span>*Order #${orderNumber} also in</span></div>`).appendTo(ordersDetailContainer);
            let first = true;
            for (const anotherTrolley of anotherTrolleys) {
                if (trolley.id !== anotherTrolley) {
                    const separator = first ? '' : ',';
                    $(`<a href="#Trolley_${anotherTrolley}">${separator}&nbsp;T${anotherTrolley}</a>`).appendTo(anotherTrolleysDiv);
                    first = false;
                }
            }
        }
    }
    for (const orderDetail of ordersDetail) {
        const orderNumber = ordersDetail[0];
        const unAssignedItems = unAssignedItemsByOrder.get(orderNumber);
        if (unAssignedItems !== undefined && unAssignedItems.length > 0) {
            $(`<div><span>*Order #${orderNumber} has <a href="#UnAssignedOrderItems_${orderNumber}">${unAssignedItems.length} un-assigned items</a></span></div>`).appendTo(ordersDetailContainer);
        }
    }
}

function printTrolleySteps(stepsContainer, trolleySteps) {
    const stepsTable = $('<table class="table table-striped">').appendTo(stepsContainer);
    printTrolleyStepsTableHeader(stepsTable);
    const stepsTableBody = $('<tbody>').appendTo(stepsTable);
    let stepNumber = 1;
    for (const trolleyStep of trolleySteps) {
        printTrolleyStep(stepsTableBody, stepNumber++, trolleyStep)
    }
}

function printTrolleyStepsTableHeader(stepsTable) {
    const header = $('<thead class="table-dark">').appendTo(stepsTable);
    const headerTr = $('<tr>').appendTo(header);
    $('<th scope="col">#Stop</th>').appendTo(headerTr);
    $('<th scope="col">Warehouse location</th>').appendTo(headerTr);
    $('<th scope="col">#Order</th>').appendTo(headerTr);
    $('<th scope="col">#Order item</th>').appendTo(headerTr);
    $('<th scope="col">Name</th>').appendTo(headerTr);
    $('<th scope="col">Volume</th>').appendTo(headerTr);
}

function printTrolleyStep(stepsTableBody, stepNumber, trolleyStep) {
    const orderItem = trolleyStep.orderItem;
    const orderItemId = orderItem.id
    const product = orderItem.product;
    const location = product.location;
    const orderId = orderItem.orderId;

    const stepRow = $('<tr>').appendTo(stepsTableBody);
    stepRow.append($(`<th scope="row">${stepNumber}</th>`));
    stepRow.append($(`<td>${location.shelvingId}, ${location.side}, ${location.row}</td>`));
    stepRow.append($(`<td>${orderId}</td>`));
    stepRow.append($(`<td>${orderItemId}</td>`));
    stepRow.append($(`<td>${product.name}</td>`));
    stepRow.append($(`<td>${product.volume}</td>`));
}

function printTrolleysMap(orderPickingSolution) {
    clearWarehouseCanvas();
    drawWarehouse();
    const mapActionsContainer = $('#mapActionsContainer');
    mapActionsContainer.children().remove();
    const trolleyCheckBoxes = [];
    const stepLookup = buildStepLookup(orderPickingSolution);
    let trolleyIndex = 0;
    for (const trolley of orderPickingSolution.trolleys) {
        const trolleySteps = getTrolleySteps(trolley, stepLookup);
        if (trolleySteps.length > 0) {
            printTrolleyPath(trolley, trolleySteps, trolleyIndex, orderPickingSolution.trolleys.length, false);
            trolleyCheckBoxes.push(trolley.id);
        }
        trolleyIndex++;
    }
    trolleyIndex = 0;
    for (const trolley of orderPickingSolution.trolleys) {
        const trolleySteps = getTrolleySteps(trolley, stepLookup);
        if (trolleySteps.length > 0) {
            printTrolleyPath(trolley, trolleySteps, trolleyIndex, orderPickingSolution.trolleys.length, true);
        }
        trolleyIndex++;
    }
    if (trolleyCheckBoxes.length > 0) {
        const mapActionsContainer = $('#mapActionsContainer');
        mapActionsContainer.append($(`<div style="display: inline-block; padding-left: 10px;">
        <button id="unSelectButton" type="button" class="btn btn-secondary btn-sm" onclick="unCheckTrolleyCheckBoxes([${trolleyCheckBoxes}])">Uncheck all</button>
        </div>`));
    }
}

function printTrolleyPath(trolley, trolleySteps, trolleyIndex, trolleyCount, writeText) {
    const trolleyPath = [];
    const trolleyLocation = trolley.location;

    trolleyPath.push(new WarehouseLocation(trolleyLocation.shelvingId, trolleyLocation.side, trolleyLocation.row));
    for (const trolleyStep of trolleySteps) {
        const location = trolleyStep.orderItem.product.location;
        trolleyPath.push(new WarehouseLocation(location.shelvingId, location.side, location.row));
    }
    trolleyPath.push(new WarehouseLocation(trolleyLocation.shelvingId, trolleyLocation.side, trolleyLocation.row));
    TROLLEY_PATHS.set(trolley.id, trolleyPath);

    const color = trolleyColor(trolley.id);
    let trolleyCheckboxEnabled = false;
    if (trolleyPath.length > 2) {
        if (writeText) {
            drawTrolleyText(color, trolleyPath, trolleyIndex, trolleyCount);
        } else {
            drawTrolleyPath(color, trolleyPath, trolleyIndex, trolleyCount);
            trolleyCheckboxEnabled = true;
            const travelDistance = TROLLEY_TRAVEL_DISTANCE.get(trolley.id) || 0;
            printTrolleyCheckbox(trolley, trolleySteps.length, travelDistance, color, trolleyCheckboxEnabled);
        }
    }
}

function printTrolleyCheckbox(trolley, stepsLength, travelDistance, color, enabled) {
    const mapActionsContainer = $('#mapActionsContainer');
    const disabledValue = enabled ? '' : 'disabled';
    const checkedValue = enabled ? 'true' : 'false';
    mapActionsContainer.append($(`<div style="display: inline-block; padding-left: 15px;">
        <div class="trolley-checkbox-rectangle" style="background-color: ${color}; display: inline-block;"></div>
        <div style="display: inline-block;">
            <label title="${stepsLength} order items assigned to this Trolley, with a travel distance of ${travelDistance} meters.">
            <input type="checkbox" id="trolleyPath_${trolley.id}" onChange="printSelectedTrolleys()" checked="${checkedValue}" ${disabledValue}/>
                Trolley_${trolley.id} (${stepsLength} items, ${travelDistance} m)
            </label>
        </div>
    </div>`));
}

function unCheckTrolleyCheckBoxes(trolleyCheckBoxes) {
    for (const trolleyCheckBoxId of trolleyCheckBoxes) {
        const trolleyCheckBox = $(`#trolleyPath_${trolleyCheckBoxId}`);
        trolleyCheckBox.prop('checked', false);
    }
    clearWarehouseCanvas();
    drawWarehouse()
}

function orderColor(orderId) {
    return pickColor('order_color_' + orderId);
}

function trolleyColor(trolleyId) {
    // Use getTrolleyColor from logisim-view.js for consistent colors
    if (typeof getTrolleyColor === 'function') {
        return getTrolleyColor(trolleyId);
    }
    // Fallback to fixed color palette matching logisim-view.js
    const colors = ['#ef4444', '#3b82f6', '#10b981', '#f59e0b', '#8b5cf6', '#06b6d4', '#ec4899', '#84cc16'];
    return colors[(parseInt(trolleyId) - 1) % colors.length];
}

function printSelectedTrolleys() {
    clearWarehouseCanvas();
    drawWarehouse();
    let it = TROLLEY_PATHS.entries();
    let trolleyIndex = 0;
    for (const trolleyEntry of it) {
        const trolleyCheck = document.getElementById('trolleyPath_' + trolleyEntry[0]);
        if (trolleyCheck.checked) {
            const color = trolleyColor(trolleyEntry[0]);
            drawTrolleyPath(color, trolleyEntry[1], trolleyIndex, TROLLEY_PATHS.size);
        }
        trolleyIndex++;
    }
    it = TROLLEY_PATHS.entries();
    trolleyIndex = 0;
    for (const trolleyEntry of it) {
        const trolleyCheck = document.getElementById('trolleyPath_' + trolleyEntry[0]);
        if (trolleyCheck.checked) {
            const color = trolleyColor(trolleyEntry[0]);
            drawTrolleyText(color, trolleyEntry[1], trolleyIndex + TROLLEY_PATHS.size, TROLLEY_PATHS.size);
        }
        trolleyIndex++;
    }
}

function refreshSolvingButtons(solving) {
    if (solving) {
        $("#solveButton").hide();
        $("#stopSolvingButton").show();
        $("#solvingSpinner").addClass("active");
        // Only use polling as fallback if SSE not connected
        if (autoRefreshIntervalId == null && !sseConnection) {
            autoRefreshIntervalId = setInterval(refreshSolution, 1000);
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

function connectSSE(problemId) {
    // Close existing connection
    if (sseConnection) {
        sseConnection.close();
    }

    sseConnection = new EventSource(`/schedules/${problemId}/stream`);

    sseConnection.addEventListener('update', function(event) {
        const data = JSON.parse(event.data);
        const solution = data.solution;
        const distances = data.distances;

        console.log('[SSE] Update received:', {
            version: data.version,
            updateCount: data.updateCount,
            score: solution.score,
            solverStatus: solution.solverStatus,
            trolleysWithSteps: solution.trolleys.filter(t => t.steps && t.steps.length > 0).length
        });

        // Detect score improvement for animation
        const newScore = solution.score;
        if (lastScore && newScore && newScore !== lastScore) {
            flashScoreImprovement();
        }
        lastScore = newScore;

        // Update state
        TROLLEY_TRAVEL_DISTANCE = new Map(Object.entries(distances || {}));
        loadedSchedule = solution;

        // Update all views
        updateWelcomeMessage(false);
        printSolutionScore(solution);
        printSolutionTable(solution);
        printTrolleysMap(solution);

        // Update LogiSim with animation during solving
        const solving = solution.solverStatus != null && solution.solverStatus !== "NOT_SOLVING";
        if (solving) {
            // Update animation data (paths will update, trolleys keep moving)
            if (typeof updateLogiSimAnimationData === 'function') {
                updateLogiSimAnimationData(solution);
            }
            // Also update stats overlay
            updateLogiSimStats(solution);
            updateLogiSimLegend(solution);
        } else {
            // Stop animation and render final state
            if (typeof stopLogiSimSolvingAnimation === 'function') {
                stopLogiSimSolvingAnimation();
            }
            updateLogiSimView();
        }

        refreshSolvingButtons(solving);
    });

    sseConnection.addEventListener('done', function(event) {
        console.log('SSE: Solving complete');
        // Stop animation
        if (typeof stopLogiSimSolvingAnimation === 'function') {
            stopLogiSimSolvingAnimation();
        }
        updateLogiSimView();
        refreshSolvingButtons(false);
        sseConnection.close();
        sseConnection = null;
    });

    sseConnection.addEventListener('error', function(event) {
        console.error('SSE error, falling back to polling');
        sseConnection.close();
        sseConnection = null;
        // Fallback to polling
        if (autoRefreshIntervalId == null) {
            autoRefreshIntervalId = setInterval(refreshSolution, 1000);
        }
    });
}

function flashScoreImprovement() {
    const scoreEl = $("#score");
    scoreEl.addClass("score-improved");
    setTimeout(() => scoreEl.removeClass("score-improved"), 500);
}

function solve() {
    solverWasNeverStarted = false;
    lastScore = null;

    fetch('/schedules', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(loadedSchedule)
    })
    .then(r => r.text())
    .then(problemId => {
        currentProblemId = problemId.replace(/"/g, '');
        refreshSolvingButtons(true);

        // Start animation AFTER server acknowledged (ensures valid problem ID)
        if (loadedSchedule && typeof startLogiSimSolvingAnimation === 'function') {
            startLogiSimSolvingAnimation(loadedSchedule);
        }

        // Connect to SSE stream for real-time updates
        connectSSE(currentProblemId);
    })
    .catch(function (error) {
        showError("Start solving failed.", error);
        // Stop animation on error
        if (typeof stopLogiSimSolvingAnimation === 'function') {
            stopLogiSimSolvingAnimation();
        }
    });
}

function analyze() {
    new bootstrap.Modal("#scoreAnalysisModal").show()
    const scoreAnalysisModalContent = $("#scoreAnalysisModalContent");
    scoreAnalysisModalContent.children().remove();
    if (loadedSchedule.score == null) {
        scoreAnalysisModalContent.text("No score to analyze yet, please first press the 'solve' button.");
    } else {
        $('#scoreAnalysisScoreLabel').text(`(${loadedSchedule.score})`);
        fetch('/schedules/analyze', {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(loadedSchedule)
        })
        .then(r => r.json())
        .then(scoreAnalysis => {
            let constraints = scoreAnalysis.constraints || [];
            scoreAnalysisModalContent.children().remove();
            scoreAnalysisModalContent.text("");

            const analysisTable = $(`<table class="table"/>`).css({textAlign: 'center'});
            const analysisTHead = $(`<thead/>`).append($(`<tr/>`)
                .append($(`<th></th>`))
                .append($(`<th>Constraint</th>`).css({textAlign: 'left'}))
                .append($(`<th>Weight</th>`))
                .append($(`<th>Score</th>`))
                .append($(`<th></th>`)));
            analysisTable.append(analysisTHead);
            const analysisTBody = $(`<tbody/>`)

            for (const constraint of constraints) {
                let row = $(`<tr/>`);
                row.append($(`<td/>`))
                    .append($(`<td/>`).text(constraint.name).css({textAlign: 'left'}))
                    .append($(`<td/>`).text(constraint.weight))
                    .append($(`<td/>`).text(constraint.score));
                analysisTBody.append(row);
                row.append($(`<td/>`));
            }
            analysisTable.append(analysisTBody);
            scoreAnalysisModalContent.append(analysisTable);
        })
        .catch(function (error) {
            showError("Analyze failed.", error);
        });
    }
}

function stopSolving() {
    if (!currentProblemId) return;

    // Close SSE connection
    if (sseConnection) {
        sseConnection.close();
        sseConnection = null;
    }

    // Stop LogiSim animation
    if (typeof stopLogiSimSolvingAnimation === 'function') {
        stopLogiSimSolvingAnimation();
    }

    fetch(`/schedules/${currentProblemId}`, {
        method: 'DELETE'
    })
    .then(() => {
        refreshSolvingButtons(false);
        refreshSolution();
    })
    .catch(function (error) {
        showError("Stop solving failed.", error);
    });
}

$(document).ready(function () {
    replaceQuickstartSolverForgeAutoHeaderFooter();

    //Initialize button listeners
    $("#solveButton").click(function () {
        solve();
    });

    $("#analyzeButton").click(function () {
        analyze();
    });

    $("#stopSolvingButton").click(function () {
        stopSolving();
    });

    // LogiSim tab - render when tab is shown
    $("#logisimTab").on("shown.bs.tab", function () {
        updateLogiSimView();
    });

    // Settings sliders - update badge values
    $("#ordersCountSlider").on("input", function() {
        $("#ordersCountValue").text($(this).val());
    });
    $("#trolleysCountSlider").on("input", function() {
        $("#trolleysCountValue").text($(this).val());
    });
    $("#bucketsCountSlider").on("input", function() {
        $("#bucketsCountValue").text($(this).val());
    });
    $("#solveTimeSlider").on("input", function() {
        $("#solveTimeValue").text($(this).val());
    });

    // Generate new data with custom settings
    $("#applySettingsButton").click(function() {
        generateCustomData();
    });

    //Initial solution loading
    refreshSolution();
});

function generateCustomData() {
    const config = {
        ordersCount: parseInt($("#ordersCountSlider").val()),
        trolleysCount: parseInt($("#trolleysCountSlider").val()),
        bucketCount: parseInt($("#bucketsCountSlider").val())
    };

    // Show loading state
    const btn = $("#applySettingsButton");
    const originalHtml = btn.html();
    btn.html('<i class="fas fa-spinner fa-spin me-1"></i> Generating...');
    btn.prop('disabled', true);

    fetch('/demo-data/generate', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(config)
    })
    .then(r => r.json())
    .then(solution => {
        loadedSchedule = solution;
        currentProblemId = null;
        solverWasNeverStarted = true;

        // Update all views
        updateWelcomeMessage(true);
        printSolutionScore(solution);
        printSolutionTable(solution);
        printTrolleysMap(solution);
        updateLogiSimView();
        refreshSolvingButtons(false);

        // Collapse settings panel
        $("#advancedSettings").collapse('hide');

        // Show success feedback
        showSuccess(`Generated ${config.ordersCount} orders with ${config.trolleysCount} trolleys`);
    })
    .catch(function (error) {
        showError("Failed to generate custom data.", error);
    })
    .finally(() => {
        btn.html(originalHtml);
        btn.prop('disabled', false);
    });
}

function showSuccess(message) {
    const notification = $(`
        <div class="alert alert-success alert-dismissible fade show" role="alert">
            <i class="fas fa-check-circle me-2"></i>${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        </div>
    `);
    $("#notificationPanel").append(notification);
    setTimeout(() => notification.alert('close'), 3000);
}

function doClickOnUnassignedEntities() {
    $('#unassignedEntitiesTab').trigger("click")
}

function updateLogiSimView() {
    if (!loadedSchedule) return;

    // Render LogiSim view
    initLogiSimView();
    renderLogiSimView(loadedSchedule);

    // Update LogiSim overlay stats
    updateLogiSimStats(loadedSchedule);
    updateLogiSimLegend(loadedSchedule);
}

function updateLogiSimStats(solution) {
    // Count unique orders and total items
    const orderIds = new Set();
    let totalItems = 0;
    let totalDistance = 0;

    const stepLookup = buildStepLookup(solution);

    for (const trolley of solution.trolleys) {
        const steps = getTrolleySteps(trolley, stepLookup);
        totalItems += steps.length;
        for (const step of steps) {
            orderIds.add(step.orderItem.orderId);
        }
        totalDistance += TROLLEY_TRAVEL_DISTANCE.get(trolley.id) || 0;
    }

    $("#logisimOrderCount").text(orderIds.size);
    $("#logisimItemCount").text(totalItems);
    $("#logisimTotalDistance").text(`${totalDistance}m`);
}

function updateLogiSimLegend(solution) {
    const legendContainer = $("#logisimTrolleyLegend");
    legendContainer.empty();

    const stepLookup = buildStepLookup(solution);

    for (const trolley of solution.trolleys) {
        const steps = getTrolleySteps(trolley, stepLookup);
        const color = trolleyColor(trolley.id);
        const distance = TROLLEY_TRAVEL_DISTANCE.get(trolley.id) || 0;

        const itemEl = $(`
            <div class="legend-item${steps.length > 0 ? ' active' : ''}" data-trolley="${trolley.id}">
                <span class="legend-color" style="background-color: ${color}; color: ${color};"></span>
                <span>Trolley ${trolley.id}</span>
                <span class="legend-distance">${distance}m</span>
            </div>
        `);

        // Click to highlight this trolley's path
        itemEl.on('click', function() {
            const trolleyId = $(this).data('trolley');
            highlightTrolleyInLogiSim(trolleyId);
        });

        legendContainer.append(itemEl);
    }
}

function highlightTrolleyInLogiSim(trolleyId) {
    // Toggle highlight for a specific trolley
    $(".legend-item").removeClass("highlighted");
    $(`.legend-item[data-trolley="${trolleyId}"]`).addClass("highlighted");
    // Re-render with highlight (if implemented in logisim-view.js)
    if (typeof setLogiSimHighlightedTrolley === 'function') {
        setLogiSimHighlightedTrolley(trolleyId);
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
                                <a class="nav-link" href="/q/swagger-ui" style="color: #1f2937;">REST API</a>
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
