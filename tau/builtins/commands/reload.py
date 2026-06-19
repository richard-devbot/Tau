from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tau.commands.registry import CommandRegistry


async def cmd_reload(reg: CommandRegistry, _args: list[str]) -> None:
    """Reload extensions, themes, and prompt appends."""
    if reg.runtime is None:
        return
    result = await reg.runtime.reload_extensions()

    from tau.extensions.context import ExtensionContext
    ctx = ExtensionContext.from_runtime(reg.runtime)
    if ctx.ui is None:
        return

    n = len(result.extensions)
    ext_word = "extension" if n == 1 else "extensions"
    if result.errors:
        e = len(result.errors)
        err_word = "error" if e == 1 else "errors"
        ctx.ui.notify(f"Reloaded {n} {ext_word} with {e} {err_word}.")
    else:
        ctx.ui.notify(f"Reloaded {n} {ext_word}.")
