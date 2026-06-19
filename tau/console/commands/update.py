from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import click


@click.command("update")
@click.argument("name", required=False, default=None)
@click.option("--local", is_flag=True, default=False,
              help="Update in project scope instead of global.")
def update(name: str | None, local: bool) -> None:
    """Update tau itself, or update an extension package by NAME."""
    if name is None:
        _update_tau()
        return

    from tau.packages.manager import PackageManager
    from tau.settings.manager import SettingsManager
    from tau.settings.paths import get_packages_venv

    cwd = Path.cwd()
    venv_dir = get_packages_venv(cwd) if local else get_packages_venv()
    pkg_manager = PackageManager(venv_dir)
    settings = SettingsManager.create(cwd)

    packages = settings.get_packages(local=local)
    targets = [p for p in packages if p.name == name]

    if not targets:
        raise click.ClickException(f"Package '{name}' not found.")

    for pkg in targets:
        click.echo(f"Updating {pkg.name}…")
        try:
            new_version = pkg_manager.update(pkg.name)
            settings.update_package_version(pkg.name, new_version, local=local)
            arrow = f" → {new_version}" if new_version else ""
            click.echo(click.style(f"✓ Updated {pkg.name}{arrow}", fg="green"))
        except Exception as e:
            click.echo(click.style(f"✗ {pkg.name}: {e}", fg="red"))

    asyncio.run(settings.flush())


def _update_tau() -> None:
    """Upgrade tau itself using whichever installer manages this install."""
    import os
    import shutil
    import subprocess
    from tau.settings.paths import get_app_name, get_package_name

    app = get_package_name()
    click.echo(f"Updating {get_app_name()}…")

    # Pick the upgrade tool that matches how this copy was installed, inferred
    # from the venv it runs in, so we upgrade the right managed environment.
    prefix = sys.prefix.replace(os.sep, "/")
    if "/pipx/" in prefix and shutil.which("pipx"):
        cmd = ["pipx", "upgrade", app]
    elif "/uv/tools/" in prefix and shutil.which("uv"):
        cmd = ["uv", "tool", "upgrade", app]
    elif shutil.which("uv"):
        cmd = ["uv", "tool", "upgrade", app]
    elif shutil.which("pipx"):
        cmd = ["pipx", "upgrade", app]
    else:
        cmd = [sys.executable, "-m", "pip", "install", "--upgrade", app]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        click.echo(click.style(f"✓ {get_app_name()} updated successfully", fg="green"))
    else:
        raise click.ClickException(result.stderr.strip() or "Update failed.")
