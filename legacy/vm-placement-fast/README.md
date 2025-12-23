---
title: Virtual Machine Placement (Python)
emoji: 👀
colorFrom: gray
colorTo: green
sdk: docker
app_port: 8080
pinned: false
license: apache-2.0
short_description: SolverForge Quickstart for the Vehicle Routing problem
---


# VM Placement Quickstart

A SolverForge quickstart demonstrating **constraint-based virtual machine placement optimization**.

## The Problem

You manage a datacenter with physical servers organized in racks, and must place virtual machines (VMs) onto those servers. Each server has limited CPU cores, memory, and storage capacity.

**The challenge**: Place all VMs while:
- Never exceeding any server's CPU, memory, or storage capacity
- Keeping database replicas on separate servers (anti-affinity)
- Placing related services together when possible (affinity)
- Minimizing the number of active servers (consolidation)
- Balancing load across active servers

## Why Constraint Solving?

With constraints, you describe *what* a valid placement looks like, not *how* to compute one. Adding a new business rule (e.g., "GPU workloads need GPU servers") is a single constraint function—not a rewrite of your algorithm.

## Quick Start

```bash
# 1. Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# 2. Install dependencies
pip install -e .

# 3. Run the application
run-app

# 4. Open http://localhost:8080 in your browser
```

**Requirement:** JDK 17+ must be installed (solverforge-legacy uses JPype to bridge Python and Java).

## Running Tests

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/test_constraints.py
```

## Project Structure

```
vm-placement-fast/
├── src/vm_placement/
│   ├── domain.py          # Server, VM, and VMPlacementPlan
│   ├── constraints.py     # Hard and soft placement constraints
│   ├── solver.py          # SolverForge configuration
│   ├── demo_data.py       # Sample infrastructure and VMs
│   ├── rest_api.py        # FastAPI endpoints
│   └── converters.py      # Domain ↔ REST model conversion
├── tests/
│   └── test_constraints.py  # Unit tests for each constraint
├── static/
│   ├── index.html         # Web UI with rack visualization
│   ├── app.js             # Frontend logic
│   └── config.js          # Advanced settings sliders
└── pyproject.toml         # Dependencies
```

## Constraints

### Hard Constraints (must be satisfied)

1. **CPU Capacity**: Server CPU cannot be exceeded by assigned VMs
2. **Memory Capacity**: Server memory cannot be exceeded by assigned VMs
3. **Storage Capacity**: Server storage cannot be exceeded by assigned VMs
4. **Anti-Affinity**: VMs in the same anti-affinity group (e.g., database replicas) must be on different servers

### Soft Constraints (optimize for)

5. **Affinity**: VMs in the same affinity group (e.g., web tier) should be on the same server
6. **Minimize Servers Used**: Consolidate VMs onto fewer servers to reduce costs
7. **Balance Utilization**: Distribute load evenly across active servers
8. **Prioritize Placement**: Higher-priority VMs should be placed first

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/demo-data` | List available datasets |
| GET | `/demo-data/{id}` | Load demo data |
| POST | `/demo-data/generate` | Generate custom infrastructure |
| POST | `/placements` | Submit for optimization |
| GET | `/placements/{id}` | Get current solution |
| GET | `/placements/{id}/status` | Get solving status |
| DELETE | `/placements/{id}` | Stop solving |
| PUT | `/placements/analyze` | Analyze placement score |

API documentation available at http://localhost:8080/q/swagger-ui

## Advanced Settings

The web UI includes configurable sliders for:

- **Racks**: Number of server racks (1-8)
- **Servers per Rack**: Servers in each rack (2-10)
- **VMs**: Number of VMs to place (5-200)
- **Solver Time**: How long to optimize (5s-2min)

Click "Generate New Data" to create custom scenarios.

## VM Placement Concepts

| Term | Definition |
|------|------------|
| **Server** | Physical machine with CPU, memory, and storage capacity |
| **VM** | Virtual machine requiring resources from a server |
| **Rack** | Physical grouping of servers in a datacenter |
| **Affinity** | VMs that should run on the same server |
| **Anti-Affinity** | VMs that must run on different servers |
| **Consolidation** | Using fewer servers to reduce power/cooling costs |

## Learn More

- [SolverForge Documentation](https://solverforge.org/docs)
