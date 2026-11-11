"""Word error rate of speech recognition against a reference subtitle file.

    python tools/stt_eval.py clip.mp4 reference.srt --model small --lang en
Prints numbers only (no transcript), so it is safe to run on any licensed material.
"""
import argparse, re, time
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("audio", type=Path); ap.add_argument("reference", type=Path)
    ap.add_argument("--model", default="small"); ap.add_argument("--lang", default="en"); ap.add_argument("--label", default="")
    a = ap.parse_args()
    ref = parse_srt(a.reference.read_text(encoding="utf-8", errors="replace"))
    t = time.time(); hyp = transcribe(a.audio, a.lang, a.model); elapsed = time.time() - t
    r, h = words(" ".join(s.text for s in ref)), words(" ".join(s.text for s in hyp))
    # start-time error: each reference line against the nearest recognised line start
    offs = sorted(min(abs(x.start - y.start) for y in hyp) for x in ref)
    print(f"{a.label or a.audio.name} model={a.model}: WER={wer(r, h):.3f} ref_words={len(r)} hyp_words={len(h)} "
          f"ref_lines={len(ref)} hyp_lines={len(hyp)} start_err_median={offs[len(offs)//2]:.2f}s "
          f"start_err_p90={offs[int(len(offs)*0.9)]:.2f}s time={elapsed:.1f}s")


if __name__ == "__main__":
    main()
