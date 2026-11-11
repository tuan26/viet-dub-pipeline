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
    """speakers: {"S1": {"gender": "male", "lines": 12}, ...}. Within a gender the
    speaker with the most lines gets the unmodified voice."""
    result: dict[str, Voice] = {}
    for gender, voice in EDGE_VOICES.items():
        same = sorted((s for s, d in speakers.items() if d.get("gender") == gender),
                      key=lambda s: (-speakers[s].get("lines", 0), s))
        for n, speaker in enumerate(same):
            pitch, rate = VARIANTS[n % len(VARIANTS)]
            result[speaker] = Voice(voice, pitch, rate)
    return result
