# SolverForge Quickstarts

This repository contains Python quickstarts for [SolverForge](https://github.com/SolverForge/solverforge-legacy), a 100% Timefold-compatible AI constraint solver. The original Timefold solver for Python has been [discontinued by Timefold](https://github.com/TimefoldAI/timefold-solver/discussions/1698#discussioncomment-13842196) and the original team is focusing on the Java and Kotlin solvers.
A roadmap to provide community support for Python is currently under review.

Priority for this repository is closing the performance gap between the Java and Python quickstarts by providing optimized solutions for all use cases.

- The original quickstarts have been moved to [legacy/](legacy/). These are based on unified Pydantic data models for API and constraint solving
- In [fast/](fast/) we are incrementally refactoring quickstarts to employ more efficient data models that limit Pydantic to API boundary validation to reduce overhead during solver moves
- In [benchmarks/](benchmarks/) we are running benchmarks to assess the performance of the different implementations

Current results are available in the [benchmarks](benchmarks/) directory:
- [Meeting Scheduling Benchmark](benchmarks/results_meeting-scheduling.md)
- [Vehicle Routing Benchmark](benchmarks/results_vehicle-routing.md)

You can also find our assessment of said results in [report.md](benchmarks/report.md).

Currently, *fast* quickstarts are available for the [employee-scheduling](fast/employee-scheduling-fast/README.MD), [meeting scheduling](fast/meeting-scheduling-fast/README.MD) and [vehicle-routing](fast/vehicle-routing-fast/README.MD) use cases, exclusively.

Being unofficial, this repository is not directly affiliated with Timefold AI, but maintainers are in touch with the Timefold AI team.

It shows different use cases and basic implementations of constraint solving in Python.

## Overview

| Use Case <img width="341" height="1">                                 | Notable Solver Concepts   <img width="541" height="1">   |
|-----------------------------------------------------------------------|----------------------------------------------------------|
| 🚚 <a href="#-vehicle-routing">Vehicle Routing</a>                    | Chained Through Time, Shadow Variables                   |
| 🧑‍💼 <a href="#-employee-scheduling">Employee Scheduling</a>         | Load Balancing                                           |
| 🛠️ <a href="#-maintenance-scheduling">Maintenance Scheduling</a>      | TimeGrain, Shadow Variable, Variable Listener            |
| 📦 <a href="#-food-packaging">Food Packaging</a>                       | Chained Through Time, Shadow Variables, Pinning          |
| 🛒 <a href="#-order-picking">Order Picking</a>                         | Chained Planning Variable, Shadow Variables              |
| 🏫 <a href="#-school-timetabling">School Timetabling</a>               | Timeslot                                                 |
| 🏭 <a href="#-facility-location-problem">Facility Location Problem</a> | Shadow Variable                                          |
| 🎤 <a href="#-conference-scheduling">Conference Scheduling</a>         | Timeslot, Justifications                                 |
| 🛏️ <a href="#-bed-allocation-scheduling">Bed Allocation Scheduling</a> | Allows Unassigned                                        |
| 🛫 <a href="#-flight-crew-scheduling">Flight Crew Scheduling</a>       |                                                          |
| 👥 <a href="#-meeting-scheduling">Meeting Scheduling</a>               | TimeGrain                                                |
| ✅ <a href="#-task-assigning">Task Assigning</a>                        | Bendable Score, Chained Through Time, Allows Unassigned  |
| 📆 <a href="#-project-job-scheduling">Project Job Scheduling</a>       | Shadow Variables, Variable Listener, Strenght Comparator |
| 🏆 <a href="#-sports-league-scheduling">Sports League Scheduling</a>   | Consecutive Sequences                                    |
| 🏅 <a href="#-tournament-scheduling">Tournament Scheduling</a>         | Pinning, Load Balancing                                  |

> [!NOTE]
> The implementations in this repository serve as a starting point and/or inspiration when creating your own application.
> Timefold Solver is a library and does not include a UI. To illustrate these use cases a rudimentary UI is included in these quickstarts.

## Use cases

### 🚚 Vehicle Routing

Find the most efficient routes for vehicles to reach visits, considering vehicle capacity and time windows when visits are available. Sometimes also called "CVRPTW".

![Vehicle Routing Screenshot](legacy/vehicle-routing/vehicle-routing-screenshot.png)

- [Run vehicle-routing](legacy/vehicle-routing/README.MD) (Python, FastAPI)
- [Run vehicle-routing (fast)](fast/vehicle-routing-fast/README.MD) (Python, FastAPI)

> [!TIP]
>  <img src="https://docs.timefold.ai/_/img/models/field-service-routing.svg" align="right" width="50px" /> [Check out our off-the-shelf model for Field Service Routing](https://app.timefold.ai/models/field-service-routing). This model goes beyond basic Vehicle Routing and supports additional constraints such as priorities, skills, fairness and more.

---

### 🧑‍💼 Employee Scheduling

Schedule shifts to employees, accounting for employee availability and shift skill requirements.

![Employee Scheduling Screenshot](java/employee-scheduling/employee-scheduling-screenshot.png)

- [Run employee-scheduling](legacy/employee-scheduling/README.MD) (Python, FastAPI)
- [Run employee-scheduling (fast)](fast/employee-scheduling-fast/README.MD) (Python, FastAPI)

> [!TIP]
>  <img src="https://docs.timefold.ai/_/img/models/employee-shift-scheduling.svg" align="right" width="50px" /> [Check out our off-the-shelf model for Employee Shift Scheduling](https://app.timefold.ai/models/employee-scheduling). This model supports many additional constraints such as skills, pairing employees, fairness and more.

---

### 🛠️ Maintenance Scheduling

Schedule maintenance jobs to crews over time to reduce both premature and overdue maintenance.

![Maintenance Scheduling Screenshot](legacy/maintenance-scheduling/maintenance-scheduling-screenshot.png)

- [Run maintenance-scheduling](legacy/maintenance-scheduling/README.adoc) (Python, FastAPI)

---

### 📦 Food Packaging

Schedule food packaging orders to manufacturing lines to minimize downtime and fulfill all orders on time.

![Food Packaging Screenshot](legacy/food-packaging/food-packaging-screenshot.png)

- [Run food-packaging](legacy/food-packaging/README.adoc) (Python, FastAPI)

---

### 🛒 Order Picking

Generate an optimal picking plan for completing a set of orders.

![Order Picking Screenshot](legacy/order-picking/order-picking-screenshot.png)

- [Run order-picking](legacy/order-picking/README.adoc) (Python, FastAPI)

---

### 🏫 School Timetabling

Assign lessons to timeslots and rooms to produce a better schedule for teachers and students.

![School Timetabling Screenshot](legacy/school-timetabling/school-timetabling-screenshot.png)

- [Run school-timetabling](legacy/school-timetabling/README.adoc) (Python, FastAPI)

Without a UI:

- [Run hello-world-school-timetabling](legacy/hello-world/README.adoc) (Java, Maven or Gradle)

---

### 🏭 Facility Location Problem

Pick the best geographical locations for new stores, distribution centers, COVID test centers, or telecom masts.

![Facility Location Screenshot](legacy/facility-location/facility-location-screenshot.png)

- [Run facility-location](legacy/facility-location/README.adoc) (Python, FastAPI)

---

### 🎤 Conference Scheduling

Assign conference talks to timeslots and rooms to produce a better schedule for speakers.

![Conference Scheduling Screenshot](legacy/conference-scheduling/conference-scheduling-screenshot.png)

- [Run conference-scheduling](legacy/conference-scheduling/README.adoc) (Python, FastAPI)

---

### 🛏️ Bed Allocation Scheduling

Assign beds to patient stays to produce a better schedule for hospitals.

![Bed Scheduling Screenshot](legacy/bed-allocation/bed-scheduling-screenshot.png)

- [Run bed-allocation-scheduling](legacy/bed-allocation/README.adoc) (Python, FastAPI)

---

### 🛫 Flight Crew Scheduling

Assign crew to flights to produce a better schedule for flight assignments.

![Flight Crew Scheduling Screenshot](legacy/flight-crew-scheduling/flight-crew-scheduling-screenshot.png)

- [Run flight-crew-scheduling](legacy/flight-crew-scheduling/README.adoc) (Python, FastAPI)

---

### 👥 Meeting Scheduling

Assign timeslots and rooms for meetings to produce a better schedule.

![Meeting Scheduling Screenshot](legacy/meeting-scheduling/meeting-scheduling-screenshot.png)

- [Run meeting-scheduling](legacy/meeting-scheduling/README.adoc) (Python, FastAPI)
- [Run meeting-scheduling (fast)](fast/meeting-scheduling-fast/README.adoc) (Python, FastAPI)

---

### ✅ Task Assigning

Assign employees to tasks to produce a better plan for task assignments.

![Task Assigning Screenshot](legacy/task-assigning/task-assigning-screenshot.png)

- [Run task-assigning](legacy/task-assigning/README.adoc) (Python, FastAPI)

---

### 📆 Project Job Scheduling

Assign jobs for execution to produce a better schedule for project job allocations.

![Project Job Scheduling Screenshot](legacy/project-job-scheduling/project-job-scheduling-screenshot.png)

- [Run project-job-scheduling](legacy/project-job-scheduling/README.adoc) (Python, FastAPI)

---

### 🏆 Sports League Scheduling

Assign rounds to matches to produce a better schedule for league matches.

![Sports League Scheduling Screenshot](legacy/sports-league-scheduling/sports-league-scheduling-screenshot.png)

- [Run sports-league-scheduling](legacy/sports-league-scheduling/README.adoc) (Python, FastAPI)

---

### 🏅 Tournament Scheduling

Tournament Scheduling service assigning teams to tournament matches.

![Tournament Scheduling Screenshot](legacy/tournament-scheduling/tournament-scheduling-screenshot.png)

- [Run tournament-scheduling](legacy/tournament-scheduling/README.adoc) (Python, FastAPI)

---

## Legal notice

This version of Timefold Quickstarts was forked on 03 August 2025 from the original Timefold Quickstarts, which was entirely Apache-2.0 licensed (a permissive license).

The original Timefold Quickstarts was [forked](https://timefold.ai/blog/2023/optaplanner-fork/) on 20 April 2023 from OptaPlanner Quickstarts.

This version of Timefold Quickstarts is a derivative work of the original Timefold Quickstarts and OptaPlanner Quickstarts, which includes copyrights of the original creators, Timefold AI, Red Hat Inc., affiliates, and contributors, that were all entirely licensed under the Apache-2.0 license.
Every source file has been modified.
