"""Hooks system: event types and service for agent lifecycle events."""

from tau.hooks.service import Hooks
from tau.hooks.types import HookEvent

from tau.hooks.session import (
    SessionStartReason,
    SessionShutdownReason,
    SessionBeforeSwitchReason,
    SessionStartEvent,
    SessionBeforeSwitchEvent,
    SessionBeforeForkEvent,
    SessionShutdownEvent,
    TreePreparation,
    SessionBeforeTreeEvent,
    SessionTreeEvent,
    SessionBeforeSwitchResult,
    SessionBeforeForkResult,
    SessionBeforeTreeResult,
)

from tau.hooks.engine import (
    AgentEndReason,
    ContextEvent,
    BeforeAgentStartEvent,
    AgentStartEvent,
    AgentEndEvent,
    AgentErrorEvent,
    TurnStartEvent,
    TurnEndEvent,
    MessageStartEvent,
    MessageUpdateEvent,
    MessageEndEvent,
    ToolExecutionFailureEvent,
    ToolExecutionStartEvent,
    ToolExecutionUpdateEvent,
    ToolExecutionEndEvent,
    ToolCallEvent,
    ToolResultEvent,
    SavePointEvent,
    SettledEvent,
    BeforeCompactionResult,
    BeforeCompactionEvent,
    CompactionStartEvent,
    CompactionEndEvent,
    ContextEventResult,
    ToolCallEventResult,
    ToolResultEventResult,
    MessageEndEventResult,
    BeforeAgentStartEventResult,
)

from tau.hooks.inference import (
    BeforeProviderRequestEvent,
    AfterProviderResponseEvent,
)

from tau.hooks.tui import (
    TuiReadyEvent,
    TuiStartEvent,
    TuiExitEvent,
    ModelSelectEvent,
    ThinkingLevelSelectEvent,
    QueueUpdateEvent,
)

from tau.hooks.runtime import (
    InputEvent,
    UserTerminalEvent,
    TerminalExecutionEvent,
    TerminalOutputEvent,
    ResourcesDiscoverEvent,
    ProjectTrustEvent,
    RuntimeStartEvent,
    RuntimeReadyEvent,
    RuntimeStopEvent,
    InputEventResult,
    UserTerminalResult,
    ResourcesDiscoverResult,
    ProjectTrustResult,
)

__all__ = [
    'Hooks',
    'HookEvent',
    # Session
    'SessionStartReason', 'SessionShutdownReason', 'SessionBeforeSwitchReason',
    'SessionStartEvent', 'SessionBeforeSwitchEvent', 'SessionBeforeForkEvent',
    'SessionShutdownEvent', 'TreePreparation', 'SessionBeforeTreeEvent', 'SessionTreeEvent',
    'SessionBeforeSwitchResult', 'SessionBeforeForkResult', 'SessionBeforeTreeResult',
    # Engine
    'AgentEndReason',
    'ContextEvent', 'BeforeAgentStartEvent', 'AgentStartEvent', 'AgentEndEvent', 'AgentErrorEvent',
    'TurnStartEvent', 'TurnEndEvent',
    'MessageStartEvent', 'MessageUpdateEvent', 'MessageEndEvent',
    'ToolExecutionFailureEvent', 'ToolExecutionStartEvent', 'ToolExecutionUpdateEvent',
    'ToolExecutionEndEvent', 'ToolCallEvent', 'ToolResultEvent',
    'SavePointEvent', 'SettledEvent',
    'BeforeCompactionResult', 'BeforeCompactionEvent', 'CompactionStartEvent', 'CompactionEndEvent',
    'ContextEventResult', 'ToolCallEventResult', 'ToolResultEventResult',
    'MessageEndEventResult', 'BeforeAgentStartEventResult',
    # Inference
    'BeforeProviderRequestEvent', 'AfterProviderResponseEvent',
    # TUI
    'TuiReadyEvent', 'TuiStartEvent', 'TuiExitEvent',
    'ModelSelectEvent', 'ThinkingLevelSelectEvent', 'QueueUpdateEvent',
    # Runtime
    'InputEvent', 'UserTerminalEvent', 'TerminalExecutionEvent', 'TerminalOutputEvent',
    'ResourcesDiscoverEvent', 'ProjectTrustEvent',
    'RuntimeStartEvent', 'RuntimeReadyEvent', 'RuntimeStopEvent',
    'InputEventResult', 'UserTerminalResult', 'ResourcesDiscoverResult', 'ProjectTrustResult',
]
