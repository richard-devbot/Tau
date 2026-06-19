from __future__ import annotations
from tau.inference.api.registry import BaseAPIRegistry
from tau.inference.api.audio.base import BaseAudioAPI


class AudioAPIRegistry(BaseAPIRegistry[BaseAudioAPI]):
    """Registry for audio API implementations."""

    @classmethod
    def from_builtins(cls) -> AudioAPIRegistry:
        from tau.inference.api.audio.builtins import AUDIO_APIS
        instance = cls()
        for name, api in AUDIO_APIS:
            instance.register(name, api)
        return instance
