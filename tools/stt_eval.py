"""Speech recognition against a reference subtitle file. Prints numbers only.

    python tools/stt_eval.py audio_or_video reference.srt --model small --lang en [--no-vad]

WER            word error rate over the whole clip
missed         reference lines of which less than half the words were recognised nearby
start_err      distance from each found reference line to the nearest recognised line start
"""
import argparse, json, re, time
from pathlib import Path

from vietdub.engines.asr import transcribe
from vietdub.srt import parse_srt

NUMBERS = {"zero": "0", "one": "1", "two": "2", "three": "3", "four": "4", "five": "5", "six": "6", "seven": "7",
           "eight": "8", "nine": "9", "ten": "10", "twenty": "20"}


def words(text: str) -> list[str]:
    text = re.sub(r"<[^>]+>|\[[^\]]*\]|\([^)]*\)", " ", text.lower())
    return [NUMBERS.get(w, w) for w in re.sub(r"[^a-z0-9' ]", " ", text).replace("'", "").split()]


def wer(ref: list[str], hyp: list[str]) -> float:
    d = list(range(len(hyp) + 1))
    for i, r in enumerate(ref, 1):
        prev, d[0] = d[0], i
        for j, h in enumerate(hyp, 1):
            prev, d[j] = d[j], min(d[j] + 1, d[j - 1] + 1, prev + (r != h))
    return d[-1] / max(len(ref), 1)


def missed_lines(ref, hyp, window: float = 1.5) -> list[int]:
    out = []
    for line in ref:
        near = [w for h in hyp if h.end > line.start - window and h.start < line.end + window for w in words(h.text)]
        want = words(line.text)
        if want and sum(1 for w in want if w in near) < 0.5 * len(want):
            out.append(line.index)
    return out


def evaluate(audio: Path, reference: Path, model: str, lang: str, vad: bool = True) -> dict:
    ref = parse_srt(reference.read_text(encoding="utf-8", errors="replace"))
    t = time.time(); hyp = transcribe(audio, lang, model, vad); elapsed = time.time() - t
    missed = missed_lines(ref, hyp)
    offs = sorted(min(abs(x.start - y.start) for y in hyp) for x in ref if x.index not in missed) or [0.0]
    return {"wer": round(wer(words(" ".join(s.text for s in ref)), words(" ".join(s.text for s in hyp))), 3),
            "ref_lines": len(ref), "hyp_lines": len(hyp), "missed": len(missed), "missed_indexes": missed,
            "start_err_median": round(offs[len(offs) // 2], 2), "start_err_p90": round(offs[int(len(offs) * 0.9)], 2),
            "seconds": round(elapsed, 1)}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("audio", type=Path); ap.add_argument("reference", type=Path)
    ap.add_argument("--model", default="small"); ap.add_argument("--lang", default="en")
    ap.add_argument("--no-vad", action="store_true"); ap.add_argument("--label", default="")
    a = ap.parse_args()
    r = evaluate(a.audio, a.reference, a.model, a.lang, not a.no_vad)
    print(json.dumps({"label": a.label or a.audio.name, "model": a.model, "vad": not a.no_vad, **r}))
