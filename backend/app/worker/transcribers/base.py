from pathlib import Path
from typing import Protocol


class TranscriptionError(Exception):
    """The audio could not be transcribed (retryable)."""


class Transcriber(Protocol):
    async def load(self) -> None:
        """Prepare the backend (e.g. load the model). Called once at worker startup."""
        ...

    async def transcribe(self, audio_path: Path) -> str:
        """Return the transcript text ('' when no speech was detected)."""
        ...
