"""Private per-tenant/per-user simulation snapshots, independent of business DB."""

import json
import os
import re
import tempfile
from pathlib import Path
from uuid import UUID

from packages.authz.rbac import UserContext

STORE_ROOT = Path(__file__).resolve().parents[2] / ".local/simulation-runs"


def owner_directory(user: UserContext):
    if not user.is_member:
        raise PermissionError("enterprise membership required")
    return STORE_ROOT / str(UUID(str(user.tenant_id))) / str(UUID(str(user.user_id)))


def save_snapshot(user: UserContext, artifact: dict):
    directory = owner_directory(user)
    if artifact["tenant_id"] != str(user.tenant_id):
        raise PermissionError("snapshot tenant mismatch")
    identifier = artifact.get("run_id") or artifact.get("comparison_id")
    if not re.fullmatch(r"[a-f0-9]{64}", identifier or ""):
        raise ValueError("invalid snapshot id")
    directory.mkdir(parents=True, mode=0o700, exist_ok=True)
    filename = directory / (identifier + ".json")
    if filename.exists():
        return
    fd, temporary = tempfile.mkstemp(prefix=".pending-", dir=directory)
    try:
        with os.fdopen(fd, "w") as target:
            json.dump(
                artifact,
                target,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
        os.replace(temporary, filename)
    finally:
        Path(temporary).unlink(missing_ok=True)


def read_snapshot(user: UserContext, identifier: str):
    directory = owner_directory(user)
    if not re.fullmatch(r"[a-f0-9]{64}", identifier):
        raise KeyError("Snapshot not found")
    filename = directory / (identifier + ".json")
    if not filename.is_file():
        raise KeyError("Snapshot not found")
    result = json.loads(filename.read_text())
    if result.get("tenant_id") != str(user.tenant_id):
        raise PermissionError("snapshot tenant mismatch")
    return result
