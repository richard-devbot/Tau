from __future__ import annotations

from tau.inference.api.registry import BaseAPIRegistry
from tau.inference.api.video.base import BaseVideoAPI


class VideoAPIRegistry(BaseAPIRegistry[BaseVideoAPI]):
    """Registry for video generation API implementations."""

    @classmethod
    def from_builtins(cls) -> VideoAPIRegistry:
        from tau.inference.api.video.builtins import VIDEO_APIS

        instance = cls()
        for name, api in VIDEO_APIS:
            instance.register(name, api)
        return instance
