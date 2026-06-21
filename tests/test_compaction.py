"""Tests for tau/session/compaction.py — token estimation, compaction logic."""
from __future__ import annotations

import json
import time

from tau.session.compaction import (
    CompactionSettings,
    estimate_tokens,
    estimate_context_tokens,
    should_compact,
    serialize_conversation,
    TOOL_RESULT_MAX_CHARS,
)
from tau.message.types import (
    UserMessage, AssistantMessage, ToolMessage,
    TextContent, ThinkingContent, ToolCallContent, ToolResultContent,
    CompactionSummaryMessage, BranchSummaryMessage,
    TerminalExecutionMessage, CustomMessage,
)
from tau.inference.types import StopReason
from tau.message.types import Usage


class TestEstimateTokens:
    def test_user_text_message(self):
        msg = UserMessage.from_text("hello world")
        tokens = estimate_tokens(msg)
        assert tokens == max(1, len("hello world") // 4)

    def test_empty_user_message(self):
        msg = UserMessage()
        tokens = estimate_tokens(msg)
        assert tokens >= 1  # minimum of 1

    def test_assistant_text_message(self):
        msg = AssistantMessage.from_text("a" * 400)
        tokens = estimate_tokens(msg)
        assert tokens == 100  # 400 chars / 4

    def test_assistant_thinking_counted(self):
        msg = AssistantMessage(contents=[ThinkingContent(content="t" * 200)])
        tokens = estimate_tokens(msg)
        assert tokens == 50  # 200 // 4

    def test_assistant_tool_call_counted(self):
        args = {"path": "/a/b"}
        name = "read_file"
        msg = AssistantMessage(contents=[ToolCallContent(id="1", name=name, args=args)])
        expected = max(1, (len(name) + len(json.dumps(args))) // 4)
        assert estimate_tokens(msg) == expected

    def test_tool_message_result(self):
        result = ToolResultContent(id="1", content="r" * 800)
        msg = ToolMessage.from_result(result)
        tokens = estimate_tokens(msg)
        assert tokens == 200  # 800 // 4

    def test_terminal_execution_message(self):
        msg = TerminalExecutionMessage(command="ls", output="file1\nfile2")
        tokens = estimate_tokens(msg)
        expected = max(1, (len("ls") + len("file1\nfile2")) // 4)
        assert tokens == expected

    def test_compaction_summary_message(self):
        msg = CompactionSummaryMessage(summary="s" * 400)
        tokens = estimate_tokens(msg)
        assert tokens == 100

    def test_branch_summary_message(self):
        msg = BranchSummaryMessage(summary="s" * 200)
        tokens = estimate_tokens(msg)
        assert tokens == 50

    def test_custom_message_text_counted(self):
        msg = CustomMessage(custom_type="info", contents=[TextContent(content="c" * 100)])
        tokens = estimate_tokens(msg)
        assert tokens == 25


class TestEstimateContextTokens:
    def test_no_messages(self):
        result = estimate_context_tokens([])
        assert result.tokens == 0

    def test_uses_heuristic_without_usage(self):
        msgs = [UserMessage.from_text("hello")]
        result = estimate_context_tokens(msgs)
        assert result.tokens >= 1
        assert result.last_usage_index is None

    def test_uses_assistant_usage_as_anchor(self):
        u = Usage(input_tokens=100, output_tokens=50)
        asst = AssistantMessage(contents=[TextContent(content="reply")])
        asst.usage = u
        asst.stop_reason = StopReason.Stop

        msgs = [UserMessage.from_text("q"), asst]
        result = estimate_context_tokens(msgs)
        assert result.usage_tokens == 150
        assert result.last_usage_index == 1

    def test_skips_aborted_assistant(self):
        u = Usage(input_tokens=1000, output_tokens=0)
        aborted = AssistantMessage(contents=[])
        aborted.usage = u
        aborted.stop_reason = StopReason.Abort

        msgs = [UserMessage.from_text("q"), aborted]
        result = estimate_context_tokens(msgs)
        # Should fall back to heuristic since only aborted assistant exists
        assert result.last_usage_index is None


class TestShouldCompact:
    def test_disabled_settings_never_compact(self):
        settings = CompactionSettings(enabled=False, reserve_tokens=1000)
        assert should_compact(100_000, 200_000, settings) is False

    def test_zero_context_window_never_compact(self):
        settings = CompactionSettings(enabled=True, reserve_tokens=1000)
        assert should_compact(100_000, 0, settings) is False

    def test_compacts_when_over_threshold(self):
        settings = CompactionSettings(enabled=True, reserve_tokens=10_000)
        # 95_000 tokens in a 100_000 window → needs 10k reserve → over threshold
        assert should_compact(95_000, 100_000, settings) is True

    def test_no_compact_when_within_threshold(self):
        settings = CompactionSettings(enabled=True, reserve_tokens=10_000)
        # 50_000 tokens in a 100_000 window → plenty of room
        assert should_compact(50_000, 100_000, settings) is False

    def test_exactly_at_threshold(self):
        settings = CompactionSettings(enabled=True, reserve_tokens=10_000)
        # 90_000 tokens, window 100_000 → 90_000 > 90_000 is False (not strictly over)
        assert should_compact(90_000, 100_000, settings) is False

    def test_one_over_threshold(self):
        settings = CompactionSettings(enabled=True, reserve_tokens=10_000)
        assert should_compact(90_001, 100_000, settings) is True


class TestSerializeConversation:
    def test_user_message(self):
        msgs = [UserMessage.from_text("hello")]
        text = serialize_conversation(msgs)
        assert "[User]: hello" in text

    def test_assistant_message(self):
        msgs = [AssistantMessage.from_text("world")]
        text = serialize_conversation(msgs)
        assert "[Assistant]: world" in text

    def test_assistant_thinking(self):
        msg = AssistantMessage(contents=[ThinkingContent(content="my thought")])
        text = serialize_conversation([msg])
        assert "[Assistant thinking]: my thought" in text

    def test_assistant_tool_call(self):
        msg = AssistantMessage(contents=[
            ToolCallContent(id="1", name="read_file", args={"path": "/tmp/f"})
        ])
        text = serialize_conversation([msg])
        assert "[Assistant tool calls]: read_file" in text

    def test_tool_result(self):
        result = ToolResultContent(id="1", content="result text")
        msg = ToolMessage.from_result(result)
        text = serialize_conversation([msg])
        assert "[Tool result]: result text" in text

    def test_tool_result_truncated(self):
        long_content = "x" * (TOOL_RESULT_MAX_CHARS + 500)
        result = ToolResultContent(id="1", content=long_content)
        msg = ToolMessage.from_result(result)
        text = serialize_conversation([msg])
        assert "truncated" in text

    def test_terminal_execution_message(self):
        msg = TerminalExecutionMessage(command="ls -la", output="file.txt")
        text = serialize_conversation([msg])
        assert "[Terminal]: Ran `ls -la`" in text
        assert "file.txt" in text

    def test_compaction_summary(self):
        msg = CompactionSummaryMessage(summary="prior history summary")
        text = serialize_conversation([msg])
        assert "[Context Summary]:" in text
        assert "prior history summary" in text

    def test_branch_summary(self):
        msg = BranchSummaryMessage(summary="branch abandoned", from_id="abc")
        text = serialize_conversation([msg])
        assert "[Branch Summary]:" in text

    def test_messages_joined_with_double_newline(self):
        msgs = [UserMessage.from_text("q"), AssistantMessage.from_text("a")]
        text = serialize_conversation(msgs)
        assert "\n\n" in text

    def test_empty_messages(self):
        assert serialize_conversation([]) == ""

    def test_custom_message(self):
        msg = CustomMessage(custom_type="info", contents=[TextContent(content="custom text")])
        text = serialize_conversation([msg])
        assert "[info]: custom text" in text
