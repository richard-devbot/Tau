"""Built-in footer status extension — git branch left, model/context right."""
from __future__ import annotations

from .git import GitBadge
from .model import ModelBadge


def register(tau: object) -> None:
    from tau.tui.component import Row

    git_badge   = GitBadge()
    model_badge = ModelBadge()
    row         = Row([(git_badge, "left"), (model_badge, "right")])  # type: ignore[arg-type]

    def _request_render(ctx: object) -> None:
        layout = getattr(ctx, "_layout", None)
        if layout is not None:
            layout._tui.request_render()

    @tau.on("tui_ready")
    def on_ready(event, ctx):
        ctx._layout.footer.add_child(row)
        git_badge.update(str(ctx.cwd))
        model_badge.update_from_ctx(ctx)
        _request_render(ctx)

    @tau.on("session_start")
    def on_session_start(event, ctx):
        if ctx.has_ui:
            git_badge.update(str(ctx.cwd))
            model_badge.update_from_ctx(ctx)
            _request_render(ctx)

    @tau.on("model_select")
    def on_model_select(event, ctx):
        if not ctx.has_ui:
            return
        model = getattr(event, "model", None)
        if model is not None:
            model_badge.set_model(
                getattr(model, "id", "") or "",
                getattr(model, "provider", "") or "",
                bool(getattr(model, "thinking", False)),
            )
        # The new model usually has a different context window, so the usage %
        # changes even though the token count didn't — refresh it immediately
        # instead of waiting for the next turn.
        model_badge.update_context_from_ctx(ctx)
        _request_render(ctx)

    @tau.on("thinking_level_select")
    def on_thinking_level_select(event, ctx):
        if not ctx.has_ui:
            return
        model_badge.set_thinking_level(getattr(event, "level", None))
        _request_render(ctx)

    @tau.on("settled")
    def on_settled(event, ctx):
        if ctx.has_ui:
            git_badge.update(str(ctx.cwd))
            model_badge.update_context_from_ctx(ctx)
            _request_render(ctx)

    @tau.on("message_end")
    def on_message_end(event, ctx):
        if ctx.has_ui:
            git_badge.update(str(ctx.cwd))
            model_badge.update_context_from_ctx(ctx)
            _request_render(ctx)

    @tau.on("compaction_end")
    def on_compaction_end(event, ctx):
        if ctx.has_ui:
            model_badge.update_context_from_ctx(ctx)
            _request_render(ctx)
