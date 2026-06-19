from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tau.tui.input import InputEvent


class Component(ABC):
    """
    Base class for all TUI components.

    A component produces a list of pre-rendered lines for a given terminal
    width. The renderer calls render() on each frame and only writes lines
    that changed since the last frame.
    """

    @abstractmethod
    def render(self, width: int) -> list[str]:
        """
        Return the component's visual representation as a list of strings.

        Each string is one terminal line. Lines must not contain newline
        characters — the renderer handles line breaks. ANSI escape codes
        are allowed; the renderer uses ansi.visible_width() for comparisons.

        Args:
            width: Available terminal columns.

        Returns:
            List of strings, one per line.
        """
        ...

    def handle_input(self, event: InputEvent) -> bool:  # noqa: ARG002
        """
        Handle a keyboard / mouse / paste event.

        Returns True if the event was consumed (stops propagation).
        Default: not handled.
        """
        return False

    def invalidate(self) -> None:
        """
        Clear any cached render state.

        Called by the renderer after a terminal resize or when the component
        needs to be fully re-rendered on the next frame.
        """


class Focusable(ABC):
    """
    Mixin for components that want explicit keyboard focus.

    When TUI.set_focus(component) is called, TUI sets ``focused = True``
    on the component and routes handle_input() calls to it exclusively
    until focus changes.  Components that display a text cursor or need
    IME positioning should implement this interface.

    Example::

        class MyInput(Component, Focusable):
            def render(self, width):
                cursor = "█" if self.focused else ""
                return [f"> {self._text}{cursor}"]
    """

    focused: bool = False


class Container(Component):
    """
    An ordered list of child components rendered top-to-bottom.

    An ordered list of child components rendered top-to-bottom.
    Children are rendered in insertion order; each child gets the full
    available width.

    Usage::

        header = Container()
        header.add_child(Banner())
        header.add_child(Spacer(1))

        tui.add_child(header)
        tui.add_child(chat)
        tui.add_child(editor)
    """

    def __init__(self) -> None:
        self.children: list[Component] = []

    def add_child(self, component: Component) -> None:
        """Append a component to the bottom of this container."""
        self.children.append(component)

    def remove_child(self, component: Component) -> None:
        """Remove a component; no-op if not present."""
        try:
            self.children.remove(component)
        except ValueError:
            pass

    def clear(self) -> None:
        """Remove all children."""
        self.children.clear()

    # -------------------------------------------------------------------------
    # Component
    # -------------------------------------------------------------------------

    def render(self, width: int) -> list[str]:
        lines: list[str] = []
        for child in self.children:
            lines.extend(child.render(width))
        return lines

    def handle_input(self, event: InputEvent) -> bool:
        for child in self.children:
            if child.handle_input(event):
                return True
        return False

    def invalidate(self) -> None:
        for child in self.children:
            child.invalidate()


class StaticComponent(Component):
    """
    A component backed by a fixed list of pre-rendered lines.
    Useful for testing and simple static content.
    """

    def __init__(self, lines: list[str]) -> None:
        self._lines = lines

    def render(self, width: int) -> list[str]:  # noqa: ARG002
        return self._lines


class Column(Component):
    """
    Renders children top-to-bottom, each getting the full width.

    Fixed counterpart to ``Container`` — children are supplied at construction
    time.  Use ``Container`` when you need to add/remove children at runtime.

    Usage::

        col = Column([Banner(), Divider(), ChatArea()])
    """

    def __init__(self, children: list[Component]) -> None:
        self.children = list(children)

    def render(self, width: int) -> list[str]:
        lines: list[str] = []
        for child in self.children:
            lines.extend(child.render(width))
        return lines

    def handle_input(self, event: InputEvent) -> bool:
        for child in reversed(self.children):
            if child.handle_input(event):
                return True
        return False

    def invalidate(self) -> None:
        for child in self.children:
            child.invalidate()


# Backwards-compatible alias
VerticalStack = Column


class Row(Component):
    """
    Renders children side-by-side in a single terminal line.

    Each child is assigned a slot — ``"left"``, ``"center"``, or ``"right"``
    — and the Row distributes the available width so that:

    - left content is flush-left
    - right content is flush-right
    - center content sits in the middle (best-effort)

    Each child's ``render()`` is called with its measured slot width and only
    the **first line** of the result is used.  This keeps Row a single-line
    primitive; stack multiple Rows inside a Column/Container for multi-line
    horizontal layouts.

    Usage::

        row = Row([
            (GitBadge(),   "left"),
            (StatusBadge(),"center"),
            (ModelBadge(), "right"),
        ])
    """

    def __init__(self, slots: list[tuple[Component, str]] | None = None) -> None:
        self._slots: list[tuple[Component, str]] = list(slots) if slots else []

    def add_slot(self, component: Component, align: str = "left") -> None:
        """Append a component with the given alignment (``"left"``, ``"center"``, ``"right"``)."""
        self._slots.append((component, align))

    def render(self, width: int) -> list[str]:
        from tau.tui.ansi import visible_width, truncate

        left_parts:   list[str] = []
        center_parts: list[str] = []
        right_parts:  list[str] = []

        for component, align in self._slots:
            lines = component.render(width)
            text = lines[0] if lines else ""
            if align == "right":
                right_parts.append(text)
            elif align == "center":
                center_parts.append(text)
            else:
                left_parts.append(text)

        left   = "  ".join(left_parts)
        center = "  ".join(center_parts)
        right  = "  ".join(right_parts)

        lw = visible_width(left)
        cw = visible_width(center)
        rw = visible_width(right)

        if center:
            # left | center (centered) | right
            center_start = max(lw + 1, (width - cw) // 2)
            right_start  = width - rw
            if center_start + cw > right_start:
                center_start = max(lw + 1, right_start - cw - 1)
            line = left
            line += " " * max(0, center_start - lw)
            line += center
            cur = center_start + cw
            line += " " * max(0, right_start - cur)
            line += right
        else:
            # left | right
            gap = width - lw - rw
            if gap >= 0:
                line = left + " " * gap + right
            else:
                line = truncate(left, max(0, width - rw)) + right

        return [line]

    def handle_input(self, event: InputEvent) -> bool:
        for component, _ in self._slots:
            if component.handle_input(event):
                return True
        return False

    def invalidate(self) -> None:
        for component, _ in self._slots:
            component.invalidate()
