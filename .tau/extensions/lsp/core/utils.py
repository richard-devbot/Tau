from __future__ import annotations

from pathlib import Path


def detect_indent(path_str: str) -> tuple[int, bool]:
    """Return (tab_size, insert_spaces) by inspecting the file's leading whitespace.

    Looks at up to 200 lines. Falls back to (4, True) on any error.
    """
    try:
        lines = Path(path_str).read_text(errors="replace").splitlines()[:200]
        tabs = sum(1 for l in lines if l.startswith("\t"))
        spaces = sum(1 for l in lines if l.startswith("  "))
        if tabs > spaces:
            return 4, False
        counts: dict[int, int] = {}
        for line in lines:
            if line.startswith(" "):
                n = len(line) - len(line.lstrip(" "))
                if n in (2, 4, 8):
                    counts[n] = counts.get(n, 0) + 1
        tab_size = max(counts, key=lambda k: counts[k]) if counts else 4
        return tab_size, True
    except Exception:
        return 4, True
