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
    user_invocable: bool = True
    commands: list[str] = field(default_factory=list)
    aliases: list[str] = field(default_factory=list)
    argument_hint: str | None = None


@dataclass
class SkillLoadError:
    path: str
    error: str


@dataclass
class LoadSkillsResult:
    skills: dict[str, Skill] = field(default_factory=dict)
    errors: list[SkillLoadError] = field(default_factory=list)
