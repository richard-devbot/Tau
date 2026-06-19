from __future__ import annotations
from asyncio import Queue
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Awaitable, Callable, Optional
import asyncio

if TYPE_CHECKING:
    from tau.inference.api.text.service import TextLLM as LLM
    from tau.inference.types import ThinkingLevel
    from tau.tool.types import Tool

from tau.message.types import LLMMessage, AssistantMessage, ToolCallContent, ToolResultContent
from tau.tool.types import ToolInvocation, ToolResult, ToolExecutionMode
from tau.hooks.engine import (
    AgentStartEvent, AgentEndEvent, AgentErrorEvent,
    TurnStartEvent, TurnEndEvent,
    MessageStartEvent, MessageUpdateEvent, MessageEndEvent, MessageRollbackEvent,
    ToolExecutionStartEvent, ToolExecutionUpdateEvent, ToolExecutionEndEvent,
    ToolExecutionFailureEvent,
)


def _make_set_event() -> asyncio.Event:
    e = asyncio.Event()
    e.set()
    return e

AbortSignal = asyncio.Event
EmitEvent = Callable[['AgentEvent'], Awaitable[None]]

class SteeringMode(str, Enum):
    """Mode for delivering steering messages: one at a time or all at once."""
    OneAtATime = "one_at_a_time"
    All = "all"


class FollowupMode(str, Enum):
    """Mode for delivering follow-up messages: one at a time or all at once."""
    OneAtATime = "one_at_a_time"
    All = "all"


class AgentEventType(str, Enum):
    """Event type identifiers for agent and engine lifecycle events."""
    AgentStart = "agent_start"
    AgentEnd = "agent_end"
    TurnStart = "turn_start"
    TurnEnd = "turn_end"
    MessageStart = "message_start"
    MessageUpdate = "message_update"
    MessageEnd = "message_end"
    ToolExecutionStart = "tool_execution_start"
    ToolExecutionUpdate = "tool_execution_update"
    ToolExecutionEnd = "tool_execution_end"
    AgentError = "agent_error"

AgentEvent = (
    AgentStartEvent
    | AgentEndEvent
    | TurnStartEvent
    | TurnEndEvent
    | MessageStartEvent
    | MessageUpdateEvent
    | MessageEndEvent
    | MessageRollbackEvent
    | ToolExecutionStartEvent
    | ToolExecutionUpdateEvent
    | ToolExecutionEndEvent
    | ToolExecutionFailureEvent
    | AgentErrorEvent
)

AfterToolCallCallback = Callable[[ToolInvocation, ToolResult, Optional[AbortSignal]], Awaitable[Optional[ToolResult]]]
BeforeToolCallCallback = Callable[[ToolInvocation, Optional[AbortSignal]], Awaitable[Optional[ToolInvocation | ToolResultContent]]]
GetFollowUpMessagesCallback = Callable[[], list[LLMMessage]]
GetSteeringMessagesCallback = Callable[[], list[LLMMessage]]
OnEventCallback = Callable[['AgentEvent'], Awaitable[None]]
ShouldSkipToolCallsCallback = Callable[[ToolCallContent], ToolResultContent]
ShouldStopAfterTurnCallback = Callable[[AssistantMessage, list[ToolResultContent]], bool]
TransformContextCallback = Callable[[list[LLMMessage], Optional[AbortSignal]], list[LLMMessage]]


@dataclass
class EngineState:
    """Mutable runtime state shared between the Engine loop and external observers."""
    system_prompt: Optional[str] = None
    messages: list[LLMMessage] = field(default_factory=list)
    pending_tool_calls: set[str] = field(default_factory=set)
    is_streaming: bool = False
    idle_event: asyncio.Event = field(default_factory=lambda: _make_set_event())
    llm: Optional[LLM] = None
    streaming_message: Optional[AssistantMessage] = None
    thinking_level: Optional[ThinkingLevel] = None
    error_message: Optional[str] = None
    tools: list[Tool] = field(default_factory=list)
    follow_up_queue: Optional[FollowupQueue] = None
    steering_queue: Optional[SteeringQueue] = None


@dataclass
class EngineOptions:
    """Engine behaviour knobs: hooks, execution strategy, and message injection callbacks."""
    after_tool_call: Optional[AfterToolCallCallback] = None
    before_tool_call: Optional[BeforeToolCallCallback] = None
    on_event: Optional[OnEventCallback] = None
    execution_mode: Optional[ToolExecutionMode] = None
    steering_mode: SteeringMode = SteeringMode.OneAtATime
    followup_mode: FollowupMode = FollowupMode.OneAtATime
    get_follow_up_messages: Optional[GetFollowUpMessagesCallback] = None
    get_steering_messages: Optional[GetSteeringMessagesCallback] = None
    should_stop_after_turn: Optional[ShouldStopAfterTurnCallback] = None
    should_skip_tool_calls: Optional[ShouldSkipToolCallsCallback] = None
    transform_context: Optional[TransformContextCallback] = None


@dataclass
class _MessageQueue:
    """Async FIFO queue for steering/follow-up messages with configurable drain behaviour."""
    mode: FollowupMode | SteeringMode
    queue: Queue[LLMMessage] = field(default_factory=Queue)

    def clear(self) -> None:
        """Clear all messages from the queue."""
        # Replace rather than drain to avoid blocking on an empty get() mid-loop.
        self.queue = Queue()

    async def enqueue(self, message: LLMMessage) -> None:
        """Add a message to the queue."""
        await self.queue.put(message)

    def is_empty(self) -> bool:
        """Check if the queue is empty."""
        return self.queue.empty()

    def snapshot(self) -> list[LLMMessage]:
        """Return a non-destructive copy of queued messages for inspection (e.g. QueueUpdateEvent)."""
        return list(self.queue._queue)  # type: ignore[attr-defined]

    async def dequeue(self) -> list[LLMMessage]:
        """Drain one (OneAtATime) or all (All) messages from the queue."""
        messages: list[LLMMessage] = []
        if self.mode.value == "one_at_a_time":
            if not self.is_empty():
                messages.append(await self.queue.get())
        else:
            while not self.is_empty():
                messages.append(await self.queue.get())
        return messages


@dataclass
class FollowupQueue(_MessageQueue):
    """Queue for follow-up messages from external sources."""
    mode: FollowupMode  # type: ignore[assignment]


@dataclass
class SteeringQueue(_MessageQueue):
    """Queue for steering messages from external sources."""
    mode: SteeringMode  # type: ignore[assignment]


