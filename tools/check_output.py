"""Measure a finished dubbing run from its output folder. Prints numbers only.

    python tools/check_output.py out_dir

- file: container streams, duration difference from the source
- sync: how late each Vietnamese line starts, how far it runs past the original line
- intelligibility: Vietnamese speech recognition of the dub track compared with the
  text that was supposed to be spoken (a proxy for clarity, not for naturalness)
"""
import json, re, subprocess, sys, wave
from pathlib import Path

import numpy as np

out = Path(sys.argv[1]); work = out / "work"
report = json.loads((out / "report.json").read_text(encoding="utf-8"))
segs = json.loads((work / "segments.json").read_text(encoding="utf-8"))
video = out / report["output"]


def probe(path, entries, stream=None):
    cmd = ["ffprobe", "-v", "error", "-show_entries", entries, "-of", "csv=p=0"]
    if stream:
        cmd += ["-select_streams", stream]
    return subprocess.check_output(cmd + [str(path)], text=True).strip()


decode = subprocess.run(["ffmpeg", "-v", "error", "-i", str(video), "-f", "null", "-"], capture_output=True, text=True)
print(f"file: video={probe(video, 'stream=codec_name,width,height', 'v:0')} audio={probe(video, 'stream=codec_name,sample_rate,channels', 'a:0')} "
      f"duration={float(probe(video, 'format=duration')):.2f}s (source {report['duration_seconds']}s) "
      f"size={video.stat().st_size/1e6:.1f}MB decode_errors={len(decode.stderr.strip().splitlines())}")

with wave.open(str(work / "dub.wav")) as w:
    sr = w.getframerate(); dub = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32)
late, over, overlaps = [], [], 0
for i, s in enumerate(segs):
    nxt = segs[i + 1]["start"] if i + 1 < len(segs) else len(dub) / sr
    idx = np.nonzero(np.abs(dub[int(s["start"] * sr): int(nxt * sr)]) > 800)[0]
    if not len(idx):
        continue
    late.append(idx[0] / sr); over.append(max(0.0, s["start"] + idx[-1] / sr - s["end"]))
    overlaps += s["start"] + idx[-1] / sr > nxt - 0.01
pct = lambda v, p: sorted(v)[min(len(v) - 1, int(len(v) * p))] if v else 0
print(f"sync: lines={len(segs)} sped_up={report['sped_up']} max_speed={report['max_speed_used']} truncated={len(report['truncated'])} "
      f"start_delay_median={pct(late, .5):.2f}s overrun_median={pct(over, .5):.2f}s overrun_p90={pct(over, .9):.2f}s "
      f"overrun_max={max(over, default=0):.2f}s runs_into_next_line={overlaps}")

from faster_whisper import WhisperModel
x = np.interp(np.arange(0, len(dub), sr / 16000), np.arange(len(dub)), dub).astype(np.float32) / 32768
heard, _ = WhisperModel("small", device="auto", compute_type="auto").transcribe(x, language="vi", vad_filter=True)
norm = lambda t: re.sub(r"[^\w ]", " ", t.lower()).split()
ref, hyp = norm(" ".join(s["translation"] for s in segs)), norm(" ".join(h.text for h in heard))
d = list(range(len(hyp) + 1))
for i, r in enumerate(ref, 1):
    prev, d[0] = d[0], i
    for j, h in enumerate(hyp, 1):
        prev, d[j] = d[j], min(d[j] + 1, d[j - 1] + 1, prev + (r != h))
print(f"intelligibility: vietnamese_words={len(ref)} misheard_rate={d[-1]/max(len(ref),1):.3f}")
print(f"speakers: {json.dumps(report.get('speakers', {}), ensure_ascii=False)}")
print(f"time: {json.dumps(report['stage_seconds'])} total={report['elapsed_seconds']}s ({report['elapsed_seconds']/report['duration_seconds']:.1f}x realtime)")
