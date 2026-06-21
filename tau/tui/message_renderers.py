from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tau.message.types import CustomMessage
    from tau.tui.theme import MessageTheme

RendererFn = Callable[["CustomMessage", "MessageTheme", int], list[str]]


class MessageRendererRegistry:
    def __init__(self) -> None:
        self._registry: dict[str, RendererFn] = {}

    def register(self, custom_type: str, fn: RendererFn) -> None:
        self._registry[custom_type] = fn

    def render(
        self,
        message: CustomMessage,
        theme: MessageTheme,
        width: int,
    ) -> list[str] | None:
        fn = self._registry.get(message.custom_type)
        if fn is None:
            return None
        return fn(message, theme, width)


message_renderer_registry = MessageRendererRegistry()
