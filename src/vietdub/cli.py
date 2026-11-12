from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .models import ReviewNeeded, VietdubError
from .rights import ALLOWED, Rights, check_rights


def _engine_options() -> argparse.ArgumentParser:
    e = argparse.ArgumentParser(add_help=False)
    e.add_argument("--lang", help="Ngôn ngữ gốc, ví dụ zh, ko, ja, en (mặc định: tự nhận)")
    e.add_argument("--asr-model", default="small", help="Model faster-whisper (mặc định: small)")
    e.add_argument("--translator", default="ollama",
                   help="ollama, gemini, hoặc none nếu phụ đề đã là tiếng Việt (mặc định: ollama)")
    e.add_argument("--model", help="Tên model dịch")
    e.add_argument("--base-url", help="Endpoint OpenAI-compatible khác cho bộ dịch")
    e.add_argument("--glossary", type=Path, help="File text: tên riêng và xưng hô cần giữ")
    e.add_argument("--tts", default="edge", help="edge, piper, beep (mặc định: edge)")
    e.add_argument("--voice", help="Giọng edge-tts (vd vi-VN-NamMinhNeural) hoặc file .onnx của Piper")
    e.add_argument("--speakers", nargs="?", const="auto", metavar="N",
                   help="Mỗi nhân vật một giọng; thêm số N nếu biết số nhân vật")
    e.add_argument("--review", action="store_true",
                   help="Dừng sau khi nhận diện người nói để bạn nghe, sửa và duyệt vai trước khi tạo giọng")
    e.add_argument("--cast", metavar="S1=male,S2=female",
                   help="Chỉ định giới tính giọng cho từng nhân vật khi máy đoán sai")
    e.add_argument("--speaker-model", type=Path, default=Path("models/3dspeaker_speech_eres2net_sv_en_voxceleb_16k.onnx"),
                   help="File model người nói (.onnx, loại sherpa-onnx đọc được)")
    e.add_argument("--separate", action="store_true", help="Dùng Demucs giữ lại nhạc nền, bỏ giọng gốc")
    e.add_argument("--max-speed", type=float, default=1.4, help="Tăng tốc giọng đọc tối đa (mặc định 1.4)")
    e.add_argument("--force", action="store_true", help="Chạy lại mọi bước, bỏ qua kết quả đã lưu")
    return e


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="vietdub", description="Tự động lồng tiếng Việt cho video.")
    p.add_argument("--version", action="version", version=__version__)
    sub = p.add_subparsers(dest="command", required=True)
    engines = _engine_options()

    r = sub.add_parser("run", parents=[engines], help="Lồng tiếng Việt cho một video")
    r.add_argument("video", type=Path)
    r.add_argument("-o", "--out", type=Path, default=Path("out"), help="Thư mục kết quả (mặc định: out)")
    r.add_argument("--license", help="Quyền sử dụng video: " + ", ".join(sorted(ALLOWED)))
    r.add_argument("--source", help="URL hoặc mô tả nguồn gốc video")
    r.add_argument("--attribution", help="Tên tác giả gốc (bắt buộc với cc-by, cc-by-sa)")
    r.add_argument("--srt", type=Path, help="Phụ đề có sẵn; bỏ qua bước nhận dạng giọng nói")

    lib = argparse.ArgumentParser(add_help=False)
    lib.add_argument("--library", type=Path, default=Path("library"), help="Thư mục thư viện (mặc định: library)")

    b = sub.add_parser("batch", parents=[engines, lib], help="Lồng tiếng mọi video đã tải trong thư viện")
    b.add_argument("--limit", type=int, default=10)

    ing = sub.add_parser("ingest", help="Tìm và tải video từ nguồn được phép")
    isub = ing.add_subparsers(dest="action", required=True)
    s = isub.add_parser("search", parents=[lib], help="Tìm video có giấy phép cho phép lồng tiếng")
    s.add_argument("source", choices=["archive", "commons", "youtube"])
    s.add_argument("query")
    s.add_argument("--limit", type=int, default=10)
    y = isub.add_parser("sync", parents=[lib], help="Lấy tập mới từ các kênh đã cấp phép trong sources.toml")
    y.add_argument("--config", type=Path, default=Path("sources.toml"))
    y.add_argument("--limit", type=int, default=20, help="Số video mới nhất xét trên mỗi kênh")
    ls = isub.add_parser("list", parents=[lib], help="Xem thư viện")
    ls.add_argument("--status")
    for name, text in (("approve", "Duyệt các mục đã tìm thấy để tải"), ("reject", "Loại các mục")):
        a = isub.add_parser(name, parents=[lib], help=text)
        a.add_argument("ids", nargs="+", help="Mã mục, hoặc 'all' cho mọi mục đang chờ duyệt")
    f = isub.add_parser("fetch", parents=[lib], help="Tải các mục đã duyệt")
    f.add_argument("--limit", type=int, default=10)
    return p


_LANG = {"eng": "en", "chi": "zh", "zho": "zh", "cmn": "zh", "jpn": "ja", "kor": "ko", "fra": "fr",
         "fre": "fr", "deu": "de", "ger": "de", "spa": "es", "rus": "ru", "tha": "th",
         "english": "en", "chinese": "zh", "japanese": "ja", "korean": "ko"}


def _language(code: str) -> str | None:
    """Catalog languages come as 'eng', 'English', 'zh'...; whisper wants two letters."""
    code = code.strip().lower()
    if len(code) == 2:
        return code
    return _LANG.get(code)  # unknown: let speech recognition detect it


def _job(args: argparse.Namespace, video: Path, out: Path, rights: Rights, srt: Path | None,
         language: str | None):
    from . import pipeline
    from .engines import tts
    from .engines.translate import ChatConfig

    if not 1.0 <= args.max_speed <= 2.0:
        raise VietdubError("--max-speed phải nằm trong khoảng 1.0–2.0.")
    chat = None
    if args.translator != "none":
        chat = ChatConfig.from_preset(args.translator, args.model, args.base_url).chat
    transcribe = None
    if not srt:
        from .engines.asr import transcribe as asr

        def transcribe(audio: Path):
            return asr(audio, language, args.asr_model)

    separate = None
    if args.separate:
        from .engines.separate import separate_background as separate

    diarize = cast = None
    if args.speakers:
        if args.tts != "edge":
            raise VietdubError("--speakers hiện chỉ dùng được với --tts edge.")
        if args.speakers != "auto" and not (args.speakers.isdigit() and int(args.speakers) > 0):
            raise VietdubError("--speakers nhận một số nguyên dương, hoặc để trống để tự đếm.")
        from .engines import casting, diarize as dia

        embed = dia.embedder(args.speaker_model)
        count = None if args.speakers == "auto" else int(args.speakers)

        def diarize(audio: Path, segments):
            return dia.assign_speakers(audio, segments, embed, count)

        forced = {}
        for pair in filter(None, (args.cast or "").split(",")):
            name, _, gender = pair.partition("=")
            if gender not in ("male", "female"):
                raise VietdubError("--cast có dạng S1=male,S2=female.")
            forced[name.strip()] = gender

        def cast(speakers: dict):
            for name, gender in forced.items():
                if name in speakers:
                    speakers[name]["gender"] = gender
            for info in speakers.values():
                info["voice_basis"] = "người duyệt" if info.get("gender") or info.get("voice") else "máy gợi ý"
            return {s: tts.edge(v.name, pitch=v.pitch, rate=v.rate) for s, v in casting.cast(speakers).items()}

    return pipeline.Job(
        diarize=diarize, cast=cast, review=bool(args.review and args.speakers),
        video=video, out_dir=out, rights=rights, synth=tts.get(args.tts, args.voice), chat=chat,
        transcribe=transcribe, separate=separate, subtitles=srt, source_language=language,
        glossary=args.glossary.read_text(encoding="utf-8") if args.glossary else "",
        max_speed=args.max_speed, force=args.force,
    )


def _summary(job, output: Path) -> None:
    rep = job.report
    print(f"Xong: {output}")
    print(f"  {rep['segments']} câu, {rep['sped_up']} câu phải tăng tốc, "
          f"{len(rep['truncated'])} câu bị cắt, {rep['elapsed_seconds']}s xử lý")
    if rep.get("speakers") and not rep.get("speakers_reviewed"):
        print("  Vai và giọng do máy tự gán, chưa có người duyệt (dùng --review để duyệt trước khi xuất).")
    if rep.get("untranslated"):
        print("  Câu bộ dịch chưa dịch được (cần sửa tay):", ", ".join(map(str, rep["untranslated"])))
    if rep["truncated"]:
        print("  Câu bị cắt (nên rút gọn bản dịch):", ", ".join(map(str, rep["truncated"])))


def _run(args: argparse.Namespace) -> int:
    from . import pipeline

    rights = check_rights(args.license, args.source, args.attribution)
    job = _job(args, args.video, args.out, rights, args.srt, args.lang)
    _summary(job, pipeline.run(job))
    return 0


def _batch(args: argparse.Namespace) -> int:
    from . import pipeline
    from .ingest.catalog import Catalog

    catalog = Catalog(args.library)
    todo = catalog.with_status("fetched")[: args.limit]
    if not todo:
        print("Không có video nào đã tải đang chờ lồng tiếng.")
        return 0
    failed = waiting = 0
    for item in todo:
        print(f"\n== {item.id}: {item.title}")
        try:
            source = item.page_url + (f" — {item.permission}" if item.permission else "")
            rights = check_rights(item.license, source, item.attribution)
            job = _job(args, Path(item.path), args.library / "dubbed" / item.slug(), rights, None,
                       args.lang or _language(item.language))
            _summary(job, pipeline.run(job))
            item.status, item.error = "dubbed", ""
        except ReviewNeeded as stop:
            print(f"Chờ duyệt vai: {stop} (sửa lines.tsv, cast.json rồi chạy lại lệnh batch)")
            waiting += 1
        except VietdubError as exc:
            item.status, item.error = "failed", str(exc)
            failed += 1
            print(f"Lỗi: {exc}", file=sys.stderr)
        catalog.save()
    return 1 if failed else 3 if waiting else 0


def _ingest(args: argparse.Namespace) -> int:
    from .ingest import archive, channels, commons, fetch, ytdlp
    from .ingest.catalog import STATUSES, Catalog

    catalog = Catalog(args.library)
    if args.action == "search":
        finder = {"archive": archive.search, "commons": commons.search,
                  "youtube": ytdlp.search_youtube_cc}[args.source]
        found = finder(args.query, args.limit)
        new = [i for i in found if catalog.add(i)]
        catalog.save()
        print(f"Tìm thấy {len(found)} video có giấy phép phù hợp, {len(new)} mục mới (chờ duyệt):")
        for i in new:
            print(f"  {i.id}  [{i.license}]  {i.title}  — {i.attribution or 'không rõ tác giả'}")
        if new:
            print("Xem từng trang nguồn để chắc giấy phép là thật, rồi: vietdub ingest approve <mã>")
    elif args.action == "sync":
        total = 0
        for channel in channels.load(args.config):
            new = [i for i in channels.sync(channel, args.limit) if catalog.add(i)]
            total += len(new)
            print(f"{channel.name}: {len(new)} tập mới")
        catalog.save()
        print(f"Tổng cộng {total} tập mới, sẵn sàng tải bằng: vietdub ingest fetch")
    elif args.action == "list":
        if args.status and args.status not in STATUSES:
            raise VietdubError("Trạng thái hợp lệ: " + ", ".join(STATUSES))
        items = catalog.with_status(args.status) if args.status else list(catalog.items.values())
        for i in items:
            print(f"{i.status:9} {i.id}  [{i.license}]  {i.title}" + (f"  ! {i.error}" if i.error else ""))
        print(f"{len(items)} mục")
    elif args.action in ("approve", "reject"):
        targets = catalog.with_status("found") if args.ids == ["all"] else [catalog.get(x) for x in args.ids]
        new_status = "approved" if args.action == "approve" else "rejected"
        for item in targets:
            retry = item.status == "failed" and not item.path  # a download that failed
            if args.action == "approve" and item.status != "found" and not retry:
                raise VietdubError(f"{item.id} đang ở trạng thái '{item.status}', không duyệt được.")
            item.status = new_status
        catalog.save()
        print(f"{len(targets)} mục → {new_status}")
    elif args.action == "fetch":
        done = fetch.fetch_approved(catalog, args.limit)
        print(f"Đã tải {done} video. Lồng tiếng bằng: vietdub batch")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return {"run": _run, "batch": _batch, "ingest": _ingest}[args.command](args)
    except ReviewNeeded as stop:
        print(f"\nĐã dừng để bạn duyệt vai. Mở thư mục: {stop}\n"
              "  1. Nghe các file .wav của từng người nói.\n"
              "  2. Sửa cột speaker (và translation nếu cần) trong lines.tsv; dấu ? là câu máy không chắc.\n"
              "  3. Trong cast.json điền gender (male/female) hoặc voice cho từng người, đổi reviewed thành true.\n"
              "  4. Chạy lại đúng lệnh này để tạo giọng và xuất video.")
        return 3
    except VietdubError as exc:
        print(f"Lỗi: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
