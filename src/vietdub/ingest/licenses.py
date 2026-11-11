"""Map the licence text or URL a source reports onto the licences vietdub accepts."""
from __future__ import annotations

import re

_BLOCKING = {"nc", "nd", "noncommercial", "noderivs", "noderivatives", "arr", "copyrighted"}


def normalize(raw: str | None) -> str | None:
    """Return cc0, public-domain, cc-by, cc-by-sa — or None when the licence is
    missing, unknown, or forbids derivatives or commercial use."""
    if not raw:
        return None
    text = raw.lower()
    tokens = set(re.split(r"[^a-z0-9]+", text))
    if tokens & _BLOCKING or "non-commercial" in text or "no derivative" in text or "all rights" in text:
        return None
    if "cc0" in tokens or "publicdomain/zero" in text:
        return "cc0"
    if "publicdomain" in tokens or "public domain" in text or "pd" in tokens:
        return "public-domain"
    if "sa" in tokens or "sharealike" in tokens or "share alike" in text:
        return "cc-by-sa" if ("by" in tokens or "attribution" in tokens) else None
    if "by" in tokens and ("cc" in tokens or "creativecommons" in tokens or "licenses" in tokens):
        return "cc-by"
    if "creative commons attribution" in text:
        return "cc-by"
    return None
