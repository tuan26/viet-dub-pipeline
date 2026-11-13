"""Real-process checks of the unattended flow (Phase 1). Starts actual worker processes,
a local translation server it can switch off, PostgreSQL restarts and kill -9, and
records what happened. Each scenario prints PASS/FAIL with the evidence.

    python tools/phase1_check.py --clips DIR --work DIR --db postgresql://... [--pg-ctl "cmd"] [--only s1,s2]

DIR must hold clip1.mp4 … clip6.mp4 (short, distinct, with speech) and long150.mp4.
Voices are the offline "beep" engine and translation is tools/fake_translator.py, so the
checks exercise orchestration, not dubbing quality.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from http.cookiejar import CookieJar
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = sys.executable
sys.path.insert(0, str(ROOT / "src"))
from vietdub.auto.store import Store  # noqa: E402

RESULTS: list[dict] = []
PROCS: list[subprocess.Popen] = []


def log(msg: str) -> None:
    print(time.strftime("%H:%M:%S"), msg, flush=True)


def wait_for(fn, timeout: float, every: float = 1.0, what: str = ""):
    end = time.time() + timeout
    while time.time() < end:
        value = fn()
        if value:
            return value
        time.sleep(every)
    raise TimeoutError(f"quá {timeout:.0f}s chờ: {what}")


class Env:
    def __init__(self, args, name: str, sources: str, limits: str = "", server: str = ""):
        self.args, self.name = args, name
        self.dir = Path(args.work) / name
        shutil.rmtree(self.dir, ignore_errors=True)
        (self.dir / "videos").mkdir(parents=True)
        self.store = Store(args.db)
        for table in ("events", "edits", "videos", "sources", "workers", "users"):
            self.store.sql(f"DELETE FROM {table}")
        self.store.sql("DELETE FROM settings WHERE key = 'paused'")
        self.config = self.dir / "pipeline.toml"
        self.config.write_text(f'''
[storage]
database = "{args.db}"
library = "library"
[limits]
retry_minutes = 0.1
max_attempts = 4
stale_minutes = 0.25
min_free_gb = 1
min_free_ram_gb = 0.5
{limits}
[server]
poll_seconds = 2
heartbeat_seconds = 3
{server}
[dubbing]
asr_model = "small"
translator = "ollama"
base_url = "http://127.0.0.1:{args.port}/v1"
model = "x"
tts = "beep"
{sources}
''', encoding="utf-8")
        self.workers: dict[str, subprocess.Popen] = {}

    def clip(self, name: str, as_name: str | None = None, folder: str = "videos") -> Path:
        dest = self.dir / folder / (as_name or name)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(Path(self.args.clips) / name, dest)
        return dest

    def worker(self, name: str) -> subprocess.Popen:
        logf = open(self.dir / f"{name}.log", "a")
        env = dict(os.environ, HF_HUB_DISABLE_XET="1", PYTHONUNBUFFERED="1")
        p = subprocess.Popen([PY, "-m", "vietdub.cli", "auto", "worker", "--config", str(self.config), "--name", name],
                             stdout=logf, stderr=subprocess.STDOUT, env=env, cwd=str(ROOT))
        self.workers[name] = p
        PROCS.append(p)
        return p

    def stop(self) -> None:
        for p in self.workers.values():
            if p.poll() is None:
                p.send_signal(signal.SIGTERM)
        for p in self.workers.values():
            try:
                p.wait(30)
            except subprocess.TimeoutExpired:
                p.kill()

    def states(self) -> dict[str, str]:
        return {v["id"]: v["state"] for v in self.store.videos()}

    def events(self, vid: str | None = None) -> list[dict]:
        return list(reversed(self.store.events(vid, 1000)))


FOLDER = '''
[[source]]
name = "mine"
type = "folder"
path = "videos"
license = "owned"
rights = "verified"
interval_minutes = {interval}
'''
DONE = ("QC_PASS", "NEEDS_REVIEW")


class Translator:
    def __init__(self, port: int):
        self.port, self.proc = port, None

    def start(self) -> None:
        if self.proc is None or self.proc.poll() is not None:
            self.proc = subprocess.Popen([PY, str(ROOT / "tools" / "fake_translator.py"), str(self.port)])
            PROCS.append(self.proc)
            time.sleep(0.5)

    def stop(self) -> None:
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            self.proc.wait(10)


def record(name: str, ok: bool, evidence: dict) -> None:
    RESULTS.append({"scenario": name, "ok": ok, "evidence": evidence})
    log(f"{'PASS' if ok else 'FAIL'} {name}: {json.dumps(evidence, ensure_ascii=False)[:600]}")


def scenario(fn):
    def run(args, tr):
        log(f"=== {fn.__name__}")
        try:
            fn(args, tr)
        except Exception as exc:
            record(fn.__name__, False, {"exception": f"{type(exc).__name__}: {exc}"})
    run.__name__ = fn.__name__
    return run


@scenario
def s1_two_workers(args, tr):
    tr.start()
    e = Env(args, "s1", FOLDER.format(interval=60))
    for i in range(1, 7):
        e.clip(f"clip{i}.mp4")
    t0 = time.time()
    e.worker("w1"); e.worker("w2")
    wait_for(lambda: len(e.states()) == 6 and all(s in DONE for s in e.states().values()), 900, 3, "6 video xong")
    wall = time.time() - t0
    e.stop()
    ev = e.events()
    dub_done = [x for x in ev if x["stage"] == "dub" and x["level"] == "info" and x["message"].startswith("→ DUBBED")]
    per_video = {}
    for x in dub_done:
        per_video.setdefault(x["video_id"], []).append(re.search(r"\[(.*?)\]", x["message"]).group(1))
    by_worker = {}
    for vid, ws in per_video.items():
        for w in ws:
            by_worker[w] = by_worker.get(w, 0) + 1
    spans = sorted((x["ts"] - x["seconds"], x["ts"], re.search(r"\[(.*?)\]", x["message"]).group(1)) for x in dub_done)
    overlap = any(a[2] != b[2] and b[0] < a[1] for a, b in zip(spans, spans[1:]))
    busy = sum(x["seconds"] for x in ev if x["stage"] in ("download", "dub", "check") and x["level"] == "info" and x["seconds"])
    ok = len(per_video) == 6 and all(len(w) == 1 for w in per_video.values()) and len(by_worker) == 2 and overlap
    record("s1_two_workers", ok, {"videos": 6, "dub_runs_per_video": {k.split(':')[-1]: v for k, v in per_video.items()},
                                  "videos_per_worker": by_worker, "ran_at_same_time": overlap,
                                  "wall_seconds": round(wall), "sum_of_step_seconds": round(busy)})


@scenario
def s2_auto_retry(args, tr):
    tr.stop()
    e = Env(args, "s2", FOLDER.format(interval=60))
    e.clip("clip1.mp4")
    e.worker("w1")
    first = wait_for(lambda: next((x for x in e.events() if x["level"] == "warning" and "Lỗi lần 1" in x["message"]), None),
                     300, 2, "lỗi lần 1")
    row = e.store.videos()[0]
    tr.start()
    done = wait_for(lambda: e.states() and list(e.states().values())[0] in DONE, 300, 2, "thành công sau khi bộ dịch chạy lại")
    e.stop()
    row2 = e.store.videos()[0]
    record("s2_auto_retry", bool(done) and row["state"] == "DOWNLOADED" and row["attempts"] >= 1,
           {"first_error": first["message"][:160], "state_after_error": row["state"], "attempts_after_error": row["attempts"],
            "retry_in_seconds": round(row["next_attempt_at"] - first["ts"]), "final_state": row2["state"],
            "attempts_recorded": row2["attempts"]})


@scenario
def s3_give_up_then_manual_retry(args, tr):
    tr.stop()
    e = Env(args, "s3", FOLDER.format(interval=60))
    e.config.write_text(e.config.read_text().replace("max_attempts = 4", "max_attempts = 2"), encoding="utf-8")
    e.clip("clip2.mp4")
    e.worker("w1")
    wait_for(lambda: e.states() and list(e.states().values())[0] == "FAILED", 300, 2, "FAILED")
    row = e.store.videos()[0]
    warnings = [x["message"][:120] for x in e.events() if x["level"] in ("warning", "error")]
    tr.start()
    e.store.release(row["id"], "DOWNLOADED", attempts=0, next_attempt_at=0, error=None)  # what “Thử lại” does
    wait_for(lambda: list(e.states().values())[0] in DONE, 300, 2, "xong sau khi thử lại tay")
    e.stop()
    record("s3_give_up_then_manual_retry", row["attempts"] == 2,
           {"state": row["state"], "attempts": row["attempts"], "error": (row["error"] or "")[:140], "log": warnings,
            "after_manual_retry": list(e.states().values())[0]})


@scenario
def s4_kill9_recovery_and_heartbeat(args, tr):
    """Two workers; one takes a long dub, the other idles and runs stale-job recovery every
    2 s. While the busy worker is alive its heartbeat must protect the job beyond the 15 s
    limit; after kill -9 the idle worker must recover and finish it."""
    tr.start()
    e = Env(args, "s4", FOLDER.format(interval=60))
    e.config.write_text(e.config.read_text().replace("stale_minutes = 0.25", "stale_minutes = 0.1"), encoding="utf-8")
    e.clip("long150.mp4")
    e.worker("wA"); e.worker("wB")
    claimed = wait_for(lambda: next((v for v in e.store.videos() if v["state"] == "DUBBING"), None), 300, 0.5, "đang lồng tiếng")
    vid, owner = claimed["id"], claimed["locked_by"]
    other = "wB" if owner == "wA" else "wA"
    started = time.time()
    wait_for(lambda: (e.store.get(vid)["progress"] or "").startswith(("[3/6]", "[4/6]", "[5/6]", "[6/6]")), 600, 0.5, "đã qua nhận dạng")
    protected = time.time() - started
    recovered_while_alive = [x for x in e.events(vid) if x["stage"] == "recover"]
    before = e.store.get(vid)
    os.kill(e.workers[owner].pid, signal.SIGKILL)
    e.workers[owner].wait()
    killed_at = time.time()
    time.sleep(5)
    stuck = e.store.get(vid)
    rec = wait_for(lambda: next((x for x in e.events(vid) if x["stage"] == "recover"), None), 120, 1, "khôi phục")
    wait_for(lambda: e.store.get(vid)["state"] in DONE, 600, 2, "xong sau khôi phục")
    e.stop()
    recovers = [x for x in e.events(vid) if x["stage"] == "recover"]
    dub_runs = [x["message"] for x in e.events(vid) if x["stage"] == "dub" and x["level"] == "info"]
    stages = json.loads(next((e.dir / "library" / "dubbed").glob("*/work/stages.json")).read_text())
    record("s4_kill9_recovery_and_heartbeat",
           not recovered_while_alive and protected > 12 and stuck["state"] == "DUBBING" and len(recovers) == 1
           and other in dub_runs[-1],
           {"busy_worker": owner, "seconds_alive_on_job_before_kill": round(protected), "stale_limit_seconds": 6,
            "recovered_while_alive": len(recovered_while_alive), "progress_when_killed": before["progress"],
            "state_5s_after_kill": stuck["state"], "recovered_after_seconds": round(rec["ts"] - killed_at),
            "recover_message": rec["message"], "finished_by": dub_runs[-1] if dub_runs else None,
            "speech_to_text_seconds_total": stages.get("speech_to_text")})


@scenario
def s5_postgres_restart(args, tr):
    if not args.pg_ctl:
        record("s5_postgres_restart", False, {"skipped": "không có --pg-ctl"})
        return
    tr.start()
    e = Env(args, "s5", FOLDER.format(interval=0.1))
    e.clip("long150.mp4")
    e.worker("w1")
    vid = wait_for(lambda: next((v["id"] for v in e.store.videos() if v["state"] == "DUBBING"), None), 300, 1, "đang lồng tiếng")
    t = time.time()
    # the restarted server inherits the command's output, so never capture it (it would never close)
    out = subprocess.run(args.pg_ctl + " restart", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120)
    restart_s = time.time() - t
    e.store = Store(args.db)  # this script's own connection also died
    wait_for(lambda: e.store.get(vid)["state"] in DONE, 600, 2, "xong dù PostgreSQL khởi động lại giữa chừng")
    mid = e.store.get(vid)
    e.clip("clip3.mp4")  # a new file after the restart: idle worker must still pick it up
    wait_for(lambda: len(e.states()) == 2 and all(s in DONE for s in e.states().values()), 300, 2, "video mới sau khởi động lại")
    e.stop()
    errors = [l for l in (e.dir / "w1.log").read_text().splitlines() if "Lỗi vòng lặp" in l or "OperationalError" in l]
    record("s5_postgres_restart", mid["state"] in DONE and mid["attempts"] == 0,
           {"pg_restart_seconds": round(restart_s, 1), "pg_ctl_ok": out.returncode == 0, "video_during_restart": mid["state"],
            "attempts": mid["attempts"], "new_video_after_restart": list(e.states().values()), "worker_loop_errors": errors[:3]})


@scenario
def s6_schedule_and_dedup(args, tr):
    tr.start()
    e = Env(args, "s6", FOLDER.format(interval=0.1))
    e.clip("clip4.mp4")
    e.worker("w1")
    wait_for(lambda: len(e.states()) == 1 and list(e.states().values())[0] in DONE, 300, 2, "video 1")
    checks_1 = e.store.source_rows()[0]["last_checked"]
    time.sleep(15)
    known_after = len(e.states())
    e.clip("clip5.mp4")
    added = time.time()
    found = wait_for(lambda: next((x for x in e.events() if x["stage"] == "discover" and "clip5" in (x["video_id"] or "")), None),
                     60, 1, "phát hiện file mới")
    e.clip("clip4.mp4", "copy_of_clip4.mp4")
    wait_for(lambda: len(e.states()) == 3 and all(s in DONE + ("DUPLICATE",) for s in e.states().values()), 300, 2, "3 video")
    e.stop()
    st = e.states()
    dub_count = sum(1 for x in e.events() if x["stage"] == "dub" and x["message"].startswith("→ DUBBED"))
    record("s6_schedule_and_dedup", known_after == 1 and dub_count == 2 and "DUPLICATE" in st.values(),
           {"videos_after_15s_idle": known_after, "new_file_found_after_seconds": round(found["ts"] - added),
            "last_checked_advanced": e.store.source_rows()[0]["last_checked"] > checks_1,
            "states": {k.split(':')[-1]: v for k, v in st.items()}, "dub_runs": dub_count})


@scenario
def s7_limits(args, tr):
    tr.start()
    ev = {}
    for key, limits, expect in (("disk", "min_free_gb = 100000", "Đĩa chỉ còn"), ("ram", "min_free_ram_gb = 100000", "RAM trống"),
                                ("daily", "daily_minutes = 0.01", "Hết hạn mức"), ("length", "max_video_minutes = 0.1", "vượt giới hạn")):
        e = Env(args, f"s7_{key}", FOLDER.format(interval=60), limits=limits)
        e.config.write_text(e.config.read_text().replace("min_free_gb = 1\n", "").replace("min_free_ram_gb = 0.5\n", "")
                            if key in ("disk", "ram") else e.config.read_text(), encoding="utf-8")
        e.clip("clip6.mp4")
        e.worker("w1")
        row = wait_for(lambda: next((v for v in e.store.videos() if v["error"] and expect in v["error"]), None), 180, 2, expect)
        time.sleep(2)
        row = e.store.get(row["id"])
        e.stop()
        ev[key] = {"state": row["state"], "attempts": row["attempts"], "error": row["error"][:110],
                   "next_attempt_in_minutes": round((row["next_attempt_at"] - time.time()) / 60, 1) if row["next_attempt_at"] else 0}
    ok = (ev["disk"]["state"] == "APPROVED" and ev["ram"]["state"] == "DOWNLOADED" and ev["daily"]["state"] == "DOWNLOADED"
          and ev["daily"]["attempts"] == 0 and ev["length"]["state"] == "FAILED")
    record("s7_limits", ok, ev)


@scenario
def s8_serve_supervisor_web_and_states(args, tr):
    tr.start()
    e = Env(args, "s8", FOLDER.format(interval=0.1) + '''
[[source]]
name = "cho-duyet"
type = "folder"
path = "pending"
license = "cc-by"
attribution = "Blender Foundation"
rights = "needs_approval"
interval_minutes = 0.1
''', server="workers = 2\ncpu_threads = 2\nnice = 7\nport = 8877")
    (e.dir / "pending").mkdir()
    e.clip("clip1.mp4"); e.clip("clip2.mp4", folder="pending")
    logf = open(e.dir / "serve.log", "w")
    serve = subprocess.Popen([PY, "-m", "vietdub.cli", "serve", "--config", str(e.config)], stdout=logf, stderr=subprocess.STDOUT,
                             env=dict(os.environ, HF_HUB_DISABLE_XET="1", PYTHONUNBUFFERED="1"), cwd=str(ROOT))
    PROCS.append(serve)
    base = "http://127.0.0.1:8877"
    wait_for(lambda: _get(base + "/healthz")[0] == 200, 60, 1, "web lên")
    workers = wait_for(lambda: [w for w in e.store.workers() if w["status"] in ("idle", "busy")] if len(e.store.workers()) == 2 else None,
                       60, 1, "2 worker")
    pids = {w["name"]: w["pid"] for w in workers}
    environ = Path(f"/proc/{pids['worker-1']}/environ").read_bytes().split(b"\0")
    nice = int(Path(f"/proc/{pids['worker-1']}/stat").read_text().rsplit(")", 1)[1].split()[16])
    threads_env = [x.decode() for x in environ if x.startswith(b"OMP_NUM_THREADS")]
    os.kill(pids["worker-2"], signal.SIGKILL)
    restarted = wait_for(lambda: next((w for w in e.store.workers() if w["name"] == "worker-2" and w["pid"] != pids["worker-2"]
                                        and w["status"] in ("idle", "busy")), None), 60, 1, "worker-2 khởi động lại")
    # the web, as a person would use it
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()), urllib.request.ProxyHandler({}))
    _post(opener, base + "/setup", {"username": "admin", "password": "secret123", "password2": "secret123"})
    csrf = re.search(r'name="csrf" content="([^"]+)"', opener.open(base + "/").read().decode()).group(1)
    pending = wait_for(lambda: next((v["id"] for v in e.store.videos() if v["state"] == "AWAITING_RIGHTS"), None), 60, 1, "chờ quyền")
    mine = wait_for(lambda: next((v["id"] for v in e.store.videos() if v["source"] == "mine" and v["state"] in DONE), None), 300, 2, "video 1 xong")
    time.sleep(8)
    still_waiting = e.store.get(pending)["state"]
    _post(opener, base + "/video/action", {"csrf": csrf, "id": pending, "action": "pause"})
    _post(opener, base + "/video/action", {"csrf": csrf, "id": pending, "action": "allow", "note": "kiểm tra: CC-BY Blender"})
    time.sleep(10)
    paused_state = e.store.get(pending)["state"]
    _post(opener, base + "/video/action", {"csrf": csrf, "id": pending, "action": "resume"})
    wait_for(lambda: e.store.get(pending)["state"] in DONE, 300, 2, "video chờ quyền xong sau khi duyệt")
    _post(opener, base + "/video/action", {"csrf": csrf, "id": mine, "action": "approve", "note": "đã xem", "override": "1"})
    final = {e.store.get(mine)["id"].split(":")[-1]: e.store.get(mine)["state"], pending.split(":")[-1]: e.store.get(pending)["state"]}
    serve.send_signal(signal.SIGTERM)
    serve.wait(60)
    stopped = {w["name"]: w["status"] for w in e.store.workers()}
    record("s8_serve_supervisor_web_and_states",
           still_waiting == "AWAITING_RIGHTS" and paused_state == "APPROVED" and final[mine.split(':')[-1]] == "READY"
           and threads_env == ["OMP_NUM_THREADS=2"] and nice == 7 and all(s == "stopped" for s in stopped.values()),
           {"worker_env": threads_env, "worker_nice": nice, "killed_pid": pids["worker-2"], "restarted_pid": restarted["pid"],
            "awaiting_after_8s": still_waiting, "state_while_paused": paused_state, "final": final, "after_sigterm": stopped})


def _get(url):
    try:
        with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(url, timeout=5) as r:
            return r.status, r.read()
    except Exception:
        return 0, b""


def _post(opener, url, data):
    with opener.open(urllib.request.Request(url, data=urllib.parse.urlencode(data).encode()), timeout=30) as r:
        return r.status


ALL = [s1_two_workers, s2_auto_retry, s3_give_up_then_manual_retry, s4_kill9_recovery_and_heartbeat, s5_postgres_restart,
       s6_schedule_and_dedup, s7_limits, s8_serve_supervisor_web_and_states]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--clips", required=True); ap.add_argument("--work", required=True); ap.add_argument("--db", required=True)
    ap.add_argument("--port", type=int, default=8099); ap.add_argument("--pg-ctl", default="")
    ap.add_argument("--only", default=""); ap.add_argument("--out", default="")
    args = ap.parse_args()
    tr = Translator(args.port)
    try:
        for s in ALL:
            if not args.only or s.__name__.split("_")[0] in args.only.split(","):
                s(args, tr)
    finally:
        for p in PROCS:
            if p.poll() is None:
                p.kill()
    if args.out:
        Path(args.out).write_text(json.dumps(RESULTS, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n{sum(r['ok'] for r in RESULTS)}/{len(RESULTS)} kịch bản đạt")


if __name__ == "__main__":
    main()
