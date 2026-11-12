"""Human check of speakers and voices before any speech is synthesized.

The run writes ``work/review/`` and stops:
  lines.tsv   one row per line; the ``speaker`` and ``translation`` columns may be edited
  cast.json   one entry per speaker: confirm ``gender`` (or name a ``voice``), then set
              ``"reviewed": true``
  *.wav       a few lines of each speaker to listen to
Running the same command again continues with the edited values.
"""
from __future__ import annotations

import csv
import json
import subprocess
from pathlib import Path

from .models import Segment, VietdubError

COLUMNS = ["index", "start", "end", "speaker", "check", "text", "translation"]


def _write(folder: Path, segments: list[Segment], speakers: dict[str, dict], audio: Path) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    with open(folder / "lines.tsv", "w", encoding="utf-8", newline="") as f:
        out = csv.writer(f, delimiter="\t")
        out.writerow(COLUMNS)
        for s in segments:
            out.writerow([s.index, f"{s.start:.2f}", f"{s.end:.2f}", s.speaker, "?" if s.uncertain else "",
                          s.text.replace("\t", " "), s.translation.replace("\t", " ")])
    cast = {"reviewed": False,
            "help": "Nghe các file .wav, sửa cột speaker trong lines.tsv nếu sai, điền gender (male/female) "
                    "hoặc voice cho từng người nói, rồi đổi reviewed thành true và chạy lại lệnh.",
            "speakers": {}}
    for name, info in speakers.items():
        own = sorted((s for s in segments if s.speaker == name), key=lambda s: -s.duration)[:3]
        samples = []
        for s in own:
            sample = folder / f"{name}_line{s.index:03d}.wav"
            subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{max(s.start - 0.2, 0):.2f}", "-i", str(audio),
                            "-t", f"{s.duration + 0.4:.2f}", str(sample)], check=False)
            samples.append(sample.name)
        cast["speakers"][name] = {
            "lines": info.get("lines", len(own)), "uncertain_lines": info.get("uncertain_lines", 0),
            "pitch_hz": info.get("pitch_hz", 0), "suggested_gender": info.get("suggested_gender", ""),
            "gender": "", "voice": "", "pitch": "", "rate": "", "samples": samples,
        }
    (folder / "cast.json").write_text(json.dumps(cast, ensure_ascii=False, indent=2), encoding="utf-8")


def sync(work: Path, segments: list[Segment], speakers: dict[str, dict], audio: Path) -> tuple[bool, dict[str, dict]]:
    """Write the review files on the first call. Afterwards return (reviewed, speakers):
    once the person has set ``reviewed``, their edits are applied to ``segments`` and the
    returned speakers are exactly the ones they confirmed."""
    folder = work / "review"
    if not (folder / "cast.json").exists():
        _write(folder, segments, speakers, audio)
        return False, speakers
    try:
        cast = json.loads((folder / "cast.json").read_text(encoding="utf-8"))
    except ValueError as exc:
        raise VietdubError(f"{folder / 'cast.json'} sai cú pháp JSON: {exc}")
    if not cast.get("reviewed"):
        return False, speakers
    by_index = {s.index: s for s in segments}
    with open(folder / "lines.tsv", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f, delimiter="\t"):
            seg = by_index.get(int(row["index"]))
            if seg is None:
                raise VietdubError(f"lines.tsv có câu số {row['index']} không tồn tại.")
            seg.speaker = (row.get("speaker") or "").strip()
            seg.uncertain = False
            if (row.get("translation") or "").strip():
                seg.translation = row["translation"].strip()
            if not seg.speaker:
                raise VietdubError(f"lines.tsv: câu {seg.index} chưa có người nói.")
    confirmed: dict[str, dict] = {}
    for name in sorted({s.speaker for s in segments}):
        entry = (cast.get("speakers") or {}).get(name)
        if entry is None:
            raise VietdubError(f"cast.json thiếu người nói '{name}' (có trong lines.tsv). Thêm mục cho người này.")
        if entry.get("gender") not in ("male", "female") and not entry.get("voice"):
            raise VietdubError(f"cast.json: người nói '{name}' cần gender là male/female, hoặc một voice.")
        confirmed[name] = {**entry, "lines": sum(1 for s in segments if s.speaker == name), "uncertain_lines": 0}
    return True, confirmed
