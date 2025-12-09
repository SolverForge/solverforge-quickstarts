"""
Integration tests for the employee scheduling solver.

Tests that the solver can find feasible solutions for demo data
and that the REST API works correctly.
"""
from employee_scheduling.rest_api import app
from employee_scheduling.domain import EmployeeScheduleModel
from employee_scheduling.converters import model_to_schedule

from fastapi.testclient import TestClient
from time import sleep
from pytest import fail
import pytest

client = TestClient(app)


@pytest.mark.timeout(120)
def test_feasible():
    """Test that the solver can find a feasible solution for SMALL demo data."""
    demo_data_response = client.get("/demo-data/SMALL")
    assert demo_data_response.status_code == 200

    job_id_response = client.post("/schedules", json=demo_data_response.json())
    assert job_id_response.status_code == 200
    job_id = job_id_response.text[1:-1]

    ATTEMPTS = 1_000
    best_score = None
    for _ in range(ATTEMPTS):
        sleep(0.1)
        schedule_response = client.get(f"/schedules/{job_id}")
        schedule_json = schedule_response.json()
        schedule_model = EmployeeScheduleModel.model_validate(schedule_json)
        schedule = model_to_schedule(schedule_model)
        if schedule.score is not None:
            best_score = schedule.score
            if schedule.score.is_feasible:
                stop_solving_response = client.delete(f"/schedules/{job_id}")
                assert stop_solving_response.status_code == 200
                return

    client.delete(f"/schedules/{job_id}")
    fail(f"Solution is not feasible after 100 seconds. Best score: {best_score}")


def test_demo_data_list():
    """Test that demo data list endpoint returns available datasets."""
    response = client.get("/demo-data")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0
    assert "SMALL" in data


def test_demo_data_small_structure():
    """Test that SMALL demo data has expected structure."""
    response = client.get("/demo-data/SMALL")
    assert response.status_code == 200
    data = response.json()

    # Check required fields
    assert "employees" in data
    assert "shifts" in data

    # Validate employees
    assert len(data["employees"]) > 0
    for employee in data["employees"]:
        assert "name" in employee

    # Validate shifts
    assert len(data["shifts"]) > 0
    for shift in data["shifts"]:
        assert "id" in shift
        assert "start" in shift
        assert "end" in shift
        assert "location" in shift
        assert "requiredSkill" in shift


def test_solver_start_and_stop():
    """Test that solver can be started and stopped."""
    demo_data_response = client.get("/demo-data/SMALL")
    assert demo_data_response.status_code == 200

    # Start solving
    start_response = client.post("/schedules", json=demo_data_response.json())
    assert start_response.status_code == 200
    job_id = start_response.text[1:-1]

    # Wait a bit
    sleep(0.5)

    # Check status
    status_response = client.get(f"/schedules/{job_id}")
    assert status_response.status_code == 200
    schedule = status_response.json()
    assert "solverStatus" in schedule

    # Stop solving
    stop_response = client.delete(f"/schedules/{job_id}")
    assert stop_response.status_code == 200


def test_solver_assigns_employees():
    """Test that solver actually assigns employees to shifts."""
    demo_data_response = client.get("/demo-data/SMALL")
    assert demo_data_response.status_code == 200

    job_id_response = client.post("/schedules", json=demo_data_response.json())
    assert job_id_response.status_code == 200
    job_id = job_id_response.text[1:-1]

    # Wait for some solving
    sleep(2)

    schedule_response = client.get(f"/schedules/{job_id}")
    schedule_json = schedule_response.json()

    # Check that some shifts have employees assigned
    assigned_shifts = [s for s in schedule_json["shifts"] if s.get("employee") is not None]
    assert len(assigned_shifts) > 0, "Solver should assign some employees to shifts"

    client.delete(f"/schedules/{job_id}")
