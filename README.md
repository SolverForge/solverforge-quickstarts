# SolverForge Quickstarts

This repository contains quickstarts for [SolverForge](https://github.com/SolverForge/solverforge), an AI constraint solver and framework for Rust and Python.
It shows different use cases and basic implementations of constraint solving.

## Overview

| Use Case <img width="341" height="1">                                 | Rust | Python (Legacy) | Notable Solver Concepts <img width="541" height="1"> |
|-----------------------------------------------------------------------|------|-----------------|-----------------------------------------------------|
| 👋 <a href="#-hello-world">Hello World</a>                            | 🚧   | ✅              | Basic Planning Problem                              |
| 🧑‍💼 <a href="#-employee-scheduling">Employee Scheduling</a>         | ✅   | ✅              | Load Balancing                                      |
| 🚚 <a href="#-vehicle-routing">Vehicle Routing</a>                    | 🚧   | ✅              | Chained Through Time, Shadow Variables              |
| 🛠️ <a href="#-maintenance-scheduling">Maintenance Scheduling</a>      | 🚧   | ✅              | TimeGrain, Shadow Variable, Variable Listener       |
| 🛒 <a href="#-order-picking">Order Picking</a>                         | 🚧   | ✅              | Chained Planning Variable, Shadow Variables         |
| 👥 <a href="#-meeting-scheduling">Meeting Scheduling</a>               | 🚧   | ✅              | TimeGrain                                           |
| 📈 <a href="#-portfolio-optimization">Portfolio Optimization</a>       | 🚧   | ✅              | Financial Constraints                               |
| 🖥️ <a href="#-vm-placement">VM Placement</a>                          | 🚧   | ✅              | Bin Packing, Resource Allocation                    |

> [!NOTE]
> The implementations in this repository serve as a starting point and/or inspiration when creating your own application.
> SolverForge is a library and does not include a UI. To illustrate these use cases a rudimentary UI is included in these quickstarts.
>
> **Rust implementations** are native SolverForge applications showcasing zero-erasure architecture.
> **Python (Legacy)** implementations use the Timefold-based legacy solver and are located in the [legacy/](legacy/) directory.

## Use cases

### 👋 Hello World

A minimal example demonstrating the basics of constraint solving with SolverForge.

- **Python (Legacy)**: [legacy/hello-world-fast](legacy/hello-world-fast/README.md)

---

### 🧑‍💼 Employee Scheduling

Schedule shifts to employees, accounting for employee availability and shift skill requirements.

- **Rust**: [rust/employee-scheduling](rust/employee-scheduling/README.md)
- **Python (Legacy)**: [legacy/employee-scheduling-fast](legacy/employee-scheduling-fast/README.md)

---

### 🚚 Vehicle Routing

Find the most efficient routes for vehicles to reach visits, considering vehicle capacity and time windows when visits are available. Sometimes also called "CVRPTW".

- **Python (Legacy)**: [legacy/vehicle-routing-fast](legacy/vehicle-routing-fast/README.md)

---

### 🛠️ Maintenance Scheduling

Schedule maintenance jobs to crews over time to reduce both premature and overdue maintenance.

- **Python (Legacy)**: [legacy/maintenance-scheduling-fast](legacy/maintenance-scheduling-fast/README.md)

---

### 🛒 Order Picking

Generate an optimal picking plan for completing a set of orders.

- **Python (Legacy)**: [legacy/order-picking-fast](legacy/order-picking-fast/README.md)

---

### 👥 Meeting Scheduling

Assign timeslots and rooms for meetings to produce a better schedule.

- **Python (Legacy)**: [legacy/meeting-scheduling-fast](legacy/meeting-scheduling-fast/README.md)

---

### 📈 Portfolio Optimization

Optimize investment portfolios to balance risk and return while satisfying various financial constraints.

- **Python (Legacy)**: [legacy/portfolio-optimization-fast](legacy/portfolio-optimization-fast/README.md)

---

### 🖥️ VM Placement

Optimize the placement of virtual machines across physical servers to maximize resource utilization and minimize costs.

- **Python (Legacy)**: [legacy/vm-placement-fast](legacy/vm-placement-fast/README.md)

---

## Legal notice

This version of SolverForge is inspired on a repo that was forked on 03 August 2025 from the original Timefold Quickstarts, which was entirely Apache-2.0 licensed (a permissive license). Derivative work is limited to the [legacy/](legacy/) folder and the original fork is available as an archive.

The original Timefold Quickstarts was [forked](https://timefold.ai/blog/2023/optaplanner-fork/) on 20 April 2023 from OptaPlanner Quickstarts.

This version of SolverForge Quickstarts is inspired on the original Timefold Quickstarts and OptaPlanner Quickstarts, which includes copyrights of the original creators, Timefold AI, Red Hat Inc., affiliates, and contributors, that were all entirely licensed under the Apache-2.0 license, for the [legacy/](legacy/) folder exclusively. Every source file has been modified.

