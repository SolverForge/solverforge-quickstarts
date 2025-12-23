// Maintenance Scheduling Color Palette
const COLOR_IDEAL = '#8AE234';           // Green - in ideal window
const COLOR_IDEAL_BG = '#8AE23433';      // Green with transparency
const COLOR_ACCEPTABLE = '#FCAF3E';      // Orange - after ideal, before due
const COLOR_ACCEPTABLE_BG = '#FCAF3E33'; // Orange with transparency
const COLOR_OVERDUE = '#EF2929';         // Red - past due date
const COLOR_OVERDUE_BG = '#EF292999';    // Red with transparency
const BRAND_GREEN = '#10b981';           // SolverForge brand green
const HIGHLIGHT_COLOR = 'rgba(99, 102, 241, 0.15)'; // Indigo highlight

var autoRefreshIntervalId = null;
let highlightedCrewId = null;

let demoDataId = null;
let scheduleId = null;
let loadedSchedule = null;

const byCrewPanel = document.getElementById("byCrewPanel");
const byCrewTimelineOptions = {
    timeAxis: {scale: "day"},
    orientation: {axis: "top"},
    stack: false,
    xss: {disabled: true}, // Items are XSS safe through JQuery
    zoomMin: 3 * 1000 * 60 * 60 * 24 // Three day in milliseconds
};
var byCrewGroupData = new vis.DataSet();
var byCrewItemData = new vis.DataSet();
var byCrewTimeline = new vis.Timeline(byCrewPanel, byCrewItemData, byCrewGroupData, byCrewTimelineOptions);

const byJobPanel = document.getElementById("byJobPanel");
const byJobTimelineOptions = {
    timeAxis: {scale: "day"},
    orientation: {axis: "top"},
    xss: {disabled: true}, // Items are XSS safe through JQuery
    zoomMin: 3 * 1000 * 60 * 60 * 24 // Three day in milliseconds
};
var byJobGroupData = new vis.DataSet();
var byJobItemData = new vis.DataSet();
var byJobTimeline = new vis.Timeline(byJobPanel, byJobItemData, byJobGroupData, byJobTimelineOptions);


$(document).ready(function () {
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
    // HACK to allow vis-timeline to work within Bootstrap tabs
    $("#byCrewTab").on('shown.bs.tab', function (event) {
        byCrewTimeline.redraw();
    })
    $("#byJobTab").on('shown.bs.tab', function (event) {
        byJobTimeline.redraw();
    })

    // Timeline item click handlers
    byCrewTimeline.on('select', function(properties) {
        if (properties.items.length > 0) {
            const itemId = properties.items[0];
            // Ignore background items (they have underscore in ID like "job1_readyToIdealEnd")
            if (!String(itemId).includes('_')) {
                showJobDetails(itemId);
            }
            byCrewTimeline.setSelection([]); // Clear selection
        }
    });
    byJobTimeline.on('select', function(properties) {
        if (properties.items.length > 0) {
            const itemId = properties.items[0];
            if (!String(itemId).includes('_')) {
                showJobDetails(itemId);
            }
            byJobTimeline.setSelection([]);
        }
    });

    setupAjax();
    fetchDemoData();
});

function setupAjax() {
    $.ajaxSetup({
        headers: {
            'Content-Type': 'application/json',
            'Accept': 'application/json,text/plain', // plain text is required by solve() returning UUID of the solver job
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
                scheduleId = null;
                demoDataId = item;

                refreshSchedule();
            });
        });

        // load first data set
        demoDataId = data[0];
        switchDataDropDownItemActive(demoDataId);
        refreshSchedule();
    }).fail(function (xhr, ajaxOptions, thrownError) {
        // disable this page as there is no data
        let $demo = $("#demo");
        $demo.empty();
        $demo.html("<h1><p align=\"center\">No test data available</p></h1>")
    });
}

function switchDataDropDownItemActive(newItem) {
    activeCssClass = "active";
    $("#testDataButton > a." + activeCssClass).removeClass(activeCssClass);
    $("#" + newItem + "TestData").addClass(activeCssClass);
}

function refreshSchedule() {
    let path = "/schedules/" + scheduleId;
    if (scheduleId === null) {
        if (demoDataId === null) {
            alert("Please select a test data set.");
            return;
        }

        path = "/demo-data/" + demoDataId;
    }

    $.getJSON(path, function (schedule) {
        loadedSchedule = schedule;
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

    const unassignedJobs = $("#unassignedJobs");
    unassignedJobs.children().remove();
    var unassignedJobsCount = 0;
    byCrewGroupData.clear();
    byJobGroupData.clear();
    byCrewItemData.clear();
    byJobItemData.clear();

    $.each(schedule.crews, (index, crew) => {
        byCrewGroupData.add({id: crew.id, content: crew.name});
    });

    $.each(schedule.jobs, (index, job) => {
        const jobGroupElement = $(`<div/>`)
            .append($(`<h5 class="card-title mb-1"/>`).text(job.name))
            .append($(`<p class="card-text ms-2 mb-0"/>`).text(`${job.durationInDays} workdays`));
        byJobGroupData.add({
            id: job.id,
            content: jobGroupElement.html()
        });
        byJobItemData.add({
            id: job.id + "_readyToIdealEnd", group: job.id,
            start: job.minStartDate, end: job.idealEndDate,
            type: "background",
            style: `background-color: ${COLOR_IDEAL_BG}`
        });
        byJobItemData.add({
            id: job.id + "_idealEndToDue", group: job.id,
            start: job.idealEndDate, end: job.maxEndDate,
            type: "background",
            style: `background-color: ${COLOR_ACCEPTABLE_BG}`
        });

        if (job.crew == null || job.startDate == null) {
            unassignedJobsCount++;
            const unassignedJobElement = $(`<div class="card-body p-2"/>`)
                .append($(`<h5 class="card-title mb-1"/>`).text(job.name))
                .append($(`<p class="card-text ms-2 mb-0"/>`).text(`${job.durationInDays} workdays`))
                .append($(`<p class="card-text ms-2 mb-0"/>`).text(`Start: ${job.minStartDate}`))
                .append($(`<p class="card-text ms-2 mb-0"/>`).text(`End: ${job.maxEndDate}`));
            const byJobJobElement = $(`<div/>`)
                .append($(`<h5 class="card-title mb-1"/>`).text(`Unassigned`));
            $.each(job.tags, (index, tag) => {
                const color = pickColor(tag);
                unassignedJobElement.append($(`<span class="badge me-1" style="background-color: ${color}"/>`).text(tag));
                byJobJobElement.append($(`<span class="badge me-1" style="background-color: ${color}"/>`).text(tag));
            });
            const card = $(`<div class="card" style="cursor: pointer;"/>`).append(unassignedJobElement);
            card.click(() => showJobDetails(job.id));
            unassignedJobs.append($(`<div class="col"/>`).append(card));
            byJobItemData.add({
                id: job.id,
                group: job.id,
                content: byJobJobElement.html(),
                start: job.minStartDate,
                end: JSJoda.LocalDate.parse(job.minStartDate).plusDays(job.durationInDays).toString(),
                style: `background-color: ${COLOR_OVERDUE_BG}`
            });
        } else {
            const beforeReady = JSJoda.LocalDate.parse(job.startDate).isBefore(JSJoda.LocalDate.parse(job.minStartDate));
            const afterDue = JSJoda.LocalDate.parse(job.endDate).isAfter(JSJoda.LocalDate.parse(job.maxEndDate));
            const byCrewJobElement = $(`<div/>`)
                .append($(`<h5 class="card-title mb-1"/>`).text(job.name))
                .append($(`<p class="card-text ms-2 mb-0"/>`).text(`${job.durationInDays} workdays`));
            const byJobJobElement = $(`<div/>`)
                .append($(`<h5 class="card-title mb-1"/>`).text(job.crew.name));
            if (beforeReady) {
                byCrewJobElement.append($(`<p class="badge badge-danger mb-0"/>`).text(`Before ready (too early)`));
                byJobJobElement.append($(`<p class="badge badge-danger mb-0"/>`).text(`Before ready (too early)`));
            }
            if (afterDue) {
                byCrewJobElement.append($(`<p class="badge badge-danger mb-0"/>`).text(`After due (too late)`));
                byJobJobElement.append($(`<p class="badge badge-danger mb-0"/>`).text(`After due (too late)`));
            }
            $.each(job.tags, (index, tag) => {
                const color = pickColor(tag);
                byCrewJobElement.append($(`<span class="badge me-1" style="background-color: ${color}"/>`).text(tag));
                byJobJobElement.append($(`<span class="badge me-1" style="background-color: ${color}"/>`).text(tag));
            });
            byCrewItemData.add({
                id: job.id, group: job.crew.id,
                content: byCrewJobElement.html(),
                start: job.startDate, end: job.endDate
            });
            byJobItemData.add({
                id: job.id, group: job.id,
                content: byJobJobElement.html(),
                start: job.startDate, end: job.endDate,
                crewId: job.crew.id
            });
        }
    });
    if (unassignedJobsCount === 0) {
        unassignedJobs.append($(`<p/>`).text(`There are no unassigned jobs.`));
    }
    byCrewTimeline.setWindow(schedule.workCalendar.fromDate, schedule.workCalendar.toDate);
    byJobTimeline.setWindow(schedule.workCalendar.fromDate, schedule.workCalendar.toDate);

    // Render crew table and clear any previous highlighting
    renderCrewTable(schedule);
    highlightedCrewId = null;
}

function solve() {
    $.post("/schedules", JSON.stringify(loadedSchedule), function (data) {
        scheduleId = data;
        refreshSolvingButtons(true);
    }).fail(function (xhr, ajaxOptions, thrownError) {
            showError("Start solving failed.", xhr);
            refreshSolvingButtons(false);
        },
        "text");
}

function analyze() {
    analyzeScore(loadedSchedule, "/schedules/analyze");
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
    var text = document.getElementById(id).innerText;
    navigator.clipboard.writeText(text);
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
          <div class="ms-auto d-flex align-items-center gap-3">
              <div class="dropdown">
                  <button class="btn dropdown-toggle" type="button" id="dropdownMenuButton" data-bs-toggle="dropdown" aria-haspopup="true" aria-expanded="false" style="background-color: #10b981; color: #ffffff; border-color: #10b981;">
                      Data
                  </button>
                  <div id="testDataButton" class="dropdown-menu" aria-labelledby="dropdownMenuButton"></div>
              </div>
          </div>
        </nav>
      </div>`),
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
             </footer>`),
    );
  }
}

// ****************************************************************************
// Job Details Modal
// ****************************************************************************

function showJobDetails(jobId) {
    const job = loadedSchedule.jobs.find(j => j.id === jobId);
    if (!job) return;

    $("#jobDetailsName").text(job.name);
    $("#jobDetailsCrew").html(job.crew ?
        `<i class="fas fa-hard-hat me-1"></i>${job.crew.name}` :
        '<span class="text-danger">Unassigned</span>');
    $("#jobDetailsDuration").text(`${job.durationInDays} workdays`);
    $("#jobDetailsMinStart").text(job.minStartDate);
    $("#jobDetailsMaxEnd").text(job.maxEndDate);
    $("#jobDetailsIdealEnd").text(job.idealEndDate);

    if (job.startDate && job.endDate) {
        $("#jobDetailsScheduled").text(`${job.startDate} to ${job.endDate}`);
    } else {
        $("#jobDetailsScheduled").html('<span class="text-muted">Not scheduled</span>');
    }

    // Tags
    const tagsContainer = $("#jobDetailsTags");
    tagsContainer.empty();
    if (job.tags && job.tags.length > 0) {
        job.tags.forEach(tag => {
            const color = pickColor(tag);
            tagsContainer.append($(`<span class="badge me-1" style="background-color: ${color}"/>`).text(tag));
        });
    } else {
        tagsContainer.html('<span class="text-muted">None</span>');
    }

    // Status alerts
    const statusDiv = $("#jobDetailsStatus");
    statusDiv.hide().removeClass("alert-danger alert-warning alert-success");

    if (!job.crew || !job.startDate) {
        statusDiv.addClass("alert-danger").text("This job is not assigned to any crew.").show();
    } else {
        const beforeReady = JSJoda.LocalDate.parse(job.startDate).isBefore(JSJoda.LocalDate.parse(job.minStartDate));
        const afterDue = JSJoda.LocalDate.parse(job.endDate).isAfter(JSJoda.LocalDate.parse(job.maxEndDate));
        const afterIdeal = JSJoda.LocalDate.parse(job.endDate).isAfter(JSJoda.LocalDate.parse(job.idealEndDate));

        if (beforeReady) {
            statusDiv.addClass("alert-warning").text("Scheduled before ready date (too early).").show();
        } else if (afterDue) {
            statusDiv.addClass("alert-danger").text("Scheduled after due date (too late).").show();
        } else if (afterIdeal) {
            statusDiv.addClass("alert-warning").text("Ends after ideal date.").show();
        } else {
            statusDiv.addClass("alert-success").text("Scheduled within ideal window.").show();
        }
    }

    new bootstrap.Modal("#jobDetailsModal").show();
}

// ****************************************************************************
// Crew Details Modal
// ****************************************************************************

function showCrewDetails(crewId) {
    const crew = loadedSchedule.crews.find(c => c.id === crewId);
    if (!crew) return;

    const crewJobs = loadedSchedule.jobs.filter(j => j.crew && j.crew.id === crewId);
    const totalWorkdays = crewJobs.reduce((sum, j) => sum + j.durationInDays, 0);

    $("#crewDetailsName").text(crew.name);
    $("#crewDetailsJobCount").text(crewJobs.length);
    $("#crewDetailsWorkdays").text(totalWorkdays);

    // Job list
    const jobList = $("#crewDetailsJobList");
    jobList.empty();

    if (crewJobs.length === 0) {
        jobList.append('<div class="list-group-item text-muted">No jobs assigned</div>');
    } else {
        crewJobs.forEach(job => {
            const afterDue = job.endDate && JSJoda.LocalDate.parse(job.endDate).isAfter(JSJoda.LocalDate.parse(job.maxEndDate));
            const statusIcon = afterDue ?
                '<i class="fas fa-exclamation-triangle text-danger me-2"></i>' :
                '<i class="fas fa-check-circle text-success me-2"></i>';

            const item = $(`
                <a href="#" class="list-group-item list-group-item-action d-flex justify-content-between align-items-center">
                    <div>
                        ${statusIcon}
                        <strong>${job.name}</strong>
                        <small class="text-muted ms-2">${job.durationInDays} days</small>
                    </div>
                    <small class="text-muted">${job.startDate || 'Not scheduled'}</small>
                </a>
            `);
            item.click((e) => {
                e.preventDefault();
                bootstrap.Modal.getInstance(document.getElementById('crewDetailsModal')).hide();
                setTimeout(() => showJobDetails(job.id), 300);
            });
            jobList.append(item);
        });
    }

    new bootstrap.Modal("#crewDetailsModal").show();
}

// ****************************************************************************
// Crew Highlighting
// ****************************************************************************

function renderCrewTable(schedule) {
    const crewTableBody = $("#crewTableBody");
    crewTableBody.empty();

    schedule.crews.forEach(crew => {
        const crewJobs = schedule.jobs.filter(j => j.crew && j.crew.id === crew.id);
        const totalWorkdays = crewJobs.reduce((sum, j) => sum + j.durationInDays, 0);
        const color = pickColor("crew" + crew.id);

        const row = $(`
            <tr class="crew-row" data-crew-id="${crew.id}">
                <td>
                    <div class="crew-color-indicator" style="background-color: ${color};">
                        <i class="fas fa-hard-hat"></i>
                    </div>
                </td>
                <td><strong>${crew.name}</strong></td>
                <td>${crewJobs.length}</td>
                <td>${totalWorkdays}</td>
                <td>
                    <button class="btn btn-sm btn-outline-secondary crew-info-btn" title="View details">
                        <i class="fas fa-info-circle"></i>
                    </button>
                </td>
            </tr>
        `);

        // Click row to highlight
        row.click((e) => {
            if (!$(e.target).closest('.crew-info-btn').length) {
                toggleCrewHighlight(crew.id);
            }
        });

        // Click info button to show details
        row.find('.crew-info-btn').click((e) => {
            e.stopPropagation();
            showCrewDetails(crew.id);
        });

        crewTableBody.append(row);
    });
}

function toggleCrewHighlight(crewId) {
    if (highlightedCrewId === crewId) {
        clearCrewHighlight();
    } else {
        highlightCrew(crewId);
    }
}

function clearCrewHighlight() {
    highlightedCrewId = null;
    $(".crew-row").removeClass("table-active");

    // Reset timeline item opacity in both views
    byCrewItemData.forEach(item => {
        if (item.originalStyle !== undefined) {
            byCrewItemData.update({ id: item.id, style: item.originalStyle });
        }
    });
    byJobItemData.forEach(item => {
        if (item.originalStyle !== undefined) {
            byJobItemData.update({ id: item.id, style: item.originalStyle });
        }
    });
}

function highlightCrew(crewId) {
    highlightedCrewId = crewId;

    // Highlight table row
    $(".crew-row").removeClass("table-active");
    $(`[data-crew-id="${crewId}"]`).addClass("table-active");

    // Dim non-highlighted timeline items in "By crew" view
    byCrewItemData.forEach(item => {
        if (item.originalStyle === undefined) {
            item.originalStyle = item.style || "";
        }
        if (item.group !== crewId) {
            byCrewItemData.update({
                id: item.id,
                style: item.originalStyle + "; opacity: 0.25;"
            });
        } else {
            byCrewItemData.update({
                id: item.id,
                style: item.originalStyle
            });
        }
    });

    // Dim non-highlighted timeline items in "By job" view
    byJobItemData.forEach(item => {
        if (item.originalStyle === undefined) {
            item.originalStyle = item.style || "";
        }
        // Check if this job belongs to the highlighted crew
        if (item.crewId !== crewId && item.type !== "background") {
            byJobItemData.update({
                id: item.id,
                style: item.originalStyle + "; opacity: 0.25;"
            });
        } else if (item.type !== "background") {
            byJobItemData.update({
                id: item.id,
                style: item.originalStyle
            });
        }
    });
}
