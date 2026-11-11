"""Channels the user holds written permission for, listed in sources.toml."""
from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

from ..models import VietdubError
from . import ytdlp
from .catalog import Item


@dataclass
class Channel:
    name: str
    url: str
    permission: str  # what was granted, by whom, when
    evidence: Path  # the email, contract or screenshot proving it
    attribution: str
    language: str = ""


def load(config: Path) -> list[Channel]:
    if not config.exists():
        raise VietdubError(f"Không tìm thấy {config}. Xem mẫu ở docs/sources.example.toml.")
    try:
        data = tomllib.loads(config.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise VietdubError(f"{config} sai cú pháp: {exc}")
    channels = []
    for n, raw in enumerate(data.get("channel", []), 1):
        label = raw.get("name") or f"kênh thứ {n}"
        for key in ("name", "url", "permission", "evidence", "attribution"):
            if not str(raw.get(key, "")).strip():
                raise VietdubError(f"{config}: {label} thiếu trường '{key}'.")
        evidence = (config.parent / raw["evidence"]).resolve()
        if not evidence.is_file():
            raise VietdubError(
                f"{config}: {label} — không thấy file bằng chứng cấp phép '{raw['evidence']}'. "
                "Kênh chỉ được theo dõi khi có văn bản cho phép lưu kèm."
            )
        channels.append(Channel(raw["name"], raw["url"], raw["permission"], evidence,
                                raw["attribution"], raw.get("language", "")))
    return channels


def sync(channel: Channel, limit: int, run: ytdlp.Runner = ytdlp.run_ytdlp) -> list[Item]:
    items = []
    for entry in ytdlp.list_channel(channel.url, limit, run):
        video_id = entry.get("id")
        url = entry.get("webpage_url") or entry.get("url")
        if not video_id or not url:
            continue
        items.append(Item(
            id=f"channel:{channel.name}:{video_id}",
            source="channel",
            title=entry.get("title") or video_id,
            page_url=url,
            license="licensed",
            attribution=channel.attribution,
            language=channel.language,
            permission=f"{channel.permission} (bằng chứng: {channel.evidence.name})",
            status="approved",  # permission is already on file for the whole channel
        ))
    return items
