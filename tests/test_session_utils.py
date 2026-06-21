"""Tests for tau/session/utils.py — session ID generation, path encoding, and file parsing."""
from __future__ import annotations

import json
import time
from pathlib import Path

from tau.message.types import (
    AssistantMessage,
    CompactionSummaryMessage,
    ImageContent,
    ToolCallContent,
    UserMessage,
)
from tau.session.utils import (
    find_most_recent_session,
    generate_id,
    get_default_session_dir,
    is_message_with_contents,
    is_valid_session_file,
)


class TestGenerateId:
    def test_returns_string(self):
        result = generate_id(set())
        assert isinstance(result, str)

    def test_avoids_existing_ids(self):
        existing = {"aaaabbbb"}
        # generate_id should not return any id already in the set
        results = {generate_id(existing) for _ in range(50)}
        assert "aaaabbbb" not in results

    def test_length_is_8(self):
        result = generate_id(set())
        assert len(result) == 8

    def test_uniqueness_across_calls(self):
        ids = {generate_id(set()) for _ in range(100)}
        # With uuid4, collisions are astronomically unlikely
        assert len(ids) > 90


class TestGetDefaultSessionDir:
    def test_creates_directory(self, tmp_path):
        sessions_dir = tmp_path / "sessions"
        cwd = "/home/user/project"
        result = get_default_session_dir(cwd, sessions_dir=sessions_dir)
        assert result.exists()
        assert result.is_dir()

    def test_encodes_path_safely(self, tmp_path):
        cwd = "/home/user/my-project"
        result = get_default_session_dir(cwd, sessions_dir=tmp_path)
        # Directory name should not contain raw slashes
        assert "/" not in result.name

    def test_idempotent(self, tmp_path):
        cwd = "/home/user/project"
        r1 = get_default_session_dir(cwd, sessions_dir=tmp_path)
        r2 = get_default_session_dir(cwd, sessions_dir=tmp_path)
        assert r1 == r2

    def test_different_cwds_produce_different_dirs(self, tmp_path):
        r1 = get_default_session_dir("/home/user/a", sessions_dir=tmp_path)
        r2 = get_default_session_dir("/home/user/b", sessions_dir=tmp_path)
        assert r1 != r2


class TestIsValidSessionFile:
    def _write_session(self, path: Path, header: dict) -> Path:
        path.write_text(json.dumps(header) + "\n", encoding="utf-8")
        return path

    def test_valid_file(self, tmp_path):
        f = tmp_path / "session.jsonl"
        # SessionType.SESSION_HEADER == "session"
        header = {
            "type": "session",
            "id": "abc123",
            "cwd": "/tmp",
            "timestamp": time.time(),
            "parent_session": None,
        }
        self._write_session(f, header)
        assert is_valid_session_file(f) is True

    def test_empty_file_is_invalid(self, tmp_path):
        f = tmp_path / "empty.jsonl"
        f.write_text("")
        assert is_valid_session_file(f) is False

    def test_nonexistent_file(self, tmp_path):
        assert is_valid_session_file(tmp_path / "nope.jsonl") is False

    def test_invalid_json_header(self, tmp_path):
        f = tmp_path / "bad.jsonl"
        f.write_text("not json\n")
        assert is_valid_session_file(f) is False

    def test_wrong_type_header(self, tmp_path):
        f = tmp_path / "wrong.jsonl"
        f.write_text(json.dumps({"type": "message", "role": "user"}) + "\n")
        assert is_valid_session_file(f) is False


class TestFindMostRecentSession:
    def _make_valid_session(self, path: Path) -> Path:
        header = {
            "type": "session",
            "id": path.stem,
            "cwd": "/tmp",
            "timestamp": time.time(),
            "parent_session": None,
        }
        path.write_text(json.dumps(header) + "\n", encoding="utf-8")
        return path

    def test_returns_none_for_empty_dir(self, tmp_path):
        result = find_most_recent_session(tmp_path)
        assert result is None

    def test_returns_none_for_nonexistent_dir(self, tmp_path):
        result = find_most_recent_session(tmp_path / "nope")
        assert result is None

    def test_returns_most_recent_file(self, tmp_path):
        self._make_valid_session(tmp_path / "old.jsonl")
        time.sleep(0.01)
        newer = self._make_valid_session(tmp_path / "new.jsonl")
        # Touch newer to ensure mtime difference
        newer.touch()
        result = find_most_recent_session(tmp_path)
        assert result == newer

    def test_ignores_invalid_files(self, tmp_path):
        bad = tmp_path / "bad.jsonl"
        bad.write_text("invalid\n")
        result = find_most_recent_session(tmp_path)
        assert result is None


class TestIsMessageWithContents:
    def test_user_with_text_content(self):
        msg = UserMessage.from_text("hello")
        assert is_message_with_contents(msg) is True

    def test_user_with_image_content(self):
        # Minimal PNG bytes
        png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 20
        msg = UserMessage(contents=[ImageContent(images=[png])])
        assert is_message_with_contents(msg) is True

    def test_assistant_with_text_content(self):
        msg = AssistantMessage.from_text("hi")
        assert is_message_with_contents(msg) is True

    def test_assistant_with_only_tool_calls_returns_false(self):
        msg = AssistantMessage(contents=[ToolCallContent(id="1", name="fn", args={})])
        assert is_message_with_contents(msg) is False

    def test_compaction_summary_message_returns_false(self):
        msg = CompactionSummaryMessage(summary="summary here")
        assert is_message_with_contents(msg) is False

    def test_empty_user_message_returns_false(self):
        msg = UserMessage()
        assert is_message_with_contents(msg) is False
