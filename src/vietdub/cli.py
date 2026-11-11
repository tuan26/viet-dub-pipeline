from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .models import VietdubError
from .rights import ALLOWED, check_rights


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="vietdub", description="Tự động lồng tiếng Việt cho video.")
    p.add_argument("--version", action="version", version=__version__)
    sub = p.add_subparsers(dest="command", required=True)

    r = sub.add_parser("run", help="Lồng tiếng Việt cho một video")
    r.add_argument("video", type=Path)
    r.add_argument("-o", "--out", type=Path, default=Path("out"), help="Thư mục kết quả (mặc định: out)")
    r.add_argument("--license", help="Quyền sử dụng video: " + ", ".join(sorted(ALLOWED)))
    r.add_argument("--source", help="URL hoặc mô tả nguồn gốc video")
    r.add_argument("--attribution", help="Tên tác giả gốc (bắt buộc với cc-by, cc-by-sa)")
    r.add_argument("--srt", type=Path, help="Phụ đề có sẵn; bỏ qua bước nhận dạng giọng nói")
    r.add_argument("--lang", help="Ngôn ngữ gốc, ví dụ zh, ko, ja, en (mặc định: tự nhận)")
    r.add_argument("--asr-model", default="small", help="Model faster-whisper (mặc định: small)")
    r.add_argument("--translator", default="ollama",
                   help="ollama, gemini, hoặc none nếu phụ đề đã là tiếng Việt (mặc định: ollama)")
    r.add_argument("--model", help="Tên model dịch")
    r.add_argument("--base-url", help="Endpoint OpenAI-compatible khác cho bộ dịch")
    r.add_argument("--glossary", type=Path, help="File text: tên riêng và xưng hô cần giữ")
    r.add_argument("--tts", default="edge", help="edge, piper, beep (mặc định: edge)")
    r.add_argument("--voice", help="Giọng edge-tts (vd vi-VN-NamMinhNeural) hoặc file .onnx của Piper")
    r.add_argument("--separate", action="store_true", help="Dùng Demucs giữ lại nhạc nền, bỏ giọng gốc")
    r.add_argument("--max-speed", type=float, default=1.4, help="Tăng tốc giọng đọc tối đa (mặc định 1.4)")
    r.add_argument("--force", action="store_true", help="Chạy lại mọi bước, bỏ qua kết quả đã lưu")
    return p


def _run(args: argparse.Namespace) -> int:
    from . import pipeline
    from .engines import tts
    from .engines.translate import ChatConfig

    rights = check_rights(args.license, args.source, args.attribution)
    if not 1.0 <= args.max_speed <= 2.0:
        raise VietdubError("--max-speed phải nằm trong khoảng 1.0–2.0.")

    chat = None
    if args.translator != "none":
        chat = ChatConfig.from_preset(args.translator, args.model, args.base_url).chat

    transcribe = None
    if not args.srt:
        from .engines.asr import transcribe as asr

        def transcribe(audio: Path):
            return asr(audio, args.lang, args.asr_model)

    separate = None
    if args.separate:
        from .engines.separate import separate_background as separate

    job = pipeline.Job(
        video=args.video,
        out_dir=args.out,
        rights=rights,
        synth=tts.get(args.tts, args.voice),
        chat=chat,
        transcribe=transcribe,
        separate=separate,
        subtitles=args.srt,
        source_language=args.lang,
        glossary=args.glossary.read_text(encoding="utf-8") if args.glossary else "",
        max_speed=args.max_speed,
        force=args.force,
    )
    output = pipeline.run(job)
    rep = job.report
    print(f"\nXong: {output}")
    print(f"  {rep['segments']} câu, {rep['sped_up']} câu phải tăng tốc, "
          f"{len(rep['truncated'])} câu bị cắt, {rep['elapsed_seconds']}s xử lý")
    if rep["truncated"]:
        print("  Câu bị cắt (nên rút gọn bản dịch):", ", ".join(map(str, rep["truncated"])))
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return _run(args)
    except VietdubError as exc:
        print(f"Lỗi: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
