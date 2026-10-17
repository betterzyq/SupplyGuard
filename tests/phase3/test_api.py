import pytest


def request():
    return {
        "preset_id": "hand-check",
        "event_overrides": [
            {"event_id": i, "duration_days": 7}
            for i in ["EVT-PORT", "EVT-PORT-SECONDARY"]
        ],
    }


def test_authentication_and_retired_account(simulation_client):
    client, headers, _ = simulation_client("external_supplier")
    assert client.post("/api/v1/simulation/run", json=request()).status_code == 401
    assert (
        client.post(
            "/api/v1/simulation/run", headers=headers, json=request()
        ).status_code
        == 403
    )


@pytest.mark.parametrize("role", ["enterprise", "admin", "logistics_manager"])
def test_run_persist_read_and_compare(simulation_client, role):
    client, headers, session = simulation_client(role)
    template = client.get(
        "/api/v1/simulation/templates?preset_id=hand-check", headers=headers
    )
    assert template.status_code == 200
    response = client.post("/api/v1/simulation/run", headers=headers, json=request())
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["tenant_id"] == str(session.user.tenant_id)
    assert result["result"]["materials"][0]["peak_shortage_units"] == "40"
    assert (
        client.get(
            "/api/v1/simulation/runs/" + result["run_id"], headers=headers
        ).json()
        == result
    )
    assert (
        client.post("/api/v1/simulation/run", headers=headers, json=request()).json()
        == result
    )
    comparison = client.post(
        "/api/v1/simulation/comparison",
        headers=headers,
        json={
            "simulation": request(),
            "plans": [
                {
                    "id": "a",
                    "name": "库存调拨",
                    "measures": [
                        {
                            "option_id": "transfer-MAT-01",
                            "quantity": 80,
                            "duration_days": 1,
                        }
                    ],
                }
            ],
        },
    )
    assert comparison.status_code == 200, comparison.text
    data = comparison.json()
    assert data["plans"][0]["delta"]["delayed_order_amount_reduced_cny"] == "1280000.00"
    assert data["plans"][0]["delta"]["incremental_cost_cny"] == "1140.00"
    assert (
        client.get(
            "/api/v1/simulation/runs/" + data["comparison_id"], headers=headers
        ).json()
        == data
    )


def test_cross_tenant_and_cross_user_snapshots_are_private(simulation_client):
    client, headers, session = simulation_client()
    result = client.post(
        "/api/v1/simulation/run", headers=headers, json=request()
    ).json()
    another, other_headers, other_session = simulation_client("admin")
    url = "/api/v1/simulation/runs/" + result["run_id"]
    assert another.get(url, headers=other_headers).status_code == 404
    other_session.user.tenant_id = session.user.tenant_id
    assert another.get(url, headers=other_headers).status_code == 404


@pytest.mark.parametrize(
    "body",
    [
        {"horizon_days": 31},
        {"horizon_days": 0},
        {"demand_percent": -1},
        {"measures": [{"option_id": "alternative-MAT-01-uncertified", "quantity": 10}]},
        {"measures": [{"option_id": "alternative-MAT-01", "quantity": 61}]},
        {"measures": [{"option_id": "transfer-MAT-01", "quantity": -1}]},
        {"events": []},
        {"event_ids": ["EVT-FLOOD"]},
        {"at_time": "2026-10-16T09:00:00"},
    ],
)
def test_invalid_requests_422(simulation_client, body):
    client, headers, _ = simulation_client()
    response = client.post("/api/v1/simulation/run", headers=headers, json=body)
    assert response.status_code == 422, response.text


def test_unknown_scenario_and_missing_snapshot(simulation_client):
    client, headers, _ = simulation_client()
    assert (
        client.get(
            "/api/v1/simulation/templates?scenario_id=missing", headers=headers
        ).status_code
        == 404
    )
    assert (
        client.get("/api/v1/simulation/runs/" + "0" * 64, headers=headers).status_code
        == 404
    )
    assert (
        client.get("/api/v1/simulation/runs/not-a-hash", headers=headers).status_code
        == 422
    )
