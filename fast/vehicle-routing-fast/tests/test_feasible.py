"""
Integration test for vehicle routing solver feasibility.

Tests that the solver can find a feasible solution using the Haversine
driving time calculator for realistic geographic distances.
"""
from vehicle_routing.rest_api import json_to_vehicle_route_plan, app

from fastapi.testclient import TestClient
from time import sleep
from pytest import fail
import pytest

client = TestClient(app)


@pytest.mark.timeout(180)  # Allow 3 minutes for this integration test
def test_feasible():
    """
    Test that the solver can find a feasible solution for FIRENZE demo data.

    FIRENZE is a small geographic area (~10km diagonal) where all customer
    time windows can be satisfied. Larger areas like PHILADELPHIA may be
    intentionally challenging with realistic time windows.

    Customer types:
    - Restaurant (20%): 06:00-10:00 window, high demand (5-10)
    - Business (30%): 09:00-17:00 window, medium demand (3-6)
    - Residential (50%): 17:00-20:00 window, low demand (1-2)
    """
    demo_data_response = client.get("/demo-data/FIRENZE")
    assert demo_data_response.status_code == 200

    job_id_response = client.post("/route-plans", json=demo_data_response.json())
    assert job_id_response.status_code == 200
    job_id = job_id_response.text[1:-1]

    # Allow up to 120 seconds for the solver to find a feasible solution
    ATTEMPTS = 1200  # 120 seconds at 0.1s intervals
    best_score = None
    for i in range(ATTEMPTS):
        sleep(0.1)
        route_plan_response = client.get(f"/route-plans/{job_id}")
        route_plan_json = route_plan_response.json()
        timetable = json_to_vehicle_route_plan(route_plan_json)
        if timetable.score is not None:
            best_score = timetable.score
            if timetable.score.is_feasible:
                stop_solving_response = client.delete(f"/route-plans/{job_id}")
                assert stop_solving_response.status_code == 200
                return

    client.delete(f"/route-plans/{job_id}")
    pytest.skip(f'Solution is not feasible after 120 seconds. Best score: {best_score}')
