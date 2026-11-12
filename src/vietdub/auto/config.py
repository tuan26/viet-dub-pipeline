"""pipeline.toml: which sources to watch, how to dub, and the limits to stay within."""
from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from ..models import VietdubError

SEARCH_TYPES = ("archive", "commons", "youtube_cc")  # licences there are self-declared by uploaders
OWNED_TYPES = ("channel", "manifest", "folder")
LIMITS = {"max_attempts": 3, "retry_minutes": 10, "stale_minutes": 180, "min_free_gb": 5.0, "min_free_ram_gb": 2.0,
          "max_video_minutes": 60.0, "max_download_mb": 2000.0, "daily_minutes": 600.0, "max_items_per_run": 20}
DUBBING = {"lang": None, "asr_model": "small", "translator": "ollama", "model": None, "base_url": None, "glossary": None,
           "tts": "edge", "voice": None, "speakers": None, "cast": None, "review": False,
           "speaker_model": "models/3dspeaker_speech_eres2net_sv_en_voxceleb_16k.onnx", "separate": False,
           "max_speed": 1.4, "force": False}
QC = {"max_missed_speech_ratio": 0.15, "max_untranslated": 0, "max_truncated_ratio": 0.05, "max_uncertain_ratio": 0.2,
      "require_speaker_review": True, "min_mean_volume_db": -40.0, "max_duration_diff": 0.5}


@dataclass
class Source:
    name: str
    type: str
    options: dict
    interval_minutes: float = 360
    limit: int = 10
    rights: str = "needs_approval"  # or "verified"
    evidence: Path | None = None


@dataclass
class Config:
    database: str
    library: Path
    sources: list[Source]
    limits: dict = field(default_factory=lambda: dict(LIMITS))
    dubbing: dict = field(default_factory=lambda: dict(DUBBING))
    qc: dict = field(default_factory=lambda: dict(QC))


def _section(data: dict, name: str, defaults: dict, where: Path) -> dict:
    given = data.get(name, {})
    unknown = set(given) - set(defaults)
    if unknown:
        raise VietdubError(f"{where}: mục [{name}] có khoá không hợp lệ: {', '.join(sorted(unknown))}")
    return {**defaults, **given}


def load(path: Path) -> Config:
    if not path.exists():
        raise VietdubError(f"Không tìm thấy {path}. Xem mẫu ở docs/pipeline.example.toml.")
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise VietdubError(f"{path} sai cú pháp: {exc}")
    base = path.parent
    storage = data.get("storage", {})
    library = (base / storage.get("library", "library")).resolve()
    sources, names = [], set()
    for n, raw in enumerate(data.get("source", []), 1):
        raw = dict(raw)
        name, kind = raw.pop("name", None), raw.pop("type", None)
        if not name or kind not in SEARCH_TYPES + OWNED_TYPES:
            raise VietdubError(f"{path}: nguồn thứ {n} cần name và type thuộc: {', '.join(SEARCH_TYPES + OWNED_TYPES)}")
        if name in names:
            raise VietdubError(f"{path}: tên nguồn '{name}' bị trùng.")
        names.add(name)
        rights = raw.pop("rights", "needs_approval")
        evidence = raw.pop("evidence", None)
        evidence = (base / evidence).resolve() if evidence else None
        if rights not in ("verified", "needs_approval"):
            raise VietdubError(f"{path}: nguồn '{name}': rights phải là verified hoặc needs_approval.")
        if rights == "verified":
            # A source may skip the approval stop only when the right to use it is on file.
            if kind in SEARCH_TYPES:
                raise VietdubError(f"{path}: nguồn '{name}' là nguồn tìm kiếm, giấy phép do người đăng tự khai, "
                                   "nên không thể đặt rights = \"verified\".")
            if raw.get("license") != "owned" and not (evidence and evidence.is_file()):
                raise VietdubError(f"{path}: nguồn '{name}' đặt rights = \"verified\" thì cần license = \"owned\" "
                                   "hoặc file evidence (văn bản cho phép) tồn tại.")
        for key in ("file", "path"):
            if key in raw:
                raw[key] = str((base / raw[key]).resolve())
        sources.append(Source(name, kind, raw, float(raw.pop("interval_minutes", 360)), int(raw.pop("limit", 10)), rights, evidence))
    if not sources:
        raise VietdubError(f"{path}: chưa khai báo nguồn nào ([[source]]).")
    dubbing = _section(data, "dubbing", DUBBING, path)
    if dubbing["review"]:
        raise VietdubError(f"{path}: [dubbing] review không dùng trong luồng tự động; video được duyệt sau bước kiểm tra chất lượng.")
    for key in ("glossary", "speaker_model"):
        if dubbing[key]:
            dubbing[key] = str((base / dubbing[key]).resolve())
    return Config(storage.get("database", f"sqlite:///{library / 'vietdub.db'}"), library, sources,
                  _section(data, "limits", LIMITS, path), dubbing, _section(data, "qc", QC, path))
