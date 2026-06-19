from __future__ import annotations

from dataclasses import dataclass
from typing import Awaitable, Callable


@dataclass
class AutocompleteItem:
    """A single completion suggestion returned by a provider."""
    label: str
    description: str = ""
    # Text inserted into the editor. When None the label itself is inserted.
    insert_text: str | None = None


@dataclass
class AutocompleteContext:
    """Snapshot passed to a provider's get_items() call."""
    text: str        # full editor text at the moment of the call
    cursor_pos: int  # character index of the cursor in text
    trigger: str     # the trigger character that activated this provider (e.g. "#")
    query: str       # text typed after the trigger up to the cursor (no spaces)


@dataclass
class AutocompleteRegistration:
    """A provider registered by an extension via tau.add_autocomplete_provider()."""
    trigger: str
    get_items: Callable[
        [AutocompleteContext],
        list[AutocompleteItem] | Awaitable[list[AutocompleteItem]],
    ]
    description: str = ""
