import json
import os
from pathlib import Path
from types import SimpleNamespace
import uuid

os.environ["DEBUG"] = "false"
os.environ["OMP_NUM_THREADS"] = "2"
os.environ["OPENBLAS_NUM_THREADS"] = "2"
import pytest  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker  # noqa: E402
from sqlalchemy.pool import NullPool  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from packages.common.config import get_settings  # noqa: E402
from packages.common.db.models.tenant import Tenant  # noqa: E402
from packages.common.db.models.user import User  # noqa: E402
from packages.common.db.models.role import Role, UserRole  # noqa: E402
from packages.common.security.jwt import create_access_token  # noqa: E402
from packages.common.db.session import get_db_session  # noqa: E402
from apps.api.main import create_app  # noqa: E402


@pytest.fixture(scope="session")
def database_url():
    root = Path(__file__).resolve().parents[2]
    record = json.loads((root / ".local/acceptance/phase-5/test-db.json").read_text())
    assert record["owner"] == "phase5_db.py" and record["name"].startswith(
        "supplyguard_p5_test_"
    )
    return make_url(get_settings().POSTGRES_URL).set(database=record["name"])


@pytest.fixture
def enterprise_clients(database_url):
    sync = create_engine(
        database_url.set(drivername="postgresql+psycopg2"), poolclass=NullPool
    )
    tenant_a, tenant_b = uuid.uuid4(), uuid.uuid4()
    identities = {}
    with sync.begin() as c:
        for tenant in [tenant_a, tenant_b]:
            c.execute(
                Tenant.__table__.insert().values(
                    id=tenant, name="P5 isolated QA", code="qa-" + tenant.hex, config={}
                )
            )
            for name in ["admin", "enterprise", "external_supplier"]:
                role = uuid.uuid4()
                uid = uuid.uuid4()
                c.execute(
                    Role.__table__.insert().values(
                        id=role,
                        tenant_id=tenant,
                        name=name,
                        description="P5 isolated role",
                    )
                )
                c.execute(
                    User.__table__.insert().values(
                        id=uid,
                        tenant_id=tenant,
                        email=f"{name}-{uid.hex}@example.invalid",
                        password_hash="not-login-enabled",
                        full_name=name,
                        department="test",
                        is_active=True,
                    )
                )
                c.execute(UserRole.__table__.insert().values(user_id=uid, role_id=role))
                identities[("a" if tenant == tenant_a else "b") + "_" + name] = uid
    engine = create_async_engine(database_url, poolclass=NullPool, echo=False)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    app = create_app()

    async def override():
        async with factory() as s:
            yield s

    app.dependency_overrides[get_db_session] = override
    client = TestClient(app)
    headers = {
        k: {"Authorization": "Bearer " + create_access_token(str(uid))}
        for k, uid in identities.items()
    }
    yield SimpleNamespace(
        client=client,
        headers=headers,
        users=identities,
        tenant_a=tenant_a,
        tenant_b=tenant_b,
        engine=sync,
    )
    client.close()
    sync.dispose()
