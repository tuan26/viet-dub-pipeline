import json, subprocess, sys, re
import numpy as np
from faster_whisper import WhisperModel
out, work = sys.argv[1], sys.argv[2]
segs = json.load(open(f"{work}/segments.json"))
raw = subprocess.run(["ffmpeg","-v","error","-i",out,"-f","s16le","-ac","1","-ar","16000","-"],capture_output=True).stdout
x = np.frombuffer(raw, np.int16).astype(np.float32)/32768
m = WhisperModel("small", device="auto", compute_type="auto")
res,_ = m.transcribe(x, language="vi", vad_filter=True)
res = list(res)
print("== nghe lại file đầu ra (whisper small, vi)")
for r in res: print(f"  {r.start:6.2f}-{r.end:6.2f}  {r.text.strip()}")
print("== câu đã lồng (thời điểm bắt đầu theo kế hoạch)")
for s in segs: print(f"  {s['start']:6.2f}-{s['end']:6.2f}  {s['translation']}")
# energy-based onset check on the dub track itself
import wave
w = wave.open(f"{work}/dub.wav"); d = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32); sr = w.getframerate()
print("== lệch giữa lúc câu gốc bắt đầu và lúc giọng Việt thực sự phát ra tiếng")
for i, s in enumerate(segs):
    a = int(s["start"]*sr); b = int((segs[i+1]["start"] if i+1 < len(segs) else len(d)/sr)*sr)
    chunk = np.abs(d[a:b]); idx = np.nonzero(chunk > 800)[0]
    onset = idx[0]/sr if len(idx) else None; last = idx[-1]/sr if len(idx) else None
    print(f"  câu {s['index']:2d}: tiếng bắt đầu sau {onset:.2f}s, kết thúc ở {s['start']+last:6.2f}s (câu gốc hết {s['end']:.2f}s, câu kế bắt đầu {b/sr:.2f}s)")
