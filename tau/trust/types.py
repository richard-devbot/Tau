from __future__ import annotations

from dataclasses import dataclass


@dataclass
class TrustOption:
    """A single choice presented to the user in the trust prompt."""

    label: str
    trusted: bool
    # Absolute path to persist; None means session-only (no disk write)
    save_path: str | None = None
    # When saving a parent path, also remove this child path from the store
    clear_child_path: str | None = None
