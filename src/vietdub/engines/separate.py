from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from ..models import TransientError, VietdubError

CHUNK_SECONDS = 180  # long tracks are separated in pieces so memory use does not grow with length


def _demucs(inputs: list[Path], out_dir: Path) -> None:
    proc = subprocess.run(
        [sys.executable, "-m", "demucs", "--two-stems", "vocals", "-o", str(out_dir), *map(str, inputs)],
        capture_output=True, text=True,
    )
    if proc.returncode < 0:
        # killed by the system, in practice for lack of memory: worth trying again later
        raise TransientError(f"Demucs bị hệ thống dừng (tín hiệu {-proc.returncode}), thường do thiếu RAM.")
    if proc.returncode != 0:
        lines = [l for l in proc.stderr.strip().splitlines() if "%|" not in l]
        raise VietdubError("Demucs lỗi:\n" + "\n".join(lines[-5:]))


def _duration(path: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                         capture_output=True, text=True).stdout.strip()
    return float(out or 0)


def separate_background(audio: Path, workdir: Path) -> tuple[Path, Path]:
    """Run Demucs; return (track without vocals, vocals only)."""
    try:
        import demucs  # noqa: F401
    except ImportError:
        raise VietdubError("Chưa cài demucs. Chạy: pip install 'vietdub[separate]' — hoặc bỏ --separate.")
    out_dir = workdir / "demucs"
    background, vocals = workdir / "background.wav", workdir / "vocals.wav"
    if _duration(audio) <= CHUNK_SECONDS * 1.5:
        _demucs([audio], out_dir)
        found = list(out_dir.glob(f"*/{audio.stem}/no_vocals.wav"))
        if not found:
            raise VietdubError("Demucs không tạo ra file kết quả.")
        shutil.copyfile(found[0], background)
        shutil.copyfile(found[0].with_name("vocals.wav"), vocals)
        return background, vocals

    pieces_dir = workdir / "demucs_in"
    shutil.rmtree(pieces_dir, ignore_errors=True)
    pieces_dir.mkdir(parents=True)
    cut = subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(audio), "-f", "segment", "-segment_time", str(CHUNK_SECONDS),
                          "-c", "copy", str(pieces_dir / "part_%04d.wav")], capture_output=True, text=True)
    pieces = sorted(pieces_dir.glob("part_*.wav"))
    if cut.returncode != 0 or not pieces:
        raise VietdubError("Không cắt được âm thanh thành từng đoạn để tách nhạc.")
    for piece in pieces:  # one at a time: finished pieces are kept if a later one fails
        if not list(out_dir.glob(f"*/{piece.stem}/no_vocals.wav")):
            _demucs([piece], out_dir)
    for stem, target in (("no_vocals", background), ("vocals", vocals)):
        listing = workdir / f"demucs_{stem}.txt"
        parts = [next(iter(out_dir.glob(f"*/{piece.stem}/{stem}.wav")), None) for piece in pieces]
        if None in parts:
            raise VietdubError("Demucs thiếu kết quả cho một đoạn.")
        listing.write_text("".join(f"file '{p}'\n" for p in parts), encoding="utf-8")
        join = subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(listing), "-c", "copy", str(target)],
                              capture_output=True, text=True)
        if join.returncode != 0:
            raise VietdubError("Không ghép được các đoạn sau khi tách nhạc.")
    shutil.rmtree(pieces_dir, ignore_errors=True)
    return background, vocals
