import logging
from typing import TYPE_CHECKING, TypeVar

from google.genai import Client
from pydantic import BaseModel

from .base_service import BaseService
from .types import AIChatResponse, Message

T = TypeVar("T", bound=BaseModel)

if TYPE_CHECKING:
    from bot.juno import Juno


class GoogleAIService(BaseService):
    def __init__(self, bot: "Juno"):
        self.bot = bot
        self.logger = logging.getLogger(__name__)
        self.logger.info("Initialized GoogleAIService")

    async def chat(self, guild_id: int, messages: list[Message], model: str | None = None) -> AIChatResponse:
        google_ai_config = (await self.bot.config_service.get_config(str(guild_id))).aiConfig.google
        model_to_use = model or google_ai_config.preferredModel

        try:
            gemini_messages = [self.map_message_to_provider(message, "google") for message in messages]
            self.logger.info(f"Calling GoogleAIService.chat() with model={model_to_use}")

            client = Client(api_key=google_ai_config.apiKey.get_secret_value())

            raw_response = await client.aio.models.generate_content(model=model_to_use, contents=gemini_messages)

            return AIChatResponse(
                model=model_to_use,
                content=raw_response.candidates[0].content.parts[0].text,
                raw_response=raw_response,
                usage={},
            )

        except Exception as e:
            self.logger.error(f"Error in GoogleAIService: {e}")
            return AIChatResponse(
                model=model_to_use,
                content=f"Chat, we ran into an error: {e}",
                raw_response=None,
                usage={},
            )

    async def chat_with_schema(self, guild_id: int, messages: list[Message], schema: type[T], model: str | None = None) -> T:
        google_ai_config = (await self.bot.config_service.get_config(str(guild_id))).aiConfig.google
        model_to_use = model or google_ai_config.preferredModel

        try:
            gemini_messages = [self.map_message_to_provider(message, "google") for message in messages]
            self.logger.info(f"Calling GoogleAIService.chat_with_schema() with model={model_to_use}")

            client = Client(api_key=google_ai_config.apiKey.get_secret_value())

            raw_response = await client.aio.models.generate_content(
                model=model_to_use,
                contents=gemini_messages,
                config={
                    "response_mime_type": "application/json",
                    "response_schema": schema,
                },
            )

            return raw_response.parsed
        except Exception as e:
            self.logger.error(f"Error in GoogleAIService.chat_with_schema(): {e}")
            raise
