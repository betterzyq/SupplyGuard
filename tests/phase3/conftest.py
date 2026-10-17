import os

os.environ["DEBUG"] = "false"
import pytest  # noqa: E402
from apps.api.routers.v1.simulation import router  # noqa: E402
from tests.phase1.test_api import client_factory  # noqa: E402,F401


@pytest.fixture
def simulation_client(client_factory, monkeypatch, tmp_path):  # noqa: F811
    monkeypatch.setattr(
        "packages.business.simulation_store.STORE_ROOT", tmp_path / "runs"
    )

    def make(role="enterprise"):
        client, headers, session = client_factory(role)
        client.app.include_router(router, prefix="/api/v1")
        return client, headers, session

    return make
