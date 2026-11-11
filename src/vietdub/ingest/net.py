"""Polite HTTP: one identifiable user agent, a pause between requests."""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from ..models import VietdubError

USER_AGENT = os.environ.get("VIETDUB_USER_AGENT", "vietdub/0.1 (video ingest tool)")
DELAY = float(os.environ.get("VIETDUB_REQUEST_DELAY", "1.0"))
_last = 0.0


def _open(url: str):
    global _last
    wait = _last + DELAY - time.monotonic()
    if wait > 0:
        time.sleep(wait)
    _last = time.monotonic()
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        return urllib.request.urlopen(req, timeout=60)
    except urllib.error.HTTPError as exc:
        hint = " (nguồn đang giới hạn tần suất, thử lại sau)" if exc.code == 429 else ""
        raise VietdubError(f"{urllib.parse.urlsplit(url).netloc} trả về HTTP {exc.code}{hint}")
    except urllib.error.URLError as exc:
        raise VietdubError(f"Không kết nối được {urllib.parse.urlsplit(url).netloc}: {exc.reason}")


def get_json(url: str, params: dict | list) -> dict:
    with _open(url + "?" + urllib.parse.urlencode(params)) as resp:
        body = resp.read()
    try:
        return json.loads(body)
    except ValueError:
        raise VietdubError(f"{urllib.parse.urlsplit(url).netloc} trả về dữ liệu không phải JSON.")


def download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_name(dest.name + ".part")
    with _open(url) as resp, open(part, "wb") as out:
        while chunk := resp.read(1 << 20):
            out.write(chunk)
    part.replace(dest)
