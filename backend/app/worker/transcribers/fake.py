"""Deterministic transcriber for tests and for running the stack without a model.

Returns FAKE_TRANSCRIPT (default below). The special values '' and 'fail' exercise the
empty-transcript and backend-error paths.
"""

import os
from pathlib import Path

from app.worker.transcribers.base import TranscriptionError


class FakeTranscriber:
    def __init__(self, text: str | None = None):
        self.text = os.environ.get("FAKE_TRANSCRIPT", "Buy milk") if text is None else text
        self.calls: list[Path] = []

    async def load(self) -> None:
        return None

    async def transcribe(self, audio_path: Path) -> str:
        self.calls.append(audio_path)
        if self.text == "fail":
            raise TranscriptionError("fake backend failure")
        return self.text
