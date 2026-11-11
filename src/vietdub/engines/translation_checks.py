"""Score translations against pattern checks. Used by the translation benchmark,
which decides whether a model or prompt change is actually better."""
from __future__ import annotations

import re

_FOREIGN = re.compile(r"[\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af]")  # Chinese, Japanese kana, Korean


def check_line(case: dict, translation: str) -> list[str]:
    """Return the reasons a translation fails its case; an empty list is a pass."""
    text = translation.lower()
    problems = []
    if not translation.strip():
        return ["bản dịch rỗng"]
    if _FOREIGN.search(translation):
        problems.append("còn chữ nước ngoài chưa dịch")
    for pattern in case.get("all", []):
        if not re.search(pattern.lower(), text):
            problems.append(f"thiếu: {pattern}")
    options = case.get("any", [])
    if options and not any(re.search(p.lower(), text) for p in options):
        problems.append("không khớp phương án nào: " + " | ".join(options[:3]))
    for pattern in case.get("none", []):
        if re.search(pattern.lower(), text):
            problems.append(f"có nội dung sai: {pattern}")
    return problems


def summarize(results: list[dict]) -> dict:
    """results: [{"cat": str, "problems": list}] -> pass counts overall and per category."""
    by_cat: dict[str, list[int]] = {}
    for r in results:
        passed, total = by_cat.setdefault(r["cat"], [0, 0])
        by_cat[r["cat"]] = [passed + (not r["problems"]), total + 1]
    done = sum(p for p, _ in by_cat.values())
    return {"passed": done, "total": len(results), "by_category": {k: f"{p}/{t}" for k, (p, t) in sorted(by_cat.items())}}
