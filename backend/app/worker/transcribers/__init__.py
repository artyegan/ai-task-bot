"""Pluggable speech-to-text. Pick one with the TRANSCRIBER setting."""

from app.core.config import Settings
from app.worker.transcribers.base import Transcriber


def build_transcriber(settings: Settings) -> Transcriber:
    if settings.transcriber == "local":
        from app.worker.transcribers.local_whisper import LocalWhisperTranscriber

        return LocalWhisperTranscriber(
            model=settings.whisper_model,
            compute_type=settings.whisper_compute_type,
            language=settings.whisper_language or None,
            initial_prompt=settings.whisper_initial_prompt or None,
        )
    if settings.transcriber == "openai_compatible":
        from app.worker.transcribers.openai_compatible import OpenAICompatibleTranscriber

        return OpenAICompatibleTranscriber(
            base_url=settings.openai_compat_base_url,
            api_key=settings.openai_compat_api_key,
            model=settings.openai_compat_model,
            language=settings.whisper_language or None,
        )
    from app.worker.transcribers.fake import FakeTranscriber

    return FakeTranscriber()
