"""Dashboard end to end with a test client: real pipeline (beep voice, fake recognition),
real automatic checks, SQLite."""
import json
import re
import shutil
import subprocess
from pathlib import Path
from urllib.parse import quote

import pytest
from starlette.testclient import TestClient

from vietdub.auto import config as auto_config
from vietdub.auto import orchestrator
from vietdub.auto.store import Store
from vietdub.engines import asr
from vietdub.models import Segment
from vietdub.web.app import create_app

pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")


@pytest.fixture
def project(tmp_path, monkeypatch):
    (tmp_path / "videos").mkdir()
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "testsrc=duration=6:size=160x120:rate=10",
                    "-f", "lavfi", "-i", "sine=frequency=220:duration=6", "-shortest", str(tmp_path / "videos" / "clip.mp4")], check=True)
    (tmp_path / "pipeline.toml").write_text('''
[storage]
library = "library"
[dubbing]
tts = "beep"
translator = "none"
[[source]]
name = "mine"
type = "folder"
path = "videos"
license = "owned"
rights = "verified"
''', encoding="utf-8")
    monkeypatch.setattr(asr, "transcribe", lambda audio, language, model, vad=True: [
        Segment(1, 0.5, 1.5, "Hello 12"), Segment(2, 2.0, 3.0, "我没有时间"), Segment(3, 4.0, 5.0, "Bye")])
    return tmp_path


def processed(project) -> tuple[auto_config.Config, Store, str]:
    cfg = auto_config.load(project / "pipeline.toml")
    store = Store(cfg.database)
    orchestrator.run_once(cfg, store, log=lambda m: None)
    return cfg, store, store.videos()[0]["id"]


def client(project) -> TestClient:
    return TestClient(create_app(project / "pipeline.toml"))


def login(c: TestClient, name: str, password: str = "secret123") -> str:
    r = c.post("/login", data={"username": name, "password": password}, follow_redirects=False)
    assert r.status_code == 303, r.text
    return csrf_of(c)


def csrf_of(c: TestClient) -> str:
    return re.search(r'<meta name="csrf" content="([^"]+)"', c.get("/videos").text).group(1)


def setup_admin(c: TestClient) -> str:
    r = c.post("/setup", data={"username": "admin", "password": "secret123", "password2": "secret123"}, follow_redirects=False)
    assert r.status_code == 303
    return csrf_of(c)


def add_user(c, csrf, name, role):
    r = c.post("/users", data={"csrf": csrf, "username": name, "password": "secret123", "role": role}, follow_redirects=False)
    assert r.status_code == 303


def test_first_run_setup_then_login_required(project):
    c = client(project)
    assert c.get("/", follow_redirects=False).headers["location"].startswith("/login")
    assert c.get("/login", follow_redirects=False).headers["location"] == "/setup"
    setup_admin(c)
    other = client(project)
    assert other.get("/setup", follow_redirects=False).headers["location"] == "/login"  # only once
    assert other.post("/login", data={"username": "admin", "password": "wrong-pass"}).status_code == 401
    for _ in range(5):
        other.post("/login", data={"username": "admin", "password": "wrong-pass"})
    assert other.post("/login", data={"username": "admin", "password": "secret123"}).status_code == 429  # locked for a while


def test_every_page_renders(project):
    _, _, vid = processed(project)
    c = client(project)
    setup_admin(c)
    for path in ["/", "/videos", "/sources", "/source/new", "/source/edit?name=mine", "/users", "/history", "/publish",
                 f"/video?id={quote(vid)}", f"/review?id={quote(vid)}", "/api/status", "/healthz"]:
        r = c.get(path)
        assert r.status_code == 200, path
        assert "Traceback" not in r.text


def test_post_without_csrf_token_is_refused(project):
    c = client(project)
    setup_admin(c)
    assert c.post("/system", data={"action": "pause"}).status_code == 403
    assert c.post("/system", data={"action": "pause", "csrf": "bad"}).status_code == 403


def test_roles(project):
    _, store, vid = processed(project)
    admin = client(project)
    token = setup_admin(admin)
    add_user(admin, token, "viewer1", "viewer")
    add_user(admin, token, "reviewer1", "reviewer")
    viewer = client(project)
    t = login(viewer, "viewer1")
    assert viewer.post("/review/save", json={"id": vid, "lines": [], "cast": {}}, headers={"X-CSRF": t}).status_code == 403
    assert viewer.get("/users").status_code == 403
    reviewer = client(project)
    t = login(reviewer, "reviewer1")
    assert reviewer.get("/source/new").status_code == 403
    r = reviewer.post("/video/action", data={"csrf": t, "id": vid, "action": "delete"}, follow_redirects=True)
    assert "quyền" in r.text and store.get(vid)["state"] != "DELETED"


def test_review_edit_history_and_rerender(project):
    cfg, store, vid = processed(project)
    out = Path(store.get(vid)["out_dir"])
    assert json.loads((out / "qc.json").read_text())["lines"]["2"] == ["chua_dich"]  # Chinese left in (translator none)
    c = client(project)
    token = setup_admin(c)
    before = len(list((out / "work" / "clips").glob("00002_*")))
    r = c.post("/review/save", headers={"X-CSRF": token}, json={"id": vid, "cast": {}, "lines": [
        {"index": 2, "translation": "Tôi không có thời gian."}, {"index": 3, "skip": True}]})
    assert r.status_code == 200 and r.json()["summary"]["changed_lines"] == 2
    assert before and not list((out / "work" / "clips").glob("00002_*"))  # only stale clips removed
    assert list((out / "work" / "clips").glob("00001_*"))
    segs = {s["index"]: s for s in json.loads((out / "work" / "segments.json").read_text())}
    assert segs[2]["translation"] == "Tôi không có thời gian." and segs[3]["translation"] == "—"
    kinds = sorted(e["kind"] for e in store.edits(vid))
    assert kinds == ["skip", "translation"] and all(e["username"] == "admin" for e in store.edits(vid))
    assert c.post("/review/save", headers={"X-CSRF": token}, json={"id": vid, "lines": [{"index": 1, "translation": ""}], "cast": {}}).status_code == 400

    r = c.post("/review/save", headers={"X-CSRF": token}, json={"id": vid, "lines": [], "cast": {}, "then": "rerender"})
    assert r.json()["state"] == "DOWNLOADED"
    assert c.post("/review/save", headers={"X-CSRF": token}, json={"id": vid, "lines": [], "cast": {}}).status_code == 409  # busy
    orchestrator.run_once(cfg, store, log=lambda m: None)
    qc = json.loads((out / "qc.json").read_text())
    assert "2" not in qc["lines"] and store.get(vid)["state"] in ("QC_PASS", "NEEDS_REVIEW")
    assert "Tôi không có thời gian." in next(out.glob("*.vi.srt")).read_text(encoding="utf-8")


def test_approve_needs_note_and_override_for_critical(project):
    _, store, vid = processed(project)
    store.update(vid, state="NEEDS_REVIEW", qc=json.dumps({"critical": 1, "warnings": 0, "reasons": ["x"]}))
    c = client(project)
    token = setup_admin(c)
    c.post("/video/action", data={"csrf": token, "id": vid, "action": "approve"})
    assert store.get(vid)["state"] == "NEEDS_REVIEW"
    c.post("/video/action", data={"csrf": token, "id": vid, "action": "approve", "note": "ok"})
    assert store.get(vid)["state"] == "NEEDS_REVIEW"
    c.post("/video/action", data={"csrf": token, "id": vid, "action": "approve", "note": "đã xem", "override": "1"})
    assert store.get(vid)["state"] == "READY"
    assert any(e["username"] == "admin" and "đã xem" in e["message"] for e in store.events(vid))


def test_pause_resume_and_delete_keeps_the_row(project):
    cfg, store, vid = processed(project)
    c = client(project)
    token = setup_admin(c)
    store.update(vid, state="APPROVED")
    c.post("/video/action", data={"csrf": token, "id": vid, "action": "pause"})
    assert store.claim("APPROVED", "w") is None
    c.post("/video/action", data={"csrf": token, "id": vid, "action": "resume"})
    store.update(vid, state="NEEDS_REVIEW")
    out = Path(store.get(vid)["out_dir"])
    c.post("/video/action", data={"csrf": token, "id": vid, "action": "delete"})
    row = store.get(vid)
    assert row["state"] == "DELETED" and not out.exists()
    assert (project / "videos" / "clip.mp4").exists()  # the user's own file is not touched
    orchestrator.run_once(cfg, store, log=lambda m: None)
    assert len(store.videos()) == 1  # not discovered again


def test_sources_rules_and_evidence(project, tmp_path):
    cfg, store, _ = processed(project)
    c = client(project)
    token = setup_admin(c)
    folder = tmp_path / "other"
    folder.mkdir()
    base = {"csrf": token, "type": "folder", "path": str(folder), "license": "licensed", "interval_minutes": "30",
            "limit": "5", "rights": "verified", "enabled": "1"}
    r = c.post("/source/new", data={**base, "name": "studio"})
    assert r.status_code == 400 and "bằng chứng" in r.text
    r = c.post("/source/new", data={**base, "name": "studio"}, files={"evidence": ("hop-dong.pdf", b"%PDF-1.4 test", "application/pdf")},
               follow_redirects=False)
    assert r.status_code == 303
    row = store.source_row("studio")
    assert row["rights"] == "verified" and Path(row["evidence"]).read_bytes() == b"%PDF-1.4 test"
    assert c.get("/source/evidence?name=studio").content == b"%PDF-1.4 test"
    r = c.post("/source/new", data={**base, "name": "search", "type": "archive", "query": "film"})
    assert r.status_code == 400 and "tự khai" in r.text
    c.post("/source/action", data={"csrf": token, "name": "studio", "action": "disable"})
    assert store.source_row("studio")["enabled"] == 0
    c.post("/source/action", data={"csrf": token, "name": "mine", "action": "delete"})
    orchestrator.run_once(cfg, store, log=lambda m: None)
    assert store.source_row("mine")["deleted"] == 1  # pipeline.toml does not bring it back


def test_media_serves_only_known_files(project):
    _, _, vid = processed(project)
    c = client(project)
    setup_admin(c)
    assert c.get(f"/media?id={quote(vid)}&kind=dubbed", headers={"Range": "bytes=0-9"}).status_code == 206
    assert c.get(f"/media?id={quote(vid)}&kind=preview&name=../../report.json").status_code == 404
    assert c.get(f"/media?id={quote(vid)}&kind=nothing").status_code == 404


def test_last_admin_cannot_be_removed(project):
    c = client(project)
    token = setup_admin(c)
    add_user(c, token, "boss2", "reviewer")
    c.post("/user/action", data={"csrf": token, "username": "admin", "action": "disable"})
    assert Store(auto_config.load(project / "pipeline.toml").database).user("admin")["disabled"] == 0
