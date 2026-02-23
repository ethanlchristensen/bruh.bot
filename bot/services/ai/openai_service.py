import logging
from typing import TYPE_CHECKING, TypeVar

from openai import AsyncClient
from pydantic import BaseModel

from .base_service import BaseService
from .types import AIChatResponse, Message

T = TypeVar("T", bound=BaseModel)

if TYPE_CHECKING:
    from bot.juno import Juno


class OpenAIService(BaseService):
    def __init__(self, bot: "Juno"):
        self.bot = bot
        self.logger = logging.getLogger(__name__)
        self.logger.info("Initialized OpenAIService")

    async def chat(self, guild_id: int, messages: list[Message], model: str | None = None) -> AIChatResponse:
        openai_config = (await self.bot.config_service.get_config(str(guild_id))).aiConfig.openai
        model_to_use = model or openai_config.preferredModel

        try:
            openai_messages = [self.map_message_to_provider(message, "openai") for message in messages]
            self.logger.info(f"Calling OpenAIService.chat() with model={model_to_use}")

            async with AsyncClient(api_key=openai_config.apiKey.get_secret_value()) as client:
                raw_response = await client.chat.completions.create(model=model_to_use, messages=openai_messages)

            return AIChatResponse(
                model=model_to_use,
                content=raw_response.choices[0].message.content,
                raw_response=raw_response,
                usage={
                    "prompt_tokens": raw_response.usage.prompt_tokens,
                    "completion_tokens": raw_response.usage.completion_tokens,
                    "total_tokens": raw_response.usage.total_tokens,
                },
            )
        except Exception as e:
            self.logger.error(f"Error in OpenAIService.chat(): {e}")
            return AIChatResponse(model=model_to_use, content=f"Error: {e}", raw_response=None, usage={})

    async def chat_with_schema(self, guild_id: int, messages: list[Message], schema: type[T], model: str | None = None) -> T:
        openai_config = (await self.bot.config_service.get_config(str(guild_id))).aiConfig.openai
        model_to_use = model or openai_config.preferredModel

        try:
            openai_messages = [self.map_message_to_provider(message, "openai") for message in messages]
            self.logger.info(f"Calling OpenAIService.chat_with_schema() with model={model_to_use}")

            async with AsyncClient(api_key=openai_config.apiKey.get_secret_value()) as client:
                raw_response = await client.beta.chat.completions.parse(
                    model=model_to_use,
                    messages=openai_messages,
                    response_format=schema,
                )

            return raw_response.choices[0].message.parsed
        except Exception as e:
            self.logger.error(f"Error in OpenAIService.chat_with_schema(): {e}")
            raise
