"""Compare TTS engines on the same Vietnamese lines: speed, failures, speech rate.

    python tools/tts_eval.py out_dir edge:vi-VN-HoaiMyNeural edge:vi-VN-NamMinhNeural piper:path/to/voice.onnx

Writes one audio file per line and engine (to listen to) and results.json.
Intelligibility is measured with --listen (Vietnamese speech recognition, slower).
"""
import json, re, sys, time
from pathlib import Path

from vietdub import media
from vietdub.engines import tts
from vietdub.models import VietdubError

LINES = [
    "Chào buổi sáng, chị đã làm xong báo cáo cho khách hàng chưa?",
    "Chưa đầy một tiếng nữa là cuộc họp bắt đầu rồi.",
    "Đừng lo, cho em hai mươi phút là xong.",
    "Tôi đã bán một nghìn hai trăm vé, không phải mười hai nghìn.",
    "Mẹ ơi, con về rồi! Con đói quá.",
    "Nghe này, đây không phải trò chơi đâu.",
    "Anh không hề nói là cậu ấy lấy tiền.",
    "Cảm ơn.",
    "Ngoài kia mưa như trút nước, nhớ mang ô nhé!",
    "Tàu rời ga lúc chín giờ kém mười lăm.",
]
out = Path(sys.argv[1]); listen = "--listen" in sys.argv
specs = [a for a in sys.argv[2:] if not a.startswith("--")]
results = {}
for spec in specs:
    kind, _, voice = spec.partition(":")
    label = f"{kind}-{Path(voice).stem.replace('vi-VN-', '').replace('Neural', '')}"
    folder = out / label; folder.mkdir(parents=True, exist_ok=True)
    synth = tts.get(kind, voice)
    row = {"failures": 0, "synth_seconds": [], "speech_seconds": [], "syllables": 0}
    for i, text in enumerate(LINES, 1):
        t = time.time()
        try:
            clip = synth(text, folder / f"{i:02d}_raw")
        except VietdubError:
            row["failures"] += 1
            continue
        row["synth_seconds"].append(time.time() - t)
        trimmed = folder / f"{i:02d}.wav"
        media.trim_silence(clip, trimmed)
        row["speech_seconds"].append(media.duration(trimmed)); row["syllables"] += len(text.split())
    speech = sum(row["speech_seconds"])
    summary = {"lines": len(LINES), "failures": row["failures"],
               "synth_seconds_per_line": round(sum(row["synth_seconds"]) / max(len(row["synth_seconds"]), 1), 2),
               "realtime_factor": round(sum(row["synth_seconds"]) / max(speech, 1e-9), 2),
               "syllables_per_second": round(row["syllables"] / max(speech, 1e-9), 2)}
    if listen:
        import numpy as np, subprocess
        from faster_whisper import WhisperModel
        model = WhisperModel("small", device="auto", compute_type="auto")
        norm = lambda s: re.sub(r"[^\w ]", " ", s.lower()).split()
        errors = total = 0
        for i, text in enumerate(LINES, 1):
            f = folder / f"{i:02d}.wav"
            if not f.exists():
                continue
            raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(f), "-f", "s16le", "-ac", "1", "-ar", "16000", "-"], capture_output=True).stdout
            heard, _ = model.transcribe(np.frombuffer(raw, np.int16).astype(np.float32) / 32768, language="vi")
            ref, hyp = norm(text), norm(" ".join(h.text for h in heard))
            d = list(range(len(hyp) + 1))
            for a, r in enumerate(ref, 1):
                prev, d[0] = d[0], a
                for b, h in enumerate(hyp, 1):
                    prev, d[b] = d[b], min(d[b] + 1, d[b - 1] + 1, prev + (r != h))
            errors += d[-1]; total += len(ref)
        summary["misheard_rate"] = round(errors / total, 3)
    results[label] = summary
    print(label, json.dumps(summary))
(out / "results.json").write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
