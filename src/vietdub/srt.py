from __future__ import annotations

import re

from .models import Segment, VietdubError

_TIME = re.compile(
    r"(\d+):(\d{2}):(\d{2})[,.](\d{1,3})\s*-->\s*(\d+):(\d{2}):(\d{2})[,.](\d{1,3})"
)


def _seconds(h: str, m: str, s: str, ms: str) -> float:
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms.ljust(3, "0")) / 1000


def parse_srt(text: str) -> list[Segment]:
    segments: list[Segment] = []
    blocks = re.split(r"\n\s*\n", text.replace("\r\n", "\n").lstrip("﻿").strip())
    for block in blocks:
        lines = [line for line in block.split("\n") if line.strip()]
        for i, line in enumerate(lines):
            match = _TIME.search(line)
            if match:
                g = match.groups()
                content = " ".join(part.strip() for part in lines[i + 1 :])
                content = re.sub(r"<[^>]+>", "", content).strip()
                if content:
                    segments.append(
                        Segment(len(segments) + 1, _seconds(*g[:4]), _seconds(*g[4:]), content)
                    )
                break
    if not segments:
        raise VietdubError("Không đọc được câu thoại nào từ file SRT.")
    return segments


def _stamp(seconds: float) -> str:
    ms = max(0, round(seconds * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def write_srt(segments: list[Segment], translated: bool = False) -> str:
    out = []
    for n, seg in enumerate(segments, 1):
        text = seg.translation if translated else seg.text
        out.append(f"{n}\n{_stamp(seg.start)} --> {_stamp(seg.end)}\n{text}\n")
    return "\n".join(out)
