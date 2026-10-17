from types import SimpleNamespace

import pytest

from scripts import prepare_phase1_demo


@pytest.mark.parametrize(
    "url,environment",
    [
        (
            "postgresql+asyncpg://supplyguard:unused@remote.example/supplyguard",
            "development",
        ),
        ("postgresql+asyncpg://other:unused@localhost/supplyguard", "development"),
        (
            "postgresql+asyncpg://supplyguard:unused@localhost/other_database",
            "development",
        ),
        ("postgresql+asyncpg://supplyguard:unused@localhost/supplyguard", "production"),
    ],
)
def test_demo_preparation_refuses_wrong_database_or_production(
    monkeypatch, url, environment
):
    monkeypatch.setattr(
        prepare_phase1_demo,
        "get_settings",
        lambda: SimpleNamespace(POSTGRES_URL=url, APP_ENV=environment),
    )
    with pytest.raises(RuntimeError):
        prepare_phase1_demo.validate_demo_database()
