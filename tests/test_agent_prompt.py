"""Tests for tau/agent/prompt/builder.py — prompt construction."""
from __future__ import annotations

import platform
from pathlib import Path

from tau.agent.prompt.builder import (
    load_project_context_file,
    _detect_os,
    _detect_shell,
    PromptBuilder,
    _DEFAULT_IDENTITY,
)
from tau.agent.prompt.types import PromptOptions
from tau.builtins.tools.read import ReadTool
from tau.builtins.tools.write import WriteTool


def _opts(cwd: Path, **kwargs) -> PromptOptions:
    return PromptOptions(cwd=cwd, project_trusted=True, **kwargs)


# ---------------------------------------------------------------------------
# load_project_context_file
# ---------------------------------------------------------------------------

class TestLoadProjectContextFile:
    def test_returns_none_when_no_file(self, tmp_path):
        assert load_project_context_file(tmp_path) is None

    def test_loads_agents_md(self, tmp_path):
        (tmp_path / "AGENTS.md").write_text("# Agent instructions\nDo stuff.")
        result = load_project_context_file(tmp_path)
        assert result is not None
        content, path = result
        assert "Agent instructions" in content
        assert path.name == "AGENTS.md"

    def test_loads_claude_md_when_no_agents_md(self, tmp_path):
        (tmp_path / "CLAUDE.md").write_text("# Claude instructions")
        content, path = load_project_context_file(tmp_path)
        assert path.name == "CLAUDE.md"

    def test_agents_md_preferred_over_claude_md(self, tmp_path):
        (tmp_path / "AGENTS.md").write_text("agents content")
        (tmp_path / "CLAUDE.md").write_text("claude content")
        content, path = load_project_context_file(tmp_path)
        assert path.name == "AGENTS.md"

    def test_empty_file_returns_none(self, tmp_path):
        (tmp_path / "AGENTS.md").write_text("   ")
        assert load_project_context_file(tmp_path) is None

    def test_case_insensitive_detection(self, tmp_path):
        (tmp_path / "agents.md").write_text("content")
        # Should not match AGENTS.MD/AGENTS.md on case-sensitive filesystems
        # We test that supported variants work
        result = load_project_context_file(tmp_path)
        # lowercase may or may not match depending on OS — just verify no exception


# ---------------------------------------------------------------------------
# _detect_os
# ---------------------------------------------------------------------------

class TestDetectOs:
    def test_returns_nonempty_string(self):
        result = _detect_os()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_macos_contains_macos(self):
        if platform.system() == "Darwin":
            assert "macOS" in _detect_os()

    def test_linux_contains_linux(self):
        if platform.system() == "Linux":
            assert "Linux" in _detect_os()


# ---------------------------------------------------------------------------
# _detect_shell
# ---------------------------------------------------------------------------

class TestDetectShell:
    def test_returns_nonempty_string(self):
        assert len(_detect_shell()) > 0

    def test_returns_shell_from_env(self, monkeypatch):
        monkeypatch.setenv("SHELL", "/bin/zsh")
        assert _detect_shell() == "zsh"

    def test_returns_basename_only(self, monkeypatch):
        monkeypatch.setenv("SHELL", "/usr/local/bin/bash")
        assert _detect_shell() == "bash"

    def test_falls_back_when_shell_unset(self, monkeypatch):
        monkeypatch.delenv("SHELL", raising=False)
        result = _detect_shell()
        assert isinstance(result, str)
        assert len(result) > 0


# ---------------------------------------------------------------------------
# PromptBuilder
# ---------------------------------------------------------------------------

class TestPromptBuilderIdentity:
    def test_default_identity_used_when_no_custom(self, tmp_path):
        builder = PromptBuilder(_opts(tmp_path))
        prompt = builder.build()
        assert _DEFAULT_IDENTITY in prompt

    def test_custom_prompt_overrides_identity(self, tmp_path):
        builder = PromptBuilder(_opts(tmp_path, custom_prompt="Custom system prompt."))
        prompt = builder.build()
        assert "Custom system prompt." in prompt
        assert _DEFAULT_IDENTITY not in prompt

    def test_system_md_overrides_default(self, tmp_path):
        tau_dir = tmp_path / ".tau"
        tau_dir.mkdir()
        (tau_dir / "SYSTEM.md").write_text("My custom identity.")
        builder = PromptBuilder(_opts(tmp_path))
        prompt = builder.build()
        assert "My custom identity." in prompt
        assert _DEFAULT_IDENTITY not in prompt


class TestPromptBuilderFooter:
    def test_footer_contains_cwd(self, tmp_path):
        builder = PromptBuilder(_opts(tmp_path))
        prompt = builder.build()
        assert str(tmp_path).replace("\\", "/") in prompt

    def test_footer_contains_date(self, tmp_path):
        from datetime import date
        builder = PromptBuilder(_opts(tmp_path))
        prompt = builder.build()
        assert date.today().isoformat() in prompt

    def test_footer_contains_os(self, tmp_path):
        builder = PromptBuilder(_opts(tmp_path))
        prompt = builder.build()
        assert "OS:" in prompt

    def test_footer_contains_shell(self, tmp_path):
        builder = PromptBuilder(_opts(tmp_path))
        prompt = builder.build()
        assert "Shell:" in prompt


class TestPromptBuilderToolsSection:
    def test_no_tools_no_section(self, tmp_path):
        builder = PromptBuilder(_opts(tmp_path, tools=[]))
        prompt = builder.build()
        assert "Available Tools" not in prompt

    def test_tools_section_lists_tools(self, tmp_path):
        builder = PromptBuilder(_opts(tmp_path, tools=[ReadTool(), WriteTool()]))
        prompt = builder.build()
        assert "Available Tools" in prompt
        assert "read" in prompt
        assert "write" in prompt

    def test_tool_guidelines_included(self, tmp_path):
        builder = PromptBuilder(_opts(tmp_path, tools=[ReadTool()]))
        prompt = builder.build()
        assert "Tool Guidelines" in prompt


class TestPromptBuilderProjectContext:
    def test_context_included_when_trusted_and_file_exists(self, tmp_path):
        (tmp_path / "AGENTS.md").write_text("Project rules here.")
        builder = PromptBuilder(_opts(tmp_path))
        prompt = builder.build()
        assert "Project rules here." in prompt
        assert "Project Instructions" in prompt

    def test_context_excluded_when_disabled(self, tmp_path):
        (tmp_path / "AGENTS.md").write_text("Project rules here.")
        builder = PromptBuilder(_opts(tmp_path, disable_context_files=True))
        prompt = builder.build()
        assert "Project rules here." not in prompt

    def test_context_excluded_when_not_trusted(self, tmp_path):
        (tmp_path / "AGENTS.md").write_text("Project rules here.")
        opts = PromptOptions(cwd=tmp_path, project_trusted=False)
        builder = PromptBuilder(opts)
        prompt = builder.build()
        assert "Project rules here." not in prompt

    def test_no_context_when_no_file(self, tmp_path):
        builder = PromptBuilder(_opts(tmp_path))
        prompt = builder.build()
        assert "Project Instructions" not in prompt


class TestPromptBuilderAppend:
    def test_append_prompt_included(self, tmp_path):
        builder = PromptBuilder(_opts(tmp_path, append_prompt="Always respond in English."))
        prompt = builder.build()
        assert "Always respond in English." in prompt

    def test_extra_appends_included(self, tmp_path):
        builder = PromptBuilder(_opts(tmp_path, extra_appends=["Extra 1", "Extra 2"]))
        prompt = builder.build()
        assert "Extra 1" in prompt
        assert "Extra 2" in prompt

    def test_append_system_md_loaded(self, tmp_path):
        tau_dir = tmp_path / ".tau"
        tau_dir.mkdir()
        (tau_dir / "APPEND_SYSTEM.md").write_text("Appended instructions.")
        builder = PromptBuilder(_opts(tmp_path))
        prompt = builder.build()
        assert "Appended instructions." in prompt
