"""Thin wrappers around ffmpeg/ffprobe and WAV assembly."""
from __future__ import annotations

import array
import shutil
import subprocess
import wave
from pathlib import Path

from .models import VietdubError
from .timing import Placement

DUB_RATE = 24000


def _run(cmd: list[str]) -> str:
    if shutil.which(cmd[0]) is None:
        raise VietdubError(f"Không tìm thấy '{cmd[0]}'. Hãy cài FFmpeg trước.")
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        tail = "\n".join(proc.stderr.strip().splitlines()[-5:])
        raise VietdubError(f"{cmd[0]} lỗi:\n{tail}")
    return proc.stdout


def duration(path: Path) -> float:
    out = _run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)]
    )
    try:
        return float(out.strip())
    except ValueError:
        raise VietdubError(f"Không đọc được thời lượng của {path}.")


def video_duration(path: Path) -> float:
    """Length of the picture track; it can differ from the container length when the
    source's audio runs longer than its video."""
    out = _run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=duration",
                "-of", "csv=p=0", str(path)]).strip()
    try:
        return float(out)
    except ValueError:
        return duration(path)


def has_audio(path: Path) -> bool:
    out = _run(
        ["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=index",
         "-of", "csv=p=0", str(path)]
    )
    return bool(out.strip())


def extract_audio(video: Path, out: Path, rate: int = 44100) -> None:
    _run(["ffmpeg", "-y", "-v", "error", "-i", str(video), "-vn", "-ac", "2", "-ar", str(rate), str(out)])


def trim_silence(src: Path, out: Path) -> None:
    """Cut the silence TTS engines put before and after the speech. Measured on real
    runs it is about a second per clip, enough to make one-word lines miss their slot."""
    edge = "silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.02"
    _run(["ffmpeg", "-y", "-v", "error", "-i", str(src), "-af", f"{edge},areverse,{edge},areverse",
          "-ac", "1", "-ar", str(DUB_RATE), "-c:a", "pcm_s16le", str(out)])


def to_dub_wav(src: Path, out: Path, speed: float = 1.0, length: float | None = None) -> None:
    """Convert a TTS clip to mono 16-bit WAV, optionally sped up and trimmed with a short fade."""
    filters = []
    if speed > 1.0001:
        filters.append(f"atempo={speed:.4f}")
    if length is not None:
        fade = min(0.08, length / 2)
        filters.append(f"afade=t=out:st={max(length - fade, 0):.3f}:d={fade:.3f}")
    cmd = ["ffmpeg", "-y", "-v", "error", "-i", str(src)]
    if filters:
        cmd += ["-af", ",".join(filters)]
    if length is not None:
        cmd += ["-t", f"{length:.3f}"]
    cmd += ["-ac", "1", "-ar", str(DUB_RATE), "-c:a", "pcm_s16le", str(out)]
    _run(cmd)


def assemble(clips: list[tuple[Placement, Path]], total_duration: float, out: Path) -> None:
    """Place each clip at its start time on one silent mono track."""
    track = array.array("h", bytes(2 * int(total_duration * DUB_RATE + 1)))
    for placement, clip in clips:
        with wave.open(str(clip), "rb") as w:
            samples = array.array("h", w.readframes(w.getnframes()))
        offset = int(placement.start * DUB_RATE)
        samples = samples[: max(len(track) - offset, 0)]
        track[offset : offset + len(samples)] = samples  # the timing plan guarantees no overlap
    with wave.open(str(out), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(DUB_RATE)
        w.writeframes(track.tobytes())


def mux(video: Path, bed: Path | None, dub: Path, out: Path, bed_volume: float) -> None:
    """Replace the video's audio with bed (background or ducked original) + dub."""
    cmd = ["ffmpeg", "-y", "-v", "error", "-i", str(video)]
    if bed is None:
        cmd += ["-i", str(dub), "-map", "0:v:0", "-map", "1:a:0"]
    else:
        cmd += [
            "-i", str(bed), "-i", str(dub),
            "-filter_complex",
            f"[1:a]volume={bed_volume}[b];[2:a]volume=1.0[d];"
            # amix adds the two tracks; the limiter keeps the sum from clipping, with headroom
            # because AAC encoding overshoots a limited signal by about 1 dB (measured)
            "[b][d]amix=inputs=2:duration=longest:normalize=0,alimiter=limit=0.8:level=false[a]",
            "-map", "0:v:0", "-map", "[a]",
        ]
    cmd += ["-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-shortest", str(out)]
    _run(cmd)
