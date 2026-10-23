"""Any OpenAI-compatible /audio/transcriptions endpoint (e.g. Groq's free tier)."""

from pathlib import Path

import httpx

from app.worker.transcribers.base import TranscriptionError


class OpenAICompatibleTranscriber:
    def __init__(self, base_url: str, api_key: str, model: str, language: str | None = None):
        if not (base_url and api_key and model):
            raise ValueError("OPENAI_COMPAT_BASE_URL, _API_KEY and _MODEL are required")
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.language = language

    async def load(self) -> None:
        return None

    async def transcribe(self, audio_path: Path) -> str:
        data = {"model": self.model, "response_format": "json"}
        if self.language:
            data["language"] = self.language
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                with audio_path.open("rb") as f:
                    r = await client.post(
                        f"{self.base_url}/audio/transcriptions",
                        headers={"Authorization": f"Bearer {self.api_key}"},
                        data=data,
                        files={"file": (audio_path.name, f, "audio/ogg")},
                    )
            r.raise_for_status()
            return (r.json().get("text") or "").strip()
        except httpx.HTTPError as exc:
            raise TranscriptionError(str(exc)) from exc
