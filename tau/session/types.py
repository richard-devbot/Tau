from __future__ import annotations
import uuid
from datetime import datetime
from pathlib import Path
from enum import Enum
from dataclasses import dataclass
from typing import Any, Literal, Annotated, TYPE_CHECKING, List

from pydantic import BaseModel, Field, ConfigDict
from tau.inference.types import ThinkingLevel

from tau.message.types import AgentMessage, ImageContent, TextContent

if TYPE_CHECKING:
    pass


def generate_timestamp() -> float:
    return datetime.now().timestamp()


def _generate_id() -> str:
    return str(uuid.uuid4())[:8]


SESSION_VERSION = 3


class SessionType(str, Enum):
    SESSION_HEADER = "session"
    SESSION_MESSAGE = "message"
    THINKING_LEVEL_CHANGE = "thinking_level_change"
    MODEL_CHANGE = "model_change"
    LABEL = "label"
    CUSTOM_INFO = "custom"
    SESSION_INFO = "session_info"
    CUSTOM_MESSAGE = "custom_message"
    LEAF = "leaf"
    COMPACTION = "compaction"
    BRANCH_SUMMARY = "branch_summary"


class BaseSessionEntry(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    id: str = Field(default_factory=_generate_id)
    timestamp: float = Field(default_factory=generate_timestamp)
    parent_id: str | None = None


class SessionHeader(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    type: Literal[SessionType.SESSION_HEADER] = SessionType.SESSION_HEADER
    version: int = SESSION_VERSION
    id: str = Field(default_factory=_generate_id)
    timestamp: float = Field(default_factory=generate_timestamp)
    cwd: Path
    parent_session: Path | None = None


class SessionInfoEntry(BaseSessionEntry):
    type: Literal[SessionType.SESSION_INFO] = SessionType.SESSION_INFO
    name: str | None = None


class MessageAttachment(BaseModel):
    path: str
    mime_type: str | None = None


class MessageMeta(BaseModel):
    attachments: list[MessageAttachment] | None = None


class MessageEntry(BaseSessionEntry):
    type: Literal[SessionType.SESSION_MESSAGE] = SessionType.SESSION_MESSAGE
    message: "AgentMessage"
    meta: MessageMeta | None = None


class ThinkingLevelChangeEntry(BaseSessionEntry):
    type: Literal[SessionType.THINKING_LEVEL_CHANGE] = SessionType.THINKING_LEVEL_CHANGE
    thinking_level: ThinkingLevel


class ModelChangeEntry(BaseSessionEntry):
    type: Literal[SessionType.MODEL_CHANGE] = SessionType.MODEL_CHANGE
    model_id: str
    provider_id: str


class LabelEntry(BaseSessionEntry):
    type: Literal[SessionType.LABEL] = SessionType.LABEL
    label: str | None = None
    target_id: str


class LeafEntry(BaseSessionEntry):
    type: Literal[SessionType.LEAF] = SessionType.LEAF
    target_id: str | None = None


class CustomInfoEntry(BaseSessionEntry):
    type: Literal[SessionType.CUSTOM_INFO] = SessionType.CUSTOM_INFO
    custom_type: str
    data: Any | None = None


class CustomMessageEntry(BaseSessionEntry):
    type: Literal[SessionType.CUSTOM_MESSAGE] = SessionType.CUSTOM_MESSAGE
    custom_type: str
    content: List["TextContent | ImageContent"]
    display: bool = True
    details: Any | None = None


class CompactionEntry(BaseSessionEntry):
    type: Literal[SessionType.COMPACTION] = SessionType.COMPACTION
    summary: str
    first_kept_entry_id: str
    tokens_before: int
    details: dict[str, Any] | None = None


class BranchSummaryEntry(BaseSessionEntry):
    type: Literal[SessionType.BRANCH_SUMMARY] = SessionType.BRANCH_SUMMARY
    from_id: str
    summary: str
    details: dict[str, Any] | None = None
    from_hook: bool = False
    label: str | None = None


SessionEntries = (
    SessionInfoEntry
    | MessageEntry
    | ThinkingLevelChangeEntry
    | ModelChangeEntry
    | LabelEntry
    | LeafEntry
    | CustomInfoEntry
    | CustomMessageEntry
    | CompactionEntry
    | BranchSummaryEntry
)

SessionEntry = Annotated[
    SessionEntries,
    Field(discriminator="type")
]

SessionFileEntry = Annotated[
    SessionHeader | SessionEntries,
    Field(discriminator="type")
]


class SessionTreeNode(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    entry: SessionEntry
    children: list[SessionTreeNode] = Field(default_factory=list)
    label: str | None = None
    label_timestamp: float | None = None


class SessionContext(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    messages: list["AgentMessage"]
    thinking_level: ThinkingLevel
    model_id: str | None = None
    provider_id: str | None = None


class SessionInfo(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    path: Path
    id: str
    cwd: Path
    name: str | None = None
    parent_session: Path | None = None
    created: datetime
    modified: datetime
    message_count: int


@dataclass
class SessionOptions:
    id: str | None = None
    parent_session: str | None = None
