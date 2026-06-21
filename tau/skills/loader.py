from __future__ import annotations

from pathlib import Path

from tau.skills.types import LoadSkillsResult, Skill, SkillLoadError


def _parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    """Parse YAML frontmatter from skill markdown text."""
    text = text.lstrip("\n")
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    fm_text = text[3:end].strip()
    body = text[end + 4 :].lstrip("\n")
    meta: dict[str, str] = {}
    for line in fm_text.splitlines():
        if ":" in line:
            key, _, val = line.partition(":")
            meta[key.strip().lower()] = val.strip()
    return meta, body


def load_skill_from_file(
    path: Path, name_hint: str | None = None
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

    name = meta.get("name") or name_hint or path.stem.lower()
    description = meta.get("description", "")
    if not description:
        return None, "missing 'description' field"

    disable = meta.get("disable-model-invocation", "").lower() in ("true", "1", "yes")

    return Skill(
        name=name.lower(),
        description=description,
        content=body,
        file_path=str(path),
        base_dir=str(path.parent),
        disable_model_invocation=disable,
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
