"""Run the stages in order. Every stage writes its result into the work directory,
so a rerun continues from the last finished stage."""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from . import media, srt, timing
from .engines.translate import ChatFn, translate
from .engines.tts import SynthFn
from .models import Segment, VietdubError
from .rights import Rights


@dataclass
class Job:
    video: Path
    out_dir: Path
    rights: Rights
    synth: SynthFn
    chat: ChatFn | None = None  # None: subtitles are already Vietnamese
    transcribe: Callable[[Path], list[Segment]] | None = None
    separate: Callable[[Path, Path], Path] | None = None
    subtitles: Path | None = None  # existing SRT; skips speech recognition
    source_language: str | None = None
    glossary: str = ""
    max_speed: float = 1.4
    original_volume: float = 0.12  # original audio level under the dub when not separated
    force: bool = False
    log: Callable[[str], None] = print
    report: dict = field(default_factory=dict)


def _load(path: Path) -> list[Segment]:
    return [Segment.from_dict(d) for d in json.loads(path.read_text(encoding="utf-8"))]


def _save(path: Path, segments: list[Segment]) -> None:
    path.write_text(
        json.dumps([s.to_dict() for s in segments], ensure_ascii=False, indent=2), encoding="utf-8"
    )


def run(job: Job) -> Path:
    if not job.video.is_file():
        raise VietdubError(f"Không tìm thấy video: {job.video}")
    work = job.out_dir / "work"
    clips_dir = work / "clips"
    clips_dir.mkdir(parents=True, exist_ok=True)
    started = time.time()
    stages: dict[str, float] = {}

    def timed(name: str, since: float) -> None:
        stages[name] = round(stages.get(name, 0.0) + time.time() - since, 2)

    total = media.duration(job.video)
    job.log(f"Video dài {total:.1f}s")

    # 1. Audio
    audio = work / "audio.wav"
    video_has_audio = media.has_audio(job.video)
    if video_has_audio and (job.force or not audio.exists()):
        job.log("[1/6] Tách âm thanh")
        t = time.time()
        media.extract_audio(job.video, audio)
        timed("extract_audio", t)

    # 2. Segments
    seg_file = work / "segments.json"
    if seg_file.exists() and not job.force:
        segments = _load(seg_file)
    elif job.subtitles:
        job.log("[2/6] Đọc phụ đề có sẵn")
        segments = srt.parse_srt(job.subtitles.read_text(encoding="utf-8"))
        _save(seg_file, segments)
    else:
        if job.transcribe is None or not video_has_audio:
            raise VietdubError("Video không có phụ đề (--srt) và không có bộ nhận dạng giọng nói.")
        job.log("[2/6] Nhận dạng lời thoại")
        t = time.time()
        segments = job.transcribe(audio)
        timed("speech_to_text", t)
        _save(seg_file, segments)
    segments = [s for s in segments if s.start < total]

    # 3. Translation
    if any(not s.translation for s in segments):
        if job.chat is None:
            for s in segments:
                s.translation = s.text
        else:
            job.log(f"[3/6] Dịch {len(segments)} câu sang tiếng Việt")
            t = time.time()
            translate(segments, job.chat, job.source_language, job.glossary)
            timed("translate", t)
        _save(seg_file, segments)

    # Lines with nothing to pronounce (music notes, punctuation) are left silent.
    segments = [s for s in segments if any(c.isalnum() for c in s.translation)]
    if not segments:
        raise VietdubError("Không có câu thoại nào để lồng tiếng.")

    # 4. Voice
    t = time.time()
    job.log(f"[4/6] Tạo giọng đọc cho {len(segments)} câu")
    raw: list[Path] = []
    for seg in segments:
        existing = [p for p in clips_dir.glob(f"{seg.index:05d}_raw.*")]
        if existing and not job.force:
            raw.append(existing[0])
        else:
            raw.append(job.synth(seg.translation, clips_dir / f"{seg.index:05d}_raw"))

    timed("text_to_speech", t)

    # 5. Timing and dub track
    t = time.time()
    job.log("[5/6] Khớp thời lượng và ghép đường tiếng")
    placements = timing.plan(segments, [media.duration(p) for p in raw], total, job.max_speed)
    fitted = []
    for placement, clip in zip(placements, raw):
        out = clips_dir / f"{placement.index:05d}_fit.wav"
        changed = placement.speed > 1.0 or placement.truncated
        media.to_dub_wav(clip, out, placement.speed, placement.length if changed else None)
        fitted.append((placement, out))
    dub = work / "dub.wav"
    media.assemble(fitted, total, dub)
    timed("fit_and_assemble", t)

    # 6. Mix and write outputs
    job.log("[6/6] Trộn tiếng và xuất video")
    bed, bed_volume = None, 1.0
    if video_has_audio:
        if job.separate is not None:
            background = work / "background.wav"
            if job.force or not background.exists():
                job.log("      Tách nhạc nền khỏi giọng gốc")
                t = time.time()
                background = job.separate(audio, work)
                timed("separate_background", t)
            bed = background
        else:
            bed, bed_volume = audio, job.original_volume
    output = job.out_dir / f"{job.video.stem}.vi.mp4"
    t = time.time()
    media.mux(job.video, bed, dub, output, bed_volume)
    timed("mix_and_export", t)

    (job.out_dir / f"{job.video.stem}.vi.srt").write_text(
        srt.write_srt(segments, translated=True), encoding="utf-8"
    )
    (job.out_dir / "CREDITS.txt").write_text(job.rights.credits(), encoding="utf-8")
    sped = [p for p in placements if p.speed > 1.0]
    job.report = {
        "video": job.video.name,
        "output": output.name,
        "rights": job.rights.to_dict(),
        "duration_seconds": round(total, 2),
        "segments": len(segments),
        "sped_up": len(sped),
        "max_speed_used": max((p.speed for p in sped), default=1.0),
        "truncated": [p.index for p in placements if p.truncated],
        "background": "separated" if job.separate and video_has_audio else "ducked-original",
        "stage_seconds": stages,
        "output_bytes": output.stat().st_size,
        "elapsed_seconds": round(time.time() - started, 1),
    }
    (job.out_dir / "report.json").write_text(
        json.dumps(job.report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return output
