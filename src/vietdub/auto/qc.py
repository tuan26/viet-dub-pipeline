"""Automatic checks on a finished dub. They decide QC_PASS or NEEDS_REVIEW; they never
publish anything and they do not judge how natural the voices sound."""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path


def _check(name: str, ok: bool, value, limit, detail: str = "") -> dict:
    return {"name": name, "ok": bool(ok), "value": value, "limit": limit, "detail": detail}


def _volume(path: Path) -> tuple[float | None, float | None]:
    err = subprocess.run(["ffmpeg", "-v", "info", "-i", str(path), "-vn", "-af", "volumedetect", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    mean, peak = re.search(r"mean_volume: (-?[\d.]+) dB", err), re.search(r"max_volume: (-?[\d.]+) dB", err)
    return (float(mean.group(1)) if mean else None, float(peak.group(1)) if peak else None)


def missed_speech(audio: Path, segments: list[dict], pad: float = 0.4) -> tuple[float, float] | None:
    """(seconds of detected speech no line covers, total seconds of detected speech),
    or None when the voice-activity detector is not installed."""
    try:
        import numpy as np
        from faster_whisper.vad import VadOptions, get_speech_timestamps
    except ImportError:
        return None
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(audio), "-f", "s16le", "-ac", "1", "-ar", "16000", "-"],
                         capture_output=True).stdout
    if not raw:
        return None
    samples = np.frombuffer(raw, np.int16).astype(np.float32) / 32768.0
    total = uncovered = 0.0
    for sp in get_speech_timestamps(samples, VadOptions(min_speech_duration_ms=250, min_silence_duration_ms=300)):
        a, b = sp["start"] / 16000, sp["end"] / 16000
        covered = sum(max(0.0, min(b, s["end"] + pad) - max(a, s["start"] - pad)) for s in segments)
        total += b - a
        uncovered += max(0.0, (b - a) - covered)
    return uncovered, total


def check(out_dir: Path, limits: dict) -> dict:
    checks: list[dict] = []
    report_file = out_dir / "report.json"
    if not report_file.exists():
        return {"status": "NEEDS_REVIEW", "reasons": ["không có report.json"], "checks": []}
    report = json.loads(report_file.read_text(encoding="utf-8"))
    work = out_dir / "work"
    segments = json.loads((work / "segments.json").read_text(encoding="utf-8")) if (work / "segments.json").exists() else []
    video = out_dir / report["output"]

    # the file itself
    decode = subprocess.run(["ffmpeg", "-v", "error", "-i", str(video), "-f", "null", "-"], capture_output=True, text=True)
    errors = len(decode.stderr.strip().splitlines()) if video.exists() else -1
    checks.append(_check("mp4_giai_ma", video.exists() and decode.returncode == 0 and errors == 0, errors, 0, "số dòng lỗi khi giải mã"))
    streams = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type:format=duration", "-of", "json", str(video)],
                             capture_output=True, text=True).stdout if video.exists() else "{}"
    info = json.loads(streams or "{}")
    kinds = {s.get("codec_type") for s in info.get("streams", [])}
    checks.append(_check("co_hinh_va_tieng", {"video", "audio"} <= kinds, sorted(kinds), ["audio", "video"]))
    # the output is cut to the picture, so compare with the source's picture length
    expected = report.get("video_stream_seconds") or report["duration_seconds"]
    diff = abs(float(info.get("format", {}).get("duration", 0)) - expected)
    checks.append(_check("thoi_luong", diff <= limits["max_duration_diff"], round(diff, 2), limits["max_duration_diff"], "lệch so với video gốc (giây)"))

    # audio level
    mean, peak = _volume(video) if video.exists() else (None, None)
    checks.append(_check("am_luong", mean is not None and mean >= limits["min_mean_volume_db"], mean, limits["min_mean_volume_db"], "âm lượng trung bình (dB)"))
    checks.append(_check("khong_vo_tieng", peak is not None and peak < -0.1, peak, -0.1, "đỉnh âm lượng (dB); sát 0 là vỡ tiếng"))

    # dialogue
    lines = len(segments)
    checks.append(_check("co_loi_thoai", lines > 0, lines, 1))
    untranslated = len(report.get("untranslated", []))
    checks.append(_check("cau_chua_dich", untranslated <= limits["max_untranslated"], untranslated, limits["max_untranslated"],
                         "câu: " + ", ".join(map(str, report.get("untranslated", [])))))
    truncated = len(report.get("truncated", [])) / max(lines, 1)
    checks.append(_check("cau_bi_cat", truncated <= limits["max_truncated_ratio"], round(truncated, 3), limits["max_truncated_ratio"],
                         "câu: " + ", ".join(map(str, report.get("truncated", [])))))
    speech = work / "vocals.wav" if (work / "vocals.wav").exists() else work / "audio.wav"
    missed = missed_speech(speech, segments) if speech.exists() else None
    if missed is None:
        checks.append(_check("loi_thoai_bi_sot", True, None, limits["max_missed_speech_ratio"], "bỏ qua: không có bộ dò tiếng nói hoặc âm thanh"))
    else:
        ratio = missed[0] / missed[1] if missed[1] else 0.0
        checks.append(_check("loi_thoai_bi_sot", ratio <= limits["max_missed_speech_ratio"], round(ratio, 3), limits["max_missed_speech_ratio"],
                             f"{missed[0]:.1f}s tiếng người không thuộc câu nào, trên {missed[1]:.1f}s"))

    # speakers
    if report.get("speakers"):
        uncertain = sum(1 for s in segments if s.get("uncertain")) / max(lines, 1)
        checks.append(_check("nguoi_noi_khong_chac", uncertain <= limits["max_uncertain_ratio"], round(uncertain, 3), limits["max_uncertain_ratio"]))
        if limits["require_speaker_review"]:
            checks.append(_check("vai_da_duoc_duyet", bool(report.get("speakers_reviewed")), bool(report.get("speakers_reviewed")), True,
                                 "vai và giọng do máy tự gán"))

    reasons = [f"{c['name']}: {c['detail'] or c['value']}" for c in checks if not c["ok"]]
    result = {"status": "QC_PASS" if not reasons else "NEEDS_REVIEW", "reasons": reasons, "checks": checks}
    (out_dir / "qc.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result
