from __future__ import annotations

from typing import Literal

# ── Tool operation types ──────────────────────────────────────────────────────

# Curated high-value set: read/navigation intelligence plus the semantic
# edit operations agents actually use. Editor-UI features (selectionRange,
# semanticTokens, documentHighlight, signatureHelp, foldingRange, etc.) are
# intentionally omitted — they are mostly unsupported by common servers or
# offer little value to an agent.
Operation = Literal[
    # Navigation
    "goToDefinition",
    "goToImplementation",
    # References & calls
    "findReferences",
    "incomingCalls",
    "outgoingCalls",
    # Symbol info
    "hover",
    "documentSymbol",
    "workspaceSymbol",
    # Diagnostics
    "diagnostics",
    # Edits
    "rename",
    "codeAction",
    "formatting",
]

NEEDS_RANGE: frozenset[str] = frozenset({"codeAction"})
NEEDS_NAME: frozenset[str] = frozenset({"rename"})
