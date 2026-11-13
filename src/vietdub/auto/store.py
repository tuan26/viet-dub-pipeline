"""State of every video, source, worker, user and edit, in PostgreSQL (production) or
SQLite (single machine, tests).

All state changes go through here so that two workers never process the same video and
an interrupted run can be resumed. The schema is versioned: opening an older database
upgrades it in place without touching existing rows.
"""
from __future__ import annotations

import json
import secrets
import time
from pathlib import Path

from ..models import TransientError, VietdubError

# state -> the in-progress state a worker moves it to while working on it
WORK = {"APPROVED": "DOWNLOADING", "DOWNLOADED": "DUBBING", "DUBBED": "CHECKING"}
BACK = {v: k for k, v in WORK.items()}
STATES = ("AWAITING_RIGHTS", "APPROVED", "DOWNLOADING", "DOWNLOADED", "DUBBING", "DUBBED", "CHECKING",
          "QC_PASS", "NEEDS_REVIEW", "READY", "REJECTED", "DUPLICATE", "FAILED", "DELETED")
FIELDS = ("id", "source", "title", "page_url", "download_url", "license", "attribution", "language", "permission",
          "rights_basis", "state", "content_hash", "path", "out_dir", "duration", "attempts", "next_attempt_at",
          "error", "qc", "locked_by", "locked_at", "created_at", "updated_at")
SCHEMA_VERSION = 2


class Store:
    def __init__(self, url: str):
        self.url = url
        self.pg = url.startswith(("postgresql://", "postgres://"))
        self._connect()
        self._migrate()

    # --- connection
    def _connect(self) -> None:
        if self.pg:
            try:
                import psycopg
                from psycopg.rows import dict_row
            except ImportError:
                raise VietdubError("Thiếu driver PostgreSQL. Chạy: pip install 'vietdub[auto]'")
            try:
                # client_encoding: a database created with the default SQL_ASCII encoding would
                # otherwise hand text back as bytes.
                self.db = psycopg.connect(self.url, autocommit=True, row_factory=dict_row,
                                          client_encoding="utf8", connect_timeout=10)
            except psycopg.Error as exc:
                raise TransientError(f"Không kết nối được PostgreSQL: {exc}")
        else:
            import sqlite3

            path = self.url.removeprefix("sqlite:///")
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            self.db = sqlite3.connect(path, isolation_level=None, timeout=30, check_same_thread=False)
            self.db.row_factory = sqlite3.Row
            self.db.execute("PRAGMA journal_mode=WAL")  # readers do not block the writer
            self.db.execute("PRAGMA busy_timeout=30000")

    def sql(self, query: str, params: tuple = ()) -> list[dict]:
        """Run one statement. A PostgreSQL connection lost (server restart, network) is
        reopened once; the statement is retried only when it never reached the server."""
        if self.pg:
            import psycopg

            if self.db.broken or self.db.closed:
                self._connect()
            try:
                cur = self.db.execute(query.replace("?", "%s"), params)
            except psycopg.OperationalError:
                if not (self.db.broken or self.db.closed):
                    raise
                # the server went away (restart, network): wait for it a little before giving up
                for wait in (0.5, 1, 2, 4, 8):
                    try:
                        self._connect()
                        break
                    except TransientError:
                        time.sleep(wait)
                else:
                    self._connect()
                cur = self.db.execute(query.replace("?", "%s"), params)
        else:
            cur = self.db.execute(query, params)
        if cur.description is None:
            return []
        return [dict(r) for r in cur.fetchall()]

    def close(self) -> None:
        try:
            self.db.close()
        except Exception:
            pass

    # --- schema
    def _columns(self, table: str) -> set[str]:
        if self.pg:
            rows = self.sql("SELECT column_name FROM information_schema.columns WHERE table_name = ?", (table,))
            return {r["column_name"] for r in rows}
        return {r["name"] for r in self.sql(f"PRAGMA table_info({table})")}

    def _add_column(self, table: str, column: str, decl: str) -> None:
        if column not in self._columns(table):
            self.sql(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")

    def _migrate(self) -> None:
        """Bring the schema to SCHEMA_VERSION. Several processes may start at once, so the
        upgrade runs under a lock and every step is safe to repeat."""
        if self.pg:
            self.sql("SELECT pg_advisory_lock(73519)")
        else:
            self.sql("BEGIN IMMEDIATE")
        try:
            self.sql("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
            rows = self.sql("SELECT value FROM settings WHERE key = 'schema_version'")
            version = int(rows[0]["value"]) if rows else 0
            if version > SCHEMA_VERSION:
                raise VietdubError(f"Cơ sở dữ liệu ở phiên bản {version}, mới hơn phần mềm ({SCHEMA_VERSION}). Hãy nâng cấp vietdub.")
            if version < 1:
                self._v1()
            if version < 2:
                self._v2()
            self.set_setting("schema_version", str(SCHEMA_VERSION))
            if not self.setting("secret_key"):
                self.set_setting("secret_key", secrets.token_hex(32))
        finally:
            if self.pg:
                self.sql("SELECT pg_advisory_unlock(73519)")
            else:
                self.sql("COMMIT")

    def _v1(self) -> None:
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

    def _v2(self) -> None:
        serial = "BIGSERIAL PRIMARY KEY" if self.pg else "INTEGER PRIMARY KEY AUTOINCREMENT"
        real = "DOUBLE PRECISION" if self.pg else "REAL"
        for column, decl in (("paused", "INTEGER NOT NULL DEFAULT 0"), ("progress", "TEXT")):
            self._add_column("videos", column, decl)
        self._add_column("events", "username", "TEXT")
        for column, decl in (("type", "TEXT"), ("options", "TEXT"), ("interval_minutes", real), ("item_limit", "INTEGER"),
                             ("rights", "TEXT"), ("evidence", "TEXT"), ("enabled", "INTEGER NOT NULL DEFAULT 1"),
                             ("deleted", "INTEGER NOT NULL DEFAULT 0"), ("origin", "TEXT"),
                             ("created_at", real), ("updated_at", real)):
            self._add_column("sources", column, decl)
        self.sql(f"""CREATE TABLE IF NOT EXISTS workers (
            name TEXT PRIMARY KEY, pid INTEGER, host TEXT, status TEXT, video_id TEXT, stage TEXT,
            started_at {real}, last_seen {real})""")
        self.sql(f"""CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY, password_hash TEXT NOT NULL, role TEXT NOT NULL,
            disabled INTEGER NOT NULL DEFAULT 0, created_at {real} NOT NULL, last_login {real})""")
        self.sql(f"""CREATE TABLE IF NOT EXISTS edits (
            id {serial}, video_id TEXT NOT NULL, ts {real} NOT NULL, username TEXT, kind TEXT,
            line_index INTEGER, field TEXT, old_value TEXT, new_value TEXT)""")
        self.sql("CREATE INDEX IF NOT EXISTS events_video ON events (video_id, id)")
        self.sql("CREATE INDEX IF NOT EXISTS edits_video ON edits (video_id, id)")

    # --- settings
    def setting(self, key: str, default: str | None = None) -> str | None:
        rows = self.sql("SELECT value FROM settings WHERE key = ?", (key,))
        return rows[0]["value"] if rows else default

    def set_setting(self, key: str, value: str) -> None:
        self.sql("INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT (key) DO UPDATE SET value = excluded.value",
                 (key, value))

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
        Another worker calling at the same moment gets a different video. Paused videos
        and videos waiting for a retry are skipped."""
        skip = " FOR UPDATE SKIP LOCKED" if self.pg else ""
        now = time.time()
        rows = self.sql(
            f"""UPDATE videos SET state = ?, locked_by = ?, locked_at = ?, updated_at = ?, progress = NULL
                WHERE id = (SELECT id FROM videos WHERE state = ? AND next_attempt_at <= ? AND paused = 0
                            ORDER BY created_at, id LIMIT 1{skip}) RETURNING *""",
            (WORK[state], worker, now, now, state, now))
        return rows[0] if rows else None

    def touch(self, video_id: str, worker: str) -> None:
        """Heartbeat for a video being worked on, so it is not mistaken for abandoned work."""
        self.sql("UPDATE videos SET locked_at = ? WHERE id = ? AND locked_by = ?", (time.time(), video_id, worker))

    def release(self, video_id: str, state: str, **fields) -> None:
        self.update(video_id, state=state, locked_by=None, locked_at=None, **fields)

    def recover_stale(self, older_than_seconds: float) -> list[str]:
        """Videos whose worker stopped sending heartbeats go back to the queue; their work
        folder is kept, so the dubbing step resumes instead of starting over."""
        cutoff = time.time() - older_than_seconds
        recovered = []
        for row in self.sql("SELECT id, state, locked_by FROM videos WHERE locked_at IS NOT NULL AND locked_at < ?", (cutoff,)):
            if row["state"] in BACK:
                # only if nobody touched it in between
                done = self.sql("""UPDATE videos SET state = ?, locked_by = NULL, locked_at = NULL, updated_at = ?
                                   WHERE id = ? AND locked_at < ? RETURNING id""",
                                (BACK[row["state"]], time.time(), row["id"], cutoff))
                if done:
                    self.log(row["id"], "recover", "warning",
                             f"Trả lại hàng đợi: {row['locked_by']} ngừng báo hoạt động khi đang ở {row['state']}")
                    recovered.append(row["id"])
        return recovered

    def by_hash(self, content_hash: str, not_id: str) -> dict | None:
        rows = self.sql("""SELECT * FROM videos WHERE content_hash = ? AND id <> ? AND state NOT IN ('DUPLICATE', 'DELETED')
                           LIMIT 1""", (content_hash, not_id))
        return rows[0] if rows else None

    def minutes_dubbed_since(self, since: float) -> float:
        rows = self.sql("SELECT COALESCE(SUM(seconds), 0) AS total FROM events WHERE stage = 'dub' AND level = 'done' AND ts >= ?", (since,))
        return float(rows[0]["total"]) / 60

    def stats(self) -> dict:
        by_state = {r["state"]: r["n"] for r in self.sql("SELECT state, COUNT(*) AS n FROM videos GROUP BY state")}
        total = self.sql("SELECT COUNT(*) AS n, COALESCE(SUM(duration), 0) AS secs FROM videos WHERE state <> 'DELETED'")[0]
        done = self.sql("SELECT COALESCE(SUM(duration), 0) AS secs FROM videos WHERE state IN ('QC_PASS', 'NEEDS_REVIEW', 'READY')")[0]
        day = time.time() - 86400
        dub_secs = self.sql("SELECT COALESCE(SUM(seconds), 0) AS s FROM events WHERE stage = 'dub' AND level = 'info' AND ts >= ?", (day,))[0]
        return {"by_state": by_state, "videos": total["n"], "minutes": float(total["secs"]) / 60,
                "minutes_dubbed": float(done["secs"]) / 60, "minutes_today": self.minutes_dubbed_since(day),
                "processing_seconds_24h": float(dub_secs["s"])}

    # --- log
    def log(self, video_id: str | None, stage: str, level: str, message: str, seconds: float | None = None,
            username: str | None = None) -> None:
        self.sql("INSERT INTO events (video_id, ts, stage, level, message, seconds, username) VALUES (?, ?, ?, ?, ?, ?, ?)",
                 (video_id, time.time(), stage, level, message[:4000], seconds, username))

    def events(self, video_id: str | None = None, limit: int = 50) -> list[dict]:
        if video_id:
            return self.sql("SELECT * FROM events WHERE video_id = ? ORDER BY id DESC LIMIT ?", (video_id, limit))
        return self.sql("SELECT * FROM events ORDER BY id DESC LIMIT ?", (limit,))

    # --- sources
    def upsert_source(self, src: dict, origin: str, replace: bool = True) -> bool:
        """Insert or (when ``replace``) update a source definition. Returns True when written."""
        now = time.time()
        values = (src["name"], src["type"], json.dumps(src.get("options", {}), ensure_ascii=False),
                  float(src.get("interval_minutes", 360)), int(src.get("limit", 10)), src.get("rights", "needs_approval"),
                  src.get("evidence") or None, 1 if src.get("enabled", True) else 0, origin, now, now)
        conflict = ("""DO UPDATE SET type = excluded.type, options = excluded.options, interval_minutes = excluded.interval_minutes,
                       item_limit = excluded.item_limit, rights = excluded.rights, evidence = excluded.evidence,
                       enabled = excluded.enabled, deleted = 0, updated_at = excluded.updated_at""" if replace else "DO NOTHING")
        rows = self.sql(f"""INSERT INTO sources (name, type, options, interval_minutes, item_limit, rights, evidence, enabled,
                            origin, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            ON CONFLICT (name) {conflict} RETURNING name""", values)
        return bool(rows)

    def source_rows(self, include_deleted: bool = False) -> list[dict]:
        where = "" if include_deleted else "WHERE deleted = 0"
        rows = self.sql(f"SELECT * FROM sources {where} ORDER BY name")
        for r in rows:
            r["options"] = json.loads(r["options"]) if r.get("options") else {}
        return rows

    def source_row(self, name: str) -> dict:
        rows = [r for r in self.source_rows(include_deleted=True) if r["name"] == name]
        if not rows:
            raise VietdubError(f"Không có nguồn '{name}'.")
        return rows[0]

    def set_source(self, name: str, **fields) -> None:
        fields["updated_at"] = time.time()
        sets = ", ".join(f"{k} = ?" for k in fields)
        self.sql(f"UPDATE sources SET {sets} WHERE name = ?", (*fields.values(), name))

    def claim_source(self, name: str, interval_minutes: float) -> bool:
        """True for exactly one caller when the source is due for a check."""
        now = time.time()
        rows = self.sql("""UPDATE sources SET last_checked = ? WHERE name = ? AND enabled = 1 AND deleted = 0
                           AND (last_checked IS NULL OR last_checked <= ?) RETURNING name""",
                        (now, name, now - interval_minutes * 60))
        return bool(rows)

    def source_due(self, name: str, interval_minutes: float) -> bool:
        rows = self.sql("SELECT last_checked FROM sources WHERE name = ?", (name,))
        return not rows or rows[0]["last_checked"] is None or time.time() - rows[0]["last_checked"] >= interval_minutes * 60

    def source_checked(self, name: str, found: int, error: str | None) -> None:
        self.sql("""INSERT INTO sources (name, last_checked, last_error, found) VALUES (?, ?, ?, ?)
                    ON CONFLICT (name) DO UPDATE SET last_checked = excluded.last_checked,
                    last_error = excluded.last_error, found = excluded.found""", (name, time.time(), error, found))

    def sources(self) -> list[dict]:
        return self.sql("SELECT * FROM sources WHERE deleted = 0 ORDER BY name")

    # --- workers
    def worker_beat(self, name: str, pid: int, host: str, status: str, video_id: str | None = None,
                    stage: str | None = None, started: bool = False) -> None:
        now = time.time()
        self.sql("""INSERT INTO workers (name, pid, host, status, video_id, stage, started_at, last_seen)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT (name) DO UPDATE SET pid = excluded.pid, host = excluded.host,
                    status = excluded.status, video_id = excluded.video_id, stage = excluded.stage, last_seen = excluded.last_seen"""
                 + (", started_at = excluded.started_at" if started else ""),
                 (name, pid, host, status, video_id, stage, now, now))

    def workers(self) -> list[dict]:
        return self.sql("SELECT * FROM workers ORDER BY name")

    # --- users
    def users(self) -> list[dict]:
        return self.sql("SELECT username, role, disabled, created_at, last_login FROM users ORDER BY username")

    def user(self, username: str) -> dict | None:
        rows = self.sql("SELECT * FROM users WHERE username = ?", (username,))
        return rows[0] if rows else None

    def add_user(self, username: str, password_hash: str, role: str) -> bool:
        return bool(self.sql("""INSERT INTO users (username, password_hash, role, created_at) VALUES (?, ?, ?, ?)
                                ON CONFLICT (username) DO NOTHING RETURNING username""",
                             (username, password_hash, role, time.time())))

    def set_user(self, username: str, **fields) -> None:
        sets = ", ".join(f"{k} = ?" for k in fields)
        self.sql(f"UPDATE users SET {sets} WHERE username = ?", (*fields.values(), username))

    # --- edit history
    def record_edit(self, video_id: str, username: str, kind: str, line_index: int | None, field: str,
                    old: str | None, new: str | None) -> None:
        self.sql("""INSERT INTO edits (video_id, ts, username, kind, line_index, field, old_value, new_value)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)""", (video_id, time.time(), username, kind, line_index, field, old, new))

    def edits(self, video_id: str | None = None, limit: int = 200) -> list[dict]:
        if video_id:
            return self.sql("SELECT * FROM edits WHERE video_id = ? ORDER BY id DESC LIMIT ?", (video_id, limit))
        return self.sql("SELECT * FROM edits ORDER BY id DESC LIMIT ?", (limit,))
