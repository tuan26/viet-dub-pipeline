"""State of every video, in PostgreSQL (production) or SQLite (single machine, tests).

All state changes go through here so that two workers never process the same video and
an interrupted run can be resumed.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from ..models import VietdubError

# state -> the in-progress state a worker moves it to while working on it
WORK = {"APPROVED": "DOWNLOADING", "DOWNLOADED": "DUBBING", "DUBBED": "CHECKING"}
STATES = ("AWAITING_RIGHTS", "APPROVED", "DOWNLOADING", "DOWNLOADED", "DUBBING", "DUBBED", "CHECKING",
          "QC_PASS", "NEEDS_REVIEW", "READY", "REJECTED", "DUPLICATE", "FAILED")
FIELDS = ("id", "source", "title", "page_url", "download_url", "license", "attribution", "language", "permission",
          "rights_basis", "state", "content_hash", "path", "out_dir", "duration", "attempts", "next_attempt_at",
          "error", "qc", "locked_by", "locked_at", "created_at", "updated_at")


class Store:
    def __init__(self, url: str):
        self.pg = url.startswith(("postgresql://", "postgres://"))
        if self.pg:
            try:
                import psycopg
                from psycopg.rows import dict_row
            except ImportError:
                raise VietdubError("Thiếu driver PostgreSQL. Chạy: pip install 'vietdub[auto]'")
            try:
                # client_encoding: a database created with the default SQL_ASCII encoding would
                # otherwise hand text back as bytes.
                self.db = psycopg.connect(url, autocommit=True, row_factory=dict_row, client_encoding="utf8")
            except psycopg.Error as exc:
                raise VietdubError(f"Không kết nối được PostgreSQL: {exc}")
        else:
            import sqlite3

            path = url.removeprefix("sqlite:///")
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            self.db = sqlite3.connect(path, isolation_level=None, timeout=30)
            self.db.row_factory = sqlite3.Row
        self._schema()

    def sql(self, query: str, params: tuple = ()) -> list[dict]:
        cur = self.db.execute(query.replace("?", "%s") if self.pg else query, params)
        if cur.description is None:
            return []
        return [dict(r) for r in cur.fetchall()]

    def _schema(self) -> None:
        serial = "BIGSERIAL PRIMARY KEY" if self.pg else "INTEGER PRIMARY KEY AUTOINCREMENT"
        real = "DOUBLE PRECISION" if self.pg else "REAL"
        self.sql(f"""CREATE TABLE IF NOT EXISTS videos (
            id TEXT PRIMARY KEY, source TEXT NOT NULL, title TEXT, page_url TEXT, download_url TEXT, license TEXT,
            attribution TEXT, language TEXT, permission TEXT, rights_basis TEXT, state TEXT NOT NULL,
            content_hash TEXT, path TEXT, out_dir TEXT, duration {real}, attempts INTEGER NOT NULL DEFAULT 0,
            next_attempt_at {real} NOT NULL DEFAULT 0, error TEXT, qc TEXT, locked_by TEXT, locked_at {real},
            created_at {real} NOT NULL, updated_at {real} NOT NULL)""")
        self.sql(f"""CREATE TABLE IF NOT EXISTS events (
            id {serial}, video_id TEXT, ts {real} NOT NULL, stage TEXT, level TEXT, message TEXT, seconds {real})""")
        self.sql(f"CREATE TABLE IF NOT EXISTS sources (name TEXT PRIMARY KEY, last_checked {real}, last_error TEXT, found INTEGER)")
        self.sql("CREATE INDEX IF NOT EXISTS videos_state ON videos (state, next_attempt_at)")
        self.sql("CREATE INDEX IF NOT EXISTS videos_hash ON videos (content_hash)")

    # --- videos
    def add(self, video: dict) -> bool:
        """Insert a newly discovered video; False when its id is already known."""
        now = time.time()
        row = {f: video.get(f) for f in FIELDS}
        row.update(attempts=0, next_attempt_at=0, created_at=now, updated_at=now)
        cols = ", ".join(FIELDS)
        marks = ", ".join("?" for _ in FIELDS)
        done = self.sql(f"INSERT INTO videos ({cols}) VALUES ({marks}) ON CONFLICT (id) DO NOTHING RETURNING id",
                        tuple(row[f] for f in FIELDS))
        return bool(done)

    def get(self, video_id: str) -> dict:
        rows = self.sql("SELECT * FROM videos WHERE id = ?", (video_id,))
        if not rows:
            raise VietdubError(f"Không có video '{video_id}'.")
        return rows[0]

    def videos(self, state: str | None = None) -> list[dict]:
        if state:
            return self.sql("SELECT * FROM videos WHERE state = ? ORDER BY created_at, id", (state,))
        return self.sql("SELECT * FROM videos ORDER BY created_at, id")

    def update(self, video_id: str, **fields) -> None:
        fields["updated_at"] = time.time()
        if "qc" in fields and not isinstance(fields["qc"], (str, type(None))):
            fields["qc"] = json.dumps(fields["qc"], ensure_ascii=False)
        sets = ", ".join(f"{k} = ?" for k in fields)
        self.sql(f"UPDATE videos SET {sets} WHERE id = ?", (*fields.values(), video_id))

    def claim(self, state: str, worker: str) -> dict | None:
        """Atomically take the oldest video waiting in ``state``; None when there is none.
        Another worker calling at the same moment gets a different video."""
        skip = " FOR UPDATE SKIP LOCKED" if self.pg else ""
        now = time.time()
        rows = self.sql(
            f"""UPDATE videos SET state = ?, locked_by = ?, locked_at = ?, updated_at = ?
                WHERE id = (SELECT id FROM videos WHERE state = ? AND next_attempt_at <= ?
                            ORDER BY created_at, id LIMIT 1{skip}) RETURNING *""",
            (WORK[state], worker, now, now, state, now))
        return rows[0] if rows else None

    def release(self, video_id: str, state: str, **fields) -> None:
        self.update(video_id, state=state, locked_by=None, locked_at=None, **fields)

    def recover_stale(self, older_than_seconds: float) -> list[str]:
        """Videos a dead worker left half-done go back to the queue; their work folder is kept,
        so the dubbing step resumes instead of starting over."""
        back = {v: k for k, v in WORK.items()}
        cutoff = time.time() - older_than_seconds
        recovered = []
        for row in self.sql("SELECT id, state FROM videos WHERE locked_at IS NOT NULL AND locked_at < ?", (cutoff,)):
            if row["state"] in back:
                self.release(row["id"], back[row["state"]])
                self.log(row["id"], "recover", "warning", f"Trả lại hàng đợi sau khi worker dừng giữa chừng ({row['state']})")
                recovered.append(row["id"])
        return recovered

    def by_hash(self, content_hash: str, not_id: str) -> dict | None:
        rows = self.sql("SELECT * FROM videos WHERE content_hash = ? AND id <> ? AND state <> 'DUPLICATE' LIMIT 1",
                        (content_hash, not_id))
        return rows[0] if rows else None

    def minutes_dubbed_since(self, since: float) -> float:
        rows = self.sql("SELECT COALESCE(SUM(seconds), 0) AS total FROM events WHERE stage = 'dub' AND level = 'done' AND ts >= ?", (since,))
        return float(rows[0]["total"]) / 60

    # --- log
    def log(self, video_id: str | None, stage: str, level: str, message: str, seconds: float | None = None) -> None:
        self.sql("INSERT INTO events (video_id, ts, stage, level, message, seconds) VALUES (?, ?, ?, ?, ?, ?)",
                 (video_id, time.time(), stage, level, message[:2000], seconds))

    def events(self, video_id: str | None = None, limit: int = 50) -> list[dict]:
        if video_id:
            return self.sql("SELECT * FROM events WHERE video_id = ? ORDER BY id DESC LIMIT ?", (video_id, limit))
        return self.sql("SELECT * FROM events ORDER BY id DESC LIMIT ?", (limit,))

    # --- sources
    def source_due(self, name: str, interval_minutes: float) -> bool:
        rows = self.sql("SELECT last_checked FROM sources WHERE name = ?", (name,))
        return not rows or rows[0]["last_checked"] is None or time.time() - rows[0]["last_checked"] >= interval_minutes * 60

    def source_checked(self, name: str, found: int, error: str | None) -> None:
        self.sql("""INSERT INTO sources (name, last_checked, last_error, found) VALUES (?, ?, ?, ?)
                    ON CONFLICT (name) DO UPDATE SET last_checked = excluded.last_checked,
                    last_error = excluded.last_error, found = excluded.found""", (name, time.time(), error, found))

    def sources(self) -> list[dict]:
        return self.sql("SELECT * FROM sources ORDER BY name")
