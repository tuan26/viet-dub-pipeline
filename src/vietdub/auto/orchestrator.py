"""One pass of the unattended flow: discover -> download -> dub -> check.

Each video moves through the states in store.py. A step that fails for a passing reason
(network, a service not answering, not enough disk or memory right now) is retried later
with a growing delay; any other failure stops that video and is shown to the user.
"""
from __future__ import annotations

import argparse
import hashlib
import shutil
import time
import traceback
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .. import media
from ..ingest import fetch as ingest_fetch
from ..ingest import net
from ..ingest.catalog import Item
from ..models import TransientError, VietdubError
from ..rights import check_rights
from . import qc as qc_module
from . import sources as sources_module
from .config import Config
from .store import Store


class Defer(Exception):
    """Not a failure: the video waits until ``until`` (budget used up for today)."""

    def __init__(self, until: float, reason: str):
        super().__init__(reason)
        self.until = until


def _item(video: dict) -> Item:
    return Item(id=video["id"], source=video["source"], title=video["title"] or "", page_url=video["page_url"] or "",
                license=video["license"] or "", attribution=video["attribution"] or "", language=video["language"] or "",
                download_url=video["download_url"] or "", permission=video["permission"] or "", path=video["path"] or "")


def _free_ram_gb() -> float | None:
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            if line.startswith("MemAvailable:"):
                return int(line.split()[1]) / 1e6
    except OSError:
        pass
    return None


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()


def download(cfg: Config, store: Store, video: dict) -> dict:
    limits = cfg.limits
    cfg.library.mkdir(parents=True, exist_ok=True)
    free = shutil.disk_usage(cfg.library).free / 1e9
    if free < limits["min_free_gb"]:
        raise TransientError(f"Đĩa chỉ còn {free:.1f} GB, dưới mức tối thiểu {limits['min_free_gb']} GB.")
    item = _item(video)
    local = bool(item.path) and Path(item.path).is_file()
    if local:
        path = Path(item.path)
    else:
        if item.download_url:
            try:
                req = urllib.request.Request(item.download_url, method="HEAD", headers={"User-Agent": net.USER_AGENT})
                size = int(urllib.request.urlopen(req, timeout=30).headers.get("Content-Length") or 0)
            except Exception:
                size = 0  # the server gave no size; the limit is checked again after the download
            if size > limits["max_download_mb"] * 1e6:
                raise VietdubError(f"File {size / 1e6:.0f} MB vượt giới hạn {limits['max_download_mb']} MB.")
        path = ingest_fetch.fetch_item(item, cfg.library)
    try:
        if path.stat().st_size > limits["max_download_mb"] * 1e6:
            raise VietdubError(f"File {path.stat().st_size / 1e6:.0f} MB vượt giới hạn {limits['max_download_mb']} MB.")
        seconds = media.duration(path)
        if seconds > limits["max_video_minutes"] * 60:
            raise VietdubError(f"Video dài {seconds / 60:.1f} phút, vượt giới hạn {limits['max_video_minutes']} phút.")
        digest = _sha256(path)
    except VietdubError:
        if not local:
            path.unlink(missing_ok=True)
        raise
    twin = store.by_hash(digest, video["id"])
    if twin:
        if not local:
            path.unlink(missing_ok=True)
        return {"state": "DUPLICATE", "content_hash": digest, "duration": seconds, "error": f"Trùng nội dung với {twin['id']}"}
    return {"state": "DOWNLOADED", "content_hash": digest, "duration": seconds, "path": str(path), "download_url": item.download_url}


def dub(cfg: Config, store: Store, video: dict) -> dict:
    from .. import cli, pipeline

    limits = cfg.limits
    ram = _free_ram_gb()
    if ram is not None and ram < limits["min_free_ram_gb"]:
        raise TransientError(f"RAM trống {ram:.1f} GB, dưới mức tối thiểu {limits['min_free_ram_gb']} GB.")
    midnight = time.mktime(time.localtime()[:3] + (0, 0, 0, 0, 0, -1))
    used = store.minutes_dubbed_since(midnight)
    minutes = (video["duration"] or 0) / 60
    if used + minutes > limits["daily_minutes"]:
        raise Defer(midnight + 86400, f"Hết hạn mức hôm nay ({used:.0f}/{limits['daily_minutes']:.0f} phút); chờ sang ngày mai.")
    source = (video["page_url"] or "") + (f" — {video['permission']}" if video["permission"] else "")
    rights = check_rights(video["license"], source, video["attribution"])
    args = argparse.Namespace(**{k: (Path(v) if k in ("glossary", "speaker_model") and v else v) for k, v in cfg.dubbing.items()})
    out_dir = cfg.library / "dubbed" / _item(video).slug()
    job = cli._job(args, Path(video["path"]), out_dir, rights, None, args.lang or cli._language(video["language"] or ""))
    job.log = lambda message: None
    started = time.time()
    pipeline.run(job)
    store.log(video["id"], "dub", "done", f"Lồng tiếng xong trong {time.time() - started:.0f}s", seconds=video["duration"])
    return {"state": "DUBBED", "out_dir": str(out_dir)}


def check(cfg: Config, store: Store, video: dict) -> dict:
    result = qc_module.check(Path(video["out_dir"]), cfg.qc)
    return {"state": result["status"], "qc": {"status": result["status"], "reasons": result["reasons"]}}


@dataclass
class Steps:
    discover: Callable = sources_module.discover
    download: Callable = download
    dub: Callable = dub
    check: Callable = check


def discover(cfg: Config, store: Store, steps: Steps, dry_run: bool, log: Callable[[str], None]) -> dict:
    counts = {"new": 0, "awaiting_rights": 0, "known": 0, "bad_licence": 0, "source_errors": 0}
    for source in cfg.sources:
        if not dry_run and not store.source_due(source.name, source.interval_minutes):
            continue
        try:
            items = steps.discover(source)
        except VietdubError as exc:
            counts["source_errors"] += 1
            log(f"Nguồn {source.name}: lỗi — {exc}")
            if not dry_run:
                store.source_checked(source.name, 0, str(exc))
                store.log(None, "discover", "error", f"{source.name}: {exc}")
            continue
        new = 0
        for item in items:
            try:
                check_rights(item.license, item.page_url, item.attribution)
            except VietdubError as exc:
                counts["bad_licence"] += 1
                log(f"  bỏ {item.id}: {exc}")
                continue
            verified = source.rights == "verified"
            basis = (f"nguồn đã xác minh ({source.evidence.name if source.evidence else 'tự sở hữu'})" if verified
                     else "chờ duyệt: quyền sử dụng chưa được xác minh")
            row = {"id": item.id, "source": source.name, "title": item.title, "page_url": item.page_url,
                   "download_url": item.download_url, "license": item.license, "attribution": item.attribution,
                   "language": item.language, "permission": item.permission, "path": item.path,
                   "rights_basis": basis, "state": "APPROVED" if verified else "AWAITING_RIGHTS"}
            if dry_run:
                log(f"  [chạy thử] {row['state']:15s} {item.id}  [{item.license}]  {item.title}")
                continue
            if store.add(row):
                new += 1
                counts["new"] += 1
                counts["awaiting_rights"] += not verified
                store.log(item.id, "discover", "info", f"Mới từ nguồn {source.name}: {basis}")
            else:
                counts["known"] += 1
        if not dry_run:
            store.source_checked(source.name, new, None)
        log(f"Nguồn {source.name}: {len(items)} video, {new} mới")
    return counts


def _attempt(cfg: Config, store: Store, video: dict, waiting_state: str, stage: str, fn: Callable, log) -> str:
    started = time.time()
    try:
        fields = fn(cfg, store, video)
        state = fields.pop("state")
        store.release(video["id"], state, error=fields.pop("error", None), **fields)
        store.log(video["id"], stage, "info", f"→ {state}", time.time() - started)
        return state
    except KeyboardInterrupt:
        store.release(video["id"], waiting_state)
        raise
    except Defer as wait:
        store.release(video["id"], waiting_state, next_attempt_at=wait.until, error=str(wait))
        store.log(video["id"], stage, "info", str(wait))
        return waiting_state
    except Exception as exc:
        permanent = isinstance(exc, VietdubError) and not isinstance(exc, TransientError)
        detail = str(exc) if isinstance(exc, VietdubError) else "".join(traceback.format_exception_only(type(exc), exc)).strip()
        attempts = video["attempts"] + 1
        if permanent or attempts >= cfg.limits["max_attempts"]:
            store.release(video["id"], "FAILED", attempts=attempts, error=detail)
            store.log(video["id"], stage, "error", f"Dừng hẳn sau {attempts} lần: {detail}", time.time() - started)
            log(f"  {video['id']}: FAILED — {detail}")
            return "FAILED"
        delay = cfg.limits["retry_minutes"] * 60 * 2 ** (attempts - 1)
        store.release(video["id"], waiting_state, attempts=attempts, next_attempt_at=time.time() + delay, error=detail)
        store.log(video["id"], stage, "warning", f"Lỗi lần {attempts}, thử lại sau {delay / 60:.0f} phút: {detail}", time.time() - started)
        log(f"  {video['id']}: lỗi lần {attempts}, sẽ thử lại — {detail}")
        return waiting_state


def run_once(cfg: Config, store: Store, worker: str = "worker-1", dry_run: bool = False,
             steps: Steps | None = None, log: Callable[[str], None] = print) -> dict:
    steps = steps or Steps()
    summary = {"recovered": 0, "processed": 0, "states": {}}
    if not dry_run:
        summary["recovered"] = len(store.recover_stale(cfg.limits["stale_minutes"] * 60))
    summary["discover"] = discover(cfg, store, steps, dry_run, log)
    if dry_run:
        return summary
    budget = cfg.limits["max_items_per_run"]
    for waiting, stage, fn in (("APPROVED", "download", steps.download), ("DOWNLOADED", "dub", steps.dub), ("DUBBED", "check", steps.check)):
        done = 0
        while done < budget and (video := store.claim(waiting, worker)):
            log(f"{stage}: {video['id']}")
            state = _attempt(cfg, store, video, waiting, stage, fn, log)
            summary["states"][state] = summary["states"].get(state, 0) + 1
            summary["processed"] += 1
            done += 1
    return summary
