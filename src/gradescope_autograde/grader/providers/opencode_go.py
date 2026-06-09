"""OpenCode Go API provider (deepseek-v4-flash, mimo-v2.5)."""

from __future__ import annotations

import json
import os
import re

import httpx
from openai import OpenAI

from gradescope_autograde.grader.providers.base import LLMProvider

_BASE_URL = "https://opencode.ai/zen/go/v1"
_DEFAULT_MODEL = "deepseek-v4-flash"
_MULTIMODAL_MODEL = "mimo-v2.5"

_MODELS = [
    {
        "id": "deepseek-v4-flash",
        "name": "DeepSeek V4 Flash",
        "context_length": 1_000_000,
        "multimodal": False,
    },
    {
        "id": "mimo-v2.5",
        "name": "MiMo V2.5",
        "context_length": 1_000_000,
        "multimodal": True,
    },
]


class OpenCodeGoProvider(LLMProvider):

    def __init__(
        self,
        model: str = _DEFAULT_MODEL,
        api_key: str | None = None,
    ) -> None:
        self._model = model
        # Create a custom httpx client that bypasses system proxies
        # to avoid SOCKS proxy issues (socksio not installed)
        _http_client = httpx.Client(
            transport=httpx.HTTPTransport(
                proxy=None,
            ),
            follow_redirects=True,
        )
        self._client = OpenAI(
            base_url=_BASE_URL,
            api_key=api_key or os.environ.get("OPENCODE_GO_API_KEY", ""),
            http_client=_http_client,
        )

    def complete(
        self,
        prompt: str,
        system_prompt: str = "",
        response_format: str | None = None,
    ) -> str:
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
        return self._parse_json_response(raw)

    @staticmethod
    def _parse_json_response(raw: str) -> dict:
        """Parse JSON from LLM response, handling markdown fences and prefix text."""
        cleaned = raw.strip()
        # Strip markdown JSON code fences
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
            cleaned = re.sub(r"\s*```$", "", cleaned)
        # Try to find the first { ... } block if prefix text exists
        brace_start = cleaned.find("{")
        if brace_start > 0:
            cleaned = cleaned[brace_start:]
        # Try to find the last } for the JSON boundary
        brace_end = cleaned.rfind("}")
        if brace_end > 0:
            cleaned = cleaned[: brace_end + 1]
        return json.loads(cleaned)

    def list_models(self) -> list[dict]:
        return list(_MODELS)

    @property
    def model(self) -> str:
        return self._model

    @model.setter
    def model(self, value: str) -> None:
        self._model = value
