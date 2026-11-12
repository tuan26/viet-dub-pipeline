"""Unattended flow. Runs on SQLite, and again on PostgreSQL when VIETDUB_TEST_PG is set
(e.g. postgresql://postgres@127.0.0.1:5432/vietdub_test)."""
import json
import os
import time
import uuid
from pathlib import Path

import pytest

from vietdub.auto import config as auto_config
from vietdub.auto import dashboard, orchestrator
from vietdub.auto.orchestrator import Steps
from vietdub.auto.store import Store
from vietdub.ingest.catalog import Item
from vietdub.models import TransientError, VietdubError

BACKENDS = ["sqlite"] + (["postgres"] if os.environ.get("VIETDUB_TEST_PG") else [])


@pytest.fixture(params=BACKENDS)
def store(request, tmp_path):
    if request.param == "sqlite":
        yield Store(f"sqlite:///{tmp_path / 'state.db'}")
        return
    s = Store(os.environ["VIETDUB_TEST_PG"])
    for table in ("videos", "events", "sources"):
        s.sql(f"DELETE FROM {table}")
    yield s


def video(i, state="APPROVED", **extra):
    return {"id": f"t:{i}", "source": "t", "title": f"V{i}", "license": "owned", "page_url": "u", "state": state, **extra}


def write_config(tmp_path, body="", rights="verified", licence="owned"):
    (tmp_path / "videos").mkdir(exist_ok=True)
    path = tmp_path / "pipeline.toml"
    path.write_text(f'''
[storage]
library = "library"
[limits]
max_attempts = 2
retry_minutes = 1
[[source]]
name = "mine"
type = "folder"
path = "videos"
license = "{licence}"
rights = "{rights}"
{body}''', encoding="utf-8")
    return path


def test_add_is_idempotent_and_claim_is_exclusive(store):
    assert store.add(video(1)) and not store.add(video(1))
    store.add(video(2))
    first, second = store.claim("APPROVED", "w1"), store.claim("APPROVED", "w2")
    assert {first["id"], second["id"]} == {"t:1", "t:2"} and first["state"] == "DOWNLOADING"
    assert store.claim("APPROVED", "w3") is None
    assert store.get("t:1")["locked_by"] == "w1"


def test_claim_skips_videos_waiting_for_a_retry(store):
    store.add(video(1))
    store.update("t:1", next_attempt_at=time.time() + 3600)
    assert store.claim("APPROVED", "w") is None


def test_stale_work_returns_to_its_queue(store):
    store.add(video(1, state="DOWNLOADED"))
    store.claim("DOWNLOADED", "dead-worker")
    store.update("t:1", locked_at=time.time() - 7200)
    assert store.recover_stale(3600) == ["t:1"]
    row = store.get("t:1")
    assert row["state"] == "DOWNLOADED" and row["locked_by"] is None
    assert store.recover_stale(3600) == []


def test_source_schedule(store):
    assert store.source_due("s", 60)
    store.source_checked("s", 3, None)
    assert not store.source_due("s", 60) and store.source_due("s", 0)


def test_config_refuses_verified_without_proof(tmp_path):
    with pytest.raises(VietdubError, match="evidence"):
        auto_config.load(write_config(tmp_path, licence="licensed"))
    path = write_config(tmp_path)
    path.write_text(path.read_text().replace('type = "folder"', 'type = "archive"'), encoding="utf-8")
    with pytest.raises(VietdubError, match="tự khai"):
        auto_config.load(path)
    assert auto_config.load(write_config(tmp_path)).sources[0].rights == "verified"


def test_config_rejects_unknown_keys_and_review_mode(tmp_path):
    with pytest.raises(VietdubError, match="max_atempts"):
        auto_config.load(_with(write_config(tmp_path), "max_attempts = 2", "max_atempts = 2"))
    with pytest.raises(VietdubError, match="review"):
        auto_config.load(write_config(tmp_path, "[dubbing]\nreview = true\n"))


def _with(path, old, new):
    path.write_text(path.read_text().replace(old, new), encoding="utf-8")
    return path


def make(tmp_path, store_obj, items, rights="verified", **step_overrides):
    cfg = auto_config.load(write_config(tmp_path, rights=rights))
    steps = Steps(discover=lambda source: items, **step_overrides)
    return cfg, steps


def ok_download(cfg, store, v):
    return {"state": "DOWNLOADED", "content_hash": "h-" + v["id"], "duration": 60.0, "path": "/x"}


def ok_dub(cfg, store, v):
    return {"state": "DUBBED", "out_dir": "/out"}


def ok_check(cfg, store, v):
    return {"state": "NEEDS_REVIEW", "qc": {"status": "NEEDS_REVIEW", "reasons": ["vai chưa duyệt"]}}


def test_unverified_source_stops_for_rights_approval(store, tmp_path):
    items = [Item("a:1", "mine", "One", "u", "cc0")]
    cfg, steps = make(tmp_path, store, items, rights="needs_approval", download=ok_download, dub=ok_dub, check=ok_check)
    summary = orchestrator.run_once(cfg, store, steps=steps, log=lambda m: None)
    assert store.get("a:1")["state"] == "AWAITING_RIGHTS" and summary["processed"] == 0


def test_verified_source_flows_to_review_and_is_not_reprocessed(store, tmp_path):
    items = [Item("a:1", "mine", "One", "u", "owned"), Item("a:2", "mine", "Bad", "u", "cc-by-nc", attribution="x")]
    calls = []

    def dub(cfg, s, v):
        calls.append(v["id"])
        return ok_dub(cfg, s, v)

    cfg, steps = make(tmp_path, store, items, download=ok_download, dub=dub, check=ok_check)
    first = orchestrator.run_once(cfg, store, steps=steps, log=lambda m: None)
    assert first["discover"]["new"] == 1 and first["discover"]["bad_licence"] == 1
    row = store.get("a:1")
    assert row["state"] == "NEEDS_REVIEW" and json.loads(row["qc"])["reasons"] == ["vai chưa duyệt"]
    store.source_checked("mine", 0, None)
    store.sql("UPDATE sources SET last_checked = 0")
    second = orchestrator.run_once(cfg, store, steps=steps, log=lambda m: None)
    assert calls == ["a:1"] and second["processed"] == 0 and second["discover"]["known"] == 1


def test_transient_failure_is_retried_then_gives_up(store, tmp_path):
    def flaky(cfg, s, v):
        raise TransientError("mạng rớt")

    cfg, steps = make(tmp_path, store, [Item("a:1", "mine", "One", "u", "owned")], download=flaky)
    orchestrator.run_once(cfg, store, steps=steps, log=lambda m: None)
    row = store.get("a:1")
    assert row["state"] == "APPROVED" and row["attempts"] == 1 and row["next_attempt_at"] > time.time()
    assert orchestrator.run_once(cfg, store, steps=steps, log=lambda m: None)["processed"] == 0  # still backing off
    store.update("a:1", next_attempt_at=0)
    orchestrator.run_once(cfg, store, steps=steps, log=lambda m: None)
    row = store.get("a:1")
    assert row["state"] == "FAILED" and row["attempts"] == 2 and "mạng rớt" in row["error"]


def test_permanent_failure_stops_at_once_and_crash_counts_as_retry(store, tmp_path):
    def too_long(cfg, s, v):
        raise VietdubError("Video dài 90 phút, vượt giới hạn")

    cfg, steps = make(tmp_path, store, [Item("a:1", "mine", "One", "u", "owned")], download=too_long)
    orchestrator.run_once(cfg, store, steps=steps, log=lambda m: None)
    assert store.get("a:1")["state"] == "FAILED" and store.get("a:1")["attempts"] == 1

    def crash(cfg, s, v):
        raise RuntimeError("bug")

    store.add(video(9))
    steps.download = crash
    orchestrator.run_once(cfg, store, steps=steps, log=lambda m: None)
    assert store.get("t:9")["state"] == "APPROVED" and "RuntimeError" in store.get("t:9")["error"]


def test_budget_defers_without_counting_an_attempt(store, tmp_path):
    def over(cfg, s, v):
        raise orchestrator.Defer(time.time() + 3600, "Hết hạn mức hôm nay")

    cfg, steps = make(tmp_path, store, [Item("a:1", "mine", "One", "u", "owned")], download=ok_download, dub=over)
    orchestrator.run_once(cfg, store, steps=steps, log=lambda m: None)
    row = store.get("a:1")
    assert row["state"] == "DOWNLOADED" and row["attempts"] == 0 and row["next_attempt_at"] > time.time()


def test_dry_run_writes_nothing(store, tmp_path):
    lines = []
    cfg, steps = make(tmp_path, store, [Item("a:1", "mine", "One", "u", "owned")], download=ok_download)
    orchestrator.run_once(cfg, store, dry_run=True, steps=steps, log=lines.append)
    assert store.videos() == [] and store.sources() == [] and any("chạy thử" in l for l in lines)


def test_same_content_from_two_ids_is_a_duplicate(store, tmp_path):
    cfg = auto_config.load(write_config(tmp_path))
    for name in ("a.mp4", "b.mp4"):
        (tmp_path / "videos" / name).write_bytes(b"same bytes")
    import vietdub.auto.orchestrator as orch
    real = orch.media.duration
    orch.media.duration = lambda p: 30.0
    try:
        summary = orchestrator.run_once(cfg, store, steps=Steps(dub=ok_dub, check=ok_check), log=lambda m: None)
    finally:
        orch.media.duration = real
    states = sorted(v["state"] for v in store.videos())
    assert states == ["DUPLICATE", "NEEDS_REVIEW"] and summary["states"]["DUPLICATE"] == 1
    assert (tmp_path / "videos" / "b.mp4").exists()  # the user's own files are never deleted


def test_dashboard_lists_videos_and_escapes_text(store):
    store.add(video(1, title="<b>Phim</b>"))
    store.log("t:1", "download", "info", "→ DOWNLOADED", 1.5)
    page = dashboard.render(store)
    assert "&lt;b&gt;Phim&lt;/b&gt;" in page and "<b>Phim</b>" not in page and "APPROVED" in page
