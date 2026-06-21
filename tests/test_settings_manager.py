"""Tests for tau/settings/manager.py — in-memory settings manager."""
from __future__ import annotations

from tau.engine.types import FollowupMode, SteeringMode
from tau.inference.types import ThinkingLevel, Transport
from tau.settings.manager import SettingsManager


def _manager(data: dict | None = None) -> SettingsManager:
    return SettingsManager.in_memory(data or {})


class TestInMemoryFactory:
    def test_creates_without_error(self):
        assert _manager() is not None

    def test_is_project_trusted_default(self):
        assert _manager().is_project_trusted() is True

    def test_drain_errors_empty(self):
        assert _manager().drain_errors() == []

    def test_drain_errors_cleared(self):
        mgr = _manager()
        mgr.drain_errors()
        assert mgr.drain_errors() == []


class TestSeedData:
    def test_seeded_model(self):
        mgr = _manager({"model": "claude-sonnet"})
        assert mgr.get_model() == "claude-sonnet"

    def test_seeded_theme(self):
        mgr = _manager({"theme": "monokai"})
        assert mgr.get_theme() == "monokai"

    def test_seeded_provider(self):
        mgr = _manager({"provider": "anthropic"})
        assert mgr.get_provider() == "anthropic"

    def test_seeded_thinking_level(self):
        mgr = _manager({"thinking_level": "high"})
        assert mgr.get_thinking_level() == ThinkingLevel.High

    def test_seeded_transport(self):
        mgr = _manager({"transport": "http"})
        assert mgr.get_transport() == Transport.HTTP

    def test_seeded_steering_mode(self):
        mgr = _manager({"steering_mode": "all"})
        assert mgr.get_steering_mode() == SteeringMode.All

    def test_seeded_follow_up_mode(self):
        mgr = _manager({"follow_up_mode": "all"})
        assert mgr.get_follow_up_mode() == FollowupMode.All

    def test_seeded_quiet_startup(self):
        mgr = _manager({"quiet_startup": True})
        assert mgr.get_quiet_startup() is True

    def test_seeded_show_thinking(self):
        mgr = _manager({"show_thinking": False})
        assert mgr.get_show_thinking() is False

    def test_seeded_show_tool_calls(self):
        mgr = _manager({"show_tool_calls": False})
        assert mgr.get_show_tool_calls() is False

    def test_seeded_enabled_models(self):
        mgr = _manager({"enabled_models": ["gpt-4o", "claude-*"]})
        assert mgr.get_enabled_models() == ["gpt-4o", "claude-*"]


class TestApplyOverrides:
    """apply_overrides() mutates the merged settings without triggering async I/O."""

    def test_override_theme(self):
        mgr = _manager({"theme": "light"})
        mgr.apply_overrides({"theme": "dark"})
        assert mgr.get_theme() == "dark"

    def test_override_model(self):
        mgr = _manager()
        mgr.apply_overrides({"model": "gpt-4o"})
        assert mgr.get_model() == "gpt-4o"

    def test_override_provider(self):
        mgr = _manager()
        mgr.apply_overrides({"provider": "openai"})
        assert mgr.get_provider() == "openai"

    def test_override_thinking_level(self):
        mgr = _manager()
        mgr.apply_overrides({"thinking_level": "max"})
        assert mgr.get_thinking_level() == ThinkingLevel.Max

    def test_multiple_overrides(self):
        mgr = _manager()
        mgr.apply_overrides({"theme": "dark", "model": "claude-sonnet"})
        assert mgr.get_theme() == "dark"
        assert mgr.get_model() == "claude-sonnet"

    def test_override_does_not_affect_global_settings(self):
        mgr = _manager({"theme": "light"})
        mgr.apply_overrides({"theme": "dark"})
        # Global settings object itself should be unchanged
        assert mgr.get_global_settings().theme == "light"


class TestGlobalAndProjectSettings:
    def test_get_global_settings_returns_settings(self):
        mgr = _manager({"theme": "dark"})
        assert mgr.get_global_settings() is not None

    def test_get_project_settings_returns_settings(self):
        mgr = _manager()
        assert mgr.get_project_settings() is not None

    def test_global_settings_deep_copy(self):
        mgr = _manager({"theme": "dark"})
        g1 = mgr.get_global_settings()
        g2 = mgr.get_global_settings()
        assert g1 is not g2


class TestDefaultValues:
    def test_retry_max_retries_has_default(self):
        mgr = _manager()
        assert isinstance(mgr.get_retry_max_retries(), int)

    def test_compaction_reserve_tokens_has_default(self):
        mgr = _manager()
        assert mgr.get_compaction_reserve_tokens() > 0

    def test_compaction_keep_recent_tokens_has_default(self):
        mgr = _manager()
        assert mgr.get_compaction_keep_recent_tokens() > 0

    def test_branch_summary_reserve_tokens_has_default(self):
        mgr = _manager()
        assert mgr.get_branch_summary_reserve_tokens() > 0

    def test_thinking_budget_high_has_default(self):
        mgr = _manager()
        assert mgr.get_thinking_budget("high") > 0

    def test_http_idle_timeout_ms_has_default(self):
        mgr = _manager()
        assert mgr.get_http_idle_timeout_ms() > 0
