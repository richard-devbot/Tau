"""HookEvent union — aggregates all event types from their domain modules."""

from __future__ import annotations

from tau.hooks.engine import (
    AgentEndEvent,
    AgentErrorEvent,
    AgentStartEvent,
    BeforeAgentStartEvent,
    BeforeCompactionEvent,
    CompactionEndEvent,
    CompactionStartEvent,
    ContextEvent,
    MessageEndEvent,
    MessageRollbackEvent,
    MessageStartEvent,
    MessageUpdateEvent,
    SavePointEvent,
    SettledEvent,
    ToolCallEvent,
    ToolExecutionEndEvent,
    ToolExecutionFailureEvent,
    ToolExecutionStartEvent,
    ToolExecutionUpdateEvent,
    ToolResultEvent,
    TurnEndEvent,
    TurnStartEvent,
)
from tau.hooks.inference import AfterProviderResponseEvent, BeforeProviderRequestEvent
from tau.hooks.runtime import (
    InputEvent,
    ProjectTrustEvent,
    ResourcesDiscoverEvent,
    RuntimeReadyEvent,
    RuntimeStartEvent,
    RuntimeStopEvent,
    TerminalExecutionEvent,
    TerminalOutputEvent,
    UserTerminalEvent,
)
from tau.hooks.session import (
    SessionBeforeForkEvent,
    SessionBeforeSwitchEvent,
    SessionBeforeTreeEvent,
    SessionShutdownEvent,
    SessionStartEvent,
    SessionTreeEvent,
)
from tau.hooks.tui import (
    ModelSelectEvent,
    QueueUpdateEvent,
    ThinkingLevelSelectEvent,
    TuiExitEvent,
    TuiReadyEvent,
    TuiStartEvent,
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
