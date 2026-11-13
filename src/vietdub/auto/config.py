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
SERVER = {"host": "127.0.0.1", "port": 8800, "workers": 1, "cpu_threads": 0, "nice": 10, "poll_seconds": 10.0,
          "heartbeat_seconds": 20.0, "max_upload_mb": 20.0}
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
    enabled: bool = True


@dataclass
class Config:
    database: str
    library: Path
    sources: list[Source]
    limits: dict = field(default_factory=lambda: dict(LIMITS))
    dubbing: dict = field(default_factory=lambda: dict(DUBBING))
    qc: dict = field(default_factory=lambda: dict(QC))
    server: dict = field(default_factory=lambda: dict(SERVER))
    path: Path | None = None

    @property
    def evidence_dir(self) -> Path:
        return self.library / "evidence"


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
        name = raw.pop("name", None)
        if name in names:
            raise VietdubError(f"{path}: tên nguồn '{name}' bị trùng.")
        names.add(name)
        for key in ("file", "path"):
            if key in raw:
                raw[key] = str((base / raw[key]).resolve())
        evidence = raw.pop("evidence", None)
        try:
            sources.append(validate_source(
                name, raw.pop("type", None), raw, raw.pop("rights", "needs_approval"),
                (base / evidence).resolve() if evidence else None,
                raw.pop("interval_minutes", 360), raw.pop("limit", 10)))
        except VietdubError as exc:
            raise VietdubError(f"{path}: nguồn thứ {n}: {exc}")
    dubbing = _section(data, "dubbing", DUBBING, path)
    if dubbing["review"]:
        raise VietdubError(f"{path}: [dubbing] review không dùng trong luồng tự động; video được duyệt sau bước kiểm tra chất lượng.")
    for key in ("glossary", "speaker_model"):
        if dubbing[key]:
            dubbing[key] = str((base / dubbing[key]).resolve())
    return Config(storage.get("database", f"sqlite:///{library / 'vietdub.db'}"), library, sources,
                  _section(data, "limits", LIMITS, path), dubbing, _section(data, "qc", QC, path),
                  _section(data, "server", SERVER, path), path.resolve())


def validate_source(name, kind, options: dict, rights: str, evidence: Path | None,
                    interval_minutes=360, limit=10, enabled: bool = True) -> Source:
    """The single place that decides whether a source definition is acceptable; used for
    pipeline.toml and for sources added in the dashboard."""
    name = (name or "").strip()
    if not name or len(name) > 60 or any(c in name for c in "/\\\n\t"):
        raise VietdubError("tên nguồn không hợp lệ (1–60 ký tự, không chứa / hoặc \\).")
    if kind not in SEARCH_TYPES + OWNED_TYPES:
        raise VietdubError(f"loại nguồn phải thuộc: {', '.join(SEARCH_TYPES + OWNED_TYPES)}")
    if rights not in ("verified", "needs_approval"):
        raise VietdubError(f"nguồn '{name}': rights phải là verified hoặc needs_approval.")
    try:
        interval_minutes, limit = float(interval_minutes), int(limit)
    except (TypeError, ValueError):
        raise VietdubError(f"nguồn '{name}': chu kỳ kiểm tra và số video phải là số.")
    if interval_minutes < 0.1 or not 1 <= limit <= 500:
        raise VietdubError(f"nguồn '{name}': chu kỳ phải ≥ 0,1 phút và số video từ 1 đến 500.")
    if rights == "verified":
        # A source may skip the approval stop only when the right to use it is on file.
        if kind in SEARCH_TYPES:
            raise VietdubError(f"nguồn '{name}' là nguồn tìm kiếm, giấy phép do người đăng tự khai, "
                               "nên không thể đặt quyền là \"đã xác minh\".")
        if options.get("license") != "owned" and not (evidence and Path(evidence).is_file()):
            raise VietdubError(f"nguồn '{name}' đặt quyền \"đã xác minh\" thì cần license = owned "
                               "hoặc file bằng chứng (văn bản cho phép).")
    if kind == "folder" and not options.get("path"):
        raise VietdubError(f"nguồn '{name}': thư mục cần đường dẫn (path).")
    if kind == "folder" and not options.get("license"):
        raise VietdubError(f"nguồn '{name}': thư mục cần khai báo license.")
    if kind == "manifest" and not options.get("file"):
        raise VietdubError(f"nguồn '{name}': cần file danh sách (file).")
    if kind == "channel" and not (options.get("url") and options.get("permission") and options.get("attribution")):
        raise VietdubError(f"nguồn '{name}': kênh cần url, permission và attribution.")
    if kind in SEARCH_TYPES and not options.get("query"):
        raise VietdubError(f"nguồn '{name}': nguồn tìm kiếm cần từ khoá (query).")
    return Source(name, kind, dict(options), interval_minutes, limit, rights, Path(evidence) if evidence else None, enabled)


def source_from_row(row: dict) -> Source:
    return Source(row["name"], row["type"], row["options"] or {}, float(row["interval_minutes"] or 360),
                  int(row["item_limit"] or 10), row["rights"] or "needs_approval",
                  Path(row["evidence"]) if row.get("evidence") else None, bool(row.get("enabled", 1)))


def source_to_row(source: Source) -> dict:
    return {"name": source.name, "type": source.type, "options": source.options, "interval_minutes": source.interval_minutes,
            "limit": source.limit, "rights": source.rights, "evidence": str(source.evidence) if source.evidence else None,
            "enabled": source.enabled}
