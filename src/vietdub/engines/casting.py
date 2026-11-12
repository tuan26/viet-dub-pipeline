"""Give every speaker a distinct Vietnamese voice."""
from __future__ import annotations

from dataclasses import dataclass

# edge-tts has one female and one male Vietnamese voice; further speakers of the
# same gender get the same voice shifted in pitch and pace so they stay distinguishable.
EDGE_VOICES = {"female": "vi-VN-HoaiMyNeural", "male": "vi-VN-NamMinhNeural"}
VARIANTS = [("+0Hz", "+0%"), ("-18Hz", "-4%"), ("+22Hz", "+5%"), ("-32Hz", "+3%"), ("+38Hz", "-3%")]


@dataclass(frozen=True)
class Voice:
    name: str
    pitch: str = "+0Hz"
    rate: str = "+0%"


def cast(speakers: dict[str, dict]) -> dict[str, Voice]:
    """speakers: {"S1": {"gender": "male", "lines": 12}, ...}. ``gender`` is what a person
    confirmed; without it the automatic ``suggested_gender`` is used. A speaker may also
    name its ``voice`` (and ``pitch``, ``rate``) outright. Within a gender the speaker
    with the most lines gets the unmodified voice."""
    result: dict[str, Voice] = {}
    gender_of = {s: d.get("gender") or d.get("suggested_gender") for s, d in speakers.items()}
    for speaker, d in speakers.items():
        if d.get("voice"):
            result[speaker] = Voice(d["voice"], d.get("pitch") or "+0Hz", d.get("rate") or "+0%")
    for gender, voice in EDGE_VOICES.items():
        same = sorted((s for s in speakers if gender_of[s] == gender and s not in result),
                      key=lambda s: (-speakers[s].get("lines", 0), s))
        for n, speaker in enumerate(same):
            pitch, rate = VARIANTS[n % len(VARIANTS)]
            result[speaker] = Voice(voice, pitch, rate)
    return result
