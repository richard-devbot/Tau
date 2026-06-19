from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Skill:
    name: str
    description: str
    content: str
    file_path: str
    base_dir: str
    disable_model_invocation: bool = False


@dataclass
class SkillLoadError:
    path: str
    error: str


@dataclass
class LoadSkillsResult:
    skills: dict[str, Skill] = field(default_factory=dict)
    errors: list[SkillLoadError] = field(default_factory=list)
