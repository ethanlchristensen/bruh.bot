import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import httpx

if TYPE_CHECKING:
    from bot.bruh_bot import BruhBot


class EmbeddingService:
    OPENROUTER_BASE = "https://openrouter.ai/api/v1"
    DEFAULT_MODEL = "openai/text-embedding-3-small"
    DEFAULT_DIMENSIONS = 1536

    def __init__(self, bot: "BruhBot"):
        self.bot = bot
        self.logger = logging.getLogger(__name__)
        self._last_request = 0.0
        self._min_interval = 0.1

    async def embed(self, texts: list[str], guild_id: int) -> list[list[float]] | None:
        texts = [t.strip() for t in texts if t and t.strip()]
        if not texts:
            return None

        config = await self.bot.config_service.get_config(str(guild_id))
        mem_cfg = config.memoryConfig
        model = mem_cfg.embeddingModel or self.DEFAULT_MODEL
        dimensions = mem_cfg.embeddingDimensions or self.DEFAULT_DIMENSIONS

        provider_config = config.aiConfig.openrouter
        api_key = provider_config.get_api_key()
        if not api_key:
            self.logger.warning("No OpenRouter API key configured, cannot generate embeddings")
            return None

        headers = self._get_headers(api_key)

        try:
            now = datetime.now(UTC).timestamp()
            if now - self._last_request < self._min_interval:
                import asyncio

                await asyncio.sleep(self._min_interval - (now - self._last_request))

            async with httpx.AsyncClient(http2=True) as client:
                resp = await client.post(
                    f"{self.OPENROUTER_BASE}/embeddings",
                    json={
                        "model": model,
                        "input": texts,
                        "dimensions": dimensions,
                    },
                    headers=headers,
                    timeout=30.0,
                )
                self._last_request = datetime.now(UTC).timestamp()

                if resp.is_error:
                    self.logger.warning(f"Embedding API error: {resp.status_code} {resp.text[:300]}")
                    return None

                data = resp.json()
                embeddings = [entry["embedding"] for entry in data.get("data", [])]
                return embeddings

        except Exception:
            self.logger.exception("Failed to generate embeddings")
            return None

    async def embed_one(self, text: str, guild_id: int) -> list[float] | None:
        result = await self.embed([text], guild_id)
        return result[0] if result else None

    @staticmethod
    def _get_headers(api_key: str) -> dict:
        return {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://mesh.etchris.dev",
            "X-Title": "bruh.bot",
        }
