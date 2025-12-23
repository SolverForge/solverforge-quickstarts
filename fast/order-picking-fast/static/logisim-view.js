/**
 * Isometric 3D Warehouse Visualization
 * Professional order picking visualization with animated trolleys
 */

const ISO = {
    // Isometric projection angles
    ANGLE: Math.PI / 6, // 30 degrees

    // Tile dimensions
    TILE_WIDTH: 48,
    TILE_HEIGHT: 24,

    // Shelf dimensions (in tiles)
    SHELF_WIDTH: 3,
    SHELF_DEPTH: 1,
    SHELF_HEIGHT: 2,

    // Warehouse layout: 5 columns (A-E) x 3 rows
    COLS: 5,
    ROWS: 3,

    // Spacing between shelves
    AISLE_WIDTH: 2,

    // Colors
    COLORS: {
        floor: '#e2e8f0',
        floorGrid: '#cbd5e1',
        shelfTop: '#ffffff',
        shelfFront: '#f1f5f9',
        shelfSide: '#e2e8f0',
        shelfBorder: '#94a3b8',
        shadow: 'rgba(0, 0, 0, 0.1)',
        trolley: [
            '#ef4444', // red
            '#3b82f6', // blue
            '#10b981', // green
            '#f59e0b', // amber
            '#8b5cf6', // purple
            '#06b6d4', // cyan
            '#ec4899', // pink
            '#84cc16', // lime
        ],
        path: 'rgba(59, 130, 246, 0.3)',
        pathActive: 'rgba(59, 130, 246, 0.6)',
    },

    // Animation state
    animationId: null,
    isSolving: false,
    trolleyAnimations: new Map(),
    currentSolution: null,

    // Canvas state
    canvas: null,
    ctx: null,
    dpr: 1,
    width: 0,
    height: 0,
    originX: 0,
    originY: 0,
};

// Column/Row mapping
const COLUMNS = ['A', 'B', 'C', 'D', 'E'];
const ROWS = ['1', '2', '3'];

/**
 * Convert isometric coordinates to screen coordinates
 */
function isoToScreen(x, y, z = 0) {
    const screenX = ISO.originX + (x - y) * (ISO.TILE_WIDTH / 2);
    const screenY = ISO.originY + (x + y) * (ISO.TILE_HEIGHT / 2) - z * ISO.TILE_HEIGHT;
    return { x: screenX, y: screenY };
}

/**
 * Get trolley color by ID
 */
function getTrolleyColor(trolleyId) {
    const index = (parseInt(trolleyId) - 1) % ISO.COLORS.trolley.length;
    return ISO.COLORS.trolley[index];
}

/**
 * Initialize the canvas
 */
function initWarehouseCanvas() {
    const container = document.getElementById('warehouseContainer');
    if (!container) return;

    let canvas = document.getElementById('warehouseCanvas');
    if (!canvas) {
        canvas = document.createElement('canvas');
        canvas.id = 'warehouseCanvas';
        container.appendChild(canvas);
    }

    ISO.canvas = canvas;
    ISO.ctx = canvas.getContext('2d');
    ISO.dpr = window.devicePixelRatio || 1;

    // Calculate canvas size based on warehouse dimensions
    const totalWidth = (ISO.COLS * (ISO.SHELF_WIDTH + ISO.AISLE_WIDTH) + ISO.AISLE_WIDTH) * ISO.TILE_WIDTH;
    const totalHeight = (ISO.ROWS * (ISO.SHELF_DEPTH + ISO.AISLE_WIDTH) + ISO.AISLE_WIDTH) * ISO.TILE_WIDTH;

    // Isometric dimensions
    ISO.width = totalWidth + 200;
    ISO.height = totalHeight / 2 + 300;

    // Set canvas size with HiDPI support
    canvas.width = ISO.width * ISO.dpr;
    canvas.height = ISO.height * ISO.dpr;
    canvas.style.width = ISO.width + 'px';
    canvas.style.height = ISO.height + 'px';

    ISO.ctx.scale(ISO.dpr, ISO.dpr);

    // Set origin point (top-center of warehouse)
    ISO.originX = ISO.width / 2;
    ISO.originY = 80;
}

/**
 * Draw the warehouse floor grid
 */
function drawFloor() {
    const ctx = ISO.ctx;
    const gridSize = ISO.COLS * (ISO.SHELF_WIDTH + ISO.AISLE_WIDTH) + ISO.AISLE_WIDTH;
    const gridDepth = ISO.ROWS * (ISO.SHELF_DEPTH + ISO.AISLE_WIDTH) + ISO.AISLE_WIDTH;

    // Draw floor tiles
    for (let x = 0; x < gridSize; x++) {
        for (let y = 0; y < gridDepth; y++) {
            const p1 = isoToScreen(x, y);
            const p2 = isoToScreen(x + 1, y);
            const p3 = isoToScreen(x + 1, y + 1);
            const p4 = isoToScreen(x, y + 1);

            ctx.beginPath();
            ctx.moveTo(p1.x, p1.y);
            ctx.lineTo(p2.x, p2.y);
            ctx.lineTo(p3.x, p3.y);
            ctx.lineTo(p4.x, p4.y);
            ctx.closePath();

            ctx.fillStyle = ISO.COLORS.floor;
            ctx.fill();
            ctx.strokeStyle = ISO.COLORS.floorGrid;
            ctx.lineWidth = 0.5;
            ctx.stroke();
        }
    }
}

/**
 * Draw a 3D shelf at grid position
 */
function drawShelf(col, row, label) {
    const ctx = ISO.ctx;

    // Calculate grid position
    const gridX = ISO.AISLE_WIDTH + col * (ISO.SHELF_WIDTH + ISO.AISLE_WIDTH);
    const gridY = ISO.AISLE_WIDTH + row * (ISO.SHELF_DEPTH + ISO.AISLE_WIDTH);

    const w = ISO.SHELF_WIDTH;
    const d = ISO.SHELF_DEPTH;
    const h = ISO.SHELF_HEIGHT;

    // Get corner points
    const topFront = [
        isoToScreen(gridX, gridY + d, h),
        isoToScreen(gridX + w, gridY + d, h),
        isoToScreen(gridX + w, gridY, h),
        isoToScreen(gridX, gridY, h),
    ];

    const bottomFront = [
        isoToScreen(gridX, gridY + d, 0),
        isoToScreen(gridX + w, gridY + d, 0),
    ];

    const bottomSide = [
        isoToScreen(gridX + w, gridY, 0),
    ];

    // Draw shadow
    ctx.beginPath();
    const shadowOffset = 0.3;
    const s1 = isoToScreen(gridX + shadowOffset, gridY + d + shadowOffset, 0);
    const s2 = isoToScreen(gridX + w + shadowOffset, gridY + d + shadowOffset, 0);
    const s3 = isoToScreen(gridX + w + shadowOffset, gridY + shadowOffset, 0);
    const s4 = isoToScreen(gridX + shadowOffset, gridY + shadowOffset, 0);
    ctx.moveTo(s1.x, s1.y);
    ctx.lineTo(s2.x, s2.y);
    ctx.lineTo(s3.x, s3.y);
    ctx.lineTo(s4.x, s4.y);
    ctx.closePath();
    ctx.fillStyle = ISO.COLORS.shadow;
    ctx.fill();

    // Draw front face
    ctx.beginPath();
    ctx.moveTo(topFront[0].x, topFront[0].y);
    ctx.lineTo(topFront[1].x, topFront[1].y);
    ctx.lineTo(bottomFront[1].x, bottomFront[1].y);
    ctx.lineTo(bottomFront[0].x, bottomFront[0].y);
    ctx.closePath();
    ctx.fillStyle = ISO.COLORS.shelfFront;
    ctx.fill();
    ctx.strokeStyle = ISO.COLORS.shelfBorder;
    ctx.lineWidth = 1;
    ctx.stroke();

    // Draw side face
    ctx.beginPath();
    ctx.moveTo(topFront[1].x, topFront[1].y);
    ctx.lineTo(topFront[2].x, topFront[2].y);
    ctx.lineTo(bottomSide[0].x, bottomSide[0].y);
    ctx.lineTo(bottomFront[1].x, bottomFront[1].y);
    ctx.closePath();
    ctx.fillStyle = ISO.COLORS.shelfSide;
    ctx.fill();
    ctx.strokeStyle = ISO.COLORS.shelfBorder;
    ctx.stroke();

    // Draw top face
    ctx.beginPath();
    ctx.moveTo(topFront[0].x, topFront[0].y);
    ctx.lineTo(topFront[1].x, topFront[1].y);
    ctx.lineTo(topFront[2].x, topFront[2].y);
    ctx.lineTo(topFront[3].x, topFront[3].y);
    ctx.closePath();
    ctx.fillStyle = ISO.COLORS.shelfTop;
    ctx.fill();
    ctx.strokeStyle = ISO.COLORS.shelfBorder;
    ctx.stroke();

    // Draw label
    const centerX = (topFront[0].x + topFront[1].x + topFront[2].x + topFront[3].x) / 4;
    const centerY = (topFront[0].y + topFront[1].y + topFront[2].y + topFront[3].y) / 4;

    ctx.font = 'bold 14px -apple-system, BlinkMacSystemFont, sans-serif';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillStyle = '#475569';
    ctx.fillText(label, centerX, centerY);
}

/**
 * Draw all shelves
 */
function drawShelves() {
    for (let col = 0; col < ISO.COLS; col++) {
        for (let row = 0; row < ISO.ROWS; row++) {
            const label = COLUMNS[col] + ',' + ROWS[row];
            drawShelf(col, row, label);
        }
    }
}

/**
 * Draw a trolley at position
 */
function drawTrolley(x, y, color, trolleyId, progress = 1) {
    const ctx = ISO.ctx;
    const pos = isoToScreen(x, y, 0.3);

    // Trolley body dimensions
    const bodyWidth = 20;
    const bodyHeight = 14;
    const bodyDepth = 8;

    // Draw trolley body (isometric box)
    ctx.save();
    ctx.translate(pos.x, pos.y);

    // Shadow
    ctx.beginPath();
    ctx.ellipse(0, 6, 12, 6, 0, 0, Math.PI * 2);
    ctx.fillStyle = 'rgba(0, 0, 0, 0.15)';
    ctx.fill();

    // Body - front
    ctx.beginPath();
    ctx.moveTo(-bodyWidth/2, -bodyDepth);
    ctx.lineTo(bodyWidth/2, -bodyDepth);
    ctx.lineTo(bodyWidth/2, bodyHeight - bodyDepth);
    ctx.lineTo(-bodyWidth/2, bodyHeight - bodyDepth);
    ctx.closePath();
    ctx.fillStyle = color;
    ctx.fill();
    ctx.strokeStyle = 'rgba(0, 0, 0, 0.2)';
    ctx.lineWidth = 1;
    ctx.stroke();

    // Body - top
    ctx.beginPath();
    ctx.moveTo(-bodyWidth/2, -bodyDepth);
    ctx.lineTo(0, -bodyDepth - 6);
    ctx.lineTo(bodyWidth/2, -bodyDepth);
    ctx.lineTo(0, -bodyDepth + 3);
    ctx.closePath();
    const lighterColor = lightenColor(color, 20);
    ctx.fillStyle = lighterColor;
    ctx.fill();
    ctx.stroke();

    // Handle
    ctx.beginPath();
    ctx.moveTo(-bodyWidth/2 + 3, -bodyDepth - 2);
    ctx.lineTo(-bodyWidth/2 + 3, -bodyDepth - 12);
    ctx.lineTo(bodyWidth/2 - 3, -bodyDepth - 12);
    ctx.lineTo(bodyWidth/2 - 3, -bodyDepth - 2);
    ctx.strokeStyle = darkenColor(color, 20);
    ctx.lineWidth = 2;
    ctx.stroke();

    // Trolley number badge
    ctx.beginPath();
    ctx.arc(0, -bodyDepth - 16, 10, 0, Math.PI * 2);
    ctx.fillStyle = 'white';
    ctx.fill();
    ctx.strokeStyle = color;
    ctx.lineWidth = 2;
    ctx.stroke();

    ctx.font = 'bold 11px -apple-system, sans-serif';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillStyle = color;
    ctx.fillText(trolleyId, 0, -bodyDepth - 16);

    ctx.restore();
}

/**
 * Lighten a hex color
 */
function lightenColor(hex, percent) {
    const num = parseInt(hex.slice(1), 16);
    const amt = Math.round(2.55 * percent);
    const R = Math.min(255, (num >> 16) + amt);
    const G = Math.min(255, ((num >> 8) & 0x00FF) + amt);
    const B = Math.min(255, (num & 0x0000FF) + amt);
    return '#' + (0x1000000 + R * 0x10000 + G * 0x100 + B).toString(16).slice(1);
}

/**
 * Darken a hex color
 */
function darkenColor(hex, percent) {
    const num = parseInt(hex.slice(1), 16);
    const amt = Math.round(2.55 * percent);
    const R = Math.max(0, (num >> 16) - amt);
    const G = Math.max(0, ((num >> 8) & 0x00FF) - amt);
    const B = Math.max(0, (num & 0x0000FF) - amt);
    return '#' + (0x1000000 + R * 0x10000 + G * 0x100 + B).toString(16).slice(1);
}

/**
 * Convert warehouse location to grid position
 */
function locationToGrid(location) {
    if (!location) return { x: 0, y: 0 };

    // Parse shelving ID like "(A, 1)"
    const shelvingId = location.shelvingId || '';
    const match = shelvingId.match(/\(([A-E]),\s*(\d)\)/);

    let col = 0, row = 0;
    if (match) {
        col = COLUMNS.indexOf(match[1]);
        row = parseInt(match[2]) - 1;
    }

    // Calculate grid position (center of aisle next to shelf)
    const gridX = ISO.AISLE_WIDTH + col * (ISO.SHELF_WIDTH + ISO.AISLE_WIDTH) + ISO.SHELF_WIDTH / 2;
    const gridY = ISO.AISLE_WIDTH + row * (ISO.SHELF_DEPTH + ISO.AISLE_WIDTH) + ISO.SHELF_DEPTH + 0.5;

    // Adjust for side (LEFT/RIGHT)
    const side = location.side;
    if (side === 'LEFT') {
        return { x: gridX - 1, y: gridY };
    } else {
        return { x: gridX + 1, y: gridY };
    }
}

/**
 * Build trolley path from steps
 */
function buildTrolleyPath(trolley, steps) {
    const path = [];

    // Start position
    if (trolley.location) {
        path.push(locationToGrid(trolley.location));
    }

    // Add each step location
    for (const step of steps) {
        if (step.orderItem && step.orderItem.product && step.orderItem.product.location) {
            path.push(locationToGrid(step.orderItem.product.location));
        }
    }

    // Return to start
    if (path.length > 1 && trolley.location) {
        path.push(locationToGrid(trolley.location));
    }

    return path;
}

/**
 * Draw trolley path
 */
function drawPath(path, color, active = false) {
    if (path.length < 2) return;

    const ctx = ISO.ctx;
    ctx.beginPath();

    const start = isoToScreen(path[0].x, path[0].y, 0.1);
    ctx.moveTo(start.x, start.y);

    for (let i = 1; i < path.length; i++) {
        const point = isoToScreen(path[i].x, path[i].y, 0.1);
        ctx.lineTo(point.x, point.y);
    }

    ctx.strokeStyle = active ? ISO.COLORS.pathActive : ISO.COLORS.path;
    ctx.lineWidth = active ? 4 : 2;
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    ctx.stroke();

    // Draw pickup markers
    for (let i = 1; i < path.length - 1; i++) {
        const point = isoToScreen(path[i].x, path[i].y, 0.5);

        ctx.beginPath();
        ctx.arc(point.x, point.y, 8, 0, Math.PI * 2);
        ctx.fillStyle = color;
        ctx.fill();
        ctx.strokeStyle = 'white';
        ctx.lineWidth = 2;
        ctx.stroke();

        ctx.font = 'bold 9px -apple-system, sans-serif';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillStyle = 'white';
        ctx.fillText(i.toString(), point.x, point.y);
    }
}

/**
 * Get position along path at progress (0-1)
 */
function getPositionOnPath(path, progress) {
    if (path.length === 0) return { x: 0, y: 0 };
    if (path.length === 1) return path[0];

    const totalSegments = path.length - 1;
    const segmentProgress = progress * totalSegments;
    const currentSegment = Math.min(Math.floor(segmentProgress), totalSegments - 1);
    const segmentT = segmentProgress - currentSegment;

    const start = path[currentSegment];
    const end = path[currentSegment + 1];

    return {
        x: start.x + (end.x - start.x) * segmentT,
        y: start.y + (end.y - start.y) * segmentT,
    };
}

/**
 * Render the full warehouse scene
 */
function renderWarehouse(solution) {
    if (!ISO.ctx) return;

    const ctx = ISO.ctx;
    ctx.clearRect(0, 0, ISO.width, ISO.height);

    // Draw floor
    drawFloor();

    // Draw shelves (back to front for proper overlap)
    drawShelves();

    if (!solution || !solution.trolleys) return;

    // Build step lookup
    const stepLookup = new Map();
    for (const step of solution.trolleySteps || []) {
        stepLookup.set(step.id, step);
    }

    // Draw paths and trolleys
    const trolleys = solution.trolleys || [];

    for (const trolley of trolleys) {
        const steps = (trolley.steps || []).map(ref =>
            typeof ref === 'string' ? stepLookup.get(ref) : ref
        ).filter(s => s);

        const color = getTrolleyColor(trolley.id);
        const path = buildTrolleyPath(trolley, steps);

        // Draw path
        if (path.length > 1) {
            drawPath(path, color, ISO.isSolving);
        }

        // Draw trolley
        const anim = ISO.trolleyAnimations.get(trolley.id);
        let pos;

        if (anim && ISO.isSolving && path.length > 1) {
            const now = Date.now();
            const elapsed = now - anim.startTime;
            const progress = (elapsed % anim.duration) / anim.duration;
            pos = getPositionOnPath(path, progress);
        } else if (path.length > 0) {
            pos = path[0];
        } else {
            pos = locationToGrid(trolley.location);
        }

        if (pos) {
            drawTrolley(pos.x, pos.y, color, trolley.id);
        }
    }
}

/**
 * Animation loop
 */
function animate() {
    if (!ISO.isSolving) {
        ISO.animationId = null;
        return;
    }

    renderWarehouse(ISO.currentSolution);
    ISO.animationId = requestAnimationFrame(animate);
}

/**
 * Start solving animation
 */
function startWarehouseAnimation(solution) {
    ISO.isSolving = true;
    ISO.currentSolution = solution;
    ISO.trolleyAnimations.clear();

    // Initialize animations for each trolley
    const stepLookup = new Map();
    for (const step of solution.trolleySteps || []) {
        stepLookup.set(step.id, step);
    }

    for (const trolley of solution.trolleys || []) {
        const steps = (trolley.steps || []).map(ref =>
            typeof ref === 'string' ? stepLookup.get(ref) : ref
        ).filter(s => s);

        const path = buildTrolleyPath(trolley, steps);
        const duration = Math.max(3000, path.length * 800);

        ISO.trolleyAnimations.set(trolley.id, {
            startTime: Date.now() + parseInt(trolley.id) * 300, // Stagger starts
            duration: duration,
            path: path,
        });
    }

    if (!ISO.animationId) {
        animate();
    }
}

/**
 * Update animation with new solution data
 */
function updateWarehouseAnimation(solution) {
    ISO.currentSolution = solution;

    // Update paths but keep animation timing
    const stepLookup = new Map();
    for (const step of solution.trolleySteps || []) {
        stepLookup.set(step.id, step);
    }

    for (const trolley of solution.trolleys || []) {
        const steps = (trolley.steps || []).map(ref =>
            typeof ref === 'string' ? stepLookup.get(ref) : ref
        ).filter(s => s);

        const path = buildTrolleyPath(trolley, steps);
        const existingAnim = ISO.trolleyAnimations.get(trolley.id);

        if (existingAnim) {
            existingAnim.path = path;
            existingAnim.duration = Math.max(3000, path.length * 800);
        } else {
            ISO.trolleyAnimations.set(trolley.id, {
                startTime: Date.now(),
                duration: Math.max(3000, path.length * 800),
                path: path,
            });
        }
    }
}

/**
 * Stop animation
 */
function stopWarehouseAnimation() {
    ISO.isSolving = false;
    if (ISO.animationId) {
        cancelAnimationFrame(ISO.animationId);
        ISO.animationId = null;
    }
    // Render final state
    if (ISO.currentSolution) {
        renderWarehouse(ISO.currentSolution);
    }
}

/**
 * Update legend with trolley info
 */
function updateLegend(solution, distances) {
    const container = document.getElementById('trolleyLegend');
    if (!container) return;

    container.innerHTML = '';

    const stepLookup = new Map();
    for (const step of solution.trolleySteps || []) {
        stepLookup.set(step.id, step);
    }

    for (const trolley of solution.trolleys || []) {
        const steps = (trolley.steps || []).map(ref =>
            typeof ref === 'string' ? stepLookup.get(ref) : ref
        ).filter(s => s);

        const color = getTrolleyColor(trolley.id);
        const distance = distances ? distances.get(trolley.id) || 0 : 0;

        const item = document.createElement('div');
        item.className = 'legend-item';
        item.innerHTML = `
            <div class="legend-color" style="background: ${color}"></div>
            <span class="legend-text">Trolley ${trolley.id}</span>
            <span class="legend-distance">${steps.length} items</span>
        `;
        container.appendChild(item);
    }
}

// Export for app.js
window.initWarehouseCanvas = initWarehouseCanvas;
window.renderWarehouse = renderWarehouse;
window.startWarehouseAnimation = startWarehouseAnimation;
window.updateWarehouseAnimation = updateWarehouseAnimation;
window.stopWarehouseAnimation = stopWarehouseAnimation;
window.updateLegend = updateLegend;
window.getTrolleyColor = getTrolleyColor;
