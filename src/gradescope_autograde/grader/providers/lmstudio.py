"""LM Studio local provider."""

from __future__ import annotations

import json
import logging

import httpx
from openai import OpenAI

from gradescope_autograde.grader.providers.base import LLMProvider

_BASE_URL = "http://localhost:1234/v1"
_MODELS_URL = "http://localhost:1234/api/v1/models"

_KNOWN_MODELS = [
    {"id": "gemma4-e4b", "name": "Gemma 4 E4B", "context_length": 131_072, "multimodal": True},
    {"id": "gemma4-12b", "name": "Gemma 4 12B", "context_length": 131_072, "multimodal": True},
    {"id": "qwen3.5-4b", "name": "Qwen 3.5 4B", "context_length": 131_072, "multimodal": False},
    {"id": "qwen3.5-9b", "name": "Qwen 3.5 9B", "context_length": 131_072, "multimodal": False},
]

_log = logging.getLogger(__name__)


class LMStudioProvider(LLMProvider):

    def __init__(self, model: str | None = None) -> None:
        self._model = model
        self._client = OpenAI(
            base_url=_BASE_URL,
            api_key="lm-studio",
        )

    def complete(
        self,
        prompt: str,
        system_prompt: str = "",
        response_format: str | None = None,
    ) -> str:
        if not self._model:
            raise RuntimeError(
                "No LM Studio model configured. "
                "Call discover_models() first or pass model= to the constructor."
            )

        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        kwargs: dict = {
            "model": self._model,
            "messages": messages,
            "temperature": 0.1,
        }
        if response_format == "json":
            kwargs["response_format"] = {"type": "json_object"}

        response = self._client.chat.completions.create(**kwargs)
        return response.choices[0].message.content or ""

    def complete_structured(
        self,
        prompt: str,
        system_prompt: str,
        json_schema: dict | None = None,
    ) -> dict:
        schema_instruction = ""
        if json_schema:
            schema_instruction = (
                f"\n\nRespond with valid JSON matching this schema:\n"
                f"{json.dumps(json_schema, indent=2)}"
            )

        full_system = system_prompt + schema_instruction

        raw = self.complete(
            prompt=prompt,
            system_prompt=full_system,
            response_format="json",
        )
        return json.loads(raw)

    def list_models(self) -> list[dict]:
        try:
            resp = httpx.get(_MODELS_URL, timeout=5.0)
            resp.raise_for_status()
            data = resp.json()
        except (httpx.HTTPError, httpx.TimeoutException):
            _log.debug("LM Studio not reachable, returning known models")
            return [
                {**m, "loaded": False, "params_string": "", "quantization": ""}
                for m in _KNOWN_MODELS
            ]

        models: list[dict] = []
        for item in data.get("data", []):
            model_id: str = item.get("id", "")
            loaded_instances = item.get("loaded_instances", [])
            params = ""
            quant = ""
            if loaded_instances:
                meta = loaded_instances[0].get("metadata", {}) if loaded_instances else {}
                params = meta.get("params_string", "")
                quant = meta.get("quantization", "")

            models.append({
                "id": model_id,
                "display_name": model_id.split("/")[-1] if "/" in model_id else model_id,
                "context_length": item.get("context_length", 131_072),
                "multimodal": False,
                "loaded": bool(loaded_instances),
                "params_string": params,
                "quantization": quant,
            })

        return models

    def discover_models(self) -> list[dict]:
        models = self.list_models()
        loaded = [m for m in models if m.get("loaded")]
        if loaded and not self._model:
            self._model = loaded[0]["id"]
        return models

    @property
    def model(self) -> str | None:
        return self._model

    @model.setter
    def model(self, value: str) -> None:
        self._model = value
