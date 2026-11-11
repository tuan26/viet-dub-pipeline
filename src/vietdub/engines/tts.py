from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Callable

from ..models import VietdubError

SynthFn = Callable[[str, Path], Path]  # (text, path without suffix) -> written audio file


def edge(voice: str = "vi-VN-HoaiMyNeural") -> SynthFn:
    """Microsoft Edge online voices via the unofficial edge-tts package (needs internet)."""
    try:
        import edge_tts
    except ImportError:
        raise VietdubError("Chưa cài edge-tts. Chạy: pip install 'vietdub[tts]' — hoặc dùng --tts piper.")
    import asyncio

    def synth(text: str, stem: Path) -> Path:
        out = stem.with_suffix(".mp3")
        try:
            asyncio.run(edge_tts.Communicate(text, voice).save(str(out)))
        except Exception as exc:  # the library raises many network error types
            raise VietdubError(f"edge-tts lỗi khi đọc câu {text!r}: {exc}")
        return out

    return synth


def piper(model: str | None) -> SynthFn:
    """Offline Piper voices. ``model`` is the path to a Vietnamese .onnx voice file."""
    if shutil.which("piper") is None:
        raise VietdubError("Không tìm thấy lệnh 'piper'. Cài bằng: pip install piper-tts")
    if not model:
        raise VietdubError("Piper cần --voice trỏ tới file giọng .onnx tiếng Việt.")

    def synth(text: str, stem: Path) -> Path:
        out = stem.with_suffix(".wav")
        proc = subprocess.run(
            ["piper", "--model", model, "--output_file", str(out)],
            input=text, capture_output=True, text=True,
        )
        if proc.returncode != 0:
            raise VietdubError("piper lỗi:\n" + "\n".join(proc.stderr.strip().splitlines()[-3:]))
        return out

    return synth


def beep() -> SynthFn:
    """Placeholder voice: a tone whose length follows the text. For dry runs and tests."""

    def synth(text: str, stem: Path) -> Path:
        out = stem.with_suffix(".wav")
        seconds = max(0.3, len(text.split()) * 0.28)
        subprocess.run(
            ["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i",
             f"sine=frequency=440:duration={seconds:.2f}", str(out)],
            check=True,
        )
        return out

    return synth


def get(name: str, voice: str | None) -> SynthFn:
    if name == "edge":
        return edge(voice or "vi-VN-HoaiMyNeural")
    if name == "piper":
        return piper(voice)
    if name == "beep":
        return beep()
    raise VietdubError(f"Bộ giọng đọc '{name}' không có. Chọn: edge, piper, beep.")
