from __future__ import annotations

from abc import ABC, abstractmethod

from tau.inference.model.types import Model
from tau.inference.types import GeneratedImage, ImageContext, ImageOptions


class BaseImageAPI(ABC):
    """Abstract base class for image generation API implementations."""
    def __init__(self, options: ImageOptions) -> None:
        self.options = options

    @abstractmethod
    async def generate(self, model: Model, context: ImageContext) -> GeneratedImage:
        """Generate an image from a prompt."""
        raise NotImplementedError
