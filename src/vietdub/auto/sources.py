"""Turn a configured source into candidate videos. No source here signs in, solves a
challenge or works around an access restriction: public APIs, yt-dlp without cookies,
files the user lists, and folders on this machine."""
from __future__ import annotations

import tomllib
from pathlib import Path

from ..ingest import archive, channels, commons, ytdlp
from ..ingest.catalog import Item
from ..models import VietdubError
from .config import Source

VIDEO_SUFFIXES = (".mp4", ".mkv", ".mov", ".webm", ".avi", ".m4v")


def _manifest(source: Source) -> list[Item]:
    """A list of direct file URLs the user has the right to use."""
    path = Path(source.options.get("file", ""))
    if not path.is_file():
        raise VietdubError(f"Nguồn '{source.name}': không thấy file danh sách {path}.")
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise VietdubError(f"{path} sai cú pháp: {exc}")
    items = []
    for n, v in enumerate(data.get("video", []), 1):
        for key in ("url", "license"):
            if not v.get(key):
                raise VietdubError(f"{path}: video thứ {n} thiếu '{key}'.")
        items.append(Item(
            id=f"manifest:{source.name}:{v.get('id') or v['url'].rsplit('/', 1)[-1]}", source=source.name,
            title=v.get("title") or v["url"].rsplit("/", 1)[-1], page_url=v.get("page_url") or v["url"],
            license=v["license"], attribution=v.get("attribution", ""), language=v.get("language", ""),
            download_url=v["url"], permission=v.get("permission", "")))
    return items


def _folder(source: Source) -> list[Item]:
    """Video files already on this machine, all under one declared licence."""
    folder = Path(source.options.get("path", ""))
    if not folder.is_dir():
        raise VietdubError(f"Nguồn '{source.name}': không thấy thư mục {folder}.")
    if not source.options.get("license"):
        raise VietdubError(f"Nguồn '{source.name}': thư mục cần khai báo license.")
    return [Item(
        id=f"folder:{source.name}:{f.name}", source=source.name, title=f.stem, page_url=str(f),
        license=source.options["license"], attribution=source.options.get("attribution", ""),
        language=source.options.get("language", ""), permission=source.options.get("permission", ""), path=str(f))
        for f in sorted(folder.iterdir()) if f.suffix.lower() in VIDEO_SUFFIXES]


def discover(source: Source) -> list[Item]:
    o = source.options
    if source.type == "archive":
        items = archive.search(o.get("query", ""), source.limit)
    elif source.type == "commons":
        items = commons.search(o.get("query", ""), source.limit)
    elif source.type == "youtube_cc":
        items = ytdlp.search_youtube_cc(o.get("query", ""), source.limit)
    elif source.type == "channel":
        if not source.evidence or not source.evidence.is_file():
            raise VietdubError(f"Nguồn '{source.name}': kênh cần file evidence (văn bản cho phép).")
        channel = channels.Channel(source.name, o.get("url", ""), o.get("permission", ""), source.evidence,
                                   o.get("attribution", ""), o.get("language", ""))
        if not (channel.url and channel.permission and channel.attribution):
            raise VietdubError(f"Nguồn '{source.name}': kênh cần url, permission và attribution.")
        items = channels.sync(channel, source.limit)
    elif source.type == "manifest":
        items = _manifest(source)[: source.limit]
    else:
        items = _folder(source)[: source.limit]
    for item in items:
        item.source = source.name
    return items
