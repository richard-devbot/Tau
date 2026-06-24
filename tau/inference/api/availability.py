"""Shared helper for listing models whose provider has usable credentials.

Each modality service (``TextLLM``, ``AudioLLM``, ``ImageLLM``, ``VideoLLM``)
exposes ``list_available()`` to power the model picker. They all apply the same
auth rule, so the logic lives here once instead of being copied per family.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any

    from tau.auth.manager import AuthManager
    from tau.inference.model.registry import ModelRegistry
    from tau.inference.model.types import Model
    from tau.inference.provider.registry import _ProviderRegistryBase


def available_models(
    models: ModelRegistry,
    providers: _ProviderRegistryBase[Any],
    auth_manager: AuthManager,
) -> list[Model]:
    """Return models whose provider has usable auth (stored credential or env var).

    A provider qualifies when it needs no credential (``AuthType.None_``, e.g.
    local Ollama), has a matching stored OAuth/API credential, or exposes a
    ``<PROVIDER>_API_KEY`` environment variable. Duplicate ``provider/id`` pairs
    are returned once.
    """
    from tau.auth.types import APICredential, OAuthCredential
    from tau.inference.provider.types import OAuthProvider
    from tau.inference.types import AuthType

    auth_manager.reload()
    result: list[Model] = []
    seen: set[str] = set()
    for candidate in models.list():
        key = f"{candidate.provider}/{candidate.id}"
        if key in seen:
            continue
        provider = providers.get(candidate.provider)
        if provider is None:
            continue
        # ``candidate.provider`` is the canonical provider id (the registry key);
        # provider objects across modalities don't all expose an ``.id`` field.
        provider_id = candidate.provider
        if getattr(provider, "auth_type", None) == AuthType.None_:
            pass  # no credential required (e.g. local Ollama)
        elif isinstance(provider, OAuthProvider):
            if not isinstance(auth_manager.get(provider_id), OAuthCredential):
                continue
        else:
            cred = auth_manager.get(provider_id)
            if not isinstance(cred, APICredential) and not os.environ.get(
                f"{provider_id.upper()}_API_KEY"
            ):
                continue
        seen.add(key)
        result.append(candidate)
    return result
