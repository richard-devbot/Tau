"""Tests for tau/session/branch_summarization.py — pure helper functions."""
from __future__ import annotations

from tau.message.types import AssistantMessage, ToolCallContent
from tau.session.branch_summarization import (
    FileOperations,
    _compute_file_lists,
    _format_file_operations,
    prepare_branch_entries,
)
from tau.session.types import MessageEntry


class TestComputeFileLists:
    def test_empty_ops(self):
        ops = FileOperations()
        read_only, modified = _compute_file_lists(ops)
        assert read_only == []
        assert modified == []

    def test_read_only_files(self):
        ops = FileOperations(read={"/a.py", "/b.py"})
        read_only, modified = _compute_file_lists(ops)
        assert sorted(read_only) == ["/a.py", "/b.py"]
        assert modified == []

    def test_written_files_are_modified(self):
        ops = FileOperations(written={"/out.py"})
        read_only, modified = _compute_file_lists(ops)
        assert "/out.py" in modified
        assert "/out.py" not in read_only

    def test_edited_files_are_modified(self):
        ops = FileOperations(edited={"/edit.py"})
        read_only, modified = _compute_file_lists(ops)
        assert "/edit.py" in modified

    def test_read_and_then_edited_is_not_read_only(self):
        ops = FileOperations(read={"/rw.py"}, edited={"/rw.py"})
        read_only, modified = _compute_file_lists(ops)
        assert "/rw.py" not in read_only
        assert "/rw.py" in modified

    def test_both_edited_and_written(self):
        ops = FileOperations(edited={"/a.py"}, written={"/b.py"})
        read_only, modified = _compute_file_lists(ops)
        assert sorted(modified) == ["/a.py", "/b.py"]

    def test_output_is_sorted(self):
        ops = FileOperations(read={"/z.py", "/a.py", "/m.py"})
        read_only, _ = _compute_file_lists(ops)
        assert read_only == sorted(read_only)


class TestFormatFileOperations:
    def test_empty_lists_returns_empty(self):
        assert _format_file_operations([], []) == ""

    def test_read_files_only(self):
        result = _format_file_operations(["/a.py", "/b.py"], [])
        assert "<read-files>" in result
        assert "/a.py" in result
        assert "<modified-files>" not in result

    def test_modified_files_only(self):
        result = _format_file_operations([], ["/out.py"])
        assert "<modified-files>" in result
        assert "/out.py" in result
        assert "<read-files>" not in result

    def test_both_sections(self):
        result = _format_file_operations(["/r.py"], ["/w.py"])
        assert "<read-files>" in result
        assert "<modified-files>" in result
        assert "/r.py" in result
        assert "/w.py" in result

    def test_leading_newlines(self):
        result = _format_file_operations(["/r.py"], [])
        assert result.startswith("\n\n")


class TestPrepareBranchEntries:
    def _make_msg_entry(self, tool_name: str, path: str) -> MessageEntry:
        """Create a MessageEntry wrapping an AssistantMessage with a tool call."""
        tc = ToolCallContent(id="tc1", name=tool_name, args={"path": path})
        msg = AssistantMessage(contents=[tc])
        return MessageEntry(message=msg)

    def test_empty_entries(self):
        prep = prepare_branch_entries([])
        assert prep.messages == []
        assert prep.total_tokens == 0

    def test_collects_file_ops_from_read_tool(self):
        entry = self._make_msg_entry("read", "/data.py")
        prep = prepare_branch_entries([entry])
        assert "/data.py" in prep.file_ops.read

    def test_collects_file_ops_from_write_tool(self):
        entry = self._make_msg_entry("write", "/out.py")
        prep = prepare_branch_entries([entry])
        assert "/out.py" in prep.file_ops.written

    def test_collects_file_ops_from_edit_tool(self):
        entry = self._make_msg_entry("edit", "/src.py")
        prep = prepare_branch_entries([entry])
        assert "/src.py" in prep.file_ops.edited

    def test_messages_collected(self):
        entry = self._make_msg_entry("read", "/x.py")
        prep = prepare_branch_entries([entry])
        assert len(prep.messages) == 1

    def test_token_budget_limits_messages(self):
        entries = [self._make_msg_entry("read", f"/file{i}.py") for i in range(10)]
        # A tiny token budget — only a few messages should be included
        prep_unlimited = prepare_branch_entries(entries)
        prep_limited = prepare_branch_entries(entries, token_budget=5)
        assert len(prep_limited.messages) <= len(prep_unlimited.messages)

    def test_multiple_entries_total_tokens(self):
        entries = [self._make_msg_entry("read", f"/f{i}.py") for i in range(3)]
        prep = prepare_branch_entries(entries)
        assert prep.total_tokens > 0
