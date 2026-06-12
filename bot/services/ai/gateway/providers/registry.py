from ..exceptions import ProviderNotFoundError
from .base import ProviderAdapter
from .ollama_provider import OllamaAdapter
from .openrouter_provider import OpenRouterAdapter

REGISTRY: dict[str, type[ProviderAdapter]] = {
    "openrouter": OpenRouterAdapter,
    "mesh_router": OpenRouterAdapter,
    "ollama": OllamaAdapter,
}


class ProviderRegistry:
    def __init__(self):
        self._adapters: dict[str, ProviderAdapter] = {name: cls() for name, cls in REGISTRY.items()}

    def get(self, provider: str) -> ProviderAdapter:
        adapter = self._adapters.get(provider)
        if not adapter:
            raise ProviderNotFoundError(provider)
        return adapter

    def keys(self):
        return self._adapters.keys()

    def __contains__(self, provider: str) -> bool:
        return provider in self._adapters
