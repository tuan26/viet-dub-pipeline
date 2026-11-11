"""Internet Archive: search movies that carry a licence URL, keep the acceptable ones."""
from __future__ import annotations

import urllib.parse
from typing import Callable

from . import net
from .catalog import Item
from .licenses import normalize

SEARCH = "https://archive.org/advancedsearch.php"
METADATA = "https://archive.org/metadata/"
GetJson = Callable[[str, dict | list], dict]


def _first(value) -> str:
    return (value[0] if isinstance(value, list) and value else value) or ""


def search(query: str, limit: int, get_json: GetJson = net.get_json) -> list[Item]:
    params = [
        ("q", f"mediatype:movies AND licenseurl:http* AND ({query})"),
        ("rows", str(limit * 3)),  # over-fetch: many licences are filtered out
        ("output", "json"),
    ] + [("fl[]", f) for f in ("identifier", "title", "licenseurl", "creator", "language")]
    docs = get_json(SEARCH, params).get("response", {}).get("docs", [])
    items = []
    for doc in docs:
        license = normalize(_first(doc.get("licenseurl")))
        creator = _first(doc.get("creator"))
        if license is None or (license in ("cc-by", "cc-by-sa") and not creator):
            continue
        items.append(Item(
            id=f"archive:{doc['identifier']}",
            source="archive",
            title=_first(doc.get("title")) or doc["identifier"],
            page_url=f"https://archive.org/details/{doc['identifier']}",
            license=license,
            attribution=creator,
            language=_first(doc.get("language")),
        ))
        if len(items) == limit:
            break
    return items


def resolve_download(item: Item, get_json: GetJson = net.get_json) -> str:
    """Pick the item's main video file: the largest original MP4/MKV/WebM, else any MP4."""
    identifier = item.id.split(":", 1)[1]
    files = get_json(METADATA + urllib.parse.quote(identifier), {}).get("files", [])
    videos = [f for f in files if f.get("name", "").lower().endswith((".mp4", ".mkv", ".webm", ".mov"))]
    if not videos:
        return ""
    originals = [f for f in videos if f.get("source") == "original"] or videos
    best = max(originals, key=lambda f: int(f.get("size") or 0))
    return f"https://archive.org/download/{identifier}/{urllib.parse.quote(best['name'])}"
