from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class FuzzyMatch:
    matches: bool
    score: float


def fuzzy_match(query: str, text: str) -> FuzzyMatch:
    """
    Match if all query characters appear in order (not necessarily consecutive).
    Lower score = better match.  Rewards consecutive runs and word-boundary hits.
    """
    q = query.lower()
    t = text.lower()

    def _match(q: str) -> FuzzyMatch:
        if not q:
            return FuzzyMatch(True, 0)
        if len(q) > len(t):
            return FuzzyMatch(False, 0)

        qi = 0
        score = 0.0
        last = -1
        consecutive = 0

        for i, ch in enumerate(t):
            if qi < len(q) and ch == q[qi]:
                is_boundary = i == 0 or bool(re.match(r"[\s\-_./:]", t[i - 1]))
                if last == i - 1:
                    consecutive += 1
                    score -= consecutive * 5
                else:
                    consecutive = 0
                    if last >= 0:
                        score += (i - last - 1) * 2
                if is_boundary:
                    score -= 10
                score += i * 0.1
                last = i
                qi += 1

        if qi < len(q):
            return FuzzyMatch(False, 0)
        if q == t:
            score -= 100
        return FuzzyMatch(True, score)

    result = _match(q)
    if result.matches:
        return result

    # Try swapped alphanumeric order (e.g. "v3" matches "3v")
    m = re.match(r"^(?P<a>[a-z]+)(?P<d>[0-9]+)$", q) or re.match(r"^(?P<d>[0-9]+)(?P<a>[a-z]+)$", q)
    if m:
        swapped = (m.group("d") + m.group("a")) if "a" in m.groupdict() else ""
        if swapped:
            alt = _match(swapped)
            if alt.matches:
                return FuzzyMatch(True, alt.score + 5)

    return result


def fuzzy_filter(items: list, query: str, get_text) -> list:
    """
    Filter and sort items by fuzzy match quality (best matches first).
    Supports space-separated tokens — all tokens must match.
    `get_text` is a callable that extracts the searchable string from an item.
    """
    if not query.strip():
        return items

    tokens = [t for t in query.strip().split() if t]
    if not tokens:
        return items

    scored: list[tuple[object, float]] = []
    for item in items:
        text = get_text(item)
        total = 0.0
        ok = True
        for token in tokens:
            m = fuzzy_match(token, text)
            if m.matches:
                total += m.score
            else:
                ok = False
                break
        if ok:
            scored.append((item, total))

    scored.sort(key=lambda x: x[1])
    return [item for item, _ in scored]
