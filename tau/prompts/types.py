from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class PromptTemplate:
    name: str
    description: str
    content: str
    argument_hint: str | None = None
    file_path: str = ""


@dataclass
class PromptLoadError:
    path: str
    error: str


@dataclass
class LoadPromptsResult:
    templates: dict[str, PromptTemplate] = field(default_factory=dict)
    errors: list[PromptLoadError] = field(default_factory=list)
