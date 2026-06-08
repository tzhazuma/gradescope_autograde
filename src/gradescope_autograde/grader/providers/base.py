"""Abstract base class for LLM providers."""

from __future__ import annotations

from abc import ABC, abstractmethod


class LLMProvider(ABC):
    """Base class that every LLM provider must implement."""

    @abstractmethod
    def complete(
        self,
        prompt: str,
        system_prompt: str = "",
        response_format: str | None = None,
    ) -> str:
        """Send a prompt and return the text response.

        Args:
            prompt: The user message to send.
            system_prompt: Optional system-level instruction.
            response_format: Optional format hint (e.g. "json").

        Returns:
            The model's text response.
        """
        ...

    @abstractmethod
    def complete_structured(
        self,
        prompt: str,
        system_prompt: str,
        json_schema: dict | None = None,
    ) -> dict:
        """Send a prompt and return a parsed JSON response.

        Args:
            prompt: The user message to send.
            system_prompt: System instruction (should include schema guidance).
            json_schema: Optional JSON schema the response should conform to.

        Returns:
            Parsed JSON dict from the model response.
        """
        ...

    @abstractmethod
    def list_models(self) -> list[dict]:
        """Return a list of available models from this provider.

        Returns:
            List of dicts with at least ``id``, ``name``, ``context_length``,
            and ``multimodal`` keys.
        """
        ...
