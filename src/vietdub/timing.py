"""Decide how each dubbed line fits the time slot of the original line."""
from __future__ import annotations

from dataclasses import dataclass

from .models import Segment

GAP = 0.05  # silence kept before the next line starts


@dataclass
class Placement:
    index: int
    start: float
    speed: float  # tempo factor applied to the synthesized clip (>= 1.0)
    length: float  # seconds the clip occupies after speed-up and trimming
    truncated: bool


def plan(
    segments: list[Segment],
    clip_durations: list[float],
    total_duration: float,
    max_speed: float = 1.4,
) -> list[Placement]:
    """A line may run past its own end into the silence before the next line,
    is sped up to at most ``max_speed``, and is trimmed only as a last resort."""
    placements = []
    for i, (seg, dur) in enumerate(zip(segments, clip_durations)):
        slot_end = segments[i + 1].start if i + 1 < len(segments) else total_duration
        available = max(slot_end - seg.start - GAP, 0.1)
        if dur <= available:
            placements.append(Placement(seg.index, seg.start, 1.0, dur, False))
            continue
        speed = min(dur / available, max_speed)
        length = dur / speed
        truncated = length > available + 1e-6
        placements.append(
            Placement(seg.index, seg.start, round(speed, 4), min(length, available), truncated)
        )
    return placements
