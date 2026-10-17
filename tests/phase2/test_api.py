import pytest


def test_network_and_tracking_require_authentication(client_factory):
    client, _, _ = client_factory("enterprise")
    for path in [
        "/business/network",
        "/business/shipments",
        "/business/shipments/SHP-001",
    ]:
        assert client.get("/api/v1" + path).status_code == 401


@pytest.mark.parametrize("role", ["admin", "enterprise", "logistics_manager"])
def test_real_auth_context_and_tenant_for_all_map_endpoints(client_factory, role):
    client, headers, session = client_factory(role)
    for path in [
        "/business/network",
        "/business/shipments",
        "/business/shipments/SHP-001",
    ]:
        response = client.get("/api/v1" + path, headers=headers)
        assert response.status_code == 200
        assert response.json()["tenant_id"] == str(session.user.tenant_id)
        assert response.json()["source_type"] == "synthetic"
    detail = client.get(
        "/api/v1/business/shipments/SHP-001",
        headers=headers,
        params={"at_time": "2026-10-16T04:30:00+08:00"},
    ).json()
    assert detail["shipment"]["order_ids"] == [o["id"] for o in detail["orders"]]
    assert detail["shipment"]["delay_hours"] == 0
    for node in detail["shipment"]["trace"]:
        assert node["at"] <= "2026-10-16T04:30:00+08:00"


@pytest.mark.parametrize(
    "query",
    [
        {"at_time": "2026-10-16T10:00:00+08:00"},
        {"at_time": "2026-10-16T03:00:00"},
        {"mode": "spacecraft"},
        {"q": "x" * 101},
    ],
)
def test_invalid_parameters_return_422(client_factory, query):
    client, headers, _ = client_factory("enterprise")
    assert (
        client.get(
            "/api/v1/business/network", headers=headers, params=query
        ).status_code
        == 422
    )


def test_unknown_resource_and_retired_token_cannot_read_maps(client_factory):
    client, headers, _ = client_factory("enterprise")
    assert (
        client.get("/api/v1/business/shipments/absent", headers=headers).status_code
        == 404
    )
    assert (
        client.get(
            "/api/v1/business/network?scenario_id=absent", headers=headers
        ).status_code
        == 404
    )
    assert (
        client.get(
            "/api/v1/business/network?supplier_id=absent", headers=headers
        ).status_code
        == 404
    )
    client, headers, _ = client_factory("external_supplier")
    assert client.get("/api/v1/business/network", headers=headers).status_code == 403
