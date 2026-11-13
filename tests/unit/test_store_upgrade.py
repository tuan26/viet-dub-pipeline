import os
import sqlite3
import threading
import time

import pytest

from vietdub.auto import config as auto_config
from vietdub.auto import orchestrator
from vietdub.auto.store import SCHEMA_VERSION, Store


def test_old_database_is_upgraded_in_place(tmp_path):
    path = tmp_path / "old.db"
    db = sqlite3.connect(path)
    db.executescript("""
        CREATE TABLE videos (id TEXT PRIMARY KEY, source TEXT NOT NULL, title TEXT, page_url TEXT, download_url TEXT, license TEXT,
            attribution TEXT, language TEXT, permission TEXT, rights_basis TEXT, state TEXT NOT NULL, content_hash TEXT, path TEXT,
            out_dir TEXT, duration REAL, attempts INTEGER NOT NULL DEFAULT 0, next_attempt_at REAL NOT NULL DEFAULT 0, error TEXT,
            qc TEXT, locked_by TEXT, locked_at REAL, created_at REAL NOT NULL, updated_at REAL NOT NULL);
        CREATE TABLE events (id INTEGER PRIMARY KEY AUTOINCREMENT, video_id TEXT, ts REAL NOT NULL, stage TEXT, level TEXT, message TEXT, seconds REAL);
        CREATE TABLE sources (name TEXT PRIMARY KEY, last_checked REAL, last_error TEXT, found INTEGER);
        INSERT INTO videos (id, source, state, created_at, updated_at) VALUES ('v1', 's', 'NEEDS_REVIEW', 1, 1);
        INSERT INTO sources VALUES ('s', 5, NULL, 2);""")
    db.commit()
    db.close()
    store = Store(f"sqlite:///{path}")
    assert store.setting("schema_version") == str(SCHEMA_VERSION)
    assert store.get("v1")["state"] == "NEEDS_REVIEW" and store.get("v1")["paused"] == 0
    assert store.sources()[0]["found"] == 2 and store.users() == [] and store.setting("secret_key")
    Store(f"sqlite:///{path}")  # opening again changes nothing


def test_newer_database_is_refused(tmp_path):
    store = Store(f"sqlite:///{tmp_path / 'x.db'}")
    store.set_setting("schema_version", str(SCHEMA_VERSION + 1))
    with pytest.raises(Exception, match="mới hơn"):
        Store(f"sqlite:///{tmp_path / 'x.db'}")


def test_source_claim_is_given_to_one_caller(tmp_path):
    store = Store(f"sqlite:///{tmp_path / 's.db'}")
    store.upsert_source({"name": "a", "type": "folder", "options": {}}, "web")
    assert store.claim_source("a", 60) and not store.claim_source("a", 60)
    store.set_source("a", last_checked=None)
    store.set_source("a", enabled=0)
    assert not store.claim_source("a", 60)


def test_heartbeat_keeps_a_long_job_from_being_recovered(tmp_path):
    url = f"sqlite:///{tmp_path / 'h.db'}"
    store = Store(url)
    store.add({"id": "v", "source": "s", "state": "DOWNLOADED"})
    store.claim("DOWNLOADED", "w1")
    store.update("v", locked_at=time.time() - 100)
    beat = orchestrator.Heartbeat(url, "w1", 0.05)
    beat.video_id = "v"
    beat.start()
    time.sleep(0.3)
    assert store.recover_stale(50) == []
    beat.stop()
    assert store.workers()[0]["name"] == "w1"


def write_config(tmp_path):
    (tmp_path / "videos").mkdir()
    (tmp_path / "pipeline.toml").write_text('''
[storage]
library = "library"
[server]
poll_seconds = 0.05
heartbeat_seconds = 0.05
[[source]]
name = "mine"
type = "folder"
path = "videos"
license = "owned"
rights = "verified"
''', encoding="utf-8")
    return auto_config.load(tmp_path / "pipeline.toml")


def test_worker_loop_respects_system_pause_and_processes_jobs(tmp_path):
    cfg = write_config(tmp_path)
    store = Store(cfg.database)
    store.add({"id": "v", "source": "mine", "state": "APPROVED", "license": "owned"})
    store.set_setting("paused", "1")
    steps = orchestrator.Steps(discover=lambda s: [], download=lambda c, s, v: {"state": "DOWNLOADED", "path": "/x", "duration": 1.0},
                               dub=lambda c, s, v: {"state": "DUBBED", "out_dir": "/o"},
                               check=lambda c, s, v: {"state": "QC_PASS", "qc": {}})
    orchestrator.work(cfg, store, "w1", steps, max_cycles=2, log=lambda m: None)
    assert store.get("v")["state"] == "APPROVED" and store.workers()[0]["status"] == "stopped"
    store.set_setting("paused", "0")
    orchestrator.work(cfg, store, "w1", steps, max_cycles=4, log=lambda m: None)
    assert store.get("v")["state"] == "QC_PASS"
