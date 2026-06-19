from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class SourceType(str, Enum):
    PYPI = "pypi"
    GIT = "git"
    LOCAL = "local"


@dataclass
class ParsedSource:
    source: SourceType
    raw: str
    name: str
    version: Optional[str] = None
    install_spec: Optional[str] = None  # argument passed to pip install
