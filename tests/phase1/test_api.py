from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.api.deps import get_db_session
from apps.api.routers.v1.admin import router as admin_router
from apps.api.routers.v1.auth import router as auth_router
from apps.api.routers.v1.business import router as business_router
from apps.api.routers.v1.users import router as users_router
from packages.common.security.jwt import create_access_token


class FakeSession:
    def __init__(self, role):
        self.user = SimpleNamespace(
            id=uuid4(),
            tenant_id=uuid4(),
            email="test@example.com",
            full_name="Test User",
            department="logistics",
            supplier_id=None,
            is_active=True,
            user_roles=[SimpleNamespace(role=SimpleNamespace(name=role))],
        )
        self.statements = []

    async def execute(self, statement):
        self.statements.append(statement)
        if "FROM users" in str(statement):
            return SimpleNamespace(scalar_one_or_none=lambda: self.user)
        return SimpleNamespace(
            scalars=lambda: SimpleNamespace(all=lambda: []), scalar_one=lambda: 0
        )

    async def commit(self):
        pass


@pytest.fixture
def client_factory(monkeypatch):
    monkeypatch.setattr("apps.api.deps.write_audit_log", AsyncMock())

    def make(role):
        app = FastAPI()
        for router in (auth_router, users_router, business_router, admin_router):
            app.include_router(router, prefix="/api/v1")
        session = FakeSession(role)

        async def session_override():
            yield session

        app.dependency_overrides[get_db_session] = session_override
        # Forged old claims must not override the persisted role.
        token = create_access_token(str(session.user.id), {"roles": ["admin"]})
        return TestClient(app), {"Authorization": f"Bearer {token}"}, session

    return make


def test_unauthenticated_denied(client_factory):
    client, _, _ = client_factory("enterprise")
    assert client.get("/api/v1/business/overview").status_code == 401
    assert (
        client.get(
            "/api/v1/business/overview", headers={"Authorization": "Bearer broken"}
        ).status_code
        == 401
    )


@pytest.mark.parametrize(
    "role", ["enterprise", "procurement_staff", "logistics_manager"]
)
def test_real_dependency_normalizes_and_protects_admin(client_factory, role):
    client, headers, session = client_factory(role)
    assert client.get("/api/v1/auth/me", headers=headers).json()["roles"] == [
        "enterprise"
    ]
    permissions = client.get("/api/v1/users/me/permissions", headers=headers).json()
    assert permissions["can_upload_document"] and not permissions["can_run_benchmark"]
    assert permissions["policy_version"] == "enterprise-v2"
    for scenario in ("port-congestion", "tier2-shutdown", "regional-flood"):
        response = client.get(
            "/api/v1/business/overview",
            headers=headers,
            params={"scenario_id": scenario},
        )
        assert response.status_code == 200
        assert response.json()["tenant_id"] == str(session.user.tenant_id)
        assert response.json()["scenario"]["id"] == scenario
    assert (
        client.get(
            "/api/v1/business/overview?scenario_id=missing", headers=headers
        ).status_code
        == 404
    )
    assert (
        len(client.get("/api/v1/business/scenarios", headers=headers).json()["items"])
        == 3
    )
    assert client.get("/api/v1/admin/audit-logs", headers=headers).status_code == 403


@pytest.mark.parametrize("role", ["external_supplier", "unassigned"])
def test_retired_role_cannot_use_existing_token(client_factory, role):
    client, headers, _ = client_factory(role)
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 403
    assert client.get("/api/v1/business/overview", headers=headers).status_code == 403


def test_admin_audit_queries_are_both_tenant_scoped(client_factory):
    client, headers, session = client_factory("admin")
    response = client.get("/api/v1/admin/audit-logs", headers=headers)
    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0}
    for statement in session.statements[-2:]:
        assert "audit_logs.tenant_id =" in str(statement)
        assert session.user.tenant_id in statement.compile().params.values()


@pytest.mark.parametrize("role", ["admin", "enterprise"])
def test_trace_reader_filters_every_table_by_tenant(role):
    import asyncio
    from fastapi import HTTPException
    from packages.observability.trace_reader import load_trace
    from tests.phase1.test_policy import context

    class EmptySession:
        def __init__(self):
            self.statements = []

        async def execute(self, statement):
            self.statements.append(statement)
            return SimpleNamespace(
                scalar_one_or_none=lambda: None,
                scalars=lambda: SimpleNamespace(all=lambda: []),
            )

    session = EmptySession()
    user = context(role)
    with pytest.raises(HTTPException) as error:
        asyncio.run(load_trace(session, "another-tenant-trace", user))
    assert error.value.status_code == 404
    assert len(session.statements) == 10
    for statement in session.statements:
        assert user.tenant_id in statement.compile().params.values()
        assert "tenant_id =" in str(statement)
