"""Central registry that aggregates models from all providers."""

from __future__ import annotations

from gradescope_autograde.grader.providers.base import LLMProvider


class ModelRegistry:

    def __init__(self) -> None:
        self._providers: dict[str, LLMProvider] = {}

    def register(self, name: str, provider: LLMProvider) -> None:
        self._providers[name] = provider

    def get_provider(self, name: str) -> LLMProvider:
        if name not in self._providers:
            available = ", ".join(sorted(self._providers)) or "(none)"
            raise KeyError(f"Provider {name!r} not registered. Available: {available}")
        return self._providers[name]

    def discover_all(self) -> list[dict]:
        results: list[dict] = []
        for provider_name, provider in self._providers.items():
            try:
                for model in provider.list_models():
                    results.append({"provider": provider_name, **model})
            except Exception:
                results.append({
                    "provider": provider_name,
                    "id": "__error__",
                    "name": f"{provider_name} (unreachable)",
                    "context_length": 0,
                    "multimodal": False,
                })
        return results
