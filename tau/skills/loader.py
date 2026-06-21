from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from tau.skills.types import LoadSkillsResult, Skill, SkillLoadError


def _parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """Parse YAML frontmatter from skill markdown text."""
    text = text.lstrip("\n")
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    fm_text = text[3:end].strip()
    body = text[end + 4 :].lstrip("\n")
    raw = yaml.safe_load(fm_text) if fm_text else {}
    if not isinstance(raw, dict):
        return {}, body
    meta = {str(key).strip().lower(): value for key, value in raw.items()}
    return meta, body


def _as_bool(value: Any, *, default: bool = False) -> bool:
    """Return a frontmatter value as a boolean."""
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"true", "1", "yes", "on"}


def _as_string_list(value: Any) -> list[str]:
    """Return a frontmatter scalar or YAML list as a list of strings."""
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip().lower() for item in value if str(item).strip()]
    text = str(value).strip()
    if not text:
        return []
    if "," in text:
        return [item.strip().lower() for item in text.split(",") if item.strip()]
    return [item.strip().lower() for item in text.split() if item.strip()]


def load_skill_from_file(
    path: Path,
    name_hint: str | None = None,
) -> tuple[Skill | None, str | None]:
    """Load a skill from a markdown file."""
    try:
        text = path.read_text(encoding="utf-8")
    except Exception as exc:
        return None, f"read error: {exc}"

    meta, body = _parse_frontmatter(text)
    body = body.strip()
    if not body:
        return None, "skill body is empty"

    name = str(meta.get("name") or name_hint or path.stem.lower()).strip().lower()
    description = str(meta.get("description", "")).strip()
    if not description:
        return None, "missing 'description' field"

    disable = _as_bool(meta.get("disable-model-invocation"))
    user_invocable = _as_bool(meta.get("user-invocable"), default=True)
    commands = _as_string_list(meta.get("commands"))
    aliases = _as_string_list(meta.get("aliases"))
    argument_hint_value = meta.get("argument-hint") or meta.get("argument_hint")
    argument_hint = str(argument_hint_value).strip() if argument_hint_value else None

    return Skill(
        name=name,
        description=description,
        content=body,
        file_path=str(path),
        base_dir=str(path.parent),
        disable_model_invocation=disable,
        user_invocable=user_invocable,
        commands=commands,
        aliases=aliases,
        argument_hint=argument_hint,
    ), None


def load_skills_from_dir(directory: Path) -> LoadSkillsResult:
    """
    Scan a directory for skills.

    Rules:
      - If a subdir contains SKILL.md  → load it as one skill (name = dirname)
      - If a .md file sits at the root → load it as one skill (name = stem)
      - Recurse into subdirs that don't have SKILL.md to find nested skill dirs
    """
    result = LoadSkillsResult()
    if not directory.is_dir():
        return result

    def _scan(d: Path) -> None:
        skill_md = d / "SKILL.md"
        if skill_md.is_file():
            skill, err = load_skill_from_file(skill_md, name_hint=d.name.lower())
            if err or skill is None:
                result.errors.append(SkillLoadError(str(skill_md), err or "unknown"))
            else:
                result.skills[skill.name] = skill
            return

        if d == directory:
            for path in sorted(d.glob("*.md")):
                skill, err = load_skill_from_file(path)
                if err or skill is None:
                    result.errors.append(SkillLoadError(str(path), err or "unknown"))
                else:
                    result.skills[skill.name] = skill

        for sub in sorted(d.iterdir()):
            if sub.is_dir():
                _scan(sub)

    _scan(directory)
    return result
