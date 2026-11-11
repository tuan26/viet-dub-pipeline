from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass
class Segment:
    """One line of dialogue, in seconds from the start of the video."""

    index: int
    start: float
    end: float
    text: str
    translation: str = ""

    @property
    def duration(self) -> float:
        return self.end - self.start

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Segment":
        return cls(
            index=int(data["index"]),
            start=float(data["start"]),
            end=float(data["end"]),
            text=data["text"],
            translation=data.get("translation", ""),
        )


class VietdubError(Exception):
    """An error the user can act on; the CLI prints it without a traceback."""
