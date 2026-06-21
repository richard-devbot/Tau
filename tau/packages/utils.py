from __future__ import annotations

import re
from pathlib import Path

from tau.packages.types import ParsedSource, SourceType
from tau.settings.paths import get_app_name


def parse_source(source: str) -> ParsedSource:
    """Parse a package source string into its components.

    Supported formats:
      pypi:package-name
      pypi:package-name@1.0.0
      git+https://github.com/user/repo
      git+https://github.com/user/repo@v1
      /absolute/path  or  ./relative/path  or  ~/path
      bare-name  (treated as pypi)
    """
    s = source.strip()

    if s.startswith("pypi:"):
        rest = s[5:]
        if "@" in rest:
            name, _, version = rest.partition("@")
        else:
            name, version = rest, None
        name = name.strip()
        spec = f"{name}=={version}" if version else name
        return ParsedSource(
            source=SourceType.PYPI, raw=source, name=name, version=version, install_spec=spec
        )

    if s.startswith("git+"):
        # git+https://github.com/user/repo@tag  →  name = "repo"
        base = re.sub(r"@[^/]+$", "", s) if "@" in s else s
        name = re.sub(r"\.git$", "", base).rstrip("/").split("/")[-1]
        return ParsedSource(source=SourceType.GIT, raw=source, name=name, install_spec=source)

    if s.startswith(("/", ".", "~")):
        path = Path(s).expanduser().resolve()
        return ParsedSource(
            source=SourceType.LOCAL, raw=source, name=path.name, install_spec=str(path)
        )

    # Bare name — treat as pypi
    m = re.match(r"^([a-zA-Z0-9_.-]+)(?:@(.+))?$", s)
    if m:
        name, version = m.group(1), m.group(2)
        spec = f"{name}=={version}" if version else name
        return ParsedSource(
            source=SourceType.PYPI, raw=source, name=name, version=version, install_spec=spec
        )

    raise ValueError(f"Cannot parse package source: {source!r}")


def extensions_from_pyproject(pyproject: Path, base: Path) -> list[Path]:
    """Read [tool.tau].extensions from a pyproject.toml and return resolved paths."""
    try:
        try:
            import tomllib  # Python 3.11+
        except ImportError:
            try:
                import tomli as tomllib  # type: ignore[no-redef]
            except ImportError:
                return []
        data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
        declared = data.get("tool", {}).get(get_app_name().lower(), {}).get("extensions", [])
        return [(base / p).resolve() for p in declared if (base / p).is_file()]
    except Exception:
        return []
