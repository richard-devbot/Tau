from __future__ import annotations

from tau.inference.api.image.base import BaseImageAPI
from tau.inference.api.registry import BaseAPIRegistry


class ImageAPIRegistry(BaseAPIRegistry[BaseImageAPI]):
    """Registry for image generation API implementations."""

    @classmethod
    def from_builtins(cls) -> ImageAPIRegistry:
        from tau.inference.api.image.builtins import IMAGE_APIS

        instance = cls()
        for name, api in IMAGE_APIS:
            instance.register(name, api)
        return instance
