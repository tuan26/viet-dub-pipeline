from __future__ import annotations

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
    whisper = WhisperModel(model, device="auto", compute_type="auto")
    result, _info = whisper.transcribe(str(audio), language=language, vad_filter=True)
    segments = [
        Segment(i, float(s.start), float(s.end), s.text.strip())
        for i, s in enumerate((s for s in result if s.text.strip()), 1)
    ]
    if not segments:
        raise VietdubError("Không nhận dạng được lời thoại nào trong video.")
    return segments
