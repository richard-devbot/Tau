"""Built-in header extension — shows app name and version above the message list."""

from __future__ import annotations


def register(tau: object) -> None:
    from tau.settings.paths import get_app_name, get_app_version
    from tau.tui.ansi import BOLD, CYAN, DIM, RESET
    from tau.tui.component import StaticComponent

    def _build() -> StaticComponent:
        name = BOLD + CYAN + get_app_name() + RESET
        version = DIM + f"v{get_app_version()}" + RESET
        return StaticComponent([f"{name} {version}"])

    @tau.on("tui_ready")
    def on_ready(event, ctx):
        if ctx.has_ui:
            ctx.ui.set_header(_build())
