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
    speaker: str = ""
    uncertain: bool = False  # the speaker label is a weak guess and should be checked

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
            speaker=data.get("speaker", ""),
            uncertain=bool(data.get("uncertain", False)),
        )


class VietdubError(Exception):
    """An error the user can act on; the CLI prints it without a traceback."""


class TransientError(VietdubError):
    """A failure worth retrying later: a network call or an online service that did not answer."""


class ReviewNeeded(VietdubError):
    """The run stopped on purpose so a person can check speakers and voices."""
