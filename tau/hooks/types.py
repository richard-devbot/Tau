"""HookEvent union — aggregates all event types from their domain modules."""
from __future__ import annotations

from tau.hooks.session import (
    SessionStartEvent, SessionBeforeSwitchEvent, SessionBeforeForkEvent,
    SessionShutdownEvent, SessionBeforeTreeEvent, SessionTreeEvent,
)
from tau.hooks.engine import (
    ContextEvent, BeforeAgentStartEvent, AgentStartEvent, AgentEndEvent, AgentErrorEvent,
    TurnStartEvent, TurnEndEvent,
    MessageStartEvent, MessageUpdateEvent, MessageEndEvent, MessageRollbackEvent,
    ToolExecutionFailureEvent, ToolExecutionStartEvent, ToolExecutionUpdateEvent,
    ToolExecutionEndEvent, ToolCallEvent, ToolResultEvent,
    SavePointEvent, SettledEvent, BeforeCompactionEvent, CompactionStartEvent, CompactionEndEvent,
)
from tau.hooks.inference import BeforeProviderRequestEvent, AfterProviderResponseEvent
from tau.hooks.tui import TuiReadyEvent, TuiStartEvent, TuiExitEvent, ModelSelectEvent, ThinkingLevelSelectEvent, QueueUpdateEvent
from tau.hooks.runtime import (
    InputEvent, InputEventResult, UserTerminalEvent, UserTerminalResult,
    TerminalExecutionEvent, TerminalOutputEvent,
    ResourcesDiscoverEvent, ResourcesDiscoverResult,
    ProjectTrustEvent, ProjectTrustResult,
    RuntimeStartEvent, RuntimeReadyEvent, RuntimeStopEvent,
)

HookEvent = (
    SessionStartEvent
    | SessionBeforeSwitchEvent
    | SessionBeforeForkEvent
    | SessionShutdownEvent
    | SessionBeforeTreeEvent
    | SessionTreeEvent
    | ContextEvent
    | BeforeAgentStartEvent
    | AgentStartEvent
    | AgentEndEvent
    | AgentErrorEvent
    | TurnStartEvent
    | TurnEndEvent
    | MessageStartEvent
    | MessageUpdateEvent
    | MessageEndEvent
    | MessageRollbackEvent
    | ToolExecutionFailureEvent
    | ToolExecutionStartEvent
    | ToolExecutionUpdateEvent
    | ToolExecutionEndEvent
    | ToolCallEvent
    | ToolResultEvent
    | ModelSelectEvent
    | ThinkingLevelSelectEvent
    | InputEvent
    | UserTerminalEvent
    | TerminalExecutionEvent
    | TerminalOutputEvent
    | SavePointEvent
    | SettledEvent
    | BeforeCompactionEvent
    | CompactionStartEvent
    | CompactionEndEvent
    | BeforeProviderRequestEvent
    | AfterProviderResponseEvent
    | QueueUpdateEvent
    | ResourcesDiscoverEvent
    | ProjectTrustEvent
    | RuntimeStartEvent
    | RuntimeReadyEvent
    | RuntimeStopEvent
    | TuiReadyEvent
    | TuiStartEvent
    | TuiExitEvent
)
