from dataclasses import dataclass, field
from typing import Literal, TypeVar

from tau.inference.types import AuthType


@dataclass
class OAuthCredential:
    """OAuth 2.0 credential with access and refresh tokens."""

    type: AuthType = field(default_factory=lambda: AuthType.OAuth, init=False)
    access: str = ""
    refresh: str = ""
    expires: int = 0  # Unix timestamp in milliseconds
    extra: dict[str, str] = field(default_factory=dict)


@dataclass
class APICredential:
    """API key credential."""

    type: AuthType = field(default_factory=lambda: AuthType.ApiKey, init=False)
    key: str = ""


AuthCredential = OAuthCredential | APICredential


@dataclass
class AuthStatus:
    """Authentication status and source information."""

    configured: bool
    source: Literal["stored", "runtime", "env"] | None = None
    label: str | None = None


T = TypeVar("T")


@dataclass
class LockResult[T]:
    """Result of a locked operation with next continuation."""

    result: T
    next: str | None = None
