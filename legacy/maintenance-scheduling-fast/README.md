---
title: Maintenance Scheduling (Python)
emoji: 🔧
colorFrom: gray
colorTo: green
sdk: docker
app_port: 8080
pinned: false
license: apache-2.0
short_description: SolverForge Quickstart for the Maintenance Scheduling problem
---

# Maintenance Scheduling (Python)

Assign maintenance jobs to crews and schedule them over time, avoiding conflicts and meeting deadlines.

- [Prerequisites](#prerequisites)
- [Run the application](#run-the-application)
- [Test the application](#test-the-application)

## Prerequisites

1. Install [Python 3.10, 3.11 or 3.12](https://www.python.org/downloads/).

2. Install JDK 17+, for example with [Sdkman](https://sdkman.io):
    ```sh
    $ sdk install java
    ```

## Run the application

1. Git clone the solverforge-quickstarts repo and navigate to this directory:
   ```sh
   $ git clone https://github.com/SolverForge/solverforge-quickstarts.git
   ...
   $ cd solverforge-quickstarts/fast/maintenance-scheduling-fast
   ```

2. Create a virtual environment:
   ```sh
   $ python -m venv .venv
   ```

3. Activate the virtual environment:
   ```sh
   $ . .venv/bin/activate
   ```

4. Install the application:
   ```sh
   $ pip install -e .
   ```

5. Run the application:
   ```sh
   $ run-app
   ```

6. Visit [http://localhost:8080](http://localhost:8080) in your browser.

7. Click on the **Solve** button.

## Problem Description

The maintenance scheduling problem assigns maintenance jobs to crews over a planning period while respecting constraints:

### Hard Constraints
- **Crew conflict**: A crew can only work on one job at a time
- **Min start date**: Jobs cannot start before their ready date
- **Max end date**: Jobs must complete before their deadline

### Soft Constraints
- **Before ideal end date**: Slight penalty for finishing too early (maintenance cycles restart sooner)
- **After ideal end date**: Heavy penalty for finishing late (risk of missing deadline)
- **Tag conflict**: Avoid scheduling jobs with the same tag (e.g., same area) at overlapping times

## Test the application

1. Run tests:
   ```sh
   $ pytest
   ```

## More information

Visit [solverforge.org](https://www.solverforge.org).
