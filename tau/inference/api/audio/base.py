from __future__ import annotations

from abc import ABC, abstractmethod

from tau.inference.model.types import Model
from tau.inference.types import (
    AudioOptions,
    STTContext,
    SynthesizedAudio,
    TranscribedAudio,
    TTSContext,
)


class BaseAudioAPI(ABC):
    """Abstract base class for audio API implementations."""

    def __init__(self, options: AudioOptions) -> None:
        self.options = options

    @abstractmethod
    async def synthesize(self, model: Model, context: TTSContext) -> SynthesizedAudio:
        """Convert text to speech."""
        raise NotImplementedError

    @abstractmethod
    async def transcribe(self, model: Model, context: STTContext) -> TranscribedAudio:
        """Convert speech to text."""
        raise NotImplementedError
