"""faster-whisper on CPU. Free, offline; the model is baked into the worker image."""

import asyncio
import os
from pathlib import Path

from app.core.logging import get_logger
from app.worker.transcribers.base import TranscriptionError

log = get_logger("transcriber.local")

MODEL_DIR = Path(os.environ.get("WHISPER_MODEL_DIR", "/models"))


class LocalWhisperTranscriber:
    def __init__(
        self,
        model: str,
        compute_type: str = "int8",
        language: str | None = None,
        initial_prompt: str | None = None,
    ):
        self.model_name = model
        self.compute_type = compute_type
        self.language = language
        self.initial_prompt = initial_prompt
        self._model = None
        # Inference is CPU-bound: one at a time, in a thread so the event loop keeps serving
        # notification jobs while a transcription runs.
        self._gate = asyncio.Semaphore(1)

    async def load(self) -> None:
        from faster_whisper import WhisperModel

        baked = MODEL_DIR / self.model_name
        source = str(baked) if baked.exists() else self.model_name  # fall back to a download
        threads = os.cpu_count() or 2
        log.info("model.loading", model=source, compute_type=self.compute_type, cpu_threads=threads)
        self._model = await asyncio.to_thread(
            WhisperModel, source, device="cpu", compute_type=self.compute_type, cpu_threads=threads
        )
        log.info("model.loaded")

    def _run(self, audio_path: Path) -> str:
        assert self._model is not None, "load() must run before transcribe()"
        segments, info = self._model.transcribe(
            str(audio_path),
            language=self.language,
            initial_prompt=self.initial_prompt,
            beam_size=5,
            vad_filter=True,
        )
        text = " ".join(s.text.strip() for s in segments).strip()
        log.info("transcribed", language=info.language, duration=round(info.duration, 1))
        return text

    async def transcribe(self, audio_path: Path) -> str:
        async with self._gate:
            try:
                return await asyncio.to_thread(self._run, audio_path)
            except Exception as exc:  # noqa: BLE001 - normalise backend errors
                raise TranscriptionError(str(exc)) from exc
