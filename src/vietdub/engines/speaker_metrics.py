"""Score predicted speaker labels against ground truth."""
from __future__ import annotations

from itertools import permutations


def best_mapping(truth: list[str], found: list[str]) -> dict[str, str]:
    """Map each found label to a true speaker so that the number of matching lines is
    largest, using each true speaker at most once (extra found labels map to nothing)."""
    true_names, found_names = sorted(set(truth)), sorted(set(found))
    hits = {(f, t): sum(1 for a, b in zip(truth, found) if a == t and b == f) for f in found_names for t in true_names}
    if len(true_names) <= 6 and len(found_names) <= 6:
        size = max(len(true_names), len(found_names))
        padded = true_names + [""] * (size - len(true_names))
        best = max(permutations(padded, len(found_names)),
                   key=lambda p: sum(hits.get((f, t), 0) for f, t in zip(found_names, p)))
        return dict(zip(found_names, best))
    mapping, used = {}, set()
    for f, t in sorted(hits, key=lambda k: -hits[k]):  # greedy for many labels
        if f not in mapping and t not in used:
            mapping[f] = t
            used.add(t)
    return {f: mapping.get(f, "") for f in found_names}


def score(truth: list[str], found: list[str | None]) -> dict:
    """truth/found are per line; a found label of None means the system gave no speaker."""
    judged = [(t, f) for t, f in zip(truth, found) if f is not None]
    mapping = best_mapping([t for t, _ in judged], [f for _, f in judged]) if judged else {}
    correct = sum(1 for t, f in judged if mapping[f] == t)
    return {
        "lines": len(truth),
        "correct": correct,
        "wrong_speaker": len(judged) - correct,
        "no_speaker": len(truth) - len(judged),
        "accuracy": round(correct / len(truth), 3) if truth else 0.0,
        "speakers_true": len(set(truth)),
        "speakers_found": len({f for _, f in judged}),
    }
