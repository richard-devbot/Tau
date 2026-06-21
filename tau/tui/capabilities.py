from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal

ImageProtocol = Literal["kitty", "iterm2"] | None


@dataclass
class TerminalCapabilities:
    images: ImageProtocol
    truecolor: bool
    hyperlinks: bool


@dataclass
class CellDimensions:
    width_px: int
    height_px: int


_cached: TerminalCapabilities | None = None
_cell_dims = CellDimensions(width_px=9, height_px=18)


def get_cell_dimensions() -> CellDimensions:
    return _cell_dims


def set_cell_dimensions(dims: CellDimensions) -> None:
    global _cell_dims
    _cell_dims = dims


def _probe_cell_dimensions() -> CellDimensions:
    """Read pixel and cell sizes from the terminal via TIOCGWINSZ."""
    try:
        import fcntl
        import struct
        import termios

        buf = struct.pack("HHHH", 0, 0, 0, 0)
        res = fcntl.ioctl(1, termios.TIOCGWINSZ, buf)
        rows, cols, width_px, height_px = struct.unpack("HHHH", res)
        if rows > 0 and cols > 0 and width_px > 0 and height_px > 0:
            return CellDimensions(width_px=width_px // cols, height_px=height_px // rows)
    except Exception:
        pass
    return CellDimensions(width_px=9, height_px=18)


def _tmux_forwards_hyperlinks() -> bool:
    try:
        import subprocess

        result = subprocess.run(
            ["tmux", "display-message", "-p", "#{client_termfeatures}"],
            capture_output=True,
            text=True,
            timeout=0.25,
        )
        return "hyperlinks" in result.stdout.split(",")
    except Exception:
        return False


def detect_capabilities() -> TerminalCapabilities:
    term = os.environ.get("TERM", "").lower()
    term_program = os.environ.get("TERM_PROGRAM", "").lower()
    terminal_emulator = os.environ.get("TERMINAL_EMULATOR", "").lower()
    color_term = os.environ.get("COLORTERM", "").lower()
    truecolor = color_term in ("truecolor", "24bit")

    if os.environ.get("TMUX") or term.startswith("tmux"):
        return TerminalCapabilities(
            images=None, truecolor=truecolor, hyperlinks=_tmux_forwards_hyperlinks()
        )

    if term.startswith("screen"):
        return TerminalCapabilities(images=None, truecolor=truecolor, hyperlinks=False)

    if os.environ.get("KITTY_WINDOW_ID") or term_program == "kitty":
        return TerminalCapabilities(images="kitty", truecolor=True, hyperlinks=True)

    if term_program == "ghostty" or "ghostty" in term or os.environ.get("GHOSTTY_RESOURCES_DIR"):
        return TerminalCapabilities(images="kitty", truecolor=True, hyperlinks=True)

    if os.environ.get("WEZTERM_PANE") or term_program == "wezterm":
        return TerminalCapabilities(images="kitty", truecolor=True, hyperlinks=True)

    if os.environ.get("ITERM_SESSION_ID") or term_program == "iterm.app":
        return TerminalCapabilities(images="iterm2", truecolor=True, hyperlinks=True)

    if os.environ.get("WT_SESSION"):
        return TerminalCapabilities(images=None, truecolor=True, hyperlinks=True)

    if term_program == "vscode":
        return TerminalCapabilities(images=None, truecolor=True, hyperlinks=True)

    if term_program == "alacritty":
        return TerminalCapabilities(images=None, truecolor=True, hyperlinks=False)

    if terminal_emulator == "jetbrains-jediterm":
        return TerminalCapabilities(images=None, truecolor=True, hyperlinks=False)

    return TerminalCapabilities(images=None, truecolor=truecolor, hyperlinks=False)


def get_capabilities() -> TerminalCapabilities:
    global _cached
    if _cached is None:
        _cached = detect_capabilities()
        set_cell_dimensions(_probe_cell_dimensions())
    return _cached


def reset_capabilities_cache() -> None:
    global _cached
    _cached = None


def is_image_line(line: str) -> bool:
    return "\x1b_G" in line or "\x1b]1337;" in line
