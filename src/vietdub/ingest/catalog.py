"""The library: one JSON file listing every video found, with its rights and status."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, fields
from pathlib import Path

from ..models import VietdubError

# found -> approved -> fetched -> dubbed ; any step may end in failed or rejected
STATUSES = ("found", "approved", "fetched", "dubbed", "failed", "rejected")


@dataclass
class Item:
    id: str  # "<source>:<source id>", the dedup key
    source: str
    title: str
    page_url: str
    license: str
    attribution: str = ""
    language: str = ""
    download_url: str = ""  # empty: downloaded with yt-dlp from page_url
    permission: str = ""  # for licensed channels: the permission on file
    status: str = "found"
    path: str = ""
    error: str = ""

    def slug(self) -> str:
        return "".join(c if c.isalnum() or c in "-_" else "_" for c in self.id)[:80]


class Catalog:
    def __init__(self, library: Path):
        self.library = library
        self.file = library / "catalog.json"
        self.items: dict[str, Item] = {}
        if self.file.exists():
            known = {f.name for f in fields(Item)}
            for raw in json.loads(self.file.read_text(encoding="utf-8")):
                item = Item(**{k: v for k, v in raw.items() if k in known})
                self.items[item.id] = item

    def add(self, item: Item) -> bool:
        """Add a new item; an id already in the catalog is left untouched."""
        if item.id in self.items:
            return False
        self.items[item.id] = item
        return True

    def get(self, item_id: str) -> Item:
        if item_id not in self.items:
            raise VietdubError(f"Không có mục '{item_id}' trong thư viện.")
        return self.items[item_id]

    def with_status(self, status: str) -> list[Item]:
        return [i for i in self.items.values() if i.status == status]

    def save(self) -> None:
        self.library.mkdir(parents=True, exist_ok=True)
        tmp = self.file.with_suffix(".tmp")
        tmp.write_text(
            json.dumps([asdict(i) for i in self.items.values()], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        tmp.replace(self.file)
