let autoRefreshIntervalId = null;
const formatter = JSJoda.DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");
const startTime = formatter.format(JSJoda.LocalDateTime.now().withHour(20).withMinute(0).withSecond(0));
const endTime = formatter.format(JSJoda.LocalDateTime.now().plusDays(1).withHour(8).withMinute(0).withSecond(0));
const zoomMin = 1000 * 60 * 60 // one hour in milliseconds
const zoomMax = 4 * 1000 * 60 * 60 * 24 // 5 days in milliseconds

const byTimelineOptions = {
    timeAxis: {scale: "hour", step: 1},
    orientation: {axis: "top"},
    stack: false,
    xss: {disabled: true}, // Items are XSS safe through JQuery
    zoomMin: zoomMin,
    zoomMax: zoomMax,
    showCurrentTime: false,
    hiddenDates: [
        {
            start: startTime,
            end: endTime,
            repeat: 'daily'
        }
    ],
};

const byRoomPanel = document.getElementById("byRoomPanel");
let byRoomGroupData = new vis.DataSet();
let byRoomItemData = new vis.DataSet();
let byRoomTimeline = new vis.Timeline(byRoomPanel, byRoomItemData, byRoomGroupData, byTimelineOptions);

const byPersonPanel = document.getElementById("byPersonPanel");
let byPersonGroupData = new vis.DataSet();
let byPersonItemData = new vis.DataSet();
let byPersonTimeline = new vis.Timeline(byPersonPanel, byPersonItemData, byPersonGroupData, byTimelineOptions);

let scheduleId = null;
let loadedSchedule = null;
let viewType = "R";
let selectedDemoData = "MEDIUM"; // Default demo data size
let analyzeCache = null; // Cache for solver's constraint analysis (assignmentId -> violations)


let appInitialized = false;

$(document).ready(function () {
    // Ensure all resources are loaded before initializing
    $(window).on('load', function() {
        if (!appInitialized) {
            appInitialized = true;
            initializeApp();
        }
    });

    // Fallback if window load event doesn't fire
    setTimeout(function() {
        if (!appInitialized) {
            appInitialized = true;
            initializeApp();
        }
    }, 100);
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
    $("#byRoomTab").click(function () {
        viewType = "R";
        byRoomTimeline.redraw();
        refreshSchedule();
    });
    $("#byPersonTab").click(function () {
        viewType = "P";
        byPersonTimeline.redraw();
        refreshSchedule();
    });
    setupAjax();
    loadDemoDataDropdown();
    refreshSchedule();
}


function loadDemoDataDropdown() {
    $.getJSON("/demo-data", function (demoDataList) {
        const dropdown = $("#testDataButton");
        dropdown.empty();

        demoDataList.forEach(function (name) {
            const isSelected = name === selectedDemoData;
            const item = $(`<a class="dropdown-item" href="#"></a>`)
                .text(name)
                .css("font-weight", isSelected ? "bold" : "normal")
                .click(function (e) {
                    e.preventDefault();
                    selectDemoData(name);
                });
            dropdown.append(item);
        });
    });
}


function selectDemoData(name) {
    selectedDemoData = name;
    scheduleId = null; // Reset solver job
    loadDemoDataDropdown(); // Refresh dropdown to show selection
    refreshSchedule();
}


function setupAjax() {
    $.ajaxSetup({
        headers: {
            'Content-Type': 'application/json', 'Accept': 'application/json,text/plain', // plain text is required by solve() returning UUID of the solver job
        }
    });

    // Extend jQuery to support $.put() and $.delete()
    jQuery.each(["put", "delete"], function (i, method) {
        jQuery[method] = function (url, data, callback, type) {
            if (jQuery.isFunction(data)) {
                type = type || callback;
                callback = data;
                data = undefined;
            }
            return jQuery.ajax({
                url: url, type: method, dataType: type, data: data, success: callback
            });
        };
    });
}


function refreshSchedule() {
    let path;
    if (scheduleId === null) {
        path = "/demo-data/" + selectedDemoData;
    } else {
        path = "/schedules/" + scheduleId;
    }

    $.getJSON(path, function (schedule) {
        loadedSchedule = schedule;
        $('#exportData').attr('href', 'data:text/plain;charset=utf-8,' + JSON.stringify(loadedSchedule));
        renderSchedule(schedule);
    })
        .fail(function (xhr, ajaxOptions, thrownError) {
            showError("Getting the schedule has failed.", xhr);
            refreshSolvingButtons(false);
        });
}


function renderSchedule(schedule) {
    refreshSolvingButtons(schedule.solverStatus != null && schedule.solverStatus !== "NOT_SOLVING");
    $("#score").text("Score: " + (schedule.score == null ? "?" : schedule.score));

    // Fetch constraint analysis from solver if we have a score
    if (schedule.score) {
        fetchConstraintAnalysis(schedule);
    } else {
        // No score yet - clear cache and render with no violations
        analyzeCache = null;
        renderViews(schedule);
    }
}


function renderViews(schedule) {
    if (viewType === "R") {
        renderScheduleByRoom(schedule);
    }
    if (viewType === "P") {
        renderScheduleByPerson(schedule);
    }
}


function fetchConstraintAnalysis(schedule) {
    $.ajax({
        url: "/schedules/analyze",
        type: "PUT",
        data: JSON.stringify(schedule),
        contentType: "application/json",
        success: function(response) {
            // Build mapping: assignmentId -> { hard: [], medium: [], soft: [] }
            analyzeCache = new Map();

            for (const constraint of response.constraints) {
                const type = getConstraintType(constraint.weight);

                for (const match of constraint.matches) {
                    const assignmentIds = extractAssignmentIds(match.justification, loadedSchedule);

                    for (const id of assignmentIds) {
                        if (!analyzeCache.has(id)) {
                            analyzeCache.set(id, { hard: [], medium: [], soft: [] });
                        }
                        analyzeCache.get(id)[type].push({
                            constraint: constraint.name,
                            score: match.score
                        });
                    }
                }
            }

            // Re-render with new analysis data
            renderViews(loadedSchedule);
        },
        error: function(xhr, status, error) {
            console.warn("Failed to fetch constraint analysis:", error);
            analyzeCache = null;
            renderViews(schedule);
        }
    });
}


function getConstraintType(weight) {
    // Weight format: "0hard/0medium/-1soft" or "1hard/0medium/0soft"
    // Extract the non-zero component
    const hardMatch = weight.match(/(-?\d+)hard/);
    const mediumMatch = weight.match(/(-?\d+)medium/);
    const softMatch = weight.match(/(-?\d+)soft/);

    if (hardMatch && parseInt(hardMatch[1], 10) !== 0) return 'hard';
    if (mediumMatch && parseInt(mediumMatch[1], 10) !== 0) return 'medium';
    if (softMatch && parseInt(softMatch[1], 10) !== 0) return 'soft';

    return 'soft'; // Default
}


function extractAssignmentIds(justification, schedule) {
    const ids = new Set();
    if (!justification?.facts) return [...ids];

    // Build meeting-to-assignment lookup
    const meetingToAssignment = new Map();
    if (schedule?.meetingAssignments) {
        for (const a of schedule.meetingAssignments) {
            const meetingId = typeof a.meeting === 'object' ? a.meeting.id : a.meeting;
            meetingToAssignment.set(meetingId, a.id);
        }
    }

    console.log("Facts:", justification.facts);
    console.log("meetingToAssignment:", [...meetingToAssignment.entries()]);

    for (const fact of justification.facts) {
        if (fact.type === 'assignment' && fact.id) {
            ids.add(fact.id);
        } else if (fact.type === 'attendance' && fact.meetingId) {
            const assignmentId = meetingToAssignment.get(fact.meetingId);
            console.log(`attendance fact meetingId=${fact.meetingId} -> assignmentId=${assignmentId}`);
            if (assignmentId) ids.add(assignmentId);
        }
    }
    console.log("Extracted IDs:", [...ids]);
    return [...ids];
}


function getConflictStatus(assignmentId) {
    // Use solver's constraint analysis if available (per-assignment violations)
    console.log(`getConflictStatus(${assignmentId}), cache has it: ${analyzeCache?.has(assignmentId)}, cache has string: ${analyzeCache?.has(String(assignmentId))}`);
    if (analyzeCache && analyzeCache.has(assignmentId)) {
        const violations = analyzeCache.get(assignmentId);

        if (violations.hard.length > 0) {
            return {
                status: 'hard',
                icon: '<span class="fas fa-exclamation-triangle text-danger me-1"></span>',
                style: 'background-color: #fee2e2; border-left: 4px solid #dc3545;',
                reason: violations.hard.map(v => v.constraint).join(', ')
            };
        }

        if (violations.medium.length > 0) {
            return {
                status: 'medium',
                icon: '<span class="fas fa-exclamation-circle text-warning me-1"></span>',
                style: 'background-color: #fef3c7; border-left: 4px solid #ffc107;',
                reason: violations.medium.map(v => v.constraint).join(', ')
            };
        }

        // Don't show soft violations in timeline - they're optimization trade-offs
        // (e.g., "Overlapping meetings" fires for ANY parallel meetings, even in different rooms)
        // Users can see soft violations in the "Analyze" modal instead
    }

    // No hard/medium violations - show green (feasible solution)
    return {
        status: 'ok',
        icon: '<span class="fas fa-check-circle text-success me-1"></span>',
        style: 'background-color: #d1fae5; border-left: 4px solid #10b981;',
        reason: ''
    };
}


function calculatePersonWorkload(schedule) {
    const personMeetingCount = new Map();

    if (!schedule.meetingAssignments || !schedule.meetings) {
        return personMeetingCount;
    }

    const meetingMap = new Map();
    schedule.meetings.forEach(m => meetingMap.set(m.id, m));

    // Count meetings per person (assigned meetings only)
    schedule.meetingAssignments.forEach(assignment => {
        if (assignment.room == null || assignment.startingTimeGrain == null) return;

        const meeting = typeof assignment.meeting === 'string'
            ? meetingMap.get(assignment.meeting)
            : assignment.meeting;
        if (!meeting) return;

        // Count required attendees
        (meeting.requiredAttendances || []).forEach(att => {
            const personId = att.person?.id || att.person;
            personMeetingCount.set(personId, (personMeetingCount.get(personId) || 0) + 1);
        });

        // Count preferred attendees
        (meeting.preferredAttendances || []).forEach(att => {
            const personId = att.person?.id || att.person;
            personMeetingCount.set(personId, (personMeetingCount.get(personId) || 0) + 1);
        });
    });

    return personMeetingCount;
}


function getWorkloadBadge(meetingCount) {
    if (meetingCount === 0) {
        return '<span class="badge bg-secondary ms-2" title="No meetings">0</span>';
    } else if (meetingCount <= 5) {
        return `<span class="badge bg-primary ms-2" title="${meetingCount} meetings">${meetingCount}</span>`;
    } else if (meetingCount <= 9) {
        return `<span class="badge bg-info text-dark ms-2" title="${meetingCount} meetings">${meetingCount}</span>`;
    } else {
        return `<span class="badge bg-dark ms-2" title="${meetingCount} meetings - Heavy workload">${meetingCount}</span>`;
    }
}


function analyzeUnassignedReason(meeting, schedule) {
    const reasons = [];

    const totalAttendees = (meeting.requiredAttendances?.length || 0) + (meeting.preferredAttendances?.length || 0);

    // Check room capacity
    const largestRoomCapacity = Math.max(...schedule.rooms.map(r => r.capacity));
    if (totalAttendees > largestRoomCapacity) {
        reasons.push(`Needs ${totalAttendees} capacity, largest room has ${largestRoomCapacity}`);
    }

    // Check if meeting duration is very long
    const durationHours = ((meeting.durationInGrains ?? meeting.duration_in_grains) * 15) / 60;
    if (durationHours > 3) {
        reasons.push(`Long meeting (${durationHours}h) - fewer available slots`);
    }

    // Check if required attendees are heavily booked
    const meetingMap = new Map();
    schedule.meetings.forEach(m => meetingMap.set(m.id, m));

    const requiredAttendeeIds = new Set((meeting.requiredAttendances || []).map(a => a.person?.id || a.person));
    let busyAttendeesCount = 0;

    schedule.meetingAssignments.forEach(assignment => {
        if (assignment.room == null || assignment.startingTimeGrain == null) return;
        if (assignment.meeting === meeting.id) return;

        const otherMeeting = typeof assignment.meeting === 'string'
            ? meetingMap.get(assignment.meeting)
            : assignment.meeting;
        if (!otherMeeting) return;

        const otherRequiredIds = new Set((otherMeeting.requiredAttendances || []).map(a => a.person?.id || a.person));
        for (const id of requiredAttendeeIds) {
            if (otherRequiredIds.has(id)) {
                busyAttendeesCount++;
                break;
            }
        }
    });

    if (busyAttendeesCount > 0 && requiredAttendeeIds.size > 0) {
        const percentBusy = Math.round((busyAttendeesCount / schedule.meetingAssignments.filter(a => a.room && a.startingTimeGrain).length) * 100);
        if (percentBusy > 30) {
            reasons.push(`Required attendees have many existing meetings`);
        }
    }

    // If still solving, add generic reason
    if (reasons.length === 0) {
        reasons.push(`Being optimized by solver`);
    }

    return reasons;
}


function renderScheduleByRoom(schedule) {
    const unassigned = $("#unassigned");
    unassigned.children().remove();
    byRoomGroupData.clear();
    byRoomItemData.clear();

    // Check if schedule.rooms exists and is an array
    if (!schedule.rooms || !Array.isArray(schedule.rooms)) {
        console.warn('schedule.rooms is not available or not an array:', schedule.rooms);
        return;
    }

    $.each(schedule.rooms.sort((e1, e2) => e1.name.localeCompare(e2.name)), (_, room) => {
        let content = `<div class="d-flex flex-column"><div><h5 class="card-title mb-1">${room.name}</h5></div>`;
        byRoomGroupData.add({
            id: room.id,
            content: content,
        });
    });

    const meetingMap = new Map();
    if (schedule.meetings && Array.isArray(schedule.meetings)) {
        schedule.meetings.forEach(m => meetingMap.set(m.id, m));
    }
    const timeGrainMap = new Map();
    if (schedule.timeGrains && Array.isArray(schedule.timeGrains)) {
        schedule.timeGrains.forEach(t => timeGrainMap.set(t.id, t));
    }
    const roomMap = new Map();
    if (schedule.rooms && Array.isArray(schedule.rooms)) {
        schedule.rooms.forEach(r => roomMap.set(r.id, r));
    }
    
    if (!schedule.meetingAssignments || !Array.isArray(schedule.meetingAssignments)) {
        console.warn('schedule.meetingAssignments is not available or not an array:', schedule.meetingAssignments);
        return;
    }
    
    $.each(schedule.meetingAssignments, (_, assignment) => {
        // Handle both string ID and full object for meeting reference
        const meet = typeof assignment.meeting === 'string' ? meetingMap.get(assignment.meeting) : assignment.meeting;
        // Handle both string ID and full object for room reference
        const room = typeof assignment.room === 'string' ? roomMap.get(assignment.room) : assignment.room;
        // Handle both string ID and full object for timeGrain reference
        const timeGrain = typeof assignment.startingTimeGrain === 'string' ? timeGrainMap.get(assignment.startingTimeGrain) : assignment.startingTimeGrain;
        
        // Skip if meeting is not found
        if (!meet) {
            console.warn(`Meeting not found for assignment ${assignment.id}`);
            return;
        }
        
        if (room == null || timeGrain == null) {
            const durationHours = ((meet.durationInGrains ?? meet.duration_in_grains) * 15) / 60;
            const requiredCount = meet.requiredAttendances?.length || 0;
            const preferredCount = meet.preferredAttendances?.length || 0;
            const totalAttendees = requiredCount + preferredCount;

            // Analyze why unassigned
            const reasons = analyzeUnassignedReason(meet, schedule);

            const unassignedElement = $(`<div class="card-body"/>`)
                .append($(`<h5 class="card-title mb-1"/>`).text(meet.topic))
                .append($(`<p class="card-text mb-1"/>`).html(`<span class="fas fa-clock me-1"></span>${durationHours} hour(s)`))
                .append($(`<p class="card-text mb-1"/>`).html(`<span class="fas fa-users me-1"></span>${totalAttendees} attendees (${requiredCount} required, ${preferredCount} preferred)`));

            if (reasons.length > 0) {
                const reasonsList = $(`<div class="mt-2 small"/>`);
                reasonsList.append($(`<span class="text-muted">Possible issues:</span>`));
                reasons.forEach(reason => {
                    reasonsList.append($(`<div class="text-warning"/>`).html(`<span class="fas fa-exclamation-circle me-1"></span>${reason}`));
                });
                unassignedElement.append(reasonsList);
            }

            unassigned.append($(`<div class="col"/>`).append($(`<div class="card h-100"/>`).append(unassignedElement)));
        } else {
            const conflictStatus = getConflictStatus(assignment.id);
            const byRoomElement = $("<div />")
                .append($("<div class='d-flex justify-content-center align-items-center' />")
                    .append($(conflictStatus.icon))
                    .append($(`<h5 class="card-title mb-1"/>`).text(meet.topic)));
            const startDate = JSJoda.LocalDate.now().withDayOfYear(timeGrain.dayOfYear ?? timeGrain.day_of_year);
            const startTime = JSJoda.LocalTime.of(0, 0, 0, 0)
                .plusMinutes((timeGrain.startingMinuteOfDay ?? timeGrain.starting_minute_of_day));
            const startDateTime = JSJoda.LocalDateTime.of(startDate, startTime);
            const endDateTime = startDateTime.plusMinutes((meet.durationInGrains ?? meet.duration_in_grains) * 15);
            byRoomItemData.add({
                id: assignment.id,
                group: typeof room === 'string' ? room : room.id,
                content: byRoomElement.html(),
                start: startDateTime.toString(),
                end: endDateTime.toString(),
                style: `min-height: 50px; ${conflictStatus.style}`,
                title: conflictStatus.reason || undefined
            });
        }
    });

    byRoomTimeline.setWindow(JSJoda.LocalDateTime.now().plusDays(1).withHour(8).toString(),
        JSJoda.LocalDateTime.now().plusDays(1).withHour(17).withMinute(45).toString());
}


function renderScheduleByPerson(schedule) {
    const unassigned = $("#unassigned");
    unassigned.children().remove();
    byPersonGroupData.clear();
    byPersonItemData.clear();

    // Check if schedule.people exists and is an array
    if (!schedule.people || !Array.isArray(schedule.people)) {
        console.warn('schedule.people is not available or not an array:', schedule.people);
        return;
    }

    // Calculate meeting count per person for workload indicators
    const personMeetingCount = calculatePersonWorkload(schedule);

    $.each(schedule.people.sort((e1, e2) => e1.fullName.localeCompare(e2.fullName)), (_, person) => {
        const meetingCount = personMeetingCount.get(person.id) || 0;
        const workloadBadge = getWorkloadBadge(meetingCount);
        let content = `<div class="d-flex flex-column">
            <div class="d-flex align-items-center">
                <h5 class="card-title mb-1">${person.fullName}</h5>
                ${workloadBadge}
            </div>
        </div>`;
        byPersonGroupData.add({
            id: person.id,
            content: content,
        });
    });
    const meetingMap = new Map();
    if (schedule.meetings && Array.isArray(schedule.meetings)) {
        schedule.meetings.forEach(m => meetingMap.set(m.id, m));
    }
    const timeGrainMap = new Map();
    if (schedule.timeGrains && Array.isArray(schedule.timeGrains)) {
        schedule.timeGrains.forEach(t => timeGrainMap.set(t.id, t));
    }
    const roomMap = new Map();
    if (schedule.rooms && Array.isArray(schedule.rooms)) {
        schedule.rooms.forEach(r => roomMap.set(r.id, r));
    }
    
    if (!schedule.meetingAssignments || !Array.isArray(schedule.meetingAssignments)) {
        console.warn('schedule.meetingAssignments is not available or not an array:', schedule.meetingAssignments);
        return;
    }
    
    $.each(schedule.meetingAssignments, (_, assignment) => {
        // Handle both string ID and full object for meeting reference
        const meet = typeof assignment.meeting === 'string' ? meetingMap.get(assignment.meeting) : assignment.meeting;
        // Handle both string ID and full object for room reference
        const room = typeof assignment.room === 'string' ? roomMap.get(assignment.room) : assignment.room;
        // Handle both string ID and full object for timeGrain reference
        const timeGrain = typeof assignment.startingTimeGrain === 'string' ? timeGrainMap.get(assignment.startingTimeGrain) : assignment.startingTimeGrain;
        
        // Skip if meeting is not found
        if (!meet) {
            console.warn(`Meeting not found for assignment ${assignment.id}`);
            return;
        }
        
        if (room == null || timeGrain == null) {
            const durationHours = ((meet.durationInGrains ?? meet.duration_in_grains) * 15) / 60;
            const requiredCount = meet.requiredAttendances?.length || 0;
            const preferredCount = meet.preferredAttendances?.length || 0;
            const totalAttendees = requiredCount + preferredCount;

            // Analyze why unassigned
            const reasons = analyzeUnassignedReason(meet, schedule);

            const unassignedElement = $(`<div class="card-body"/>`)
                .append($(`<h5 class="card-title mb-1"/>`).text(meet.topic))
                .append($(`<p class="card-text mb-1"/>`).html(`<span class="fas fa-clock me-1"></span>${durationHours} hour(s)`))
                .append($(`<p class="card-text mb-1"/>`).html(`<span class="fas fa-users me-1"></span>${totalAttendees} attendees (${requiredCount} required, ${preferredCount} preferred)`));

            if (reasons.length > 0) {
                const reasonsList = $(`<div class="mt-2 small"/>`);
                reasonsList.append($(`<span class="text-muted">Possible issues:</span>`));
                reasons.forEach(reason => {
                    reasonsList.append($(`<div class="text-warning"/>`).html(`<span class="fas fa-exclamation-circle me-1"></span>${reason}`));
                });
                unassignedElement.append(reasonsList);
            }

            unassigned.append($(`<div class="col"/>`).append($(`<div class="card h-100"/>`).append(unassignedElement)));
        } else {
            const conflictStatus = getConflictStatus(assignment.id);
            const startDate = JSJoda.LocalDate.now().withDayOfYear(timeGrain.dayOfYear ?? timeGrain.day_of_year);
            const startTime = JSJoda.LocalTime.of(0, 0, 0, 0)
                .plusMinutes((timeGrain.startingMinuteOfDay ?? timeGrain.starting_minute_of_day));
            const startDateTime = JSJoda.LocalDateTime.of(startDate, startTime);
            const endDateTime = startDateTime.plusMinutes((meet.durationInGrains ?? meet.duration_in_grains) * 15);
            meet.requiredAttendances.forEach(attendance => {
                const byPersonElement = $("<div />")
                    .append($("<div class='d-flex justify-content-center align-items-center' />")
                        .append($(conflictStatus.icon))
                        .append($(`<h5 class="card-title mb-1"/>`).text(meet.topic)));
                byPersonElement.append($("<div class='d-flex justify-content-center' />").append($(`<span class="badge text-bg-success m-1" style="background-color: ${pickColor(meet.id)}" />`).text("Required")));
                if (meet.preferredAttendances.map(a => a.person).indexOf(attendance.person) >= 0) {
                    byPersonElement.append($("<div class='d-flex justify-content-center' />").append($(`<span class="badge text-bg-info m-1" style="background-color: ${pickColor(meet.id)}" />`).text("Preferred")));
                }
                byPersonItemData.add({
                    id: `${assignment.id}-${attendance.person.id}`,
                    group: attendance.person.id,
                    content: byPersonElement.html(),
                    start: startDateTime.toString(),
                    end: endDateTime.toString(),
                    style: `min-height: 50px; ${conflictStatus.style}`,
                    title: conflictStatus.reason || undefined
                });
            });
            meet.preferredAttendances.forEach(attendance => {
                if (meet.requiredAttendances.map(a => a.person).indexOf(attendance.person) === -1) {
                    const byPersonElement = $("<div />")
                        .append($("<div class='d-flex justify-content-center align-items-center' />")
                            .append($(conflictStatus.icon))
                            .append($(`<h5 class="card-title mb-1"/>`).text(meet.topic)));
                    byPersonElement.append($("<div class='d-flex justify-content-center' />").append($(`<span class="badge text-bg-info m-1" style="background-color: ${pickColor(meet.id)}" />`).text("Preferred")));
                    byPersonItemData.add({
                        id: `${assignment.id}-${attendance.person.id}`,
                        group: attendance.person.id,
                        content: byPersonElement.html(),
                        start: startDateTime.toString(),
                        end: endDateTime.toString(),
                        style: `min-height: 50px; ${conflictStatus.style}`,
                        title: conflictStatus.reason || undefined
                    });
                }
            });
        }
    });

    byPersonTimeline.setWindow(JSJoda.LocalDateTime.now().plusDays(1).withHour(8).toString(),
        JSJoda.LocalDateTime.now().plusDays(1).withHour(17).withMinute(45).toString());
}


// Click handlers for timeline items
byRoomTimeline.on('select', function (properties) {
    if (properties.items.length > 0) {
        showMeetingDetails(properties.items[0]);
    }
});

byPersonTimeline.on('select', function (properties) {
    if (properties.items.length > 0) {
        // For person view, item id is "assignmentId-personId", extract assignmentId
        const itemId = properties.items[0];
        const assignmentId = itemId.includes('-') ? itemId.split('-').slice(0, -1).join('-') : itemId;
        showMeetingDetails(assignmentId);
    }
});


function showMeetingDetails(assignmentId) {
    if (!loadedSchedule) return;

    // Find the assignment
    const assignment = loadedSchedule.meetingAssignments.find(a => a.id === assignmentId);
    if (!assignment) {
        console.warn('Assignment not found:', assignmentId);
        return;
    }

    // Build lookup maps
    const meetingMap = new Map();
    loadedSchedule.meetings.forEach(m => meetingMap.set(m.id, m));
    const roomMap = new Map();
    loadedSchedule.rooms.forEach(r => roomMap.set(r.id, r));
    const personMap = new Map();
    loadedSchedule.people.forEach(p => personMap.set(p.id, p));

    // Get meeting and room details
    const meeting = typeof assignment.meeting === 'string' ? meetingMap.get(assignment.meeting) : assignment.meeting;
    const room = typeof assignment.room === 'string' ? roomMap.get(assignment.room) : assignment.room;
    const timeGrain = typeof assignment.startingTimeGrain === 'string'
        ? loadedSchedule.timeGrains.find(t => t.id === assignment.startingTimeGrain)
        : assignment.startingTimeGrain;

    if (!meeting) {
        console.warn('Meeting not found for assignment:', assignmentId);
        return;
    }

    // Get conflict status
    const conflictStatus = getConflictStatus(assignmentId);

    // Build modal content
    const content = $("#meetingDetailsModalContent");
    content.empty();

    // Meeting title and status
    const statusBadge = conflictStatus.status === 'hard'
        ? '<span class="badge bg-danger ms-2">Hard Conflict</span>'
        : conflictStatus.status === 'medium'
            ? '<span class="badge bg-warning ms-2">Medium Issue</span>'
            : conflictStatus.status === 'soft'
                ? '<span class="badge bg-info ms-2">Soft Issue</span>'
                : '<span class="badge bg-success ms-2">OK</span>';

    content.append($('<h4/>').html(meeting.topic + statusBadge));

    // Show reason if any
    if (conflictStatus.reason) {
        content.append($('<div class="alert alert-info py-2"/>').text(conflictStatus.reason));
    }

    // Details table
    const detailsTable = $('<table class="table table-sm"/>');
    const tbody = $('<tbody/>');

    // Duration
    const durationHours = ((meeting.durationInGrains ?? meeting.duration_in_grains) * 15) / 60;
    tbody.append($('<tr/>')
        .append($('<th scope="row" style="width: 150px"/>').text('Duration'))
        .append($('<td/>').text(`${durationHours} hour(s) (${(meeting.durationInGrains ?? meeting.duration_in_grains)} time grains)`)));

    // Room
    if (room) {
        tbody.append($('<tr/>')
            .append($('<th scope="row"/>').text('Room'))
            .append($('<td/>').text(`${room.name} (capacity: ${room.capacity})`)));
    } else {
        tbody.append($('<tr/>')
            .append($('<th scope="row"/>').text('Room'))
            .append($('<td/>').html('<span class="text-danger">Not assigned</span>')));
    }

    // Time
    if (timeGrain) {
        const startDate = JSJoda.LocalDate.now().withDayOfYear(timeGrain.dayOfYear ?? timeGrain.day_of_year);
        const startTime = JSJoda.LocalTime.of(0, 0, 0, 0).plusMinutes((timeGrain.startingMinuteOfDay ?? timeGrain.starting_minute_of_day));
        const endTime = startTime.plusMinutes((meeting.durationInGrains ?? meeting.duration_in_grains) * 15);
        tbody.append($('<tr/>')
            .append($('<th scope="row"/>').text('Time'))
            .append($('<td/>').text(`${startDate.toString()} ${startTime.toString()} - ${endTime.toString()}`)));
    } else {
        tbody.append($('<tr/>')
            .append($('<th scope="row"/>').text('Time'))
            .append($('<td/>').html('<span class="text-danger">Not scheduled</span>')));
    }

    detailsTable.append(tbody);
    content.append(detailsTable);

    // Required Attendees section
    content.append($('<h5 class="mt-3"/>').text('Required Attendees'));
    if (meeting.requiredAttendances && meeting.requiredAttendances.length > 0) {
        const reqList = $('<ul class="list-group list-group-flush"/>');
        meeting.requiredAttendances.forEach(att => {
            const person = att.person?.fullName || (personMap.get(att.person)?.fullName) || att.person;
            reqList.append($('<li class="list-group-item py-1"/>')
                .html(`<span class="fas fa-user me-2 text-success"></span>${person}`));
        });
        content.append(reqList);
    } else {
        content.append($('<p class="text-muted"/>').text('No required attendees'));
    }

    // Preferred Attendees section
    content.append($('<h5 class="mt-3"/>').text('Preferred Attendees'));
    if (meeting.preferredAttendances && meeting.preferredAttendances.length > 0) {
        const prefList = $('<ul class="list-group list-group-flush"/>');
        meeting.preferredAttendances.forEach(att => {
            const person = att.person?.fullName || (personMap.get(att.person)?.fullName) || att.person;
            prefList.append($('<li class="list-group-item py-1"/>')
                .html(`<span class="fas fa-user me-2 text-info"></span>${person}`));
        });
        content.append(prefList);
    } else {
        content.append($('<p class="text-muted"/>').text('No preferred attendees'));
    }

    // Conflict details section
    if (conflictStatus.status !== 'ok' && analyzeCache && analyzeCache.has(assignmentId)) {
        content.append($('<h5 class="mt-3 text-danger"/>').text('Conflicts'));
        const conflictList = $('<ul class="list-group list-group-flush"/>');

        const violations = analyzeCache.get(assignmentId);

        // Show hard violations
        violations.hard.forEach(v => {
            conflictList.append($('<li class="list-group-item py-1 text-danger"/>')
                .html(`<span class="fas fa-exclamation-triangle me-2"></span>${v.constraint}`));
        });

        // Show medium violations
        violations.medium.forEach(v => {
            conflictList.append($('<li class="list-group-item py-1 text-warning"/>')
                .html(`<span class="fas fa-exclamation-circle me-2"></span>${v.constraint}`));
        });

        // Show soft violations
        violations.soft.forEach(v => {
            conflictList.append($('<li class="list-group-item py-1 text-info"/>')
                .html(`<span class="fas fa-info-circle me-2"></span>${v.constraint}`));
        });

        content.append(conflictList);
    }

    // Update modal title
    $("#meetingDetailsModalLabel").text("Meeting Details: " + meeting.topic);

    // Show modal
    bootstrap.Modal.getOrCreateInstance(document.getElementById("meetingDetailsModal")).show();
}


function solve() {
    if (!loadedSchedule) {
        showError("No schedule data loaded. Please wait for the data to load or refresh the page.");
        return;
    }
    
    console.log('Sending schedule data for solving:', loadedSchedule);
    $.post("/schedules", JSON.stringify(loadedSchedule), function (data) {
        scheduleId = data;
        refreshSolvingButtons(true);
    }).fail(function (xhr, ajaxOptions, thrownError) {
        showError("Start solving failed.", xhr);
        refreshSolvingButtons(false);
    }, "text");
}


function analyze() {
    bootstrap.Modal.getOrCreateInstance(document.getElementById("scoreAnalysisModal")).show();
    const scoreAnalysisModalContent = $("#scoreAnalysisModalContent");
    scoreAnalysisModalContent.children().remove();
    if (loadedSchedule.score == null) {
        scoreAnalysisModalContent.text("No score to analyze yet, please first press the 'solve' button.");
    } else {
        $('#scoreAnalysisScoreLabel').text(`(${loadedSchedule.score})`);
        $.put("/schedules/analyze", JSON.stringify(loadedSchedule), function (scoreAnalysis) {
            let constraints = scoreAnalysis.constraints;
            constraints.sort((a, b) => {
                let aComponents = getScoreComponents(a.score), bComponents = getScoreComponents(b.score);
                if (aComponents.hard < 0 && bComponents.hard > 0) return -1;
                if (aComponents.hard > 0 && bComponents.soft < 0) return 1;
                if (Math.abs(aComponents.hard) > Math.abs(bComponents.hard)) {
                    return -1;
                } else {
                    if (aComponents.medium < 0 && bComponents.medium > 0) return -1;
                    if (aComponents.medium > 0 && bComponents.medium < 0) return 1;
                    if (Math.abs(aComponents.medium) > Math.abs(bComponents.medium)) {
                        return -1;
                    } else {
                        if (aComponents.soft < 0 && bComponents.soft > 0) return -1;
                        if (aComponents.soft > 0 && bComponents.soft < 0) return 1;

                        return Math.abs(bComponents.soft) - Math.abs(aComponents.soft);
                    }
                }
            });
            constraints.map((e) => {
                let components = getScoreComponents(e.weight);
                e.type = components.hard != 0 ? 'hard' : (components.medium != 0 ? 'medium' : 'soft');
                e.weight = components[e.type];
                let scores = getScoreComponents(e.score);
                e.implicitScore = scores.hard != 0 ? scores.hard : (scores.medium != 0 ? scores.medium : scores.soft);
            });
            scoreAnalysis.constraints = constraints;

            scoreAnalysisModalContent.children().remove();
            scoreAnalysisModalContent.text("");

            const analysisTable = $(`<table class="table"/>`).css({textAlign: 'center'});
            const analysisTHead = $(`<thead/>`).append($(`<tr/>`)
                .append($(`<th></th>`))
                .append($(`<th>Constraint</th>`).css({textAlign: 'left'}))
                .append($(`<th>Type</th>`))
                .append($(`<th># Matches</th>`))
                .append($(`<th>Weight</th>`))
                .append($(`<th>Score</th>`))
                .append($(`<th></th>`)));
            analysisTable.append(analysisTHead);
            const analysisTBody = $(`<tbody/>`)
            $.each(scoreAnalysis.constraints, (index, constraintAnalysis) => {
                let icon = constraintAnalysis.type == "hard" && constraintAnalysis.implicitScore < 0 ? '<span class="fas fa-exclamation-triangle" style="color: red"></span>' : '';
                if (!icon) icon = constraintAnalysis.matches.length == 0 ? '<span class="fas fa-check-circle" style="color: green"></span>' : '';

                let row = $(`<tr/>`);
                row.append($(`<td/>`).html(icon))
                    .append($(`<td/>`).text(constraintAnalysis.name).css({textAlign: 'left'}))
                    .append($(`<td/>`).text(constraintAnalysis.type))
                    .append($(`<td/>`).html(`<b>${constraintAnalysis.matches.length}</b>`))
                    .append($(`<td/>`).text(constraintAnalysis.weight))
                    .append($(`<td/>`).text(constraintAnalysis.implicitScore));
                analysisTBody.append(row);
                row.append($(`<td/>`));
            });
            analysisTable.append(analysisTBody);
            scoreAnalysisModalContent.append(analysisTable);
        }).fail(function (xhr, ajaxOptions, thrownError) {
            showError("Analyze failed.", xhr);
        }, "text");
    }
}


function getScoreComponents(score) {
    let components = {hard: 0, medium: 0, soft: 0};

    $.each([...score.matchAll(/(-?[0-9]+)(hard|medium|soft)/g)], (i, parts) => {
        components[parts[2]] = parseInt(parts[1], 10);
    });

    return components;
}


function refreshSolvingButtons(solving) {
    if (solving) {
        $("#solveButton").hide();
        $("#stopSolvingButton").show();
        $("#solvingSpinner").addClass("active");
        if (autoRefreshIntervalId == null) {
            autoRefreshIntervalId = setInterval(refreshSchedule, 2000);
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

function stopSolving() {
    $.delete("/schedules/" + scheduleId, function () {
        refreshSolvingButtons(false);
        refreshSchedule();
    }).fail(function (xhr, ajaxOptions, thrownError) {
        showError("Stop solving failed.", xhr);
    });
}


function copyTextToClipboard(id) {
    var text = $("#" + id).text().trim();

    var dummy = document.createElement("textarea");
    document.body.appendChild(dummy);
    dummy.value = text;
    dummy.select();
    document.execCommand("copy");
    document.body.removeChild(dummy);
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
