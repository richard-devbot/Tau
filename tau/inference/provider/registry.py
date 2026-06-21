from __future__ import annotations

from typing import TypeVar

from tau.inference.provider.types import (
    APIProvider,
    AudioProvider,
    AuthType,
    ImageProvider,
    OAuthProvider,
    VideoProvider,
)

TextProvider = APIProvider | OAuthProvider

_T = TypeVar("_T")


class _ProviderRegistryBase[T]:
    """Internal shared base for all provider sub-registries."""

    def __init__(self) -> None:
        self._providers: dict[str, _T] = {}

    def _key(self, _provider: _T) -> str:
        raise NotImplementedError

    def register(self, provider: _T) -> None:
        self._providers[self._key(provider)] = provider

    def unregister(self, key: str) -> None:
        self._providers.pop(key, None)

    def list(self) -> list[_T]:
        return list(self._providers.values())

    def get(self, key: str) -> _T | None:
        return self._providers.get(key)

    def reset(self) -> None:
        self._providers.clear()


class TextProviderRegistry(_ProviderRegistryBase[TextProvider]):
    """Registry mapping provider IDs to text-LLM provider instances."""

    def _key(self, provider: TextProvider) -> str:
        return provider.id

    def is_using_oauth(self, provider: str) -> bool:
        """Return True if the named provider uses OAuth auth; raise ValueError if unknown."""
        if p := self.get(provider):
            return p.auth_type == AuthType.OAuth
        raise ValueError(f"Provider '{provider}' not found.")

    def get_oauth_providers(self) -> list[OAuthProvider]:
        """Return all registered OAuth-authenticated providers."""
        return [p for p in self._providers.values() if isinstance(p, OAuthProvider)]

    def get_api_providers(self) -> list[APIProvider]:
        """Return all registered API-key-authenticated providers."""
        return [p for p in self._providers.values() if isinstance(p, APIProvider)]

    def get_oauth_provider(self, provider: str) -> OAuthProvider | None:
        """Return the named provider only if it is an OAuthProvider."""
        p = self.get(provider)
        return p if isinstance(p, OAuthProvider) else None

    def get_api_provider(self, provider: str) -> APIProvider | None:
        """Return the named provider only if it is an APIProvider."""
        p = self.get(provider)
        return p if isinstance(p, APIProvider) else None

    @classmethod
    def from_builtins(cls) -> TextProviderRegistry:
        from tau.builtins.providers.text import providers

        instance = cls()
        for provider in providers:
            instance.register(provider)
        return instance


class ImageProviderRegistry(_ProviderRegistryBase[ImageProvider]):
    """Registry mapping provider names to image-generation provider instances."""

    def _key(self, provider: ImageProvider) -> str:
        return provider.name

    @classmethod
    def from_builtins(cls) -> ImageProviderRegistry:
        from tau.builtins.providers.image import providers

        instance = cls()
        for provider in providers:
            instance.register(provider)
        return instance


class AudioProviderRegistry(_ProviderRegistryBase[AudioProvider]):
    """Registry mapping provider names to audio (STT/TTS) provider instances."""

    def _key(self, provider: AudioProvider) -> str:
        return provider.name

    @classmethod
    def from_builtins(cls) -> AudioProviderRegistry:
        from tau.builtins.providers.audio import providers

        instance = cls()
        for provider in providers:
            instance.register(provider)
        return instance


class VideoProviderRegistry(_ProviderRegistryBase[VideoProvider]):
    """Registry mapping provider names to video-generation provider instances."""

    def _key(self, provider: VideoProvider) -> str:
        return provider.name

    @classmethod
    def from_builtins(cls) -> VideoProviderRegistry:
        from tau.builtins.providers.video import providers

        instance = cls()
        for provider in providers:
            instance.register(provider)
        return instance


class ProviderRegistry:
    """Unified registry holding all provider types (text, image, audio, video)."""

    def __init__(
        self,
        text: TextProviderRegistry | None = None,
        image: ImageProviderRegistry | None = None,
        audio: AudioProviderRegistry | None = None,
        video: VideoProviderRegistry | None = None,
    ) -> None:
        self.text = text or TextProviderRegistry()
        self.image = image or ImageProviderRegistry()
        self.audio = audio or AudioProviderRegistry()
        self.video = video or VideoProviderRegistry()

    @classmethod
    def from_builtins(cls) -> ProviderRegistry:
        return cls(
            text=TextProviderRegistry.from_builtins(),
            image=ImageProviderRegistry.from_builtins(),
            audio=AudioProviderRegistry.from_builtins(),
            video=VideoProviderRegistry.from_builtins(),
        )
