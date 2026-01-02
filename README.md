# SolverForge Quickstarts

This repository contains quickstarts for [SolverForge](https://github.com/SolverForge/solverforge-legacy), an AI constraint solver and framework for Rust and Python.
It shows different use cases and basic implementations of constraint solving. The legacy (Timefold-based) quicktarts have been moved to [legacy](legacy/).

## Overview

| Use Case <img width="341" height="1">                                 | Notable Solver Concepts   <img width="541" height="1">   |
|-----------------------------------------------------------------------|----------------------------------------------------------|
| 🚚 <a href="#-vehicle-routing">Vehicle Routing</a>                    | Chained Through Time, Shadow Variables                   |
| 🧑‍💼 <a href="#-employee-scheduling">Employee Scheduling</a>         | Load Balancing                                           |
| 🛠️ <a href="#-maintenance-scheduling">Maintenance Scheduling</a>      | TimeGrain, Shadow Variable, Variable Listener            |
| 🛒 <a href="#-order-picking">Order Picking</a>                         | Chained Planning Variable, Shadow Variables              |
| 👥 <a href="#-meeting-scheduling">Meeting Scheduling</a>               | TimeGrain                                                |

> [!NOTE]
> The implementations in this repository serve as a starting point and/or inspiration when creating your own application.
> SolverForge is a library and does not include a UI. To illustrate these use cases a rudimentary UI is included in these quickstarts.

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

### 🛒 Order Picking

Generate an optimal picking plan for completing a set of orders.

![Order Picking Screenshot](legacy/order-picking/order-picking-screenshot.png)

- [Run order-picking](legacy/order-picking/README.adoc) (Python, FastAPI)

---

### 👥 Meeting Scheduling

Assign timeslots and rooms for meetings to produce a better schedule.

![Meeting Scheduling Screenshot](legacy/meeting-scheduling/meeting-scheduling-screenshot.png)

- [Run meeting-scheduling](legacy/meeting-scheduling/README.adoc) (Python, FastAPI)
- [Run meeting-scheduling (fast)](fast/meeting-scheduling-fast/README.adoc) (Python, FastAPI)

---

## Legal notice

This version of SolverForge is inspired on a repo that was forked on 03 August 2025 from the original Timefold Quickstarts, which was entirely Apache-2.0 licensed (a permissive license). Derivative work is limited to the [legacy/](legacy/) folder and the original fork is available as an archive.

The original Timefold Quickstarts was [forked](https://timefold.ai/blog/2023/optaplanner-fork/) on 20 April 2023 from OptaPlanner Quickstarts.

This version of SolverForge Quickstarts is inspired on the original Timefold Quickstarts and OptaPlanner Quickstarts, which includes copyrights of the original creators, Timefold AI, Red Hat Inc., affiliates, and contributors, that were all entirely licensed under the Apache-2.0 license, for the [legacy/](legacy/) folder exclusively. Every source file has been modified.

