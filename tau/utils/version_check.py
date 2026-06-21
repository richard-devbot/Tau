from __future__ import annotations

import contextlib

_TIMEOUT = 5.0


def _pypi_url() -> str:
    """PyPI JSON endpoint for this app's distribution (keyed on the app name)."""
    from tau.settings.paths import get_package_name

    return f"https://pypi.org/pypi/{get_package_name()}/json"


def _is_newer(latest: str, current: str) -> bool:
    """True if ``latest`` is a strictly newer release than ``current``.

    Uses PEP 440 comparison (handles rc/dev/post suffixes correctly). Falls back
    to a naive dotted-int compare if packaging is unavailable or a version string
    is non-standard; on total failure, conservatively reports "not newer".
    """
    try:
        from packaging.version import InvalidVersion, Version

        try:
            return Version(latest) > Version(current)
        except InvalidVersion:
            pass
    except ImportError:
        pass

    def _parse(v: str) -> tuple[int, ...]:
        parts = []
        for x in v.strip().split("."):
            with contextlib.suppress(ValueError):
                parts.append(int(x))
        return tuple(parts)

    try:
        return _parse(latest) > _parse(current)
    except Exception:
        return False


async def check_for_new_version(current_version: str) -> str | None:
    """Return the latest PyPI version string if newer than current, else None."""
    try:
        import httpx

        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(_pypi_url(), headers={"Accept": "application/json"})
            if not resp.is_success:
                return None
            data = resp.json()
            latest = data.get("info", {}).get("version", "")
            if latest and _is_newer(latest, current_version):
                return latest
    except Exception:
        return None
    return None
