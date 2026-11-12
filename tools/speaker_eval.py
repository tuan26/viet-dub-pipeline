"""Compare speaker-detection methods on clips that have ground truth.

    python tools/speaker_eval.py --models models/ --clip NAME=path/to/vocals.wav ...

Ground truth: tests/data/speakers/NAME.json. Lines marked confidence=low are clustered
but not scored. Methods:
  lines:<model>       one embedding per line, then clustering (vietdub's approach)
  turns:<model>       pyannote segmentation 3.0 + embeddings via sherpa-onnx; each line
                      takes the speaker of the turn it overlaps most
Each runs with the speaker count detected automatically and with the true count given.
"""
import argparse, json, time
from pathlib import Path

import numpy as np
import sherpa_onnx

from vietdub.engines import diarize
from vietdub.engines.speaker_metrics import score

EMBEDDERS = {
    "wespeaker-r34": "wespeaker_en_voxceleb_resnet34_LM.onnx", "wespeaker-r293": "wespeaker_en_voxceleb_resnet293_LM.onnx",
    "wespeaker-cam++": "wespeaker_en_voxceleb_CAM++_LM.onnx", "titanet-large": "nemo_en_titanet_large.onnx",
    "eres2net-en": "3dspeaker_speech_eres2net_sv_en_voxceleb_16k.onnx",
    "campplus-zh-en": "3dspeaker_speech_campplus_sv_zh_en_16k-common_advanced.onnx",
}
ap = argparse.ArgumentParser()
ap.add_argument("--models", type=Path, required=True); ap.add_argument("--clip", action="append", required=True)
ap.add_argument("--out", type=Path); ap.add_argument("--only", default=""); ap.add_argument("--methods", default="lines,turns"); ap.add_argument("--context", type=float, default=2.5); ap.add_argument("--threshold", type=float, default=0.75)
args = ap.parse_args()
truth_dir = Path(__file__).parent.parent / "tests/data/speakers"


def extractor(path):
    ex = sherpa_onnx.SpeakerEmbeddingExtractor(sherpa_onnx.SpeakerEmbeddingExtractorConfig(model=str(path), num_threads=2))
    def embed(samples):
        stream = ex.create_stream(); stream.accept_waveform(16000, samples); stream.input_finished()
        return np.array(ex.compute(stream))
    return embed


def by_lines(samples, lines, embed, n):
    need = int(args.context * 16000); vecs = []
    for l in lines:
        a, b = int(l["start"] * 16000), int(l["end"] * 16000)
        if b - a < need:
            pad = (need - (b - a)) // 2; a, b = max(0, a - pad), min(len(samples), b + pad)
        vecs.append(embed(samples[a:b]))
    return [f"S{x}" for x in diarize.cluster(vecs, args.threshold, n, min_lines=1 if n else 2)]


def by_turns(samples, lines, model, n):
    cfg = sherpa_onnx.OfflineSpeakerDiarizationConfig(
        segmentation=sherpa_onnx.OfflineSpeakerSegmentationModelConfig(
            pyannote=sherpa_onnx.OfflineSpeakerSegmentationPyannoteModelConfig(model=str(args.models / "pyannote_seg3.onnx"))),
        embedding=sherpa_onnx.SpeakerEmbeddingExtractorConfig(model=str(model), num_threads=2),
        clustering=sherpa_onnx.FastClusteringConfig(num_clusters=n or -1, threshold=0.5),
        min_duration_on=0.2, min_duration_off=0.3)
    turns = sherpa_onnx.OfflineSpeakerDiarization(cfg).process(samples).sort_by_start_time()
    out = []
    for l in lines:
        overlap = {}
        for t in turns:
            o = min(l["end"], t.end) - max(l["start"], t.start)
            if o > 0:
                overlap[t.speaker] = overlap.get(t.speaker, 0) + o
        out.append(f"S{max(overlap, key=overlap.get)}" if overlap else None)
    return out


rows = []
for item in args.clip:
    name, wav = item.split("=", 1)
    lines = json.loads((truth_dir / f"{name}.json").read_text(encoding="utf-8"))["lines"]
    samples = diarize.load_audio(Path(wav))
    keep = [i for i, l in enumerate(lines) if l["confidence"] != "low"]
    truth = [lines[i]["speaker"] for i in keep]; n_true = len(set(truth))
    for label, file in EMBEDDERS.items():
        if not (args.models / file).exists() or (args.only and label not in args.only.split(",")):
            continue
        embed = extractor(args.models / file)
        for method, fn in (("lines", lambda n: by_lines(samples, lines, embed, n)), ("turns", lambda n: by_turns(samples, lines, args.models / file, n))):
            if method not in args.methods.split(","):
                continue
            for mode, n in (("auto", None), ("known", n_true)):
                if mode == "known" and any(l["confidence"] == "low" for l in lines):
                    continue  # the true count is unknown when unlabelled characters also speak
                t = time.time(); found = fn(n); el = time.time() - t
                s = score(truth, [found[i] for i in keep])
                rows.append({"clip": name, "method": f"{method}:{label}", "count": mode, **s, "seconds": round(el, 1)})
                print(f"{name:22s} {method}:{label:15s} {mode:5s} acc={s['accuracy']:.2f} correct={s['correct']}/{s['lines']} wrong={s['wrong_speaker']} none={s['no_speaker']} found={s['speakers_found']} true={s['speakers_true']} {el:.1f}s", flush=True)
if args.out:
    args.out.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
