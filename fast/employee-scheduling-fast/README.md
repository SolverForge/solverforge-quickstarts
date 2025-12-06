---
title: Employee Scheduling (Python)
emoji: 👀
colorFrom: gray
colorTo: green
sdk: docker
app_port: 8080
pinned: false
license: apache-2.0
short_description: SolverForge Quickstart for the Employee Scheduling problem
---

# Employee Scheduling (Python)

Schedule shifts to employees, accounting for employee availability and shift skill requirements.

- [Prerequisites](#prerequisites)
- [Run the application](#run-the-application)
- [Test the application](#test-the-application)

## Prerequisites

1. Install [Python 3.11 or 3.12](https://www.python.org/downloads/).

2. Install JDK 17+, for example with [Sdkman](https://sdkman.io):

   ```sh
   $ sdk install java
   ```

## Run the application

1. Git clone the solverforge-solver-python repo and navigate to this directory:

   ```sh
   $ git clone https://github.com/SolverForge/solverforge-quickstarts.git
   ...
   $ cd solverforge-quickstarts/employee-scheduling-fast
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

## Test the application

1. Run tests:

   ```sh
   $ pytest
   ```

## More information

Visit [solverforge.org](https://www.solverforge.org).
