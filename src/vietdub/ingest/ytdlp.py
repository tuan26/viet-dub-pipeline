"""yt-dlp wrapper: YouTube Creative Commons search, channel listing, download."""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Callable

from ..models import VietdubError
from .catalog import Item
from .licenses import normalize

Runner = Callable[[list[str]], str]


def run_ytdlp(args: list[str]) -> str:
    if shutil.which("yt-dlp") is None:
        raise VietdubError("Chưa cài yt-dlp. Chạy: pip install 'vietdub[ingest]'")
    proc = subprocess.run(["yt-dlp", "--no-warnings", *args], capture_output=True, text=True)
    if proc.returncode != 0 and not proc.stdout.strip():
        raise VietdubError("yt-dlp lỗi:\n" + "\n".join(proc.stderr.strip().splitlines()[-3:]))
    return proc.stdout


def _entries(output: str) -> list[dict]:
    return [json.loads(line) for line in output.splitlines() if line.startswith("{")]


def search_youtube_cc(query: str, limit: int, run: Runner = run_ytdlp) -> list[Item]:
    """YouTube marks reusable videos with the 'Creative Commons Attribution' licence;
    everything else (the standard YouTube licence) is dropped."""
    out = run(["--dump-json", "--skip-download", f"ytsearch{limit * 5}:{query}"])
    items = []
    for info in _entries(out):
        license = normalize(info.get("license"))
        author = info.get("channel") or info.get("uploader") or ""
        if license != "cc-by" or not author:
            continue
        items.append(Item(
            id=f"youtube:{info['id']}",
            source="youtube",
            title=info.get("title", info["id"]),
            page_url=info.get("webpage_url") or f"https://www.youtube.com/watch?v={info['id']}",
            license="cc-by",
            attribution=author,
            language=info.get("language") or "",
        ))
        if len(items) == limit:
            break
    return items


def list_channel(url: str, limit: int, run: Runner = run_ytdlp) -> list[dict]:
    """Newest uploads of a channel or playlist, without downloading anything."""
    out = run(["--flat-playlist", "--dump-json", "--playlist-end", str(limit), url])
    return _entries(out)


def download(page_url: str, dest: Path, run: Runner = run_ytdlp) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    run(["-f", "bv*[height<=1080]+ba/b", "--merge-output-format", "mp4", "-o", str(dest), page_url])
    if not dest.exists():
        raise VietdubError(f"yt-dlp không tạo được file cho {page_url}")
