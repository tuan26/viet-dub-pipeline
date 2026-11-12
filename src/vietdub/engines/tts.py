from __future__ import annotations

import shutil
import subprocess
import time
from pathlib import Path
from typing import Callable

from ..models import VietdubError

SynthFn = Callable[[str, Path], Path]  # (text, path without suffix) -> written audio file


def edge(voice: str = "vi-VN-HoaiMyNeural", retries: int = 4, pause: float = 1.5,
         pitch: str = "+0Hz", rate: str = "+0%") -> SynthFn:
    """Microsoft Edge online voices via the unofficial edge-tts package (needs internet)."""
    try:
        import edge_tts
    except ImportError:
        raise VietdubError("Chưa cài edge-tts. Chạy: pip install 'vietdub[tts]' — hoặc dùng --tts piper.")
    import asyncio
    import os

    # aiohttp ignores proxy environment variables unless told, so pass it explicitly.
    proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")

    def synth(text: str, stem: Path) -> Path:
        out = stem.with_suffix(".mp3")
        # The service drops a request now and then ("No audio was received"); retrying succeeds.
        for attempt in range(1, retries + 1):
            try:
                asyncio.run(edge_tts.Communicate(text, voice, proxy=proxy, pitch=pitch, rate=rate).save(str(out)))
                return out
            except Exception as exc:  # the library raises many network error types
                out.unlink(missing_ok=True)
                if attempt == retries:
                    raise VietdubError(f"edge-tts lỗi khi đọc câu {text!r} sau {retries} lần thử: {exc}")
                time.sleep(pause * attempt)
        return out

    return synth


def piper(model: str | None) -> SynthFn:
    """Offline Piper voices. ``model`` is the path to a Vietnamese .onnx voice file."""
    import importlib.util
    import sys

    # Installed in the same environment it is run as a module, so it works without
    # the environment's bin directory on PATH.
    if importlib.util.find_spec("piper") is not None:
        command = [sys.executable, "-m", "piper"]
    elif shutil.which("piper"):
        command = ["piper"]
    else:
        raise VietdubError("Không tìm thấy Piper. Cài bằng: pip install piper-tts")
    if not model:
        raise VietdubError("Piper cần --voice trỏ tới file giọng .onnx tiếng Việt.")

    def synth(text: str, stem: Path) -> Path:
        out = stem.with_suffix(".wav")
        proc = subprocess.run(
            [*command, "--model", model, "--output_file", str(out)],
            input=text, capture_output=True, text=True,
        )
        if proc.returncode != 0 or not out.exists():
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
