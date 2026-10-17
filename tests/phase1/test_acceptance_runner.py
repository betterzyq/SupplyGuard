import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location(
    "acceptance_services", SCRIPTS / "acceptance_services.py"
)
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


def test_occupied_port_is_never_reclaimed(monkeypatch, tmp_path):
    monkeypatch.setattr(runner, "STATE", tmp_path)
    monkeypatch.setattr(runner, "port_busy", lambda _: True)
    monkeypatch.setattr(runner, "load_record", lambda _: None)
    monkeypatch.setattr(
        runner.subprocess,
        "run",
        lambda *a, **k: pytest.fail("must not build or modify database"),
    )
    monkeypatch.setattr(
        runner.os, "killpg", lambda *a: pytest.fail("must not stop another process")
    )
    with pytest.raises(RuntimeError, match="occupied by an unowned"):
        runner.up()


def test_stop_refuses_unverified_identity(monkeypatch):
    monkeypatch.setattr(
        runner, "load_record", lambda _: {"pid": 1, "root": "unrelated"}
    )
    monkeypatch.setattr(
        runner.os,
        "killpg",
        lambda *a: pytest.fail("unverified process must never receive a signal"),
    )
    runner.stop("api")


def test_pid_reuse_cannot_match_identity():
    assert not runner.owns_process(
        "api", {"root": str(runner.ROOT), "name": "api", "pid": 1, "birth": "wrong"}
    )


def test_frontend_fingerprint_stable_and_source_sensitive(monkeypatch, tmp_path):
    import phase1_check

    (tmp_path / "src").mkdir()
    source = tmp_path / "src/page.tsx"
    source.write_text("one")
    monkeypatch.setattr(phase1_check, "WEB", tmp_path)
    first = phase1_check.frontend_fingerprint()
    assert first == phase1_check.frontend_fingerprint()
    source.write_text("two")
    assert first != phase1_check.frontend_fingerprint()
