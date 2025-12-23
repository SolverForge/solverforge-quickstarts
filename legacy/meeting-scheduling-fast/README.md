---
title: Meeting Scheduling (Python)
emoji: 👀
colorFrom: gray
colorTo: green
sdk: docker
app_port: 8080
pinned: false
license: apache-2.0
short_description: SolverForge Quickstart for the Meeting Scheduling problem
---

# Meeting Scheduling (Python)

Schedule meetings between employees, where each meeting has a topic, duration, required and preferred attendees.

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

1. Git clone the solverforge-quickstarts repo and navigate to this directory:

   ```sh
   $ git clone https://github.com/SolverForge/solverforge-quickstarts.git
   ...
   $ cd solverforge-quickstarts/fast/meeting-scheduling-fast
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

## Problem Description

Schedule meetings between employees, where:

* Each meeting has a topic, duration, required and preferred attendees.
* Each meeting needs a room with sufficient capacity.
* Meetings should not overlap with other meetings if they share resources (room or attendees).
* Meetings should be scheduled as soon as possible.
* Preferred attendees should be able to attend if possible.

## More information

Visit [solverforge.org](https://www.solverforge.org).
