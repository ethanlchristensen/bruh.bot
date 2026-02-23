import logging
from typing import TYPE_CHECKING, TypeVar

import ollama
from pydantic import BaseModel

from .base_service import BaseService
from .types import AIChatResponse, Message

T = TypeVar("T", bound=BaseModel)

if TYPE_CHECKING:
    from bot.juno import Juno


class OllamaService(BaseService):
    def __init__(self, bot: "Juno"):
        self.logger = logging.getLogger(__name__)
        self.bot = bot
        self.client = ollama.AsyncClient(host=self.bot.config_service.base.ollamaEndpoint)
        self.logger.info(f"Initialized OllamaService with host={self.bot.config_service.base.ollamaEndpoint}")

    async def chat(self, guild_id: int, messages: list[Message], model: str | None = None) -> AIChatResponse:
        ollama_config = (await self.bot.config_service.get_config(str(guild_id))).aiConfig.ollama
        model_to_use = model or ollama_config.preferredModel

        try:
            ollama_messages = [self.map_message_to_provider(message, "ollama") for message in messages]
            self.logger.info(f"Calling OllamaService.chat() with model={model_to_use}")

            raw_response = await self.client.chat(model=model_to_use, messages=ollama_messages)

            return AIChatResponse(
                model=model_to_use,
                content=raw_response.get("message", {}).get("content", ""),
                raw_response=raw_response,
                usage=raw_response.get("usage", {}),
            )
        except Exception as e:
            self.logger.error(f"Error in OllamaService.chat(): {e}")
            return AIChatResponse(model=model_to_use, content=f"Error: {e}", raw_response=None, usage={})

    async def chat_with_schema(self, guild_id: int, messages: list[Message], schema: type[T], model: str | None = None) -> T:
        ollama_config = (await self.bot.config_service.get_config(str(guild_id))).aiConfig.ollama
        model_to_use = model or ollama_config.preferredModel

        try:
            ollama_messages = [self.map_message_to_provider(message, "ollama") for message in messages]
            self.logger.info(f"Calling OllamaService.chat_with_schema() with model={model_to_use}")

            raw_response = await self.client.chat(
                model=model_to_use,
                messages=ollama_messages,
                format=schema.model_json_schema(),
            )

            return schema.model_validate_json(raw_response.message.content)
        except Exception as e:
            self.logger.error(f"Error in OllamaService.chat_with_schema(): {e}")
            raise
