from __future__ import annotations

import difflib
import re
from typing import Callable

# Matches a standard unified diff line: prefix (+/-/ ) followed by optional
# line number then content.
_UNIFIED_LINE = re.compile(r"^([+\- ])(\s*\d*)\s?(.*)$")


def _is_diff(text: str) -> bool:
    """Heuristic: return True if text looks like a unified diff."""
    lines = text.splitlines()
    has_marker = any(l.startswith(("---", "+++", "@@")) for l in lines[:20])
    has_change = any(l.startswith(("+", "-")) and len(l) > 1 for l in lines[:20])
    return has_marker and has_change


def _word_diff(old: str, new: str, inverse: Callable[[str], str]) -> tuple[str, str]:
    """Highlight changed words with inverse video."""
    old_words = re.split(r"(\s+)", old)
    new_words = re.split(r"(\s+)", new)
    sm = difflib.SequenceMatcher(None, old_words, new_words, autojunk=False)

    old_out, new_out = [], []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        old_chunk = "".join(old_words[i1:i2])
        new_chunk = "".join(new_words[j1:j2])
        if tag == "equal":
            old_out.append(old_chunk)
            new_out.append(new_chunk)
        elif tag == "replace":
            old_out.append(inverse(old_chunk) if old_chunk.strip() else old_chunk)
            new_out.append(inverse(new_chunk) if new_chunk.strip() else new_chunk)
        elif tag == "delete":
            old_out.append(inverse(old_chunk) if old_chunk.strip() else old_chunk)
        elif tag == "insert":
            new_out.append(inverse(new_chunk) if new_chunk.strip() else new_chunk)

    return "".join(old_out), "".join(new_out)


def render_diff(
    diff_text: str,
    added: Callable[[str], str],
    removed: Callable[[str], str],
    context: Callable[[str], str],
    hunk: Callable[[str], str],
    inverse: Callable[[str], str],
) -> list[str]:
    """
    Render a unified diff string with ANSI colors.

    - Header lines (---, +++) and hunk markers (@@): styled with ``hunk``
    - Added lines (+): styled with ``added``
    - Removed lines (-): styled with ``removed``
    - Context lines ( ): styled with ``context``
    - Adjacent single-line add/remove pairs get intra-line word highlighting
      via ``inverse``.
    """
    raw_lines = diff_text.splitlines()
    result: list[str] = []
    i = 0

    while i < len(raw_lines):
        line = raw_lines[i]

        # Header / hunk marker
        if line.startswith(("---", "+++", "@@", "diff ", "index ", "new file", "deleted file")):
            result.append(hunk(line))
            i += 1
            continue

        if line.startswith("-"):
            # Collect consecutive removed lines
            removed_lines: list[str] = []
            while i < len(raw_lines) and raw_lines[i].startswith("-"):
                removed_lines.append(raw_lines[i][1:])
                i += 1

            # Collect consecutive added lines that immediately follow
            added_lines: list[str] = []
            while i < len(raw_lines) and raw_lines[i].startswith("+"):
                added_lines.append(raw_lines[i][1:])
                i += 1

            # Intra-line diff only when it's a 1:1 change
            if len(removed_lines) == 1 and len(added_lines) == 1:
                old_hi, new_hi = _word_diff(removed_lines[0], added_lines[0], inverse)
                result.append(removed("-" + old_hi))
                result.append(added("+" + new_hi))
            else:
                for l in removed_lines:
                    result.append(removed("-" + l))
                for l in added_lines:
                    result.append(added("+" + l))
            continue

        if line.startswith("+"):
            result.append(added(line))
            i += 1
            continue

        if line.startswith(" "):
            result.append(context(line))
            i += 1
            continue

        # Unrecognised line — pass through dimmed
        result.append(context(line))
        i += 1

    return result
