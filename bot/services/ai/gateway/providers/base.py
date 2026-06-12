from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from bot.services.ai.gateway.schemas.chunks import StreamChunk
from bot.services.ai.gateway.schemas.models import ModelInfo
from bot.services.ai.gateway.schemas.request import NormalizedRequest
from bot.services.ai.gateway.schemas.response import NormalizedResponse


class ProviderAdapter(ABC):
    @abstractmethod
    async def stream(self, request: NormalizedRequest, api_key: str) -> AsyncIterator[StreamChunk]: ...

    @abstractmethod
    async def complete(self, request: NormalizedRequest, api_key: str) -> NormalizedResponse: ...

    @abstractmethod
    async def get_models(self, api_key: str) -> list[ModelInfo]: ...
