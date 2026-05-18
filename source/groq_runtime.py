from __future__ import annotations

import base64
import json
from typing import Any

import requests

from config import settings

try:
    from groq import Groq
except ImportError:
    Groq = None


GROQ_CHAT_URL = "https://api.groq.com/openai/v1/chat/completions"


class AiRuntime:
    def __init__(self) -> None:
        self.groq_client = Groq(api_key=settings.groq_api_key) if Groq and settings.groq_api_key else None

    def available_providers(self) -> list[dict[str, str]]:
        providers = []
        if settings.groq_api_key:
            providers.append({"id": "groq", "label": "Groq", "default_model": settings.groq_assistant_model})
        providers.append({"id": "local_gemma", "label": "Local Gemma", "default_model": settings.local_ollama_model})
        return providers

    def parse_search_query(
        self,
        query: str,
        *,
        categories: list[str],
        characters: list[str],
        provider: str,
        local_model: str | None = None,
    ) -> dict[str, Any]:
        if provider == "local_gemma":
            return self._local_json(
                model=local_model or settings.local_ollama_model,
                prompt=self._search_prompt(query, categories, characters),
            )
        return self._groq_json(
            model=settings.groq_search_model,
            system_prompt="Return JSON only. You classify a media-library search query into intent filters.",
            user_prompt=self._search_prompt(query, categories, characters),
        )

    def route_assistant(
        self,
        message: str,
        *,
        commands: list[dict[str, Any]],
        state: dict[str, Any],
        provider: str,
        local_model: str | None = None,
    ) -> dict[str, Any]:
        prompt = self._assistant_prompt(message, commands, state)
        if provider == "local_gemma":
            return self._local_json(model=local_model or settings.local_ollama_model, prompt=prompt)
        return self._groq_json(
            model=settings.groq_assistant_model,
            system_prompt="Return JSON only. You are a library assistant that picks one UI command or none.",
            user_prompt=prompt,
        )

    def transcribe_audio(self, audio_base64: str, mime_type: str, language: str) -> dict[str, str]:
        if not self.groq_client:
            raise RuntimeError("Groq is not configured for transcription.")
        audio_bytes = base64.b64decode(audio_base64)
        transcription = self.groq_client.audio.transcriptions.create(
            file=("voice.webm", audio_bytes),
            model=settings.groq_transcription_model,
            response_format="json",
            language=language,
            temperature=0.0,
        )
        text = getattr(transcription, "text", None)
        if text is None and isinstance(transcription, dict):
            text = transcription.get("text", "")
        return {"text": str(text or "").strip(), "model": settings.groq_transcription_model}

    def _groq_json(self, *, model: str, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        if not settings.groq_api_key:
            raise RuntimeError("Groq is not configured.")
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0,
        }
        response = requests.post(
            GROQ_CHAT_URL,
            headers={
                "Authorization": f"Bearer {settings.groq_api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=120,
        )
        response.raise_for_status()
        data = response.json()
        content = data["choices"][0]["message"]["content"]
        return json.loads(content)

    def _local_json(self, *, model: str, prompt: str) -> dict[str, Any]:
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "options": {"temperature": 0},
        }
        response = requests.post(settings.local_ollama_api, json=payload, timeout=180)
        response.raise_for_status()
        data = response.json()
        return json.loads(data["response"])

    def _search_prompt(self, query: str, categories: list[str], characters: list[str]) -> str:
        return f"""
Return one JSON object with exactly these keys:
- keywords: array of lowercase phrases
- categories: array chosen only from the known categories when directly relevant
- characters: array chosen only from the known characters when directly relevant
- cleaned_filter: one of "any", "only_cleaned", "only_uncleaned"
- summary: short sentence

Known categories:
{", ".join(categories)}

Known characters:
{", ".join(characters) or "(none)"}

Rules:
- Do not invent categories or characters.
- Use "any" unless the user explicitly asks for cleaned, no-watermark, original, or watermarked clips.
- Keep keywords literal and short.

User query:
{query}
""".strip()

    def _assistant_prompt(self, message: str, commands: list[dict[str, Any]], state: dict[str, Any]) -> str:
        command_text = "\n".join(
            f"- {command['name']}: {command['description']}. params: {json.dumps(command.get('parameters', {}), ensure_ascii=True)}"
            for command in commands
        )
        return f"""
Return one JSON object with exactly these keys:
- reply: concise helpful text
- command: a command name from the registry or empty string
- args: object

Command registry:
{command_text}

Current state:
{json.dumps(state, ensure_ascii=True)}

Rules:
- If the user asks to search, use command "search_library" with args {{ "query": "..." }}.
- If the user asks about plans or billing, use "show_billing".
- If the user asks about devices or folders, use "show_devices".
- If the user asks how to connect a machine, use "show_connector_help".
- If no command is needed, return empty command and an empty args object.

User message:
{message}
""".strip()
