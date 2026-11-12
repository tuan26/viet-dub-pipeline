from __future__ import annotations

import subprocess
from pathlib import Path

from ..models import Segment, VietdubError


def split_on_pauses(words: list[tuple[float, float, str]], max_pause: float = 0.7) -> list[tuple[float, float, str]]:
    """Group timed words into lines, starting a new line after a pause. Word times give
    tighter line boundaries than whisper's segment times, and a pause often marks a
    change of speaker."""
    lines: list[list[tuple[float, float, str]]] = []
    for word in words:
        if lines and word[0] - lines[-1][-1][1] < max_pause:
            lines[-1].append(word)
        else:
            lines.append([word])
    return [(g[0][0], g[-1][1], "".join(w[2] for w in g).strip()) for g in lines]


def transcribe(audio: Path, language: str | None, model: str = "small", vad: bool = True) -> list[Segment]:
    """Speech-to-text with faster-whisper. ``language`` None means auto-detect."""
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        raise VietdubError(
            "Chưa cài faster-whisper. Chạy: pip install 'vietdub[asr]' — hoặc đưa phụ đề có sẵn bằng --srt."
        )
    import numpy as np

    # Decode with ffmpeg ourselves: faster-whisper's own decoder breaks on some PyAV versions.
    proc = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(audio), "-f", "s16le", "-ac", "1", "-ar", "16000", "-"],
        capture_output=True,
    )
    if proc.returncode != 0 or not proc.stdout:
        raise VietdubError(f"Không giải mã được âm thanh {audio} để nhận dạng.")
    samples = np.frombuffer(proc.stdout, np.int16).astype(np.float32) / 32768.0

    whisper = WhisperModel(model, device="auto", compute_type="auto")
    result, _info = whisper.transcribe(samples, language=language, vad_filter=vad, word_timestamps=True)
    lines: list[tuple[float, float, str]] = []
    for s in result:
        if not s.text.strip():
            continue
        if s.words:
            lines += split_on_pauses([(float(w.start), float(w.end), w.word) for w in s.words])
        else:
            lines.append((float(s.start), float(s.end), s.text.strip()))
    segments = [Segment(i, a, b, text) for i, (a, b, text) in enumerate((l for l in lines if l[2]), 1)]
    if not segments:
        raise VietdubError("Không nhận dạng được lời thoại nào trong video.")
    return segments
