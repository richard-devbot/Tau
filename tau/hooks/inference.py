from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass
class BeforeProviderRequestEvent:
    """Fired just before the LLM API call is made."""

    type: Literal["before_provider_request"] = field(default="before_provider_request", init=False)
    model: Any = None
    messages: list[Any] = field(default_factory=list)
    options: Any = None


@dataclass
class AfterProviderResponseEvent:
    """Fired immediately after the LLM streaming response is fully collected."""

    type: Literal["after_provider_response"] = field(default="after_provider_response", init=False)
    model: Any = None
    response: Any = None
