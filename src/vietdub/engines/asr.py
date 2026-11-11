from __future__ import annotations

import subprocess
from pathlib import Path

from ..models import Segment, VietdubError


def transcribe(audio: Path, language: str | None, model: str = "small") -> list[Segment]:
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
    result, _info = whisper.transcribe(samples, language=language, vad_filter=True)
    segments = [
        Segment(i, float(s.start), float(s.end), s.text.strip())
        for i, s in enumerate((s for s in result if s.text.strip()), 1)
    ]
    if not segments:
        raise VietdubError("Không nhận dạng được lời thoại nào trong video.")
    return segments
