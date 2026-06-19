from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Literal, Any
from tau.engine.types import SteeringMode, FollowupMode
from tau.inference.types import Transport, ThinkingLevel


class SCOPE(str, Enum):
    GLOBAL = "global"
    PROJECT = "project"


@dataclass
class LockResult:
    result: Any
    next: str | None = None


@dataclass
class SettingsError:
    scope: SCOPE
    error: Exception


@dataclass
class ProviderRetrySettings:
    timeout_ms: Optional[int] = None
    max_retries: Optional[int] = None
    max_retry_delay_ms: Optional[int] = None


@dataclass
class RetrySettings:
    enabled: Optional[bool] = None
    max_retries: Optional[int] = None
    base_delay_ms: Optional[int] = None
    provider: Optional[ProviderRetrySettings] = None


@dataclass
class ThinkingBudgetsSettings:
    minimal: Optional[int] = None
    low: Optional[int] = None
    medium: Optional[int] = None
    high: Optional[int] = None
    xhigh: Optional[int] = None
    max: Optional[int] = None


@dataclass
class ImageSettings:
    auto_resize: Optional[bool] = None    # resize images to 2000×2000 max before sending to LLM (default: True)
    block_images: Optional[bool] = None   # prevent all images from being sent to the LLM (default: False)


@dataclass
class CompactionSettings:
    enabled: Optional[bool] = None              # enable auto-compaction (default: True)
    reserve_tokens: Optional[int] = None        # tokens reserved for LLM response (default: 16384)
    keep_recent_tokens: Optional[int] = None    # recent tokens to keep verbatim (default: 20000)


@dataclass
class BranchSummarySettings:
    enabled: Optional[bool] = None        # enable branch summarization (default: True)
    skip_prompt: Optional[bool] = None    # always skip the "Summarize branch?" prompt (default: False)
    reserve_tokens: Optional[int] = None  # tokens to reserve when summarizing (default: 16384)


@dataclass
class ExtensionEntry:
    """Per-extension config entry stored in the ``extensions.list`` settings block."""
    path: str
    name: Optional[str] = None
    enabled: bool = True
    source: Optional[str] = None
    author: Optional[str] = None
    settings: Optional[dict] = field(default=None)


@dataclass
class ExtensionsSettings:
    """Global extension toggle plus per-extension configuration list."""
    enabled: Optional[bool] = None          # global on/off for all extensions
    list: Optional[list[ExtensionEntry]] = None


@dataclass
class PackageEntry:
    """A package installed via pip/uv/poetry into the tau-managed venv."""
    source: str                             # "pypi:name@1.0", "git+https://...", "/local/path"
    name: str                               # package name (normalised)
    version: Optional[str] = None           # installed version, if known
    installed_path: Optional[str] = None    # path to package dir inside the venv
    enabled: bool = True


@dataclass
class PackagesSettings:
    """Installed package list stored in settings."""
    list: Optional[list[PackageEntry]] = None


@dataclass
class TerminalSettings:
    shell_path: Optional[str] = None             # custom shell binary (default: system shell)
    shell_command_prefix: Optional[str] = None   # lines prepended inside the shell before each command


@dataclass
class HTTPProxySettings:
    url: Optional[str] = None                           # Proxy URL for both HTTP and HTTPS (overrides env vars)
    no_proxy: Optional[str] = None                      # Comma-separated hosts to exclude from proxying
    headers: Optional[dict[str, str]] = None            # Custom headers for proxy (e.g., authentication)


@dataclass
class Settings:
    # Model / provider
    provider: Optional[str] = None
    model: Optional[str] = None
    thinking_level: Optional[ThinkingLevel] = None
    transport: Optional[Transport] = None
    enabled_models: Optional[list[str]] = None

    # UI
    theme: Optional[str] = None
    show_thinking: Optional[bool] = None
    show_tool_calls: Optional[bool] = None
    show_images: Optional[bool] = None
    picker_max_visible: Optional[int] = None

    # Queue behaviour
    steering_mode: Optional[SteeringMode] = None
    follow_up_mode: Optional[FollowupMode] = None

    # Nested sub-settings
    retry: Optional[RetrySettings] = None
    thinking_budgets: Optional[ThinkingBudgetsSettings] = None
    image: Optional[ImageSettings] = None
    compaction: Optional[CompactionSettings] = None
    branch_summary: Optional[BranchSummarySettings] = None

    # Execution
    terminal: Optional[TerminalSettings] = None

    # Network
    http_idle_timeout_ms: Optional[int] = None  # idle timeout for LLM HTTP streams (default: 60000)
    websocket_connect_timeout_ms: Optional[int] = None  # WebSocket connect/open handshake timeout
    http_proxy: Optional[HTTPProxySettings] = None  # HTTP proxy configuration (overrides env vars)

    # Project trust (global only)
    project_trust: Optional[Literal["ask", "always", "never"]] = None  # default: "ask" — controls loading of project files (.tau/ config, extensions), project context files (AGENTS.md/CLAUDE.md), and project skills

    # Session
    session_dir: Optional[str] = None

    # Startup
    quiet_startup: Optional[bool] = None  # suppress startup notices (default: False)

    # UI behaviour
    double_escape_action: Optional[Literal["fork", "tree", "none"]] = None  # action on double-Escape with empty editor (default: "fork")
    tree_filter_mode: Optional[Literal["default", "no-tools", "user-only", "labeled-only", "all"]] = None  # default /tree filter mode
    autocomplete_max_visible: Optional[int] = None  # max items in autocomplete dropdown (default: 5)
    show_hardware_cursor: Optional[bool] = None  # show terminal cursor while positioning (IME support, default: False)
    editor_padding_x: Optional[int] = None  # horizontal padding for the input editor (default: 0)

    # Extensions
    extensions: Optional[ExtensionsSettings] = None

    # Packages
    packages: Optional[PackagesSettings] = None
