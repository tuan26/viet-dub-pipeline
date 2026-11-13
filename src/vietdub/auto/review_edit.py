"""Edits a person makes to a finished dub in the dashboard.

Edits change segments.json and speakers.json in the video's work folder, are recorded in
the edit history, and delete only the voice clips they make stale. Re-exporting then runs
the normal pipeline, which reuses everything else (audio, separation, recognition,
translation, untouched clips), so it takes about a minute instead of a full run.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import time
from pathlib import Path

from ..engines import casting, tts
from ..engines.translate import _suspect
from ..models import VietdubError

SKIP = "—"  # a translation with nothing to pronounce leaves the line silent
MAX_TEXT = 500
_SPEAKER = re.compile(r"^[\w .\-]{1,30}$")


def voice_catalog() -> list[dict]:
    """The voices a reviewer can choose: each edge-tts Vietnamese voice and its pitch/pace variants."""
    out = []
    for gender, name in casting.EDGE_VOICES.items():
        for n, (pitch, rate) in enumerate(casting.VARIANTS):
            label = ("Nữ" if gender == "female" else "Nam") + f" — {name.split('-')[2].replace('Neural', '')}"
            label += " (gốc)" if n == 0 else f" biến thể {n} ({pitch}, {rate})"
            out.append({"id": voice_id(name, pitch, rate), "name": name, "pitch": pitch, "rate": rate,
                        "gender": gender, "label": label})
    return out


def voice_id(name: str, pitch: str = "+0Hz", rate: str = "+0%") -> str:
    return f"{name}|{pitch or '+0Hz'}|{rate or '+0%'}"


def _voice(vid: str) -> dict:
    for v in voice_catalog():
        if v["id"] == vid:
            return v
    raise VietdubError(f"Giọng '{vid}' không có trong danh sách.")


def _read(path: Path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def _write(path: Path, data) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)  # never leave a half-written file behind


def load(out_dir: Path) -> dict:
    work = out_dir / "work"
    segments = _read(work / "segments.json", [])
    speakers = _read(work / "speakers.json", {})
    qc = _read(out_dir / "qc.json", {})
    report = _read(out_dir / "report.json", {})
    current = casting.cast(speakers) if speakers else {}
    flags = qc.get("lines", {})
    lines = [{"index": s["index"], "start": s["start"], "end": s["end"], "text": s["text"],
              "translation": s.get("translation", ""), "speaker": s.get("speaker", ""), "uncertain": bool(s.get("uncertain")),
              "skipped": not any(c.isalnum() for c in s.get("translation", "")),
              "flags": flags.get(str(s["index"]), [])} for s in segments]
    people = []
    for name, info in speakers.items():
        v = current.get(name)
        people.append({"name": name, "lines": sum(1 for l in lines if l["speaker"] == name),
                       "suggested_gender": info.get("suggested_gender", ""), "pitch_hz": info.get("pitch_hz", 0),
                       "voice": voice_id(v.name, v.pitch, v.rate) if v else "",
                       "confirmed_by": info.get("confirmed_by", ""), "confirmed_at": info.get("confirmed_at")})
    return {"lines": lines, "speakers": people, "speakers_enabled": bool(speakers), "qc": qc, "report": report,
            "voices": voice_catalog()}


def _invalidate(clips: Path, index: int) -> int:
    removed = 0
    for pattern in (f"{index:05d}_raw.*", f"{index:05d}_trim.wav", f"{index:05d}_fit.wav"):
        for f in clips.glob(pattern):
            f.unlink(missing_ok=True)
            removed += 1
    return removed


def apply(store, video_id: str, out_dir: Path, username: str, lines: list[dict], cast: dict[str, str]) -> dict:
    """Apply a reviewer's changes. ``lines``: [{"index", "translation"?, "speaker"?, "skip"?}];
    ``cast``: {speaker: voice id}. Speakers given a voice here count as confirmed by ``username``."""
    work = out_dir / "work"
    seg_file, spk_file = work / "segments.json", work / "speakers.json"
    segments = _read(seg_file, None)
    if segments is None:
        raise VietdubError("Video này chưa có danh sách câu thoại để sửa.")
    speakers = _read(spk_file, {})
    by_index = {s["index"]: s for s in segments}
    stale: set[int] = set()
    changed = 0
    for edit in lines:
        try:
            index = int(edit["index"])
        except (KeyError, TypeError, ValueError):
            raise VietdubError("Thiếu số thứ tự câu.")
        seg = by_index.get(index)
        if seg is None:
            raise VietdubError(f"Không có câu số {index}.")
        if "translation" in edit or "skip" in edit:
            new = SKIP if edit.get("skip") else (edit.get("translation") or "").strip()
            if not new:
                raise VietdubError(f"Câu {index}: bản dịch trống. Dùng \"Bỏ câu này\" nếu không muốn đọc câu này.")
            if len(new) > MAX_TEXT:
                raise VietdubError(f"Câu {index}: bản dịch dài quá {MAX_TEXT} ký tự.")
            if new != seg.get("translation", ""):
                store.record_edit(video_id, username, "skip" if new == SKIP else "translation", index, "translation",
                                  seg.get("translation", ""), new)
                seg["translation"] = new
                stale.add(index)
                changed += 1
        if "speaker" in edit and speakers:
            new = (edit.get("speaker") or "").strip()
            if not _SPEAKER.match(new):
                raise VietdubError(f"Câu {index}: tên người nói không hợp lệ (1–30 chữ, số, khoảng trắng, . _ -).")
            if new != seg.get("speaker", ""):
                store.record_edit(video_id, username, "speaker", index, "speaker", seg.get("speaker", ""), new)
                seg["speaker"] = new
                seg["uncertain"] = False
                stale.add(index)
                changed += 1
                speakers.setdefault(new, {"suggested_gender": "", "pitch_hz": 0})
    voice_changes = 0
    if speakers:
        now = time.time()
        current = casting.cast(speakers)
        for name, vid in cast.items():
            if name not in speakers:
                continue
            v = _voice(vid)
            old = current.get(name)
            old_id = voice_id(old.name, old.pitch, old.rate) if old else ""
            info = speakers[name]
            if vid != old_id or not info.get("confirmed_by"):
                store.record_edit(video_id, username, "voice", None, name, old_id, vid)
            if vid != old_id:
                voice_changes += 1
                stale.update(s["index"] for s in segments if s.get("speaker") == name)
            info.update(voice=v["name"], pitch=v["pitch"], rate=v["rate"], gender=v["gender"],
                        confirmed_by=username, confirmed_at=now)
        used = {s.get("speaker") for s in segments if any(c.isalnum() for c in s.get("translation", ""))}
        for name in list(speakers):
            if name not in used:
                del speakers[name]  # nobody speaks as this name any more
            else:
                speakers[name]["lines"] = sum(1 for s in segments if s.get("speaker") == name)
        missing = sorted(n for n in used if n and n not in speakers)
        if missing:
            raise VietdubError("Chưa có giọng cho người nói: " + ", ".join(missing))
    untranslated_file = work / "untranslated.json"
    if untranslated_file.exists():
        still = [i for i in _read(untranslated_file, []) if i in by_index and _suspect(by_index[i]["text"], by_index[i].get("translation", ""))
                 and i not in stale]
        _write(untranslated_file, still)
    removed = sum(_invalidate(work / "clips", i) for i in stale)
    _write(seg_file, segments)
    if speakers:
        _write(spk_file, speakers)
    return {"changed_lines": changed, "voice_changes": voice_changes, "stale_lines": len(stale), "clips_removed": removed}


def preview(out_dir: Path, dubbing: dict, text: str, vid: str | None) -> Path:
    """Synthesize one line with the chosen voice, for listening before saving. Cached."""
    text = (text or "").strip()
    if not text or len(text) > MAX_TEXT:
        raise VietdubError(f"Câu nghe thử phải có từ 1 đến {MAX_TEXT} ký tự.")
    folder = out_dir / "work" / "previews"
    folder.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha1(f"{vid}|{text}|{dubbing.get('tts')}".encode()).hexdigest()[:16]
    found = list(folder.glob(f"{key}.*"))
    if found:
        return found[0]
    if dubbing.get("tts") == "edge" and vid:
        v = _voice(vid)
        synth = tts.edge(v["name"], pitch=v["pitch"], rate=v["rate"])
    else:
        synth = tts.get(dubbing.get("tts") or "edge", dubbing.get("voice"))
    return synth(text, folder / key)


def sample(out_dir: Path, speaker: str) -> Path:
    """The speaker's longest line cut from the original audio, to hear who it is."""
    work = out_dir / "work"
    segments = [s for s in _read(work / "segments.json", []) if s.get("speaker") == speaker]
    if not segments:
        raise VietdubError(f"Không có câu nào của người nói '{speaker}'.")
    longest = max(segments, key=lambda s: s["end"] - s["start"])
    folder = work / "samples"
    folder.mkdir(parents=True, exist_ok=True)
    safe = hashlib.sha1(speaker.encode()).hexdigest()[:12]
    out = folder / f"{safe}_{longest['index']}.wav"
    if not out.exists():
        source = work / "audio.wav"
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{max(longest['start'] - 0.2, 0):.2f}", "-i", str(source),
                        "-t", f"{longest['end'] - longest['start'] + 0.4:.2f}", str(out)], check=True)
    return out
