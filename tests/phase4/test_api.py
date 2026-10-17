import pytest
from apps.api.routers.v1.prediction import router
from packages.prediction import runtime


def setup(client_factory, role="enterprise"):
    client, headers, session = client_factory(role)
    client.app.include_router(router, prefix="/api/v1")
    return client, headers, session


@pytest.mark.parametrize("role", ["admin", "enterprise", "logistics_manager"])
def test_auth_public_report_tenant_and_private_artifact_block(
    client_factory, monkeypatch, role
):
    client, headers, session = setup(client_factory, role)
    monkeypatch.setattr(
        runtime, "report", lambda: {"domain": "dataco-retail-historical"}
    )
    assert client.get("/api/v1/prediction/report").status_code == 401
    response = client.get("/api/v1/prediction/report", headers=headers)
    assert response.status_code == 200
    assert response.json()["tenant_id"] == str(session.user.tenant_id)
    for name in ["model.joblib", "cases.json", "test-predictions.csv"]:
        assert (
            client.get(
                "/api/v1/prediction/artifacts/" + name, headers=headers
            ).status_code
            == 404
        )
    contracts = client.get("/api/v1/prediction/evaluation-contracts", headers=headers)
    assert contracts.status_code == (200 if role == "admin" else 403)


def test_missing_report_and_unsupported_manufacturing(client_factory, monkeypatch):
    client, headers, _ = setup(client_factory)

    def missing():
        raise FileNotFoundError()

    monkeypatch.setattr(runtime, "report", missing)
    assert client.get("/api/v1/prediction/report", headers=headers).status_code == 503
    response = client.post(
        "/api/v1/prediction/predict",
        headers=headers,
        json={"domain": "manufacturing", "case_id": "SG-2026-0001"},
    )
    assert response.status_code == 422
    assert (
        client.post(
            "/api/v1/prediction/predict",
            headers=headers,
            json={"case_id": "abc", "model_path": "/tmp/x"},
        ).status_code
        == 422
    )


def test_retired_user_cannot_read_public_report(client_factory):
    client, headers, _ = setup(client_factory, "external_supplier")
    assert client.get("/api/v1/prediction/report", headers=headers).status_code == 403
