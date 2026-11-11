"""Who speaks each line: one voice embedding per segment, then clustering.

The embedding model is WeSpeaker ResNet34-LM (ONNX, CC-BY-4.0, usable commercially
with attribution). The clustering and the pitch estimate are plain numpy so they can
be tested, and the embedding function can be swapped for another model.
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Callable

from ..models import Segment, VietdubError

RATE = 16000
MODEL_URL = "https://huggingface.co/Wespeaker/wespeaker-voxceleb-resnet34-LM/resolve/main/voxceleb_resnet34_LM.onnx"
EmbedFn = Callable[["np.ndarray"], "np.ndarray"]  # mono float32 samples at 16 kHz -> vector


def load_audio(path: Path):
    import numpy as np

    proc = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path), "-f", "s16le", "-ac", "1", "-ar", str(RATE), "-"],
        capture_output=True,
    )
    if proc.returncode != 0 or not proc.stdout:
        raise VietdubError(f"Không giải mã được âm thanh {path}.")
    return np.frombuffer(proc.stdout, np.int16).astype(np.float32) / 32768.0


def wespeaker(model_path: Path) -> EmbedFn:
    try:
        import kaldi_native_fbank as knf
        import numpy as np
        import onnxruntime as ort
    except ImportError:
        raise VietdubError("Thiếu thư viện nhận diện người nói. Chạy: pip install 'vietdub[speakers]'")
    if not model_path.is_file():
        raise VietdubError(f"Không thấy model người nói tại {model_path}. Tải từ:\n  {MODEL_URL}")
    session = ort.InferenceSession(str(model_path), providers=["CPUExecutionProvider"])

    def embed(samples):
        opts = knf.FbankOptions()
        opts.frame_opts.samp_freq = RATE
        opts.frame_opts.dither = 0.0
        opts.mel_opts.num_bins = 80
        fbank = knf.OnlineFbank(opts)
        fbank.accept_waveform(RATE, (samples * 32768).tolist())
        fbank.input_finished()
        feats = np.stack([fbank.get_frame(i) for i in range(fbank.num_frames_ready)])
        feats = feats - feats.mean(axis=0, keepdims=True)
        return session.run(None, {"feats": feats[None].astype(np.float32)})[0][0]

    return embed


def cluster(vectors, threshold: float = 0.75, speakers: int | None = None, min_lines: int = 1) -> list[int]:
    """Average-linkage clustering on cosine distance. Merging stops at ``speakers``
    clusters when given, otherwise when the closest pair is further than ``threshold``."""
    import numpy as np

    x = np.asarray(vectors, dtype=np.float64)
    x = x / np.maximum(np.linalg.norm(x, axis=1, keepdims=True), 1e-9)
    dist = 1.0 - x @ x.T
    groups = [[i] for i in range(len(x))]
    while len(groups) > (speakers or 1):
        best, pair = None, None
        for a in range(len(groups)):
            for b in range(a + 1, len(groups)):
                d = dist[np.ix_(groups[a], groups[b])].mean()
                if best is None or d < best:
                    best, pair = d, (a, b)
        if speakers is None and best > threshold:
            break
        a, b = pair
        groups[a] += groups.pop(b)
    # A "speaker" with fewer than min_lines lines is usually a noisy embedding of a
    # short line, so it joins the nearest real speaker.
    if speakers is None and min_lines > 1:
        big = [g for g in groups if len(g) >= min_lines]
        if big:
            for small in [g for g in groups if len(g) < min_lines]:
                min(big, key=lambda g: dist[np.ix_(small, g)].mean()).extend(small)
            groups = big
    labels = [0] * len(x)
    # number speakers in order of first appearance
    for number, group in enumerate(sorted(groups, key=min)):
        for i in group:
            labels[i] = number
    return labels


def pitch(samples) -> float:
    """Median fundamental frequency in Hz (autocorrelation, 60-400 Hz); 0 if unvoiced."""
    import numpy as np

    frame, hop, values = int(0.04 * RATE), int(0.02 * RATE), []
    lo, hi = RATE // 400, RATE // 60
    for start in range(0, len(samples) - frame, hop):
        w = samples[start : start + frame]
        w = w - w.mean()
        energy = float(w @ w)
        if energy < 1e-3 * frame * 0.01:
            continue
        ac = np.correlate(w, w, "full")[frame - 1 :]
        lag = lo + int(np.argmax(ac[lo:hi]))
        if ac[lag] > 0.35 * ac[0]:
            values.append(RATE / lag)
    return float(np.median(values)) if values else 0.0


def assign_speakers(
    audio: Path,
    segments: list[Segment],
    embed: EmbedFn,
    speakers: int | None = None,
    threshold: float = 0.75,
    context: float = 2.5,
) -> dict[str, dict]:
    """Set ``segment.speaker`` ("S1", "S2", ...) and return per-speaker info:
    {"S1": {"lines": n, "pitch_hz": f, "gender": "male" | "female"}}."""
    import numpy as np

    samples = load_audio(audio)
    # Film lines are short (about 1-2 s); measured on real films, embeddings of such short
    # pieces are too noisy to cluster, so each line is widened to ``context`` seconds.
    min_len = int(context * RATE)
    pieces = []
    for seg in segments:
        a, b = int(seg.start * RATE), int(seg.end * RATE)
        if b - a < min_len:  # widen very short lines so the embedding has enough speech
            pad = (min_len - (b - a)) // 2
            a, b = max(0, a - pad), min(len(samples), b + pad)
        pieces.append(samples[a:b] if b > a else samples[:min_len])
    labels = cluster([embed(p) for p in pieces], threshold, speakers, min_lines=2)
    info: dict[str, dict] = {}
    for seg, label, piece in zip(segments, labels, pieces):
        seg.speaker = f"S{label + 1}"
        info.setdefault(seg.speaker, {"lines": 0, "_pitch": []})
        info[seg.speaker]["lines"] += 1
        f0 = pitch(samples[int(seg.start * RATE) : int(seg.end * RATE)])
        if f0:
            info[seg.speaker]["_pitch"].append(f0)
    for data in info.values():
        f0 = float(np.median(data.pop("_pitch"))) if data["_pitch"] else 0.0
        data["pitch_hz"] = round(f0, 1)
        data["gender"] = "female" if f0 >= 165 else "male"
    return info
