from __future__ import annotations

import asyncio

from tau.tui.commands.context import CommandContext


def open_model_selector(ctx: CommandContext) -> None:
    """Open the model selector modal."""
    import asyncio

    try:
        from tau.inference.api.text.service import TextLLM
        models = TextLLM.list_available()
    except Exception as exc:
        ctx.notify(f"Failed to load models: {exc}")
        return

    if not models:
        ctx.notify("No models available. Use /login to add providers.")
        return

    llm = getattr(getattr(ctx.runtime.agent, "_engine", None), "llm", None) if ctx.runtime.agent else None
    model = getattr(llm, "model", None) if llm is not None else None
    current_key = f"{model.provider}/{model.id}" if model is not None else ""

    def commit(value: tuple[str, str]) -> None:
        model_id, provider = value
        asyncio.ensure_future(_apply_model(ctx, model_id, provider))

    ctx.layout.open_model_selector(models, current_key, commit, lambda: ctx.notify("Model selection cancelled."))


async def _apply_model(ctx: CommandContext, model_id: str, provider: str) -> None:
    try:
        await ctx.runtime.set_model(model_id, provider)
        ctx.notify(f"Model set to {provider}/{model_id}")
        if ctx.on_palette_refresh is not None:
            ctx.on_palette_refresh()
    except Exception as exc:
        ctx.notify(f"Failed to set model: {exc}")


def open_effort_selector(ctx: CommandContext) -> None:
    from tau.inference.types import ThinkingLevel

    agent = ctx.runtime.agent
    model = None
    if agent is not None:
        model = getattr(agent._engine.llm, "model", None)

    if model is None or not getattr(model, "thinking", False):
        ctx.notify("Model doesn't support thinking")
        return

    current_level = None
    if agent is not None:
        current_level = agent._engine.llm.api.options.thinking_level
    current = current_level.value if current_level else ThinkingLevel.Off.value

    levels = [lv.value for lv in ThinkingLevel]

    def commit(level_val: str) -> None:
        asyncio.ensure_future(_apply_effort(ctx, level_val))

    ctx.layout.open_effort_selector(levels, current, commit, lambda: ctx.notify("Effort selection cancelled."))


def get_palette_overrides(agent: object) -> dict[str, str]:
    """Return dynamic palette description overrides for /model and /effort."""
    overrides: dict[str, str] = {}

    llm = getattr(getattr(agent, "_engine", None), "llm", None) if agent is not None else None
    model = getattr(llm, "model", None) if llm is not None else None

    if model is not None:
        provider = getattr(model, "provider", "") or ""
        model_id = getattr(model, "id", "") or ""
        overrides["model"] = f"{provider}/{model_id}" if provider else model_id
    else:
        overrides["model"] = "Switch the active model"

    effort_val = None
    if llm is not None:
        opts = getattr(getattr(llm, "api", None), "options", None)
        if opts is not None:
            level = getattr(opts, "thinking_level", None)
            if level is not None:
                effort_val = getattr(level, "value", str(level))
    overrides["effort"] = effort_val if effort_val is not None else "Set thinking effort level"

    return overrides


async def _apply_effort(ctx: CommandContext, level_val: str) -> None:
    from tau.hooks.tui import ThinkingLevelSelectEvent
    from tau.inference.types import ThinkingLevel

    agent = ctx.runtime.agent
    if agent is None:
        return
    previous_level = agent._engine.llm.api.options.thinking_level
    level = ThinkingLevel(level_val)
    agent._engine.llm.api.options.thinking_level = None if level == ThinkingLevel.Off else level

    sm = ctx.runtime.session_manager
    if sm is not None:
        sm.append_thinking_level_change(level)

    settings = ctx.runtime.settings_manager
    if settings is not None:
        settings.set_thinking_level(level)

    await ctx.runtime.hooks.emit(ThinkingLevelSelectEvent(level=level, previous_level=previous_level))

    ctx.notify(f"Effort set to {level_val}")
    if ctx.on_palette_refresh is not None:
        ctx.on_palette_refresh()
