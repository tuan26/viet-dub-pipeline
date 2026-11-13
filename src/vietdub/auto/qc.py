"""Automatic checks on a finished dub. They decide QC_PASS or NEEDS_REVIEW and point at
the lines worth a look; they never publish anything.

QC_PASS means only that these mechanical checks passed. It says nothing about whether the
translation is right, whether the voices fit, or whether the rights are in order.
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

DISCLAIMER = ("Kiểm tra tự động chỉ đo các lỗi kỹ thuật (file, thời lượng, âm lượng, câu chưa dịch, câu bị cắt, "
              "tiếng người không có câu thoại, người nói không chắc). QC_PASS không có nghĩa là bản dịch đúng nghĩa, "
              "giọng hợp vai, hay quyền sử dụng đã được kiểm tra đầy đủ.")
CRITICAL = {"mp4_giai_ma", "co_hinh_va_tieng", "thoi_luong", "am_luong", "co_loi_thoai", "cau_chua_dich"}
LABELS = {
    "mp4_giai_ma": "File MP4 giải mã không lỗi", "co_hinh_va_tieng": "Có cả hình và tiếng",
    "thoi_luong": "Thời lượng khớp video gốc", "am_luong": "Âm lượng đủ nghe", "khong_vo_tieng": "Không vỡ tiếng",
    "co_loi_thoai": "Có lời thoại", "cau_chua_dich": "Không còn câu chưa dịch", "cau_bi_cat": "Ít câu bị cắt",
    "loi_thoai_bi_sot": "Ít lời thoại bị sót", "nguoi_noi_khong_chac": "Ít câu không chắc người nói",
    "vai_da_duoc_duyet": "Vai và giọng đã có người duyệt",
}
LINE_FLAGS = {
    "chua_dich": "Còn chữ nước ngoài / chưa dịch", "bi_cat": "Câu đọc bị cắt cho vừa thời gian",
    "doc_nhanh": "Phải đọc nhanh hơn 1,25 lần", "nguoi_noi_khong_chac": "Máy không chắc ai nói câu này",
    "so_khong_khop": "Con số trong câu gốc không có trong bản dịch", "do_dai_la": "Độ dài bản dịch khác thường so với câu gốc",
}
_FOREIGN = re.compile(r"[一-鿿぀-ヿ가-힯]")
_CJK = re.compile(r"[一-鿿぀-ヿ가-힯]")


def _check(name: str, ok: bool, value, limit, detail: str = "") -> dict:
    return {"name": name, "label": LABELS.get(name, name), "ok": bool(ok), "value": value, "limit": limit,
            "detail": detail, "severity": "critical" if name in CRITICAL else "warning"}


def _volume(path: Path) -> tuple[float | None, float | None]:
    err = subprocess.run(["ffmpeg", "-v", "info", "-i", str(path), "-vn", "-af", "volumedetect", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    mean, peak = re.search(r"mean_volume: (-?[\d.]+) dB", err), re.search(r"max_volume: (-?[\d.]+) dB", err)
    return (float(mean.group(1)) if mean else None, float(peak.group(1)) if peak else None)


def speech_regions(audio: Path) -> list[tuple[float, float]] | None:
    """Stretches of detected speech, or None when the voice-activity detector is not installed."""
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
    return [(sp["start"] / 16000, sp["end"] / 16000)
            for sp in get_speech_timestamps(samples, VadOptions(min_speech_duration_ms=250, min_silence_duration_ms=300))]


def uncovered(regions: list[tuple[float, float]], segments: list[dict], pad: float = 0.4,
              min_gap: float = 0.6) -> tuple[float, float, list[tuple[float, float]]]:
    """(uncovered seconds, speech seconds, gaps): parts of detected speech no line covers."""
    spans = sorted((s["start"] - pad, s["end"] + pad) for s in segments)
    total = missed = 0.0
    gaps = []
    for a, b in regions:
        total += b - a
        cursor, holes = a, []
        for s, e in spans:
            if e <= cursor or s >= b:
                continue
            if s > cursor:
                holes.append((cursor, s))
            cursor = max(cursor, e)
        if cursor < b:
            holes.append((cursor, b))
        for h in holes:
            missed += h[1] - h[0]
            if h[1] - h[0] >= min_gap:
                gaps.append((round(h[0], 2), round(h[1], 2)))
    return missed, total, gaps


def missed_speech(audio: Path, segments: list[dict], pad: float = 0.4) -> tuple[float, float] | None:
    regions = speech_regions(audio)
    if regions is None:
        return None
    missed, total, _ = uncovered(regions, segments, pad)
    return missed, total


def line_flags(segments: list[dict], report: dict) -> dict[int, list[str]]:
    untranslated = set(report.get("untranslated", []))
    truncated = set(report.get("truncated", []))
    speed = {int(k): v for k, v in (report.get("line_speed") or {}).items()}
    flags: dict[int, list[str]] = {}
    for s in segments:
        own, text, tr = [], s.get("text", ""), s.get("translation", "")
        if s["index"] in untranslated or _FOREIGN.search(tr):
            own.append("chua_dich")
        if s["index"] in truncated:
            own.append("bi_cat")
        if speed.get(s["index"], 1.0) > 1.25:
            own.append("doc_nhanh")
        if s.get("uncertain"):
            own.append("nguoi_noi_khong_chac")
        digits = set(re.findall(r"\d+", text))
        if digits and not digits <= set(re.findall(r"\d+", tr)):
            own.append("so_khong_khop")
        if not _CJK.search(text) and any(c.isalnum() for c in tr):
            src_words, vi_words = len(text.split()), len(tr.split())
            if src_words >= 4 and not 0.5 <= vi_words / src_words <= 3.5:
                own.append("do_dai_la")
        if own:
            flags[s["index"]] = own
    return flags


def check(out_dir: Path, limits: dict) -> dict:
    checks: list[dict] = []
    report_file = out_dir / "report.json"
    if not report_file.exists():
        result = {"status": "NEEDS_REVIEW", "reasons": ["không có report.json"], "checks": [], "lines": {}, "gaps": [],
                  "critical": 1, "warnings": 0, "disclaimer": DISCLAIMER}
        return result
    report = json.loads(report_file.read_text(encoding="utf-8"))
    work = out_dir / "work"
    segments = json.loads((work / "segments.json").read_text(encoding="utf-8")) if (work / "segments.json").exists() else []
    spoken = [s for s in segments if any(c.isalnum() for c in s.get("translation", ""))]
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
    lines = len(spoken)
    flags = line_flags(spoken, report)
    checks.append(_check("co_loi_thoai", lines > 0, lines, 1))
    untranslated = sorted(i for i, f in flags.items() if "chua_dich" in f)
    checks.append(_check("cau_chua_dich", len(untranslated) <= limits["max_untranslated"], len(untranslated), limits["max_untranslated"],
                         "câu: " + ", ".join(map(str, untranslated))))
    truncated = len(report.get("truncated", [])) / max(lines, 1)
    checks.append(_check("cau_bi_cat", truncated <= limits["max_truncated_ratio"], round(truncated, 3), limits["max_truncated_ratio"],
                         "câu: " + ", ".join(map(str, report.get("truncated", [])))))
    speech = work / "vocals.wav" if (work / "vocals.wav").exists() else work / "audio.wav"
    regions = speech_regions(speech) if speech.exists() else None
    gaps: list[tuple[float, float]] = []
    if regions is None:
        checks.append(_check("loi_thoai_bi_sot", True, None, limits["max_missed_speech_ratio"], "bỏ qua: không có bộ dò tiếng nói hoặc âm thanh"))
    else:
        # every recognised line counts as covered, including ones left silent on purpose
        missed, total, gaps = uncovered(regions, segments)
        ratio = missed / total if total else 0.0
        checks.append(_check("loi_thoai_bi_sot", ratio <= limits["max_missed_speech_ratio"], round(ratio, 3), limits["max_missed_speech_ratio"],
                             f"{missed:.1f}s tiếng người không thuộc câu nào, trên {total:.1f}s"))

    # speakers
    if report.get("speakers"):
        uncertain = sum(1 for s in spoken if s.get("uncertain")) / max(lines, 1)
        checks.append(_check("nguoi_noi_khong_chac", uncertain <= limits["max_uncertain_ratio"], round(uncertain, 3), limits["max_uncertain_ratio"]))
        if limits["require_speaker_review"]:
            checks.append(_check("vai_da_duoc_duyet", bool(report.get("speakers_reviewed")), bool(report.get("speakers_reviewed")), True,
                                 "vai và giọng do máy tự gán"))

    failed = [c for c in checks if not c["ok"]]
    reasons = [f"{c['name']}: {c['detail'] or c['value']}" for c in failed]
    result = {"status": "QC_PASS" if not failed else "NEEDS_REVIEW", "reasons": reasons, "checks": checks,
              "critical": sum(1 for c in failed if c["severity"] == "critical"),
              "warnings": sum(1 for c in failed if c["severity"] == "warning"),
              "lines": {str(k): v for k, v in flags.items()}, "gaps": gaps, "disclaimer": DISCLAIMER}
    (out_dir / "qc.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result
