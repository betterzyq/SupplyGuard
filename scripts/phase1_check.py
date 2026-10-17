#!/usr/bin/env python3
"""Offline, bounded verification. No dependency installation or service restart."""

import json
import hashlib
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYTHON = ROOT / ".venv/bin/python"
NODE = ROOT / ".venv/bin/node"
WEB = ROOT / "apps/web"
OUTPUT = ROOT / ".local/acceptance/phase-1"


def frontend_fingerprint():
    paths = (
        sorted((WEB / "src").rglob("*"))
        + sorted((WEB / "public").rglob("*"))
        + [
            WEB / p
            for p in (
                "package.json",
                "package-lock.json",
                "next.config.js",
                "tsconfig.json",
                "tsconfig.acceptance.json",
                "tailwind.config.ts",
                "postcss.config.js",
            )
        ]
    )
    digest = hashlib.sha256()
    for path in paths:
        if path.is_file():
            digest.update(str(path.relative_to(WEB)).encode())
            digest.update(path.read_bytes())
    digest.update(b"acceptance-backend-8100")
    return digest.hexdigest()


def bounded_environment():
    env = os.environ.copy()
    env.update(
        DEBUG="false",
        LANGSMITH_TRACING="false",
        OMP_NUM_THREADS="2",
        OPENBLAS_NUM_THREADS="2",
        MKL_NUM_THREADS="2",
        NEXT_TELEMETRY_DISABLED="1",
        CIRCLE_NODE_TOTAL="2",
        NODE_OPTIONS="--max-old-space-size=1536",
        SUPPLYGUARD_NEXT_DIST_DIR=".next-check",
        SUPPLYGUARD_TSCONFIG="tsconfig.acceptance.json",
    )
    env["PATH"] = str(ROOT / ".venv/bin") + os.pathsep + env.get("PATH", "")
    return env


def constrain_cpu():
    if hasattr(os, "sched_getaffinity"):
        os.sched_setaffinity(0, set(sorted(os.sched_getaffinity(0))[:2]))
    os.nice(10)


def changed_python():
    tracked = subprocess.check_output(
        ["git", "diff", "--name-only", "--diff-filter=ACMR"], cwd=ROOT, text=True
    ).splitlines()
    added = subprocess.check_output(
        ["git", "ls-files", "--others", "--exclude-standard"], cwd=ROOT, text=True
    ).splitlines()
    # Stable targets keep this command useful after the phase is committed.
    stable = [
        "packages/authz",
        "packages/business",
        "tests/phase1",
        "tests/phase2",
        "tests/phase3",
        "packages/graphrag/graph_permissions.py",
        "packages/observability/trace_reader.py",
        "packages/agents/nodes/permission_node.py",
        "packages/mcp_servers/common/registry.py",
        "packages/mcp_servers/excel_report_mcp/tools.py",
        "apps/api/deps.py",
        "apps/api/schemas/auth.py",
        "scripts/check_authz.py",
        "scripts/seed_db.py",
        "scripts/prepare_phase1_demo.py",
        "scripts/acceptance_services.py",
        "scripts/phase1_check.py",
        "scripts/phase1_smoke.py",
        "scripts/phase2_check.py",
        "scripts/phase2_smoke.py",
        "scripts/phase3_check.py",
        "scripts/phase3_smoke.py",
        "scripts/inspect_simulation.py",
    ] + [
        f"apps/api/routers/v1/{name}.py"
        for name in (
            "auth",
            "admin",
            "business",
            "simulation",
            "router",
            "supply_chain",
        )
    ]
    dirty = [p for p in tracked + added if p.endswith(".py") and (ROOT / p).is_file()]
    return sorted({str(ROOT / p) for p in stable + dirty})


def run(test_paths=None):
    os.chdir(ROOT)
    constrain_cpu()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    env = bounded_environment()
    steps = [
        (
            "python-tests",
            [str(PYTHON), "-m", "pytest", *(test_paths or ["tests/phase1"]), "-q"],
            ROOT,
        ),
        (
            "python-lint",
            [str(ROOT / ".venv/bin/ruff"), "check", *changed_python()],
            ROOT,
        ),
        (
            "production-build",
            [str(NODE), "node_modules/next/dist/bin/next", "build"],
            WEB,
        ),
        (
            "typescript",
            [
                str(NODE),
                "node_modules/typescript/bin/tsc",
                "--project",
                "tsconfig.acceptance.json",
                "--noEmit",
            ],
            WEB,
        ),
    ]
    report = {
        "started_at": datetime.now(timezone.utc).isoformat(),
        "steps": [],
        "status": "running",
    }
    next_env = WEB / "next-env.d.ts"
    original_next_env = next_env.read_bytes()
    try:
        for name, command, cwd in steps:
            print(f"CHECK {name}", flush=True)
            result = subprocess.run(
                command,
                cwd=cwd,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            (OUTPUT / f"{name}.log").write_text(result.stdout)
            print(result.stdout[-10000:], flush=True)
            report["steps"].append(
                {"name": name, "exit_code": result.returncode, "log": f"{name}.log"}
            )
            if result.returncode:
                report["status"] = "failed"
                (OUTPUT / "checks.json").write_text(json.dumps(report, indent=2))
                return result.returncode
    finally:
        next_env.write_bytes(original_next_env)

    report["status"] = "passed"
    report["completed_at"] = datetime.now(timezone.utc).isoformat()
    (OUTPUT / "checks.json").write_text(json.dumps(report, indent=2))
    print("PASS: offline checks and isolated production build")
    return 0


def run_browser(script="phase1_browser.mjs"):
    constrain_cpu()
    env = bounded_environment()
    qa = ROOT / ".local/browser-qa"
    if not (qa / "node_modules/playwright").exists():
        print("Browser QA tooling not installed; see docs/manual-acceptance.md")
        return 1
    env.update(
        PLAYWRIGHT_BROWSERS_PATH=str(ROOT / ".local/qa-browsers"),
        FONTCONFIG_FILE=str(qa / "fontconfig.xml"),
        TMPDIR=str(qa / "tmp"),
    )
    env["LD_LIBRARY_PATH"] = (
        str(qa / "runtime/usr/lib/x86_64-linux-gnu")
        + os.pathsep
        + env.get("LD_LIBRARY_PATH", "")
    )
    return subprocess.call(
        [str(NODE), str(ROOT / "scripts" / script)], cwd=ROOT, env=env
    )


if __name__ == "__main__":
    raise SystemExit(run_browser() if "--browser" in sys.argv else run())
