"""Tests for tau/tui/ansi.py — ANSI escape code utilities."""
from __future__ import annotations

from tau.tui.ansi import (
    RESET, BOLD, DIM, ITALIC, UNDERLINE, RED, GREEN, BLUE,
    fg, bg, fg256, bg256, style,
    strip_ansi, visible_width, truncate, pad, wrap,
    _char_width, _AnsiStateTracker,
)


class TestColorGenerators:
    def test_fg_truecolor(self):
        assert fg(255, 0, 128) == "\x1b[38;2;255;0;128m"

    def test_bg_truecolor(self):
        assert bg(0, 128, 255) == "\x1b[48;2;0;128;255m"

    def test_fg256(self):
        assert fg256(42) == "\x1b[38;5;42m"

    def test_bg256(self):
        assert bg256(200) == "\x1b[48;5;200m"

    def test_style_wraps_with_reset(self):
        result = style("hello", BOLD, RED)
        assert result.startswith(BOLD + RED)
        assert result.endswith(RESET)
        assert "hello" in result

    def test_style_single_code(self):
        result = style("x", BLUE)
        assert BLUE in result
        assert "x" in result
        assert result.endswith(RESET)


class TestStripAnsi:
    def test_strips_sgr(self):
        assert strip_ansi(f"{BOLD}hello{RESET}") == "hello"

    def test_strips_color(self):
        assert strip_ansi(f"{RED}red{RESET}") == "red"

    def test_plain_text_unchanged(self):
        assert strip_ansi("plain") == "plain"

    def test_empty_string(self):
        assert strip_ansi("") == ""

    def test_multiple_codes(self):
        text = f"{BOLD}{RED}bold red{RESET}"
        assert strip_ansi(text) == "bold red"

    def test_truecolor(self):
        text = f"{fg(255, 0, 0)}red{RESET}"
        assert strip_ansi(text) == "red"


class TestVisibleWidth:
    def test_ascii_string(self):
        assert visible_width("hello") == 5

    def test_empty_string(self):
        assert visible_width("") == 0

    def test_ansi_codes_not_counted(self):
        assert visible_width(f"{BOLD}abc{RESET}") == 3

    def test_wide_cjk_chars(self):
        # CJK characters are 2 columns wide
        assert visible_width("日本") == 4

    def test_mixed_ascii_and_cjk(self):
        assert visible_width("a日") == 3


class TestCharWidth:
    def test_ascii_letter(self):
        assert _char_width("a") == 1

    def test_space(self):
        assert _char_width(" ") == 1

    def test_cjk_wide(self):
        assert _char_width("中") == 2

    def test_null_byte(self):
        assert _char_width("\x00") == 0


class TestTruncate:
    def test_short_text_unchanged(self):
        assert truncate("hello", 10) == "hello"

    def test_truncates_long_text(self):
        result = truncate("hello world", 7)
        assert visible_width(result) <= 7
        assert "…" in strip_ansi(result)

    def test_exact_width_unchanged(self):
        text = "hello"
        assert truncate(text, 5) == text

    def test_truncates_ansi_text(self):
        text = f"{RED}hello world{RESET}"
        result = truncate(text, 7)
        assert visible_width(result) <= 7


class TestPad:
    def test_left_pad(self):
        result = pad("hi", 5)
        assert result == "hi   "
        assert visible_width(result) == 5

    def test_right_pad(self):
        result = pad("hi", 5, align="right")
        assert result == "   hi"

    def test_center_pad(self):
        result = pad("hi", 6, align="center")
        assert visible_width(result) == 6
        assert "hi" in result

    def test_no_padding_needed(self):
        result = pad("hello", 3)
        assert result == "hello"

    def test_custom_char(self):
        result = pad("hi", 5, char="-")
        assert result == "hi---"


class TestWrap:
    def test_short_line_not_wrapped(self):
        assert wrap("hello", 80) == ["hello"]

    def test_wraps_long_line(self):
        lines = wrap("a" * 10, 5)
        assert len(lines) == 2
        for line in lines:
            assert visible_width(strip_ansi(line)) <= 5

    def test_respects_newlines(self):
        lines = wrap("line1\nline2", 80)
        assert len(lines) == 2

    def test_zero_width_returns_text(self):
        result = wrap("hello", 0)
        assert result == ["hello"]

    def test_wraps_with_ansi(self):
        text = f"{RED}{'a' * 12}{RESET}"
        lines = wrap(text, 5)
        assert len(lines) > 1
        for line in lines:
            assert visible_width(line) <= 5

    def test_empty_string(self):
        assert wrap("", 10) == [""]


class TestAnsiStateTracker:
    def test_initially_no_state(self):
        t = _AnsiStateTracker()
        assert t.has_state() is False
        assert t.active_codes() == ""

    def test_bold_sets_state(self):
        t = _AnsiStateTracker()
        t.process(BOLD)
        assert t.has_state() is True
        assert BOLD in t.active_codes()

    def test_reset_clears_state(self):
        t = _AnsiStateTracker()
        t.process(BOLD)
        t.process(RESET)
        assert t.has_state() is False

    def test_fg_color_tracked(self):
        t = _AnsiStateTracker()
        t.process(RED)
        assert t.has_state() is True
        assert RED in t.active_codes()

    def test_italic_tracked(self):
        t = _AnsiStateTracker()
        t.process(ITALIC)
        assert t.has_state() is True

    def test_underline_tracked(self):
        t = _AnsiStateTracker()
        t.process(UNDERLINE)
        assert t.has_state() is True

    def test_dim_tracked(self):
        t = _AnsiStateTracker()
        t.process(DIM)
        assert t.has_state() is True

    def test_multiple_codes_accumulated(self):
        t = _AnsiStateTracker()
        t.process(BOLD)
        t.process(RED)
        codes = t.active_codes()
        assert BOLD in codes
        assert RED in codes

    def test_non_sgr_code_ignored(self):
        t = _AnsiStateTracker()
        t.process("\x1b[2J")  # clear screen, not SGR
        assert t.has_state() is False

    def test_truecolor_fg_tracked(self):
        t = _AnsiStateTracker()
        t.process(fg(100, 200, 50))
        assert t.has_state() is True
        codes = t.active_codes()
        assert "38;2" in codes
