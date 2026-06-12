import asyncio
from collections.abc import AsyncIterator

from bot.services.ai.gateway.exceptions import ProviderAuthError, ProviderNotFoundError
from bot.services.ai.gateway.providers.registry import ProviderRegistry
from bot.services.ai.gateway.schemas.request import NormalizedRequest
from bot.services.ai.gateway.schemas.response import NormalizedResponse


class MeshGateway:
    """
    SDK-style gateway. Framework-agnostic — no HTTP concepts here.

    The caller is responsible for supplying credentials, typically fetched
    from the database before invoking any method.

    Basic usage:
        from ai_gateway.gateway import gateway

        # Fetch key from DB in your view/service
        api_key = user.provider_keys.get(provider="anthropic").api_key

        response = await gateway.complete(request, credentials={"api_key": api_key})

    Streaming:
        async for chunk in gateway.stream(request, credentials={"api_key": api_key}):
            yield chunk
    """

    def __init__(self):
        self.registry = ProviderRegistry()

    def _resolve_key(self, provider: str, credentials: dict | None) -> str:
        """
        Uses the key passed in from the caller (fetched from DB).
        No global fallback — every call must supply credentials.
        """
        if provider == "ollama":
            if credentials:
                return credentials.get("endpoint") or credentials.get("api_key") or "http://localhost:11434"
            return "http://localhost:11434"

        if credentials:
            key = credentials.get("api_key") or credentials.get(provider)
            if key:
                return key

        raise ProviderAuthError(f"No API key supplied for provider '{provider}'.")

    def _get_adapter(self, provider: str):
        adapter = self.registry.get(provider)
        if not adapter:
            raise ProviderNotFoundError(provider)
        return adapter

    async def complete(
        self,
        request: NormalizedRequest,
        credentials: dict | None = None,
    ) -> NormalizedResponse:
        """Non-streaming completion."""
        adapter = self._get_adapter(request.provider)
        api_key = self._resolve_key(request.provider, credentials)
        return await adapter.complete(request, api_key=api_key)

    async def stream(
        self,
        request: NormalizedRequest,
        credentials: dict | None = None,
    ) -> AsyncIterator:
        """Streaming completion. Yields chunks."""
        adapter = self._get_adapter(request.provider)
        api_key = self._resolve_key(request.provider, credentials)
        async for chunk in adapter.stream(request, api_key=api_key):
            yield chunk

    async def get_models(
        self,
        provider: str,
        credentials: dict | None = None,
    ) -> list:
        """Fetch available models for a single provider."""
        try:
            api_key = self._resolve_key(provider, credentials)
        except Exception:
            api_key = ""
        adapter = self._get_adapter(provider)
        return await adapter.get_models(api_key)

    async def get_all_models(
        self,
        credentials_map: dict[str, str],
    ) -> dict[str, list]:
        """
        Fetch models from all providers concurrently.

        credentials_map: { "anthropic": "sk-ant-...", "openai": "sk-..." }
        Unknown providers are skipped. Failures are caught per-provider.
        """

        async def _fetch(provider: str, api_key: str):
            try:
                adapter = self._get_adapter(provider)
                models = await adapter.get_models(api_key)
                return provider, models
            except Exception:
                return provider, []

        tasks = [_fetch(provider, key) for provider, key in credentials_map.items() if provider in self.registry]

        if not tasks:
            return {}

        results = await asyncio.gather(*tasks)
        return {provider: models for provider, models in results if models}

    def list_providers(self) -> list[str]:
        """Returns names of all registered providers."""
        return list(self.registry.keys())


_gateway_instance = None


def get_mesh_gateway() -> MeshGateway:
    global _gateway_instance
    if _gateway_instance is None:
        _gateway_instance = MeshGateway()
    return _gateway_instance
