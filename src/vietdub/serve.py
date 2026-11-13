"""`vietdub serve`: the dashboard plus a supervised pool of worker processes.

Workers are separate processes so a crash or an out-of-memory kill in the heavy steps
never takes the dashboard down, and a dead worker is restarted. In Docker the web and
the workers can also run as separate containers (`vietdub serve --workers 0` and
`vietdub auto worker`).
"""
from __future__ import annotations

import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

from .auto import config as auto_config
from .auto.orchestrator import import_sources
from .auto.store import Store


def _detach_and_follow_parent() -> None:
    """Runs in each worker right after fork: its own session (so a Ctrl+C in the terminal
    reaches only `serve`), and on Linux a SIGTERM if `serve` dies without cleaning up."""
    os.setsid()
    try:
        import ctypes

        ctypes.CDLL("libc.so.6", use_errno=True).prctl(1, signal.SIGTERM)  # PR_SET_PDEATHSIG
    except Exception:
        pass


def worker_env(server: dict) -> dict:
    env = dict(os.environ)
    if server.get("cpu_threads"):
        n = str(int(server["cpu_threads"]))
        for key in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "VIETDUB_CPU_THREADS"):
            env[key] = n
    return env


class Supervisor(threading.Thread):
    def __init__(self, config_path: Path, count: int, server: dict, database: str):
        super().__init__(daemon=True)
        self.config_path, self.count, self.server, self.database = config_path, count, server, database
        self.procs: dict[str, subprocess.Popen] = {}
        self.restarts: dict[str, int] = {}
        self._stop = threading.Event()

    def _start(self, name: str) -> None:
        cmd = [sys.executable, "-m", "vietdub.cli", "auto", "worker", "--config", str(self.config_path), "--name", name]
        self.procs[name] = subprocess.Popen(cmd, env=worker_env(self.server), preexec_fn=_detach_and_follow_parent)
        print(f"[serve] khởi động {name} (pid {self.procs[name].pid})", flush=True)

    def run(self) -> None:
        store = Store(self.database)
        for i in range(1, self.count + 1):
            self._start(f"worker-{i}")
        while not self._stop.wait(3):
            for name, proc in list(self.procs.items()):
                code = proc.poll()
                if code is None:
                    continue
                n = self.restarts[name] = self.restarts.get(name, 0) + 1
                delay = min(60, 5 * n)
                msg = f"{name} dừng với mã {code}; khởi động lại sau {delay}s (lần {n})"
                print(f"[serve] {msg}", flush=True)
                try:
                    store.log(None, "worker", "warning", msg)
                except Exception:
                    pass
                if self._stop.wait(delay):
                    return
                self._start(name)

    def stop(self, grace: float = 30) -> None:
        self._stop.set()
        for proc in self.procs.values():
            if proc.poll() is None:
                proc.send_signal(signal.SIGTERM)  # the worker puts its current video back in the queue
        deadline = time.time() + grace
        for proc in self.procs.values():
            try:
                proc.wait(max(0.1, deadline - time.time()))
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGKILL)


def serve(config_path: Path, host: str | None, port: int | None, workers: int | None) -> int:
    import uvicorn

    from .web.app import create_app

    cfg = auto_config.load(config_path)
    store = Store(cfg.database)
    imported = import_sources(cfg, store)
    if imported:
        print(f"[serve] đã nhập {imported} nguồn từ {config_path}", flush=True)
    count = cfg.server["workers"] if workers is None else workers
    supervisor = Supervisor(cfg.path, count, cfg.server, cfg.database)
    supervisor.start()
    host, port = host or cfg.server["host"], port or cfg.server["port"]
    if not store.users():
        print(f"[serve] chưa có tài khoản nào: mở http://{host}:{port}/setup để tạo tài khoản quản trị", flush=True)
    # uvicorn re-raises SIGTERM after its own shutdown; with this handler that becomes a normal
    # exit, so the workers below are stopped instead of being left running
    signal.signal(signal.SIGTERM, lambda signum, frame: sys.exit(0))
    try:
        uvicorn.run(create_app(cfg.path), host=host, port=port, log_level="warning")
    finally:
        print("[serve] đang dừng các worker…", flush=True)
        supervisor.stop()
        print("[serve] đã dừng.", flush=True)
    return 0
