from __future__ import annotations

from pathlib import Path
from typing import Callable

from ..models import VietdubError
from . import archive, net, ytdlp
from .catalog import Catalog, Item


def fetch_item(item: Item, library: Path) -> Path:
    if item.source == "archive" and not item.download_url:
        item.download_url = archive.resolve_download(item)
        if not item.download_url:
            raise VietdubError("Mục này không có file video tải được.")
    if item.download_url:
        suffix = Path(item.download_url.split("?")[0]).suffix.lower() or ".mp4"
        dest = library / "videos" / f"{item.slug()}{suffix}"
        net.download(item.download_url, dest)
    else:
        dest = library / "videos" / f"{item.slug()}.mp4"
        ytdlp.download(item.page_url, dest)
    return dest


def fetch_approved(
    catalog: Catalog,
    limit: int,
    fetch: Callable[[Item, Path], Path] = fetch_item,
    log: Callable[[str], None] = print,
) -> int:
    """Download approved items. One failure is recorded and does not stop the rest."""
    done = 0
    for item in catalog.with_status("approved")[:limit]:
        log(f"Tải {item.id}: {item.title}")
        try:
            item.path = str(fetch(item, catalog.library))
            item.status, item.error = "fetched", ""
            done += 1
        except VietdubError as exc:
            item.status, item.error = "failed", str(exc)
            log(f"  Lỗi: {exc}")
        catalog.save()
    return done
