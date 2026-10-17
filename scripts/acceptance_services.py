#!/usr/bin/env python3
"""Own-process-only acceptance runner. Never stop port owners or other services."""

import argparse
import fcntl
import json
import os
import resource
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from phase1_check import (  # noqa: E402
    NODE,
    PYTHON,
    WEB,
    bounded_environment,
    frontend_fingerprint,
)

STATE = ROOT / ".local/acceptance/services"
SPECS = {
    "api": {"port": 8100, "marker": "apps.api.main:app"},
    "web": {"port": 3100, "marker": "node_modules/next/dist/bin/next"},
}


def pid_birth(pid):
    # /proc comm can contain spaces; fields after ')' begin with state (field 3).
    return Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[19]


def load_record(name):
    path = STATE / f"{name}.json"
    return json.loads(path.read_text()) if path.exists() else None


def owns_process(name, record):
    if not record or record.get("root") != str(ROOT) or record.get("name") != name:
        return False
    try:
        pid = int(record["pid"])
        if pid <= 1 or pid_birth(pid) != record["birth"]:
            return False
        command = (
            Path(f"/proc/{pid}/cmdline").read_bytes().replace(b"\0", b" ").decode()
        )
        cwd = Path(f"/proc/{pid}/cwd").resolve()
        # next changes the title of its main process after startup.
        expected = SPECS[name]["marker"] in command or (
            name == "web" and command.startswith("next-server ")
        )
        return (
            expected
            and cwd == (ROOT if name == "api" else WEB)
            and os.getpgid(pid) == pid
            and record.get("boot_id")
            == Path("/proc/sys/kernel/random/boot_id").read_text().strip()
        )
    except (
        FileNotFoundError,
        ProcessLookupError,
        PermissionError,
        KeyError,
        ValueError,
    ):
        return False


def port_busy(port):
    with socket.socket() as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("127.0.0.1", port))
            return False
        except OSError:
            return True


def bounded_child(api):
    os.sched_setaffinity(0, set(sorted(os.sched_getaffinity(0))[:2]))
    os.nice(10)
    if api:
        resource.setrlimit(resource.RLIMIT_AS, (3 * 1024**3, 3 * 1024**3))


def launch(name, env):
    spec = SPECS[name]
    if name == "api":
        command = [
            str(PYTHON),
            "-m",
            "uvicorn",
            "apps.api.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(spec["port"]),
        ]
        cwd = ROOT
    else:
        command = [
            str(NODE),
            "node_modules/next/dist/bin/next",
            "start",
            "--hostname",
            "127.0.0.1",
            "--port",
            str(spec["port"]),
        ]
        cwd = WEB
    with (STATE / f"{name}.log").open("ab") as logfile:
        proc = subprocess.Popen(
            command,
            cwd=cwd,
            env=env,
            stdout=logfile,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            preexec_fn=lambda: bounded_child(name == "api"),
        )
    record = {
        "root": str(ROOT),
        "name": name,
        "pid": proc.pid,
        "birth": pid_birth(proc.pid),
        "boot_id": Path("/proc/sys/kernel/random/boot_id").read_text().strip(),
    }
    (STATE / f"{name}.json").write_text(json.dumps(record))
    for _ in range(100):
        if proc.poll() is not None:
            raise RuntimeError(f"{name} exited; see {STATE / (name + '.log')}")
        if port_busy(spec["port"]):
            print(f"STARTED {name}: 127.0.0.1:{spec['port']} pid={proc.pid}")
            return
        time.sleep(0.2)
    raise RuntimeError(f"{name} startup timed out; see project acceptance log")


def stop(name):
    record = load_record(name)
    if not owns_process(name, record):
        print(f"SKIP {name}: no verified owned process")
        return
    pid = int(record["pid"])
    os.killpg(pid, signal.SIGTERM)
    for _ in range(50):
        if not owns_process(name, record):
            break
        try:
            if (
                Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[0]
                == "Z"
            ):
                break
        except FileNotFoundError:
            break
        time.sleep(0.1)
    else:
        # Identity must still match before escalation, never kill a reused PID.
        if owns_process(name, record):
            os.killpg(pid, signal.SIGKILL)
    (STATE / f"{name}.json").unlink(missing_ok=True)
    print(f"STOPPED {name}: verified project process group {pid}")


def up():
    STATE.mkdir(parents=True, exist_ok=True)
    for name, spec in SPECS.items():
        if port_busy(spec["port"]) and not owns_process(name, load_record(name)):
            raise RuntimeError(
                f"Port {spec['port']} occupied by an unowned process; refusing to change it"
            )
    env = bounded_environment()
    env.update(
        SUPPLYGUARD_NEXT_DIST_DIR=".next-acceptance",
        BACKEND_URL="http://127.0.0.1:8100",
    )
    stamp = STATE / "frontend-fingerprint.txt"
    fingerprint = frontend_fingerprint()
    if (
        not (WEB / ".next-acceptance/BUILD_ID").exists()
        or not stamp.exists()
        or stamp.read_text() != fingerprint
    ):
        if owns_process("web", load_record("web")):
            raise RuntimeError(
                "Frontend sources changed; run acceptance-down before rebuilding"
            )
        print(
            "Building isolated acceptance frontend (two CPU cores, node heap 1536 MB)",
            flush=True,
        )
        next_env = WEB / "next-env.d.ts"
        original_next_env = next_env.read_bytes()
        try:
            result = subprocess.run(
                [str(NODE), "node_modules/next/dist/bin/next", "build"],
                cwd=WEB,
                env=env,
                preexec_fn=lambda: bounded_child(False),
            )
        finally:
            next_env.write_bytes(original_next_env)
        if result.returncode:
            raise RuntimeError("Acceptance frontend build failed")
        stamp.write_text(fingerprint)
    result = subprocess.run(
        [str(PYTHON), "scripts/prepare_phase1_demo.py"],
        cwd=ROOT,
        env=env,
        preexec_fn=lambda: bounded_child(True),
    )
    if result.returncode:
        raise RuntimeError(
            "Demo account preparation failed; existing services were not changed"
        )
    started = []
    try:
        for name in SPECS:
            if owns_process(name, load_record(name)):
                print(f"ALREADY RUNNING {name}")
            else:
                started.append(name)
                launch(name, env)
    except Exception:
        for name in reversed(started):
            stop(name)
        raise


def print_browser_access():
    print("\n访问提示：验收网页只监听当前服务器的 127.0.0.1:3100。")
    print("电脑浏览器的 localhost 指向电脑；服务器内测试通过不代表已建立电脑端口转发。")
    print("VS Code Remote-SSH：在“端口 / Ports”面板转发 3100，打开面板显示的本地地址。")
    print("或在你自己电脑的 PowerShell / 终端执行（替换 SSH_PORT 和 SSH_HOST）：")
    print(
        "  ssh -N -o ExitOnForwardFailure=yes -L 127.0.0.1:3100:127.0.0.1:3100 -p SSH_PORT root@SSH_HOST"
    )
    print("保持 SSH 窗口开启，再用电脑浏览器访问 http://127.0.0.1:3100/login")
    print("操作详情：docs/manual-acceptance.md 的“从自己的电脑访问 AutoDL”。")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["up", "down", "status"])
    action = parser.parse_args().action
    STATE.mkdir(parents=True, exist_ok=True)
    lock = (STATE / "services.lock").open("a")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as exc:
        raise RuntimeError(
            "Another SupplyGuard acceptance operation is running"
        ) from exc
    if action == "up":
        up()
        print_browser_access()
    elif action == "down":
        for name in reversed(SPECS):
            stop(name)
    else:
        for name, spec in SPECS.items():
            owned = owns_process(name, load_record(name))
            print(
                f"{name}: {'running (verified SupplyGuard acceptance process)' if owned else 'not owned/running'}; port {spec['port']}: {'occupied' if port_busy(spec['port']) else 'free'}"
            )
        if owns_process("web", load_record("web")):
            print_browser_access()


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
