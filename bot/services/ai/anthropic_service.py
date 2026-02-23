import logging
from typing import TYPE_CHECKING, TypeVar

from anthropic import AsyncAnthropic
from pydantic import BaseModel

from .base_service import BaseService
from .types import AIChatResponse, Message

T = TypeVar("T", bound=BaseModel)

if TYPE_CHECKING:
    from bot.juno import Juno


class AnthropicService(BaseService):
    def __init__(self, bot: "Juno"):
        self.bot = bot
        self.logger = logging.getLogger(__name__)
        self.logger.info("Initialized AnthropicService")

    async def chat(self, guild_id: int, messages: list[Message], model: str | None = None, max_tokens: int = 1024) -> AIChatResponse:
        anthropic_config = (await self.bot.config_service.get_config(str(guild_id))).aiConfig.antropic
        model_to_use = model or anthropic_config.preferredModel

        try:
            anthropic_messages = [self.map_message_to_provider(message, "anthropic") for message in messages]
            self.logger.info(f"Calling AnthropicService.chat() with model={model_to_use}")

            async with AsyncAnthropic(api_key=anthropic_config.apiKey.get_secret_value()) as client:
                raw_response = await client.messages.create(model=model_to_use, max_tokens=max_tokens, messages=anthropic_messages)

            return AIChatResponse(
                model=model_to_use,
                content=raw_response.content[0].text,
                raw_response=raw_response,
                usage={
                    "prompt_tokens": raw_response.usage.input_tokens,
                    "completion_tokens": raw_response.usage.output_tokens,
                    "total_tokens": raw_response.usage.input_tokens + raw_response.usage.output_tokens,
                },
            )
        except Exception as e:
            self.logger.error(f"Error in AnthropicService.chat(): {e}")
            return AIChatResponse(model=model_to_use, content=f"Error: {e}", raw_response=None, usage={})

    async def chat_with_schema(self, guild_id: int, messages: list[Message], schema: type[T], model: str | None = None) -> T:
        anthropic_config = (await self.bot.config_service.get_config(str(guild_id))).aiConfig.antropic
        model_to_use = model or anthropic_config.preferredModel

        try:
            anthropic_messages = [self.map_message_to_provider(message, "anthropic") for message in messages]
            self.logger.info(f"Calling AnthropicService.chat_with_schema() with model={model_to_use}")

            tool = {
                "name": "structured_output",
                "description": f"Provide structured output matching the {schema.__name__} schema",
                "input_schema": schema.model_json_schema(),
            }

            async with AsyncAnthropic(api_key=anthropic_config.apiKey.get_secret_value()) as client:
                raw_response = await client.messages.create(
                    model=model_to_use,
                    max_tokens=1024,
                    tools=[tool],
                    tool_choice={"type": "tool", "name": "structured_output"},
                    messages=anthropic_messages,
                )

            tool_use = next((block for block in raw_response.content if block.type == "tool_use"), None)

            if not tool_use:
                raise ValueError("No tool use found in response")

            return schema.model_validate(tool_use.input)

        except Exception as e:
            self.logger.error(f"Error in AnthropicService.chat_with_schema(): {e}")
            raise
