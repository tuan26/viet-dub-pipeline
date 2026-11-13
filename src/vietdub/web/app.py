"""The dashboard. Server-rendered pages (Jinja2) plus two small JSON endpoints for the
review editor; no build step, no JavaScript framework, so it is easy to install and to
maintain. Heavy work never runs in a request: the dashboard only changes state, and the
workers pick it up.
"""
from __future__ import annotations

import json
import os
import re
import secrets
import shutil
import threading
import time
from pathlib import Path

from starlette.applications import Starlette
from starlette.concurrency import run_in_threadpool
from starlette.middleware import Middleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse, RedirectResponse, Response
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles
from starlette.templating import Jinja2Templates

from .. import __version__
from ..auto import config as auto_config
from ..auto import qc as qc_module
from ..auto import review_edit
from ..auto.orchestrator import _free_ram_gb, import_sources
from ..auto.store import STATES, Store
from ..models import VietdubError
from .auth import ROLE_LABELS, ROLES, Throttle, allowed, hash_password, validate_password, verify_password

HERE = Path(__file__).parent
STATE_LABELS = {
    "AWAITING_RIGHTS": "Chờ xác minh quyền", "APPROVED": "Chờ tải", "DOWNLOADING": "Đang tải",
    "DOWNLOADED": "Chờ lồng tiếng", "DUBBING": "Đang lồng tiếng", "DUBBED": "Chờ kiểm tra", "CHECKING": "Đang kiểm tra",
    "QC_PASS": "Đạt kiểm tra — chờ duyệt", "NEEDS_REVIEW": "Cần duyệt", "READY": "Đã duyệt", "REJECTED": "Đã từ chối",
    "DUPLICATE": "Trùng nội dung", "FAILED": "Lỗi", "DELETED": "Đã xoá",
}
STATE_GROUP = {
    "AWAITING_RIGHTS": "wait", "APPROVED": "queue", "DOWNLOADED": "queue", "DUBBED": "queue",
    "DOWNLOADING": "busy", "DUBBING": "busy", "CHECKING": "busy", "QC_PASS": "review", "NEEDS_REVIEW": "review",
    "READY": "done", "REJECTED": "off", "DUPLICATE": "off", "DELETED": "off", "FAILED": "error",
}
SOURCE_TYPES = {"folder": "Thư mục trên máy", "manifest": "Danh sách file (TOML)", "channel": "Kênh đã cấp phép (yt-dlp)",
                "archive": "Internet Archive (tìm kiếm)", "commons": "Wikimedia Commons (tìm kiếm)",
                "youtube_cc": "YouTube Creative Commons (tìm kiếm)"}
EDITABLE = ("QC_PASS", "NEEDS_REVIEW", "READY", "REJECTED")
# action: (allowed states, role needed, label)
ACTIONS = {
    "allow": (("AWAITING_RIGHTS",), "admin", "Xác nhận quyền"),
    "deny": (("AWAITING_RIGHTS",), "admin", "Từ chối quyền"),
    "pause": (("AWAITING_RIGHTS", "APPROVED", "DOWNLOADED", "DUBBED", "FAILED", "DOWNLOADING", "DUBBING", "CHECKING"), "reviewer", "Tạm dừng"),
    "resume": (STATES, "reviewer", "Tiếp tục"),
    "retry": (("FAILED",), "reviewer", "Thử lại"),
    "redo": (("QC_PASS", "NEEDS_REVIEW", "READY", "REJECTED", "FAILED"), "reviewer", "Lồng tiếng lại"),
    "recheck": (("QC_PASS", "NEEDS_REVIEW", "READY"), "reviewer", "Chạy lại kiểm tra"),
    "approve": (("QC_PASS", "NEEDS_REVIEW"), "reviewer", "Duyệt bản cuối"),
    "reject": (("QC_PASS", "NEEDS_REVIEW", "READY"), "reviewer", "Từ chối bản cuối"),
    "delete": (tuple(s for s in STATES if s not in ("DOWNLOADING", "DUBBING", "CHECKING", "DELETED")), "admin", "Xoá"),
}


def _ts(value) -> str:
    return time.strftime("%Y-%m-%d %H:%M", time.localtime(value)) if value else ""


def _ago(value) -> str:
    if not value:
        return ""
    s = int(time.time() - value)
    return f"{s}s trước" if s < 90 else f"{s // 60} phút trước" if s < 5400 else f"{s // 3600} giờ trước" if s < 172800 else _ts(value)


def _slug(text: str) -> str:
    return re.sub(r"[^\w.-]+", "_", text)[:60] or "x"


def create_app(config_path: Path) -> Starlette:
    cfg = auto_config.load(Path(config_path))
    local = threading.local()

    def db() -> Store:
        if getattr(local, "store", None) is None:
            local.store = Store(cfg.database)
        return local.store

    boot = db()
    import_sources(cfg, boot)
    secret = boot.setting("secret_key")
    throttle = Throttle()
    templates = Jinja2Templates(directory=str(HERE / "templates"))
    templates.env.filters.update(ts=_ts, ago=_ago, minutes=lambda s: f"{(s or 0) / 60:.1f}",
                                 secs=lambda s: f"{s:.0f}s" if s is not None else "")
    templates.env.globals.update(STATE_LABELS=STATE_LABELS, STATE_GROUP=STATE_GROUP, ROLE_LABELS=ROLE_LABELS,
                                 SOURCE_TYPES=SOURCE_TYPES, QC_LABELS=qc_module.LABELS, LINE_FLAGS=qc_module.LINE_FLAGS,
                                 version=__version__, allowed=allowed, ACTIONS=ACTIONS)

    # --- request helpers
    def user_of(request: Request) -> dict | None:
        name = request.session.get("user")
        if not name:
            return None
        u = db().user(name)
        return u if u and not u["disabled"] else None

    def flash(request: Request, message: str, kind: str = "ok") -> None:
        request.session.setdefault("flash", []).append([kind, message])

    def render(request: Request, name: str, status: int = 200, **ctx) -> Response:
        u = user_of(request)
        messages = request.session.pop("flash", [])
        paused = db().setting("paused") == "1"
        return templates.TemplateResponse(request, name, {"user": u, "csrf": request.session.get("csrf", ""),
                                                          "messages": messages, "system_paused": paused, **ctx},
                                          status_code=status)

    def guard(role: str):
        """Decorator: login required, at least ``role``; POST requests must carry the CSRF token."""
        def wrap(fn):
            async def endpoint(request: Request):
                u = user_of(request)
                if u is None:
                    if request.url.path.startswith("/api/") or request.headers.get("accept", "").startswith("application/json"):
                        return JSONResponse({"error": "Cần đăng nhập."}, status_code=401)
                    return RedirectResponse(f"/login?next={request.url.path}", status_code=303)
                if not allowed(u["role"], role):
                    return render(request, "error.html", 403, message="Tài khoản của bạn không có quyền làm việc này.")
                if request.method == "POST":
                    token = request.headers.get("x-csrf")
                    if token is None and request.headers.get("content-type", "").startswith(("application/x-www-form-urlencoded", "multipart/form-data")):
                        token = (await request.form()).get("csrf")
                    if not token or not secrets.compare_digest(str(token), request.session.get("csrf", "")):
                        return render(request, "error.html", 403, message="Phiên làm việc hết hạn hoặc yêu cầu không hợp lệ. Hãy tải lại trang.")
                request.state.user = u
                return await fn(request)
            return endpoint
        return wrap

    def video_or_404(video_id: str) -> dict | None:
        try:
            return db().get(video_id)
        except VietdubError:
            return None

    # --- login
    async def login(request: Request):
        if not db().users():
            return RedirectResponse("/setup", status_code=303)
        if request.method == "GET":
            return render(request, "login.html", next=request.query_params.get("next", "/"))
        form = await request.form()
        name, password = str(form.get("username", "")).strip(), str(form.get("password", ""))
        nxt = str(form.get("next", "/"))
        nxt = nxt if nxt.startswith("/") and not nxt.startswith("//") else "/"
        key = f"{name}|{request.client.host if request.client else ''}"
        wait = throttle.blocked(key)
        if wait:
            return render(request, "login.html", 429, next=nxt, error=f"Sai quá nhiều lần. Thử lại sau {wait:.0f} giây.")
        u = db().user(name)
        ok = u is not None and not u["disabled"] and await run_in_threadpool(verify_password, password, u["password_hash"])
        if not ok:
            throttle.fail(key)
            return render(request, "login.html", 401, next=nxt, error="Sai tên đăng nhập hoặc mật khẩu.")
        throttle.ok(key)
        request.session.clear()
        request.session.update(user=name, csrf=secrets.token_urlsafe(24))
        db().set_user(name, last_login=time.time())
        return RedirectResponse(nxt, status_code=303)

    async def logout(request: Request):
        request.session.clear()
        return RedirectResponse("/login", status_code=303)

    async def setup(request: Request):
        """The very first account. Available only while the database has no account."""
        if db().users():
            return RedirectResponse("/login", status_code=303)
        if request.method == "GET":
            return render(request, "setup.html")
        form = await request.form()
        name, password = str(form.get("username", "")).strip(), str(form.get("password", ""))
        try:
            if not re.fullmatch(r"[\w.\-]{3,30}", name):
                raise VietdubError("Tên đăng nhập 3–30 ký tự: chữ, số, . _ -")
            validate_password(password)
            if password != form.get("password2"):
                raise VietdubError("Hai lần nhập mật khẩu không khớp.")
        except VietdubError as exc:
            return render(request, "setup.html", 400, error=str(exc), username=name)
        db().add_user(name, await run_in_threadpool(hash_password, password), "admin")
        db().log(None, "human", "info", f"Tạo tài khoản quản trị đầu tiên '{name}'", username=name)
        request.session.clear()
        request.session.update(user=name, csrf=secrets.token_urlsafe(24))
        return RedirectResponse("/", status_code=303)

    # --- dashboard
    def resources() -> dict:
        disk = shutil.disk_usage(cfg.library if cfg.library.exists() else cfg.library.parent)
        try:
            load = os.getloadavg()[0]
        except OSError:
            load = None
        return {"disk_free_gb": disk.free / 1e9, "disk_total_gb": disk.total / 1e9, "ram_free_gb": _free_ram_gb(),
                "load": load, "cpus": os.cpu_count(), "limits": cfg.limits}

    def worker_rows() -> list[dict]:
        rows = db().workers()
        limit = cfg.server["heartbeat_seconds"] * 3 + cfg.server["poll_seconds"] + 30
        for w in rows:
            w["alive"] = w["status"] != "stopped" and time.time() - (w["last_seen"] or 0) < limit
        return rows

    @guard("viewer")
    async def dashboard(request: Request):
        store = db()
        return render(request, "dashboard.html", stats=store.stats(), res=resources(), workers=worker_rows(),
                      sources=store.source_rows(), events=store.events(limit=25), now=time.time())

    @guard("viewer")
    async def api_status(request: Request):
        store = db()
        return JSONResponse({"stats": store.stats(), "workers": worker_rows(), "paused": store.setting("paused") == "1"})

    @guard("admin")
    async def system(request: Request):
        form = await request.form()
        action = form.get("action")
        if action in ("pause", "resume"):
            db().set_setting("paused", "1" if action == "pause" else "0")
            db().log(None, "human", "info", "Tạm dừng toàn hệ thống" if action == "pause" else "Tiếp tục toàn hệ thống",
                     username=request.state.user["username"])
            flash(request, "Đã tạm dừng: worker sẽ không nhận việc mới." if action == "pause" else "Hệ thống tiếp tục chạy.")
        return RedirectResponse(form.get("back") or "/", status_code=303)

    # --- videos
    @guard("viewer")
    async def videos(request: Request):
        state, q, source = (request.query_params.get(k, "") for k in ("state", "q", "source"))
        group = request.query_params.get("group", "")
        rows = [v for v in db().videos() if (not state or v["state"] == state) and (not source or v["source"] == source)
                and (not group or STATE_GROUP.get(v["state"]) == group)
                and (not q or q.lower() in (v["title"] or "").lower() or q.lower() in v["id"].lower())
                and (state == "DELETED" or v["state"] != "DELETED")]
        for v in rows:
            v["qc_summary"] = json.loads(v["qc"]) if v["qc"] else {}
        return render(request, "videos.html", videos=rows, state=state, q=q, source=source, group=group,
                      sources=[s["name"] for s in db().source_rows()])

    @guard("viewer")
    async def video(request: Request):
        v = video_or_404(request.query_params.get("id", ""))
        if v is None:
            return render(request, "error.html", 404, message="Không có video này.")
        out = Path(v["out_dir"]) if v["out_dir"] else None
        qc = json.loads((out / "qc.json").read_text(encoding="utf-8")) if out and (out / "qc.json").exists() else None
        report = json.loads((out / "report.json").read_text(encoding="utf-8")) if out and (out / "report.json").exists() else None
        return render(request, "video.html", v=v, qc=qc, report=report, events=db().events(v["id"], 200),
                      edits=db().edits(v["id"], 200), has_output=bool(report and (out / report["output"]).exists()))

    @guard("viewer")
    async def video_action(request: Request):
        form = await request.form()
        u = request.state.user
        v = video_or_404(str(form.get("id", "")))
        action = str(form.get("action", ""))
        back = f"/video?id={v['id']}" if v else "/videos"
        if v is None or action not in ACTIONS:
            flash(request, "Yêu cầu không hợp lệ.", "error")
            return RedirectResponse("/videos", status_code=303)
        states, role, label = ACTIONS[action]
        if not allowed(u["role"], role):
            flash(request, f"Cần quyền {ROLE_LABELS[role]} để {label.lower()}.", "error")
            return RedirectResponse(back, status_code=303)
        if v["state"] not in states:
            flash(request, f"Không thể {label.lower()} khi video đang ở trạng thái “{STATE_LABELS[v['state']]}”.", "error")
            return RedirectResponse(back, status_code=303)
        note = str(form.get("note", "")).strip()
        store = db()
        try:
            if action in ("allow", "approve") and not note:
                raise VietdubError("Cần ghi chú căn cứ duyệt (ai duyệt, dựa trên gì).")
            if action == "approve":
                qc = json.loads(v["qc"]) if v["qc"] else {}
                if qc.get("critical") and form.get("override") != "1":
                    raise VietdubError("Bản này còn lỗi nghiêm trọng. Đánh dấu “Tôi đã kiểm tra các lỗi nghiêm trọng” nếu vẫn muốn duyệt.")
                store.release(v["id"], "READY")
            elif action == "allow":
                store.release(v["id"], "APPROVED", rights_basis=f"Xác nhận bởi {u['username']}: {note}")
            elif action in ("deny", "reject"):
                store.release(v["id"], "REJECTED")
            elif action == "pause":
                store.update(v["id"], paused=1)
            elif action == "resume":
                store.update(v["id"], paused=0)
            elif action == "retry":
                target = "DOWNLOADED" if v["path"] and Path(v["path"]).exists() else "APPROVED"
                store.release(v["id"], target, attempts=0, next_attempt_at=0, error=None, paused=0)
            elif action == "redo":
                store.release(v["id"], "DOWNLOADED", attempts=0, next_attempt_at=0, error=None, qc=None, paused=0)
            elif action == "recheck":
                store.release(v["id"], "DUBBED", attempts=0, next_attempt_at=0, error=None, paused=0)
            elif action == "delete":
                removed = []
                for target in (v["out_dir"], v["path"]):
                    if not target:
                        continue
                    p = Path(target).resolve()
                    if cfg.library in p.parents and p.exists():  # only files the system made itself
                        shutil.rmtree(p) if p.is_dir() else p.unlink()
                        removed.append(p.name)
                # the row stays so the same video is not downloaded again
                store.release(v["id"], "DELETED", out_dir=None, qc=None, path=None if removed else v["path"])
        except VietdubError as exc:
            flash(request, str(exc), "error")
            return RedirectResponse(back, status_code=303)
        store.log(v["id"], "human", "info", f"{label}" + (f": {note}" if note else ""), username=u["username"])
        flash(request, f"Đã {label.lower()}.")
        return RedirectResponse(back, status_code=303)

    # --- review
    @guard("viewer")
    async def review(request: Request):
        v = video_or_404(request.query_params.get("id", ""))
        if v is None or not v["out_dir"] or not (Path(v["out_dir"]) / "work" / "segments.json").exists():
            return render(request, "error.html", 404, message="Video này chưa có bản lồng tiếng để duyệt.")
        out = Path(v["out_dir"])
        data = await run_in_threadpool(review_edit.load, out)
        report = data["report"]
        version = int((out / report["output"]).stat().st_mtime) if report.get("output") and (out / report["output"]).exists() else 0
        can_edit = allowed(request.state.user["role"], "reviewer") and v["state"] in EDITABLE
        return render(request, "review.html", v=v, data=data, version=version, can_edit=can_edit,
                      edits=db().edits(v["id"], 50), editable_states=[STATE_LABELS[s] for s in EDITABLE])

    @guard("reviewer")
    async def review_save(request: Request):
        body = await request.json()
        v = video_or_404(str(body.get("id", "")))
        if v is None:
            return JSONResponse({"error": "Không có video này."}, status_code=404)
        if v["state"] not in EDITABLE:
            return JSONResponse({"error": f"Không sửa được khi video đang “{STATE_LABELS[v['state']]}”."}, status_code=409)
        u = request.state.user["username"]
        try:
            summary = await run_in_threadpool(review_edit.apply, db(), v["id"], Path(v["out_dir"]), u,
                                              list(body.get("lines") or []), dict(body.get("cast") or {}))
        except VietdubError as exc:
            return JSONResponse({"error": str(exc)}, status_code=400)
        store = db()
        then = body.get("then")
        if then == "rerender":
            store.release(v["id"], "DOWNLOADED", attempts=0, next_attempt_at=0, error=None, qc=None, paused=0)
            message = "Đã lưu. Worker sẽ xuất lại video (chỉ làm lại các câu đã sửa)."
        elif summary["changed_lines"] or summary["voice_changes"]:
            if v["state"] == "READY":
                store.release(v["id"], "NEEDS_REVIEW")  # an approved dub that changed needs approving again
            message = "Đã lưu. Bấm “Lưu và xuất lại” để tạo video mới với các thay đổi."
        else:
            message = "Đã lưu."
        store.log(v["id"], "human", "info",
                  f"Sửa bản lồng tiếng: {summary['changed_lines']} thay đổi câu, {summary['voice_changes']} đổi giọng"
                  + ("; xuất lại" if then == "rerender" else ""), username=u)
        return JSONResponse({"ok": True, "message": message, "summary": summary, "state": store.get(v["id"])["state"]})

    @guard("reviewer")
    async def review_preview(request: Request):
        body = await request.json()
        v = video_or_404(str(body.get("id", "")))
        if v is None or not v["out_dir"]:
            return JSONResponse({"error": "Không có video này."}, status_code=404)
        try:
            path = await run_in_threadpool(review_edit.preview, Path(v["out_dir"]), cfg.dubbing,
                                           str(body.get("text", "")), body.get("voice") or None)
        except VietdubError as exc:
            return JSONResponse({"error": str(exc)}, status_code=400)
        from urllib.parse import quote

        return JSONResponse({"url": f"/media?id={quote(v['id'], safe='')}&kind=preview&name={path.name}"})

    # --- media: only files the database points at
    @guard("viewer")
    async def media(request: Request):
        v = video_or_404(request.query_params.get("id", ""))
        kind = request.query_params.get("kind", "")
        if v is None:
            return Response("Không có video này.", status_code=404)
        out = Path(v["out_dir"]) if v["out_dir"] else None
        report = json.loads((out / "report.json").read_text(encoding="utf-8")) if out and (out / "report.json").exists() else {}
        path, download = None, None
        if kind == "original" and v["path"]:
            path = Path(v["path"])
        elif kind in ("dubbed", "srt", "credits") and report:
            name = {"dubbed": report["output"], "srt": Path(report["output"]).with_suffix(".srt").name, "credits": "CREDITS.txt"}[kind]
            path = out / name
            download = name if request.query_params.get("download") else None
        elif kind == "preview" and out:
            name = request.query_params.get("name", "")
            if re.fullmatch(r"[0-9a-f]{16}\.(mp3|wav)", name):
                path = out / "work" / "previews" / name
        elif kind == "sample" and out:
            try:
                path = await run_in_threadpool(review_edit.sample, out, request.query_params.get("speaker", ""))
            except (VietdubError, Exception):
                path = None
        if path is None or not path.is_file():
            return Response("Không có file.", status_code=404)
        return FileResponse(path, filename=download) if download else FileResponse(path)

    # --- sources
    @guard("viewer")
    async def sources(request: Request):
        store = db()
        counts: dict[str, dict] = {}
        for v in store.videos():
            c = counts.setdefault(v["source"], {"total": 0, "waiting": 0})
            c["total"] += 1
            c["waiting"] += v["state"] == "AWAITING_RIGHTS"
        return render(request, "sources.html", sources=store.source_rows(), counts=counts, now=time.time())

    def source_form_values(form) -> dict:
        keys = ("name", "type", "query", "url", "permission", "attribution", "language", "file", "path", "license",
                "interval_minutes", "limit", "rights")
        return {k: str(form.get(k, "")).strip() for k in keys} | {"enabled": form.get("enabled") == "1"}

    async def save_source(request: Request, existing: dict | None):
        form = await request.form()
        values = source_form_values(form)
        if existing:
            values["name"] = existing["name"]
        options = {k: values[k] for k in ("query", "url", "permission", "attribution", "language", "file", "path", "license") if values[k]}
        evidence = Path(existing["evidence"]) if existing and existing.get("evidence") else None
        upload = form.get("evidence")
        store = db()
        try:
            if not existing and values["name"] in {r["name"] for r in store.source_rows(include_deleted=True)}:
                raise VietdubError(f"Đã có nguồn tên '{values['name']}'.")
            for key in ("path", "file"):
                if options.get(key) and not Path(options[key]).exists():
                    raise VietdubError(f"Không thấy {'thư mục' if key == 'path' else 'file'} {options[key]} trên máy chủ.")
            if upload is not None and getattr(upload, "filename", ""):
                data = await upload.read(int(cfg.server["max_upload_mb"] * 1e6) + 1)
                if len(data) > cfg.server["max_upload_mb"] * 1e6:
                    raise VietdubError(f"File bằng chứng lớn hơn {cfg.server['max_upload_mb']:.0f} MB.")
                folder = cfg.evidence_dir / _slug(values["name"])
                folder.mkdir(parents=True, exist_ok=True)
                evidence = folder / f"{time.strftime('%Y%m%d-%H%M%S')}_{_slug(Path(upload.filename).name)}"
                evidence.write_bytes(data)
            src = auto_config.validate_source(values["name"], values["type"], options, values["rights"] or "needs_approval",
                                              evidence, values["interval_minutes"] or 360, values["limit"] or 10, values["enabled"])
        except VietdubError as exc:
            return render(request, "source_form.html", 400, values=values, existing=existing, error=str(exc))
        store.upsert_source(auto_config.source_to_row(src), "web")
        store.log(None, "human", "info", f"{'Sửa' if existing else 'Thêm'} nguồn {src.name} ({src.type}, quyền: {src.rights})",
                  username=request.state.user["username"])
        flash(request, f"Đã lưu nguồn {src.name}.")
        return RedirectResponse("/sources", status_code=303)

    @guard("admin")
    async def source_new(request: Request):
        if request.method == "GET":
            return render(request, "source_form.html", values={"type": "folder", "rights": "needs_approval", "interval_minutes": "360",
                                                                "limit": "10", "enabled": True}, existing=None)
        return await save_source(request, None)

    @guard("admin")
    async def source_edit(request: Request):
        name = request.query_params.get("name") or ""
        try:
            row = db().source_row(name)
        except VietdubError:
            return render(request, "error.html", 404, message="Không có nguồn này.")
        if request.method == "GET":
            values = {"name": row["name"], "type": row["type"], "interval_minutes": row["interval_minutes"], "limit": row["item_limit"],
                      "rights": row["rights"], "enabled": bool(row["enabled"]), **row["options"]}
            return render(request, "source_form.html", values=values, existing=row)
        return await save_source(request, row)

    @guard("admin")
    async def source_action(request: Request):
        form = await request.form()
        name, action = str(form.get("name", "")), str(form.get("action", ""))
        store = db()
        try:
            store.source_row(name)
        except VietdubError:
            flash(request, "Không có nguồn này.", "error")
            return RedirectResponse("/sources", status_code=303)
        labels = {"enable": "Bật nguồn", "disable": "Tắt nguồn", "check_now": "Kiểm tra ngay", "delete": "Xoá nguồn"}
        if action == "enable":
            store.set_source(name, enabled=1)
        elif action == "disable":
            store.set_source(name, enabled=0)
        elif action == "check_now":
            store.set_source(name, last_checked=None)
        elif action == "delete":
            store.set_source(name, deleted=1, enabled=0)  # kept so pipeline.toml does not bring it back
        else:
            flash(request, "Yêu cầu không hợp lệ.", "error")
            return RedirectResponse("/sources", status_code=303)
        store.log(None, "human", "info", f"{labels[action]} {name}", username=request.state.user["username"])
        flash(request, f"Đã {labels[action].lower()} {name}." + (" Worker sẽ kiểm tra trong vòng chờ kế tiếp." if action == "check_now" else ""))
        return RedirectResponse("/sources", status_code=303)

    @guard("viewer")
    async def source_evidence(request: Request):
        try:
            row = db().source_row(request.query_params.get("name", ""))
        except VietdubError:
            return Response("Không có nguồn này.", status_code=404)
        if not row.get("evidence") or not Path(row["evidence"]).is_file():
            return Response("Nguồn này không có file bằng chứng.", status_code=404)
        return FileResponse(row["evidence"], filename=Path(row["evidence"]).name)

    # --- users
    @guard("admin")
    async def users(request: Request):
        if request.method == "POST":
            form = await request.form()
            name, password, role = (str(form.get(k, "")).strip() for k in ("username", "password", "role"))
            try:
                if not re.fullmatch(r"[\w.\-]{3,30}", name):
                    raise VietdubError("Tên đăng nhập 3–30 ký tự: chữ, số, . _ -")
                if role not in ROLES:
                    raise VietdubError("Vai trò không hợp lệ.")
                validate_password(password)
                if not db().add_user(name, await run_in_threadpool(hash_password, password), role):
                    raise VietdubError(f"Đã có tài khoản '{name}'.")
            except VietdubError as exc:
                flash(request, str(exc), "error")
                return RedirectResponse("/users", status_code=303)
            db().log(None, "human", "info", f"Tạo tài khoản {name} ({ROLE_LABELS[role]})", username=request.state.user["username"])
            flash(request, f"Đã tạo tài khoản {name}.")
            return RedirectResponse("/users", status_code=303)
        return render(request, "users.html", users=db().users())

    @guard("admin")
    async def user_action(request: Request):
        form = await request.form()
        me = request.state.user["username"]
        name, action = str(form.get("username", "")), str(form.get("action", ""))
        store = db()
        target = store.user(name)
        try:
            if not target:
                raise VietdubError("Không có tài khoản này.")
            admins = [u for u in store.users() if u["role"] == "admin" and not u["disabled"]]
            removing_admin = target["role"] == "admin" and (action == "disable" or (action == "role" and form.get("role") != "admin"))
            if removing_admin and len(admins) <= 1:
                raise VietdubError("Phải còn ít nhất một tài khoản quản trị đang hoạt động.")
            if name == me and action in ("disable", "role"):
                raise VietdubError("Không tự khoá hoặc tự đổi vai trò của chính mình.")
            if action == "disable":
                store.set_user(name, disabled=1)
            elif action == "enable":
                store.set_user(name, disabled=0)
            elif action == "role":
                role = str(form.get("role", ""))
                if role not in ROLES:
                    raise VietdubError("Vai trò không hợp lệ.")
                store.set_user(name, role=role)
            elif action == "password":
                password = str(form.get("password", ""))
                validate_password(password)
                store.set_user(name, password_hash=await run_in_threadpool(hash_password, password))
            else:
                raise VietdubError("Yêu cầu không hợp lệ.")
        except VietdubError as exc:
            flash(request, str(exc), "error")
            return RedirectResponse("/users", status_code=303)
        store.log(None, "human", "info", f"Tài khoản {name}: {action}", username=me)
        flash(request, "Đã cập nhật tài khoản.")
        return RedirectResponse("/users", status_code=303)

    # --- history and future phases
    @guard("viewer")
    async def history(request: Request):
        store = db()
        human = [e for e in store.events(limit=400) if e["stage"] == "human"][:150]
        return render(request, "history.html", edits=store.edits(limit=150), human=human)

    @guard("viewer")
    async def publish(request: Request):
        ready = db().videos("READY")
        return render(request, "publish.html", ready=ready)

    async def health(request: Request):
        try:
            db().sql("SELECT 1")
            return JSONResponse({"ok": True, "version": __version__})
        except Exception as exc:
            return JSONResponse({"ok": False, "error": str(exc)}, status_code=503)

    routes = [
        Route("/login", login, methods=["GET", "POST"]), Route("/logout", logout, methods=["POST"]),
        Route("/setup", setup, methods=["GET", "POST"]), Route("/healthz", health),
        Route("/", dashboard), Route("/api/status", api_status), Route("/system", system, methods=["POST"]),
        Route("/videos", videos), Route("/video", video), Route("/video/action", video_action, methods=["POST"]),
        Route("/review", review), Route("/review/save", review_save, methods=["POST"]),
        Route("/review/preview", review_preview, methods=["POST"]), Route("/media", media),
        Route("/sources", sources), Route("/source/new", source_new, methods=["GET", "POST"]),
        Route("/source/edit", source_edit, methods=["GET", "POST"]), Route("/source/action", source_action, methods=["POST"]),
        Route("/source/evidence", source_evidence),
        Route("/users", users, methods=["GET", "POST"]), Route("/user/action", user_action, methods=["POST"]),
        Route("/history", history), Route("/publish", publish),
        Mount("/static", StaticFiles(directory=str(HERE / "static")), name="static"),
    ]
    middleware = [Middleware(SessionMiddleware, secret_key=secret, session_cookie="vietdub_session", max_age=12 * 3600,
                             same_site="lax", https_only=bool(os.environ.get("VIETDUB_HTTPS_ONLY")))]
    app = Starlette(routes=routes, middleware=middleware)
    app.state.config = cfg
    return app
