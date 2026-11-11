from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from ..models import VietdubError


def separate_background(audio: Path, workdir: Path) -> Path:
    """Run Demucs and return the track without vocals (music and effects)."""
    try:
        import demucs  # noqa: F401
    except ImportError:
        raise VietdubError("Chưa cài demucs. Chạy: pip install 'vietdub[separate]' — hoặc bỏ --separate.")
    out_dir = workdir / "demucs"
    proc = subprocess.run(
        [sys.executable, "-m", "demucs", "--two-stems", "vocals", "-o", str(out_dir), str(audio)],
        capture_output=True, text=True,
    )
    found = list(out_dir.glob(f"*/{audio.stem}/no_vocals.wav"))
    if proc.returncode != 0 or not found:
        raise VietdubError("Demucs lỗi:\n" + "\n".join(proc.stderr.strip().splitlines()[-5:]))
    target = workdir / "background.wav"
    shutil.copyfile(found[0], target)
    return target
