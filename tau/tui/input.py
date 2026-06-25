from __future__ import annotations

import asyncio
import contextlib
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

_log = logging.getLogger(__name__)

if TYPE_CHECKING:
    from tau.message.types import UserMessage
    from tau.runtime.service import Runtime
    from tau.modes.interactive.components.layout import Layout
    from tau.tui.tui import TUI


# ── Key event ─────────────────────────────────────────────────────────────────

# Modifier name aliases → canonical name. Matching is order- and alias-independent,
# so "ctrl+shift+p", "shift+ctrl+p", and "control+shift+p" are all equivalent.
_MOD_ALIASES = {
    "ctrl": "ctrl",
    "control": "ctrl",
    "alt": "alt",
    "opt": "alt",
    "option": "alt",
    "shift": "shift",
    "super": "meta",
    "cmd": "meta",
    "command": "meta",
    "win": "meta",
    "meta": "meta",
}

# Base-key name aliases → canonical name.
_KEY_ALIASES = {
    "esc": "escape",
    "return": "enter",
    "del": "delete",
    "spacebar": "space",
    " ": "space",
    "pgup": "pageup",
    "pgdn": "pagedown",
    "pagedown": "pagedown",
    "pageup": "pageup",
    "page_up": "pageup",
    "page_down": "pagedown",  # parser emits the underscore form
}


def _normalize_keyid(key_id: str) -> tuple[frozenset[str], str]:
    """Parse a key identifier like 'ctrl+shift+p' into (modifiers, base_key).

    Order- and alias-independent. Handles '+' as a base key (e.g. 'ctrl++')."""
    mods: set[str] = set()
    base_parts: list[str] = []
    for tok in key_id.split("+"):
        t = tok.strip().lower()
        if t in _MOD_ALIASES:
            mods.add(_MOD_ALIASES[t])
        else:
            base_parts.append(tok)
    base = "+".join(base_parts).lower()
    base = _KEY_ALIASES.get(base, base)
    return frozenset(mods), base


@dataclass
class KeyEvent:
    """A single parsed keyboard event."""

    key: str  # canonical name: "a", "enter", "up", "f1", etc.
    char: str | None = None  # printable character if the key produces one
    ctrl: bool = False
    alt: bool = False
    shift: bool = False
    meta: bool = False  # super / cmd / win (Kitty keyboard protocol)
    released: bool = False  # True on key-up (Kitty keyboard protocol only)
    repeat: bool = False  # True on auto-repeat (Kitty keyboard protocol only)
    raw: str = ""  # original bytes received from stdin

    def __str__(self) -> str:
        parts = []
        if self.ctrl:
            parts.append("ctrl")
        if self.alt:
            parts.append("alt")
        if self.shift:
            parts.append("shift")
        if self.meta:
            parts.append("meta")
        parts.append(self.key)
        return "+".join(parts)

    def _signature(self) -> tuple[frozenset[str], str]:
        mods = {
            name
            for name, on in (
                ("ctrl", self.ctrl),
                ("alt", self.alt),
                ("shift", self.shift),
                ("meta", self.meta),
            )
            if on
        }
        base = _KEY_ALIASES.get(self.key.lower(), self.key.lower())
        return frozenset(mods), base

    def matches(self, *keys: str) -> bool:
        """True if this event matches any of the given key combos.

        Matching is exact on modifiers (so 'escape' does NOT match 'alt+escape')
        but modifier-order- and alias-independent: 'ctrl+shift+p', 'shift+ctrl+p'
        and 'control+shift+p' all match the same event.
        """
        sig = self._signature()
        return any(_normalize_keyid(k) == sig for k in keys)


def matches_key(event: KeyEvent, *keys: str) -> bool:
    """Module-level convenience mirroring :meth:`KeyEvent.matches`."""
    return isinstance(event, KeyEvent) and event.matches(*keys)


class Key:
    """Ergonomic, typo-resistant key identifiers for use with ``matches`` / ``matches_key``.

    Use the constants for special/symbol keys and the modifier builders for
    combinations::

        event.matches(Key.ESCAPE)
        event.matches(Key.ctrl("c"))
        event.matches(Key.ctrl_shift("p"))   # order-independent with shift_ctrl

    Identifiers are plain strings, so they interoperate with literal combos.
    """

    # Special keys
    ESCAPE = "escape"
    ENTER = "enter"
    TAB = "tab"
    SPACE = "space"
    BACKSPACE = "backspace"
    DELETE = "delete"
    INSERT = "insert"
    HOME = "home"
    END = "end"
    PAGE_UP = "pageup"
    PAGE_DOWN = "pagedown"
    UP = "up"
    DOWN = "down"
    LEFT = "left"
    RIGHT = "right"
    F1 = "f1"
    F2 = "f2"
    F3 = "f3"
    F4 = "f4"
    F5 = "f5"
    F6 = "f6"
    F7 = "f7"
    F8 = "f8"
    F9 = "f9"
    F10 = "f10"
    F11 = "f11"
    F12 = "f12"

    @staticmethod
    def ctrl(key: str) -> str:
        return f"ctrl+{key}"

    @staticmethod
    def alt(key: str) -> str:
        return f"alt+{key}"

    @staticmethod
    def shift(key: str) -> str:
        return f"shift+{key}"

    @staticmethod
    def meta(key: str) -> str:
        return f"meta+{key}"

    @staticmethod
    def ctrl_shift(key: str) -> str:
        return f"ctrl+shift+{key}"

    @staticmethod
    def ctrl_alt(key: str) -> str:
        return f"ctrl+alt+{key}"

    @staticmethod
    def alt_shift(key: str) -> str:
        return f"alt+shift+{key}"

    @staticmethod
    def ctrl_shift_alt(key: str) -> str:
        return f"ctrl+shift+alt+{key}"


@dataclass
class PasteEvent:
    """Bracketed paste — text pasted into the terminal."""

    text: str
    raw: str = ""


@dataclass
class MouseEvent:
    """Mouse button press or release."""

    x: int
    y: int
    button: int
    pressed: bool
    raw: str = ""


@dataclass
class BgColorEvent:
    """Terminal background color response (OSC 11).

    Emitted when the terminal replies to an ``\\x1b]11;?\\x1b\\\\`` query.
    Each channel is normalised to 0–255.
    """

    r: int
    g: int
    b: int

    @property
    def is_dark(self) -> bool:
        """True when luminance < 0.5 (dark background)."""
        return (0.2126 * self.r + 0.7152 * self.g + 0.0722 * self.b) < 128


@dataclass
class FocusEvent:
    """Terminal window focus change (DECSET 1004).

    Emitted when the terminal reports ``\\x1b[I`` (focus gained) or
    ``\\x1b[O`` (focus lost).
    """

    focused: bool
    raw: str = ""


InputEvent = KeyEvent | PasteEvent | MouseEvent | BgColorEvent | FocusEvent


# ── CSI / SS3 lookup tables ───────────────────────────────────────────────────

# CSI final-byte → key name (no parameters)
_CSI_SIMPLE: dict[str, str] = {
    "A": "up",
    "B": "down",
    "C": "right",
    "D": "left",
    "H": "home",
    "F": "end",
    "Z": "tab",  # shift+tab (also sets shift below)
    "P": "f1",
    "Q": "f2",
    "R": "f3",
    "S": "f4",
}

# CSI tilde number → key name
_CSI_TILDE: dict[int, str] = {
    1: "home",
    2: "insert",
    3: "delete",
    4: "end",
    5: "page_up",
    6: "page_down",
    7: "home",
    8: "end",
    11: "f1",
    12: "f2",
    13: "f3",
    14: "f4",
    15: "f5",
    17: "f6",
    18: "f7",
    19: "f8",
    20: "f9",
    21: "f10",
    23: "f11",
    24: "f12",
}

# SS3 (ESC O) final-byte → key name
_SS3: dict[str, str] = {
    "P": "f1",
    "Q": "f2",
    "R": "f3",
    "S": "f4",
    "H": "home",
    "F": "end",
    "A": "up",
    "B": "down",
    "C": "right",
    "D": "left",
    "M": "enter",
}

# Kitty keypad / functional keys (Unicode private-use codes) → standard equivalents.
# int → an ASCII codepoint that continues normal char dispatch; str → a key name.
_KITTY_KP_EQUIV: dict[int, int | str] = {
    57399: 48,
    57400: 49,
    57401: 50,
    57402: 51,
    57403: 52,  # KP 0-4
    57404: 53,
    57405: 54,
    57406: 55,
    57407: 56,
    57408: 57,  # KP 5-9
    57409: 46,
    57410: 47,
    57411: 42,
    57412: 45,
    57413: 43,  # . / * - +
    57414: 13,
    57415: 61,
    57416: 44,  # KP Enter, =, ,
    57417: "left",
    57418: "right",
    57419: "up",
    57420: "down",
    57421: "page_up",
    57422: "page_down",
    57423: "home",
    57424: "end",
    57425: "insert",
    57426: "delete",
}


# Kitty / CSI modifier byte → (shift, alt, ctrl, meta)
# The modifier is encoded as: (value - 1) with bit flags
# bit 0 = shift, bit 1 = alt, bit 2 = ctrl, bit 3 = super (→ meta)
def _decode_modifier(mod: int) -> tuple[bool, bool, bool, bool]:
    m = mod - 1
    return bool(m & 1), bool(m & 2), bool(m & 4), bool(m & 8)


def _decode_mod_field(field: str) -> tuple[bool, bool, bool, bool, bool, bool]:
    """Decode a CSI modifier field, which may carry a Kitty ``:event_type``.

    Terminals that enable the Kitty "report event types" flag (Tau requests it
    via ``\\x1b[>3u``) append the event type to the modifier with a colon, e.g.
    ``1:1`` (press), ``1:2`` (repeat), ``1:3`` (release). Plain terminals send
    just the modifier (``1``). Ghostty uses the colon form even for unmodified
    arrows, so this must be parsed or the keypress is lost.

    Returns ``(shift, alt, ctrl, meta, released, repeat)``. Raises ``ValueError``
    when the modifier component is not an integer.
    """
    sub = field.split(":")
    shift, alt, ctrl, meta = _decode_modifier(int(sub[0]))
    event = 1
    if len(sub) >= 2 and sub[1]:
        with contextlib.suppress(ValueError):
            event = int(sub[1])
    return shift, alt, ctrl, meta, event == 3, event == 2


# Control characters → key names
_CTRL_CHARS: dict[str, tuple[str, bool]] = {
    "\x00": ("space", True),  # ctrl+space / ctrl+@
    "\x01": ("a", True),
    "\x02": ("b", True),
    "\x03": ("c", True),
    "\x04": ("d", True),
    "\x05": ("e", True),
    "\x06": ("f", True),
    "\x07": ("g", True),
    "\x08": ("backspace", False),  # ctrl+h / backspace on some terminals
    "\x09": ("tab", False),
    "\x0a": ("enter", False),
    "\x0b": ("k", True),
    "\x0c": ("l", True),
    "\x0d": ("enter", False),
    "\x0e": ("n", True),
    "\x0f": ("o", True),
    "\x10": ("p", True),
    "\x11": ("q", True),
    "\x12": ("r", True),
    "\x13": ("s", True),
    "\x14": ("t", True),
    "\x15": ("u", True),
    "\x16": ("v", True),
    "\x17": ("w", True),
    "\x18": ("x", True),
    "\x19": ("y", True),
    "\x1a": ("z", True),
    "\x1c": ("\\", True),
    "\x1d": ("]", True),
    "\x1e": ("6", True),
    "\x1f": ("-", True),
    "\x7f": ("backspace", False),
}


# ── Sequence completeness ─────────────────────────────────────────────────────


def _split_text_unit(buf: str) -> tuple[str, str]:
    """Peel one logical character unit off the front of a plain-text buffer.

    ASCII code points are returned one at a time so a burst of auto-repeated
    keys (a held Space, fast typing, or an unbracketed paste) splits into one
    event per character. A run of non-ASCII code points is kept together so
    multi-codepoint graphemes (ZWJ emoji sequences, combining marks) survive as
    a single event.

    Returns ``(unit, rest)``.
    """
    if ord(buf[0]) < 0x80:
        return buf[0], buf[1:]
    i = 1
    while i < len(buf) and ord(buf[i]) >= 0x80:
        i += 1
    return buf[:i], buf[i:]


def _is_complete(buf: str) -> bool | None:
    """
    Return True if buf is a complete escape sequence,
    False if it will never be one, None if it's incomplete (needs more data).
    """
    if not buf.startswith("\x1b"):
        return True  # not an escape — single char, always complete

    if len(buf) == 1:
        return None  # bare ESC, could be start of sequence

    second = buf[1]

    # SS3: ESC O <char>
    if second == "O":
        if len(buf) < 3:
            return None
        return True

    # CSI: ESC [ <params> <final>
    if second == "[":
        if len(buf) < 3:
            return None
        # Bracketed paste: ESC [ 2 0 0 ~ ... ESC [ 2 0 1 ~
        # Must be checked first because ~ is a valid CSI final byte and the
        # generic scan below would fire on \x1b[200~ before the content arrives.
        if buf.startswith("\x1b[200~"):
            return True if "\x1b[201~" in buf else None
        # Basic mouse: ESC [ M <button> <col> <row> — exactly 6 bytes.
        # Must be checked before the generic final-byte scan because 'M' is a
        # valid CSI final byte and would otherwise terminate prematurely,
        # leaving the 3 parameter bytes to be parsed as text.
        if buf[2] == "M":
            return len(buf) >= 6
        # Final byte is 0x40–0x7E (@–~)
        for i in range(2, len(buf)):
            c = buf[i]
            code = ord(c)
            if 0x40 <= code <= 0x7E:
                return True
        return None  # still accumulating params

    # APC: ESC _ ... ST  (zero-width cursor markers etc.)
    if second == "_":
        if buf.endswith("\x1b\\") or buf.endswith("\x07"):
            return True
        return None

    # OSC: ESC ] ... BEL or ST
    if second == "]":
        if buf.endswith("\x07") or buf.endswith("\x1b\\"):
            return True
        return None

    # DCS / PM / SOS / APC variants: ESC P/X/^ ... ST
    if second in ("P", "X", "^"):
        if buf.endswith("\x1b\\"):
            return True
        return None

    # Other 2-char sequences (ESC <char>): complete
    return True


# ── Parser ────────────────────────────────────────────────────────────────────


class InputParser:
    """
    Stateful parser that converts raw stdin bytes into InputEvent objects.

    Usage:
        parser = InputParser()
        for event in parser.feed(raw_bytes):
            handle(event)
    """

    def __init__(self) -> None:
        self._buf = ""

    def feed(self, data: str) -> list[InputEvent]:
        self._buf += data
        events: list[InputEvent] = []
        while self._buf:
            # Plain text (not an escape sequence): peel off one character unit at
            # a time. A single read can batch several repeated bytes together —
            # e.g. holding Space floods the OS auto-repeat into one "   " chunk.
            # Splitting per character means each keypress becomes its own event,
            # so key matching (matches("space"), etc.) works and held keys don't
            # collapse into a single bogus multi-char event.
            if not self._buf.startswith("\x1b"):
                unit, self._buf = _split_text_unit(self._buf)
                event = self._parse_one(unit)
                if event is not None:
                    events.append(event)
                continue
            complete = _is_complete(self._buf)
            if complete is None:
                break  # need more data
            event = self._parse_one(self._buf)
            if event is not None:
                events.append(event)
            self._buf = ""
        return events

    def flush(self) -> list[InputEvent]:
        """
        Force-parse whatever remains in the buffer.
        Called after a short read timeout to emit a bare ESC rather than
        waiting indefinitely for a sequence that never arrives.
        """
        if not self._buf:
            return []
        event = self._parse_one(self._buf)
        self._buf = ""
        return [event] if event is not None else []

    def _parse_one(self, raw: str) -> InputEvent | None:
        # ── Bracketed paste ───────────────────────────────────────────────────
        if raw.startswith("\x1b[200~"):
            # strip opening and closing markers
            text = raw[6:]
            if text.endswith("\x1b[201~"):
                text = text[:-6]
            return PasteEvent(text=text, raw=raw)

        # ── Control characters ────────────────────────────────────────────────
        if len(raw) == 1 and raw in _CTRL_CHARS:
            name, is_ctrl = _CTRL_CHARS[raw]
            return KeyEvent(key=name, char=None, ctrl=is_ctrl, raw=raw)

        # ── Printable ASCII / Unicode ─────────────────────────────────────────
        if len(raw) == 1 and raw >= " " and raw != "\x7f":
            return KeyEvent(key=raw.lower(), char=raw, shift=raw.isupper(), raw=raw)

        if not raw.startswith("\x1b"):
            # Multi-byte UTF-8 character (emoji, CJK, etc.)
            return KeyEvent(key=raw, char=raw, raw=raw)

        # ── Bare ESC ──────────────────────────────────────────────────────────
        if raw == "\x1b":
            return KeyEvent(key="escape", char=None, raw=raw)

        second = raw[1] if len(raw) > 1 else ""

        # ── Alt + char: ESC <char> ────────────────────────────────────────────
        if len(raw) == 2 and second not in ("[", "O", "_", "]", "P", "X", "^"):
            inner = self._parse_one(second)
            if inner is not None and isinstance(inner, KeyEvent):
                inner.alt = True
                inner.raw = raw
                return inner
            return KeyEvent(key=second, char=second, alt=True, raw=raw)

        # ── SS3: ESC O <char> ─────────────────────────────────────────────────
        if second == "O" and len(raw) == 3:
            final = raw[2]
            name = _SS3.get(final)
            if name:
                return KeyEvent(key=name, char=None, raw=raw)

        # ── CSI: ESC [ ... ───────────────────────────────────────────────────
        if second == "[":
            return self._parse_csi(raw)

        # ── OSC 11 — terminal background-colour response ─────────────────────
        # Reply format: ESC ] 11 ; rgb:RRRR/GGGG/BBBB BEL-or-ST
        if second == "]":
            body = raw[2:]
            if body.endswith("\x07"):
                body = body[:-1]
            elif body.endswith("\x1b\\"):
                body = body[:-2]
            if body.startswith("11;rgb:"):
                try:
                    parts = body[7:].split("/")
                    r = int(parts[0], 16) >> 8  # 16-bit → 8-bit
                    g = int(parts[1], 16) >> 8
                    b = int(parts[2], 16) >> 8
                    return BgColorEvent(r=r, g=g, b=b)
                except (ValueError, IndexError):
                    pass

        # ── APC / other non-key sequences (ignore) ───────────────────────────
        return None

    def _parse_csi(self, raw: str) -> InputEvent | None:
        # raw = ESC [ <params> <final>
        payload = raw[2:]  # strip ESC [
        if not payload:
            return None

        final = payload[-1]
        params_str = payload[:-1]

        # ── Mouse: SGR — ESC [ < button ; col ; row M/m ─────────────────────
        if params_str.startswith("<"):
            return self._parse_mouse(raw, params_str[1:], final)

        # ── Mouse: basic — ESC [ M <button+32> <col+32> <row+32> ─────────────
        # Terminals that don't support SGR (mode 1006) fall back to this 6-byte
        # form. We must parse it here; if left unhandled, the 3 raw bytes leak
        # into the event queue as printable characters and corrupt the editor.
        if final == "M" and not params_str and len(raw) == 6:
            b = ord(raw[3]) - 32
            x = max(1, ord(raw[4]) - 32)
            y = max(1, ord(raw[5]) - 32)
            button = b & 0x03
            if b & 0x40:
                button += 64  # scroll wheel
            return MouseEvent(x=x, y=y, button=button, pressed=True, raw=raw)

        # ── Kitty protocol: ESC [ <cp> ; <mods> u ────────────────────────────
        if final == "u":
            return self._parse_kitty(raw, params_str)

        # ── Shift+Tab: ESC [ Z ────────────────────────────────────────────────
        if final == "Z" and not params_str:
            return KeyEvent(key="tab", char=None, shift=True, raw=raw)

        # ── Focus in/out: ESC [ I / ESC [ O (DECSET 1004) ────────────────────
        if final in ("I", "O") and not params_str:
            return FocusEvent(focused=final == "I", raw=raw)

        # ── Simple CSI: ESC [ <letter> (no params) ───────────────────────────
        if not params_str:
            name = _CSI_SIMPLE.get(final)
            if name:
                return KeyEvent(key=name, char=None, raw=raw)
            return None

        # ── CSI with params ───────────────────────────────────────────────────
        parts = params_str.split(";")

        # ESC [ 1 ; <mod>[:<event>] <letter>  — modified arrow/navigation.
        # The modifier field may carry a Kitty event-type sub-parameter; Ghostty
        # sends it even for unmodified arrows (e.g. ESC [ 1 ; 1 : 1 A).
        if len(parts) == 2 and parts[0] == "1":
            try:
                shift, alt, ctrl, meta, released, repeat = _decode_mod_field(parts[1])
            except ValueError:
                return None
            name = _CSI_SIMPLE.get(final)
            if name:
                return KeyEvent(
                    key=name,
                    char=None,
                    shift=shift,
                    alt=alt,
                    ctrl=ctrl,
                    meta=meta,
                    released=released,
                    repeat=repeat,
                    raw=raw,
                )

        # ESC [ <n> ~ — tilde sequences
        if final == "~" and len(parts) == 1:
            try:
                n = int(parts[0])
            except ValueError:
                return None
            name = _CSI_TILDE.get(n)
            if name:
                return KeyEvent(key=name, char=None, raw=raw)

        # ESC [ <n> ; <mod>[:<event>] ~ — modified tilde sequences (event-type aware)
        if final == "~" and len(parts) == 2:
            try:
                n = int(parts[0])
                shift, alt, ctrl, meta, released, repeat = _decode_mod_field(parts[1])
            except ValueError:
                return None
            name = _CSI_TILDE.get(n)
            if name:
                return KeyEvent(
                    key=name,
                    char=None,
                    shift=shift,
                    alt=alt,
                    ctrl=ctrl,
                    meta=meta,
                    released=released,
                    repeat=repeat,
                    raw=raw,
                )

        return None

    def _parse_kitty(self, raw: str, params_str: str) -> KeyEvent | None:
        # ESC [ <codepoint> u
        # ESC [ <codepoint> ; <mods> u
        # ESC [ <codepoint> ; <mods> ; <event_type> u  (Kitty keyboard protocol)
        #   event_type: 1=press  2=repeat  3=release
        # Kitty field layout: `key[:shifted:base] ; modifiers[:event] ; text`.
        parts = params_str.split(";")
        try:
            # The key field may carry alternate keys after colons; use the first.
            codepoint = int(parts[0].split(":")[0])
        except (ValueError, IndexError):
            return None

        shift = alt = ctrl = meta = False
        released = repeat = False
        if len(parts) >= 2 and parts[1]:
            # The event type is appended to the modifier field after a colon.
            mod_field = parts[1].split(":")
            with contextlib.suppress(ValueError, IndexError):
                shift, alt, ctrl, meta = _decode_modifier(int(mod_field[0]))
            event_str = (
                mod_field[1] if len(mod_field) >= 2 else (parts[2] if len(parts) >= 3 else "")
            )
            if event_str:
                try:
                    et = int(event_str)  # 1 = press, 2 = repeat, 3 = release
                    released = et == 3
                    repeat = et == 2
                except ValueError:
                    pass

        # Normalize keypad / functional keys to their standard equivalents.
        kp = _KITTY_KP_EQUIV.get(codepoint)
        if isinstance(kp, str):
            return KeyEvent(
                key=kp,
                char=None,
                shift=shift,
                alt=alt,
                ctrl=ctrl,
                meta=meta,
                released=released,
                repeat=repeat,
                raw=raw,
            )
        if isinstance(kp, int):
            codepoint = kp

        # Map codepoint to key name
        try:
            ch = chr(codepoint)
        except (ValueError, OverflowError):
            return None

        # Special codepoints
        _kitty_special: dict[int, str] = {
            27: "escape",
            13: "enter",
            9: "tab",
            127: "backspace",
            57358: "caps_lock",
            57359: "scroll_lock",
            57360: "num_lock",
            57361: "print_screen",
            57362: "pause",
            57363: "menu",
            57376: "f13",
            57377: "f14",
        }
        # Arrow / navigation codepoints (Kitty uses Unicode private area)
        _kitty_nav: dict[int, str] = {
            57352: "up",
            57353: "down",
            57354: "right",
            57355: "left",
            57356: "end",
            57357: "home",
            57358: "page_up",
            57359: "page_down",
            57399: "kp0",
            57400: "kp1",
            57401: "kp2",
            57402: "kp3",
        }

        if codepoint in _kitty_special:
            key = _kitty_special[codepoint]
            return KeyEvent(
                key=key,
                char=None,
                shift=shift,
                alt=alt,
                ctrl=ctrl,
                meta=meta,
                released=released,
                repeat=repeat,
                raw=raw,
            )

        if codepoint in _kitty_nav:
            key = _kitty_nav[codepoint]
            return KeyEvent(
                key=key,
                char=None,
                shift=shift,
                alt=alt,
                ctrl=ctrl,
                meta=meta,
                released=released,
                repeat=repeat,
                raw=raw,
            )

        # Regular character
        key = ch.lower()
        char = ch if ch.isprintable() else None
        return KeyEvent(
            key=key,
            char=char,
            shift=shift,
            alt=alt,
            ctrl=ctrl,
            meta=meta,
            released=released,
            repeat=repeat,
            raw=raw,
        )

    def _parse_mouse(self, raw: str, params: str, final: str) -> MouseEvent | None:
        # SGR mouse: ESC [ < button ; col ; row M/m
        try:
            parts = params.split(";")
            button, x, y = int(parts[0]), int(parts[1]), int(parts[2])
        except (ValueError, IndexError):
            return None
        pressed = final == "M"
        return MouseEvent(x=x, y=y, button=button, pressed=pressed, raw=raw)


# ── InputHandler ──────────────────────────────────────────────────────────────


class InputHandler:
    """Owns all user-input state and handling: submit, paste, clipboard, steer.

    Receives ``layout``, ``tui``, and ``runtime`` at construction. Bind to the
    layout callbacks once via ``bind()``.  The ``turn_has_content`` property
    lets the global key handler decide whether Escape is a pre- or mid-stream
    abort.
    """

    _LARGE_PASTE_LINES = 10
    _LARGE_PASTE_CHARS = 1000

    def __init__(self, runtime: Runtime, layout: Layout, tui: TUI) -> None:
        self._runtime = runtime
        self._layout = layout
        self._tui = tui

        self._invoke_task: asyncio.Task | None = None
        self._pending_tasks: set[asyncio.Task] = set()
        self._turn_has_content: bool = False
        self._last_user_text: str = ""

        # Raw /command and !terminal inputs entered while the agent was busy.
        # Running them mid-turn corrupts the tool_use/tool_result pairing (and
        # !bash would execute immediately, racing the in-flight turn), so they
        # are held here and replayed verbatim once the turn settles (drained by
        # ``on_settled``, fired from the agent's ``settled`` event).
        self._deferred_inputs: list[str] = []
        self._draining_deferred: bool = False

        # Maps session counter → (uuid, absolute_path) for media stored in the project media dir.
        self._clipboard_images: dict[int, tuple[str, str]] = {}
        self._clipboard_image_notes: dict[int, str] = {}
        self._clipboard_image_counter: int = 0
        self._clipboard_audio: dict[int, tuple[str, str]] = {}
        self._clipboard_audio_counter: int = 0
        self._clipboard_video: dict[int, tuple[str, str]] = {}
        self._clipboard_video_counter: int = 0
        self._pasted_texts: dict[int, str] = {}
        self._paste_counter: int = 0

    def _track_task(self, task: asyncio.Task) -> asyncio.Task:
        self._pending_tasks.add(task)
        task.add_done_callback(self._pending_tasks.discard)
        return task

    def shutdown(self) -> None:
        for task in self._pending_tasks:
            task.cancel()
        self._pending_tasks.clear()

    def bind(self) -> None:
        """Wire submit/followup/dequeue and clipboard callbacks onto the layout."""
        self._layout.on_submit(self._on_submit)
        self._layout.on_followup(self._on_followup)
        self._layout.on_dequeue(self._on_dequeue)
        self._layout.input.on_paste = self._on_paste
        self._layout.input.on_paste_text = self._on_paste_text
        self._layout.input.on_history_transform = self._transform_for_history

    @property
    def turn_has_content(self) -> bool:
        return self._turn_has_content

    def mark_turn_content(self) -> None:
        """Record that the assistant has produced output this turn.

        Once set, Escape becomes a mid-stream abort (keep the partial response)
        rather than a pre-stream undo (discard the user message and restore the
        editor). Called by the agent-hook handler on the first streamed token.
        """
        self._turn_has_content = True

    # ── Submit / followup / dequeue ───────────────────────────────────────────

    def _notify(self, message: str, type: str = "info") -> None:  # noqa: A002
        import time
        from typing import cast

        from tau.message.types import CustomMessage, ImageContent, LinesContent, TextContent

        custom_type = "tool" if type == "tool" else "system"
        msg = CustomMessage(
            custom_type=custom_type,
            timestamp=time.time(),
            contents=cast(
                list[TextContent | ImageContent | LinesContent], [TextContent(content=message)]
            ),
        )
        self._layout.add_message(msg)
        self._tui.request_render()

    def _on_submit(self, text: str) -> None:
        from tau.message.types import UserMessage

        self.save_history()
        agent = self._runtime.agent

        if text.startswith("/") or text.startswith("!"):
            self._extract_clipboard_images(text)
            self._extract_clipboard_audio(text)
            self._extract_clipboard_video(text)
            self._pasted_texts.clear()
            self._paste_counter = 0
            # While the agent is mid-turn, defer commands/terminal input until it
            # goes idle instead of firing them now and corrupting the turn.
            if agent is not None and not agent.is_idle():
                self._defer_input(text)
                return
            if text.startswith("/"):
                self._layout.add_message(self._make_slash_message(text))
                self._tui.request_render()
            asyncio.ensure_future(self._invoke(text))
            return

        images, missing_images = self._extract_clipboard_images(text)
        if missing_images:
            plural = "s" if missing_images > 1 else ""
            self._notify(
                f"{missing_images} image{plural} could not be found —"
                f" the media file{plural} may have been deleted or moved.",
                type="error",
            )
            return

        audio = self._extract_clipboard_audio(text)
        video = self._extract_clipboard_video(text)
        expanded = self._expand_pasted_texts(text)

        if agent is not None and (images or audio or video):
            from tau.inference.model.types import Modality

            model = getattr(getattr(agent._engine, "llm", None), "model", None)
            if model is not None:
                if images and Modality.Image not in model.input:
                    self._notify(f"Image modality is not supported by {model.name}.", type="error")
                    return
                if audio and Modality.Audio not in model.input:
                    self._notify(f"Audio modality is not supported by {model.name}.", type="error")
                    return
                if video and Modality.Video not in model.input:
                    self._notify(f"Video modality is not supported by {model.name}.", type="error")
                    return

        if agent is not None and not agent.is_idle():
            self._track_task(asyncio.ensure_future(self._steer(expanded, images, audio, video)))
            return

        # Strip resolved image markers from the text sent to the model so the
        # LLM doesn't see raw [image:uuid] placeholders alongside actual image bytes.
        stripped = re.sub(r"\[image(?::[^\]]+| #\d+)\]", "", expanded).strip()
        model_text = stripped if stripped else expanded

        user_msg = UserMessage.with_media(text, images, audio, video)
        self._layout.add_message(user_msg)
        self._last_user_text = text
        self._turn_has_content = False
        self._tui.request_render()
        self._track_task(
            asyncio.ensure_future(
                self._invoke(self._expand_at_mentions(model_text), images, audio, video)
            )
        )

    def _on_followup(self, text: str) -> None:
        images, _ = self._extract_clipboard_images(text)
        audio = self._extract_clipboard_audio(text)
        video = self._extract_clipboard_video(text)
        expanded = self._expand_pasted_texts(text)
        self._track_task(
            asyncio.ensure_future(
                self._queue_followup(expanded, images, audio, video, display_text=text)
            )
        )

    # ── Deferred /command + !terminal ─────────────────────────────────────────

    def _defer_input(self, text: str) -> None:
        """Hold a /command or !terminal input until the turn settles, then replay it.

        No wakeup is scheduled here: the busy agent is in a turn that will emit
        ``settled`` when it finishes, which drives ``on_settled`` to drain this.
        """
        self._deferred_inputs.append(text)
        self._layout.set_deferred_queue(list(self._deferred_inputs))
        self._tui.request_render()

    async def on_settled(self) -> None:
        """Replay deferred /command + !terminal inputs once the turn has settled.

        Fired from the agent's ``settled`` event (same lifecycle point follow-up
        messages drain at). Each input is run to completion via ``_invoke`` so the
        next only starts after the previous turn/command fully finishes. A
        replayed prompt-style /command starts its own turn and re-emits
        ``settled``; the re-entrancy guard makes that nested call a no-op, and the
        loop here continues once ``_invoke`` returns.
        """
        if self._draining_deferred or not self._deferred_inputs:
            return
        agent = self._runtime.agent
        if agent is None or not agent.is_idle():
            # Not safe yet; a later settled (when the agent next goes idle) retries.
            return
        self._draining_deferred = True
        try:
            # Stop if the agent goes busy again (e.g. the abort path re-running
            # steering grabbed it); remaining inputs drain on the next settled.
            while self._deferred_inputs and agent.is_idle():
                text = self._deferred_inputs.pop(0)
                self._layout.set_deferred_queue(list(self._deferred_inputs))
                self._tui.request_render()
                if text.startswith("/"):
                    self._layout.add_message(self._make_slash_message(text))
                    self._tui.request_render()
                await self._invoke(text)
        finally:
            self._draining_deferred = False

    def _take_queued_texts(self) -> list[str]:
        """Snapshot and clear all pending steering/follow-up message texts.

        Returns the queued texts (oldest first) and empties both queues, so the
        caller can decide whether to restore them to the editor or run them.
        """
        from tau.message.types import TextContent

        agent = self._runtime.agent
        if agent is None:
            return []
        engine = agent._engine

        def _extract_texts(queue) -> list[str]:
            if queue is None:
                return []
            return [
                "".join(
                    c.content for c in getattr(msg, "contents", []) if isinstance(c, TextContent)
                )
                for msg in queue.snapshot()
            ]

        all_texts = _extract_texts(engine.state.steering_queue) + _extract_texts(
            engine.state.follow_up_queue
        )
        all_texts = [t for t in all_texts if t.strip()]
        if not all_texts:
            return []
        engine.clear_all_queues()
        self._layout.set_pending_queue([], [])
        return all_texts

    def _take_deferred_texts(self) -> list[str]:
        """Snapshot and clear pending deferred /command + !terminal inputs."""
        if not self._deferred_inputs:
            return []
        texts, self._deferred_inputs = self._deferred_inputs, []
        self._layout.set_deferred_queue([])
        return texts

    def _on_dequeue(self) -> None:
        all_texts = self._take_queued_texts() + self._take_deferred_texts()
        if not all_texts:
            return
        self._layout.restore_queued_to_editor(all_texts)
        self._tui.request_render()

    # ── Escape abort ──────────────────────────────────────────────────────────

    def escape_abort(self) -> None:
        """Escape pressed while agent is running.

        Pre-stream: undo the user message and restore editor.
        Mid-stream: keep partial response; signal via abort only.
        """
        agent = self._runtime.agent
        if agent is None:
            return

        had_content = self._turn_has_content
        # Anything typed while the agent ran was meant as the *next* task, not
        # part of the one being interrupted. Take it now and run it once the
        # aborted task goes idle, rather than discarding it to the editor.
        queued = self._take_queued_texts()
        agent.abort()

        if not had_content:
            # Pre-stream: no assistant output yet. Cancel the in-flight invoke,
            # drop the user message from the transcript and (if it was already
            # persisted) the session file, and put the text back in the editor.
            if self._invoke_task is not None and not self._invoke_task.done():
                self._invoke_task.cancel()
            self._layout.messages.remove_pending_user_turn()
            sm = self._runtime.session_manager
            if sm is not None:
                sm.remove_last_message(role="user")
            last_text = self._last_user_text
            self._last_user_text = ""
            if last_text:
                self._layout.input.set_text(last_text)
            self._clear_clipboard_caches()

        self._turn_has_content = False
        # Stop the spinner immediately. The pre-stream branch cancels the invoke
        # task, which interrupts the engine before it can emit AgentEndEvent (the
        # event that normally stops the spinner), so rely on this explicit stop.
        # If queued input runs next, _on_agent_start will start it again.
        self._layout.spinner.stop()
        if queued:
            self._track_task(asyncio.ensure_future(self._run_queued_next(queued)))
        self._tui.request_render()

    def _clear_clipboard_caches(self) -> None:
        """Clear all clipboard media caches."""
        self._clipboard_images.clear()
        self._clipboard_image_notes.clear()
        self._clipboard_image_counter = 0
        self._clipboard_audio.clear()
        self._clipboard_audio_counter = 0
        self._clipboard_video.clear()
        self._clipboard_video_counter = 0
        self._pasted_texts.clear()
        self._paste_counter = 0

    async def _run_queued_next(self, texts: list[str]) -> None:
        """Submit queued input as the next task once the aborted task is idle.

        Waits for the interrupted run to finish unwinding, then re-submits the
        combined queued text through the normal submit path so it renders and
        runs exactly as if freshly entered.
        """
        agent = self._runtime.agent
        if agent is None:
            return
        await agent.wait_for_idle()
        combined = "\n\n".join(texts).strip()
        if combined:
            self._on_submit(combined)

    # ── Invoke / steer / queue ────────────────────────────────────────────────

    async def _invoke(
        self,
        text: str,
        images: list[bytes] | None = None,
        audio: list[bytes] | None = None,
        video: list[bytes] | None = None,
    ) -> None:
        self._invoke_task = asyncio.current_task()
        try:
            from tau.agent.types import PromptOptions

            if images or audio or video:
                options = PromptOptions(
                    images=images or [],
                    audio=audio or [],
                    video=video or [],
                )
            else:
                options = None
            await self._runtime.user_input(text, options)
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            _log.exception("Error during invoke")
            self._layout.spinner.set_label(f"error: {exc}")
            self._layout.spinner.stop()
            self._tui.request_render()
        finally:
            self._invoke_task = None

    @staticmethod
    def _build_user_message(
        text: str,
        images: list[bytes] | None = None,
        audio: list[bytes] | None = None,
        video: list[bytes] | None = None,
    ) -> UserMessage:
        """Build a UserMessage from text plus any combination of media.

        Carries the same media a fresh turn would, so steering and follow-up
        messages match a freshly submitted message.
        """
        from tau.message.types import UserMessage

        return UserMessage.with_media(text, images, audio, video)

    async def _steer(
        self,
        text: str,
        images: list[bytes] | None = None,
        audio: list[bytes] | None = None,
        video: list[bytes] | None = None,
    ) -> None:
        agent = self._runtime.agent
        if agent is None:
            return
        try:
            expanded = self._expand_at_mentions(text)
            msg = self._build_user_message(expanded, images, audio, video)
            await agent._engine.steer(msg)
        except Exception as exc:
            _log.exception("Error during steer")
            self._layout.spinner.set_label(f"error: {exc}")
            self._tui.request_render()

    async def _queue_followup(
        self,
        text: str,
        images: list[bytes] | None = None,
        audio: list[bytes] | None = None,
        video: list[bytes] | None = None,
        display_text: str | None = None,
    ) -> None:
        shown = display_text if display_text is not None else text

        agent = self._runtime.agent
        if agent is None or agent.is_idle():
            user_msg = self._build_user_message(shown, images, audio, video)
            self._layout.add_message(user_msg)
            self._tui.request_render()
            await self._invoke(self._expand_at_mentions(text), images, audio, video)
        else:
            try:
                msg = self._build_user_message(self._expand_at_mentions(text), images, audio, video)
                await agent._engine.follow_up(msg)
            except Exception as exc:
                _log.exception("Error during follow-up")
                self._layout.spinner.set_label(f"error: {exc}")
                self._tui.request_render()

    # ── Paste handling ────────────────────────────────────────────────────────

    _AUDIO_SUFFIXES = {".mp3", ".wav", ".ogg", ".flac", ".m4a", ".aac", ".opus", ".weba"}
    _VIDEO_SUFFIXES = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v", ".wmv", ".flv"}

    def _paste_file(self, src_path: str) -> None:
        """Detect file type by extension and route to the appropriate store method."""
        try:
            suffix = "." + src_path.rsplit(".", 1)[-1].lower() if "." in src_path else ".png"
            with open(src_path, "rb") as f:
                data = f.read()
            if suffix in self._AUDIO_SUFFIXES:
                self._store_clipboard_audio(data, suffix)
            elif suffix in self._VIDEO_SUFFIXES:
                self._store_clipboard_video(data, suffix)
            else:
                self._store_clipboard_image(data, suffix)
        except Exception:
            _log.debug("Failed to paste file %r", src_path, exc_info=True)

    def _on_paste(self) -> None:
        import io

        try:
            from PIL import ImageGrab

            item = ImageGrab.grabclipboard()
            if item is None:
                return
            if isinstance(item, list):
                for p in item:
                    self._paste_file(str(p))
                return
            buf = io.BytesIO()
            item.save(buf, format="PNG")
            self._store_clipboard_image(buf.getvalue(), ".png")
        except Exception:
            _log.debug("Clipboard image grab failed", exc_info=True)

    def _get_media_dir(self) -> Path:
        sm = self._runtime.session_manager
        if sm is not None:
            return sm.session_dir / "media"
        from tau.settings.paths import CONFIG_DIR_PATH

        return CONFIG_DIR_PATH / "sessions" / "global" / "media"

    def _find_media_by_uuid(self, uid: str) -> Path | None:
        """Search all project session media dirs for a file matching the UUID.

        History is global across projects, so an image pasted in project A must
        still be resolvable when re-submitted from a session in project B.
        """
        from tau.settings.paths import get_sessions_dir

        try:
            for project_dir in get_sessions_dir().iterdir():
                if not project_dir.is_dir():
                    continue
                media_dir = project_dir / "media"
                if not media_dir.is_dir():
                    continue
                for p in media_dir.glob(f"{uid}.*"):
                    return p
        except OSError:
            _log.debug("failed to locate media by uuid %s", uid, exc_info=True)
        return None

    def _store_clipboard_image(self, raw: bytes, suffix: str) -> None:
        import uuid as _uuid

        try:
            from tau.utils.image_processing import process_image

            sm = self._runtime.settings_manager
            auto_resize = sm.get_image_auto_resize() if sm is not None else True
            result = process_image(raw, auto_resize=auto_resize)
            data = result.data
            suffix = ".png" if result.mime_type == "image/png" else suffix
            note = result.dimension_note()
            media_dir = self._get_media_dir()
            media_dir.mkdir(parents=True, exist_ok=True)
            file_uuid = str(_uuid.uuid4())
            media_path = media_dir / f"{file_uuid}{suffix}"
            media_path.write_bytes(data)
            self._clipboard_image_counter += 1
            idx = self._clipboard_image_counter
            self._clipboard_images[idx] = (file_uuid, str(media_path))
            if note:
                self._clipboard_image_notes[idx] = note
            self._layout.input.insert_at_cursor(f"[image #{idx}]")
            self._tui.request_render()
        except Exception as exc:
            _log.exception("Failed to store clipboard image")
            self._notify(f"Could not store image: {exc}", type="error")

    def _store_clipboard_audio(self, raw: bytes, suffix: str) -> None:
        import uuid as _uuid

        try:
            media_dir = self._get_media_dir()
            media_dir.mkdir(parents=True, exist_ok=True)
            file_uuid = str(_uuid.uuid4())
            media_path = media_dir / f"{file_uuid}{suffix}"
            media_path.write_bytes(raw)
            self._clipboard_audio_counter += 1
            idx = self._clipboard_audio_counter
            self._clipboard_audio[idx] = (file_uuid, str(media_path))
            self._layout.input.insert_at_cursor(f"[audio #{idx}]")
            self._tui.request_render()
        except Exception as exc:
            _log.exception("Failed to store clipboard audio")
            self._notify(f"Could not store audio: {exc}", type="error")

    def _store_clipboard_video(self, raw: bytes, suffix: str) -> None:
        import uuid as _uuid

        try:
            media_dir = self._get_media_dir()
            media_dir.mkdir(parents=True, exist_ok=True)
            file_uuid = str(_uuid.uuid4())
            media_path = media_dir / f"{file_uuid}{suffix}"
            media_path.write_bytes(raw)
            self._clipboard_video_counter += 1
            idx = self._clipboard_video_counter
            self._clipboard_video[idx] = (file_uuid, str(media_path))
            self._layout.input.insert_at_cursor(f"[video #{idx}]")
            self._tui.request_render()
        except Exception as exc:
            _log.exception("Failed to store clipboard video")
            self._notify(f"Could not store video: {exc}", type="error")

    def _extract_clipboard_audio(self, text: str) -> list[bytes]:
        audio: list[bytes] = []
        seen: set[int] = set()
        for m in re.finditer(r"\[audio #(\d+)\]", text):
            idx = int(m.group(1))
            if idx in seen:
                continue
            seen.add(idx)
            entry = self._clipboard_audio.get(idx)
            if entry is None:
                continue
            _, path = entry
            try:
                with open(path, "rb") as f:
                    audio.append(f.read())
            except OSError:
                _log.warning("failed to read clipboard audio %s", path, exc_info=True)
        # Also resolve persistent [audio:{uuid}] markers from history
        seen_uuids: set[str] = set()
        for m in re.finditer(r"\[audio:([^\]]+)\]", text):
            uid = m.group(1)
            if uid in seen_uuids:
                continue
            seen_uuids.add(uid)
            p = self._find_media_by_uuid(uid)
            if p is not None:
                with contextlib.suppress(OSError):
                    audio.append(p.read_bytes())
        self._clipboard_audio.clear()
        self._clipboard_audio_counter = 0
        return audio

    def _extract_clipboard_video(self, text: str) -> list[bytes]:
        video: list[bytes] = []
        seen: set[int] = set()
        for m in re.finditer(r"\[video #(\d+)\]", text):
            idx = int(m.group(1))
            if idx in seen:
                continue
            seen.add(idx)
            entry = self._clipboard_video.get(idx)
            if entry is None:
                continue
            _, path = entry
            try:
                with open(path, "rb") as f:
                    video.append(f.read())
            except OSError:
                _log.warning("failed to read clipboard video %s", path, exc_info=True)
        # Also resolve persistent [video:{uuid}] markers from history
        seen_uuids: set[str] = set()
        for m in re.finditer(r"\[video:([^\]]+)\]", text):
            uid = m.group(1)
            if uid in seen_uuids:
                continue
            seen_uuids.add(uid)
            p = self._find_media_by_uuid(uid)
            if p is not None:
                with contextlib.suppress(OSError):
                    video.append(p.read_bytes())
        self._clipboard_video.clear()
        self._clipboard_video_counter = 0
        return video

    # ESC[<code>;5u — control bytes some terminals (tmux popups with
    # extended-keys-format=csi-u) re-encode inside a bracketed paste.
    _CSI_U_CTRL_RE = re.compile(r"\x1b\[(\d+);5u")

    def _sanitize_paste(self, text: str) -> str:
        """Clean bracketed-paste text before it is stored or inserted.

        1. Decode CSI-u re-encoded control bytes back to their literal byte,
           so a pasted newline doesn't leak into the buffer as "[106;5u".
        2. Normalize line endings (CRLF/CR -> LF) and expand tabs to spaces.
        3. Drop remaining non-printable characters (keep newlines).
        4. Prepend a space when pasting a path right after a word character.
        """

        def _decode(m: re.Match[str]) -> str:
            cp = int(m.group(1))
            if 97 <= cp <= 122:  # ctrl+a..z
                return chr(cp - 96)
            if 65 <= cp <= 90:  # ctrl+A..Z
                return chr(cp - 64)
            return m.group(0)

        text = self._CSI_U_CTRL_RE.sub(_decode, text)
        text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\t", "    ")
        text = "".join(ch for ch in text if ch == "\n" or ord(ch) >= 32)
        # Strip trailing newlines — copying a line from the terminal often includes
        # the newline, which would create a ghost empty line in the input box.
        text = text.rstrip("\n")

        # Readability: pasting a path (/, ~, .) right after a word char gets a space.
        if text[:1] in ("/", "~", "."):
            inp = self._layout.input
            buf, cur = inp.text, getattr(inp, "_cursor", 0)
            if cur > 0 and buf[cur - 1 : cur].isalnum():
                text = " " + text
        return text

    def _on_paste_text(self, text: str) -> None:
        text = self._sanitize_paste(text)
        if not text:
            return
        lines = text.split("\n")
        if len(lines) > self._LARGE_PASTE_LINES or len(text) > self._LARGE_PASTE_CHARS:
            self._paste_counter += 1
            idx = self._paste_counter
            self._pasted_texts[idx] = text
            marker = (
                f"[paste #{idx} +{len(lines)} lines]"
                if len(lines) > self._LARGE_PASTE_LINES
                else f"[paste #{idx} {len(text)} chars]"
            )
            self._layout.input.insert_at_cursor(marker)
            self._tui.request_render()
        else:
            self._layout.input.insert_at_cursor(text)
            self._tui.request_render()

    def _expand_pasted_texts(self, text: str) -> str:
        if not self._pasted_texts:
            return text

        def _replace(m: re.Match) -> str:
            idx = int(m.group(1))
            return self._pasted_texts.get(idx) or m.group(0)

        expanded = re.sub(r"\[paste #(\d+)(?: \+\d+ lines| \d+ chars)\]", _replace, text)
        self._pasted_texts.clear()
        self._paste_counter = 0
        return expanded

    def _transform_for_history(self, text: str) -> str:
        """Replace session-scoped [image/audio/video #N] markers with persistent [type:{uuid}] ones.

        Paste markers are stripped entirely since their content is already expanded into the text
        before this is called (or they reference temp data that won't survive the session).
        """

        def _replace_image(m: re.Match) -> str:
            idx = int(m.group(1))
            entry = self._clipboard_images.get(idx)
            return f"[image:{entry[0]}]" if entry else ""

        def _replace_audio(m: re.Match) -> str:
            idx = int(m.group(1))
            entry = self._clipboard_audio.get(idx)
            return f"[audio:{entry[0]}]" if entry else ""

        def _replace_video(m: re.Match) -> str:
            idx = int(m.group(1))
            entry = self._clipboard_video.get(idx)
            return f"[video:{entry[0]}]" if entry else ""

        result = re.sub(r"\[image #(\d+)\]", _replace_image, text)
        result = re.sub(r"\[audio #(\d+)\]", _replace_audio, result)
        result = re.sub(r"\[video #(\d+)\]", _replace_video, result)
        result = re.sub(r"\[paste #\d+(?: \+\d+ lines| \d+ chars)\]", "", result)
        return result.strip()

    def _extract_clipboard_images(self, text: str) -> tuple[list[bytes], int]:
        """Extract image bytes from markers in text.

        Returns (images, missing_count) where missing_count is the number of
        persistent [image:uuid] markers whose media files could not be found.
        """
        images: list[bytes] = []
        seen: set[int] = set()
        for m in re.finditer(r"\[image #(\d+)\]", text):
            idx = int(m.group(1))
            if idx in seen:
                continue
            seen.add(idx)
            entry = self._clipboard_images.get(idx)
            if entry is None:
                continue
            _, path = entry
            try:
                with open(path, "rb") as f:
                    images.append(f.read())
            except OSError:
                _log.warning("failed to read clipboard image %s", path, exc_info=True)
        # Also resolve persistent [image:{uuid}] markers from history
        missing = 0
        seen_uuids: set[str] = set()
        for m in re.finditer(r"\[image:([^\]]+)\]", text):
            uid = m.group(1)
            if uid in seen_uuids:
                continue
            seen_uuids.add(uid)
            p = self._find_media_by_uuid(uid)
            if p is not None:
                try:
                    images.append(p.read_bytes())
                except OSError:
                    missing += 1
            else:
                missing += 1
        self._clipboard_images.clear()
        self._clipboard_image_notes.clear()
        self._clipboard_image_counter = 0
        return images, missing

    def _extract_clipboard_image_contents(self, text: str) -> list[Any]:
        """Like _extract_clipboard_images but returns ImageContent with dimension notes."""
        from tau.message.types import ImageContent as _IC

        contents = []
        seen: set[int] = set()
        for m in re.finditer(r"\[image #(\d+)\]", text):
            idx = int(m.group(1))
            if idx in seen:
                continue
            seen.add(idx)
            entry = self._clipboard_images.get(idx)
            if entry is None:
                continue
            _, path = entry
            try:
                with open(path, "rb") as f:
                    data = f.read()
                note = self._clipboard_image_notes.get(idx)
                contents.append(_IC(images=[data], dimension_note=note))
            except OSError:
                _log.warning("failed to read clipboard image content %s", path, exc_info=True)
        # Also resolve persistent [image:{uuid}] markers from history
        seen_uuids: set[str] = set()
        for m in re.finditer(r"\[image:([^\]]+)\]", text):
            uid = m.group(1)
            if uid in seen_uuids:
                continue
            seen_uuids.add(uid)
            p = self._find_media_by_uuid(uid)
            if p is not None:
                with contextlib.suppress(OSError):
                    contents.append(_IC(images=[p.read_bytes()]))
        self._clipboard_images.clear()
        self._clipboard_image_notes.clear()
        self._clipboard_image_counter = 0
        return contents

    # ── At-mentions ───────────────────────────────────────────────────────────

    def _expand_at_mentions(self, text: str) -> str:
        sm = self._runtime.session_manager
        cwd = sm.cwd if sm is not None else Path.cwd()
        pattern = re.compile(r"@([^\s@]+)")
        attachments: list[str] = []
        for m in pattern.finditer(text):
            raw_path = m.group(1)
            path = Path(raw_path) if Path(raw_path).is_absolute() else cwd / raw_path
            if path.is_file():
                try:
                    content = path.read_text(errors="replace")
                    attachments.append(f'<file path="{raw_path}">\n{content}\n</file>')
                except OSError:
                    _log.debug("failed to read @mention file %s", path, exc_info=True)
        if not attachments:
            return text
        return "\n".join(attachments) + "\n\n" + text

    # ── Slash message factory ─────────────────────────────────────────────────

    def _make_slash_message(self, text: str) -> object:
        from tau.message.types import SkillInvocationMessage, TemplateInvocationMessage, UserMessage

        if text.startswith("/skill:"):
            from tau.skills.registry import skill_registry

            skill_part = text[7:].strip().split(None, 1)
            skill_name = skill_part[0].lower() if skill_part else ""
            skill_args = skill_part[1] if len(skill_part) > 1 else ""
            skill = skill_registry.get(skill_name)
            if skill is not None:
                return SkillInvocationMessage(
                    name=skill_name, args=skill_args, content=skill.content
                )

        parts = text[1:].strip().split(None, 1)
        name = parts[0].lower() if parts else ""
        args_str = parts[1] if len(parts) > 1 else ""
        if self._runtime.commands.get(name) is None:
            from tau.prompts.registry import prompt_registry

            tmpl = prompt_registry.get(name)
            if tmpl is not None:
                expanded = prompt_registry.expand(name, args_str)
                if expanded is not None:
                    return TemplateInvocationMessage(
                        name=name, args=args_str, expanded_content=expanded
                    )

        return UserMessage.from_text(text)

    # ── History ───────────────────────────────────────────────────────────────

    def load_history(self) -> None:
        path = _history_path()
        if not path.exists():
            return
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
            entries: list[str] = []
            current: list[str] = []
            for line in lines:
                if line == "\x00":
                    if current:
                        entries.append("\n".join(current))
                        current = []
                else:
                    current.append(line)
            if current:
                entries.append("\n".join(current))
            self._layout.input._history = entries[-500:]
        except OSError:
            _log.debug("failed to load history", exc_info=True)

    def save_history(self) -> None:
        history = self._layout.input._history
        if not history:
            return
        path = _history_path()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            chunks: list[str] = []
            for entry in history[-500:]:
                chunks.append(entry.replace("\x00", ""))
                chunks.append("\x00")
            path.write_text("\n".join(chunks), encoding="utf-8")
        except OSError:
            _log.debug("failed to save history", exc_info=True)


def _history_path():
    from tau.settings.paths import CONFIG_DIR_PATH

    return CONFIG_DIR_PATH / "history"


# ── Keybindings ───────────────────────────────────────────────────────────────

# Named action → list of key combo strings that trigger it
KeyMap = dict[str, list[str]]

_DEFAULTS: KeyMap = {
    # Selection / list navigation
    "tui.select.up": ["up", "ctrl+p"],
    "tui.select.down": ["down", "ctrl+n"],
    "tui.select.page_up": ["page_up"],
    "tui.select.page_down": ["page_down"],
    "tui.select.top": ["home"],
    "tui.select.bottom": ["end"],
    "tui.select.confirm": ["enter", "tab"],
    "tui.select.dismiss": ["escape"],
    # Text input
    "tui.input.submit": ["enter"],
    "tui.input.newline": ["shift+enter"],
    "tui.input.clear": ["ctrl+u"],
    "tui.input.word_back": ["ctrl+w"],
    # Message queuing
    "app.message.followup": ["alt+enter"],  # queue as follow-up (waits for agent to finish)
    "app.message.dequeue": ["alt+up"],  # restore queued messages into editor
    # App-level
    "tui.app.quit": ["ctrl+c", "ctrl+d"],
    "tui.app.abort": ["ctrl+c"],
    # Scroll (message list)
    "tui.scroll.up": ["page_up"],
    "tui.scroll.down": ["page_down"],
    "tui.scroll.top": ["home"],
    "tui.scroll.bottom": ["end"],
}


class KeybindingsManager:
    """
    Central registry mapping named actions to key combo strings.
    User overrides are merged on top of defaults at construction time.
    """

    def __init__(self, overrides: KeyMap | None = None) -> None:
        self._map: KeyMap = {k: list(v) for k, v in _DEFAULTS.items()}
        if overrides:
            for action, keys in overrides.items():
                self._map[action] = list(keys)

    def matches(self, event: KeyEvent, action: str) -> bool:
        """Return True if `event` triggers the named action.

        Uses KeyEvent.matches so user-supplied combos are modifier-order- and
        alias-independent ('shift+ctrl+x' == 'ctrl+shift+x' == 'control+shift+x').
        """
        combos = self._map.get(action, [])
        return event.matches(*combos)

    def keys_for(self, action: str) -> list[str]:
        """Return the key combo strings registered for `action`."""
        return list(self._map.get(action, []))

    def bind(self, action: str, keys: list[str]) -> None:
        """Replace all bindings for an action."""
        self._map[action] = list(keys)

    def add_binding(self, action: str, key: str) -> None:
        """Append an extra key combo for an action without removing existing ones."""
        self._map.setdefault(action, [])
        if key not in self._map[action]:
            self._map[action].append(key)


_keybindings_instance: KeybindingsManager | None = None


def get_keybindings() -> KeybindingsManager:
    """Return the global KeybindingsManager singleton (created lazily)."""
    global _keybindings_instance
    if _keybindings_instance is None:
        _keybindings_instance = KeybindingsManager()
    return _keybindings_instance


def configure_keybindings(overrides: KeyMap) -> None:
    """Apply user overrides to the global singleton (call once at startup)."""
    global _keybindings_instance
    _keybindings_instance = KeybindingsManager(overrides)
