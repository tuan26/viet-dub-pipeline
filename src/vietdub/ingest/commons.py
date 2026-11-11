"""Wikimedia Commons: every file states its licence in machine-readable metadata."""
from __future__ import annotations

import re
from typing import Callable

from . import net
from .catalog import Item
from .licenses import normalize

API = "https://commons.wikimedia.org/w/api.php"
GetJson = Callable[[str, dict | list], dict]


def _plain(html: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", html or "")).strip()


def search(query: str, limit: int, get_json: GetJson = net.get_json) -> list[Item]:
    data = get_json(API, {
        "action": "query", "format": "json", "maxlag": "5",
        "generator": "search", "gsrsearch": f"filetype:video {query}",
        "gsrnamespace": "6", "gsrlimit": str(min(limit * 2, 50)),
        "prop": "imageinfo", "iiprop": "url|extmetadata",
    })
    items = []
    for page in data.get("query", {}).get("pages", {}).values():
        info = (page.get("imageinfo") or [{}])[0]
        meta = {k: v.get("value", "") for k, v in info.get("extmetadata", {}).items()}
        license = normalize(meta.get("License") or meta.get("LicenseShortName"))
        artist = _plain(meta.get("Artist", ""))
        if license is None or not info.get("url") or (license in ("cc-by", "cc-by-sa") and not artist):
            continue
        items.append(Item(
            id=f"commons:{page['pageid']}",
            source="commons",
            title=page.get("title", "").removeprefix("File:"),
            page_url=info.get("descriptionurl", ""),
            license=license,
            attribution=artist,
            download_url=info["url"],
        ))
        if len(items) == limit:
            break
    return items
