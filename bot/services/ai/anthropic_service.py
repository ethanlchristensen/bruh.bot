import logging
from typing import TypeVar

import anthropic
from pydantic import BaseModel

from ..config_service import DynamicConfig
from .base_service import BaseService
from .types import AIChatResponse, Message

T = TypeVar("T", bound=BaseModel)


class AnthropicService(BaseService):
    def __init__(self, config: DynamicConfig):
        self.logger = logging.getLogger(__name__)
        self.client = anthropic.Anthropic(api_key=config.aiConfig.anthropic.apiKey)
        self.default_model = config.aiConfig.anthropic.preferredModel
        self.logger.info(f"Initializing AnthropicService with default_model={self.default_model}")

    async def chat(
        self,
        messages: list[Message],
        model: str | None = None,
        max_tokens: int = 1024,
    ) -> AIChatResponse:
        try:
            model_to_use = model or self.default_model

            anthropic_messages = [self.map_message_to_provider(message, "anthropic") for message in messages]

            self.logger.info(f"Calling AnthropicService.chat() with model={model_to_use}")

            raw_response = self.client.messages.create(model=model_to_use, max_tokens=max_tokens, messages=anthropic_messages)

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
            return {}

    async def chat_with_schema(self, messages: list[Message], schema: type[T], model: str | None = None) -> T:
        """
        Anthropic structured output using tool use pattern.
        Note: This uses Anthropic's tool calling feature to enforce schema.
        """
        try:
            model_to_use = model or self.default_model

            anthropic_messages = [self.map_message_to_provider(message, "anthropic") for message in messages]

            self.logger.info(f"Calling AnthropicService.chat_with_schema() with model={model_to_use} and schema={schema.__name__}")

            # Convert Pydantic schema to Anthropic tool format
            tool = {
                "name": "structured_output",
                "description": f"Provide structured output matching the {schema.__name__} schema",
                "input_schema": schema.model_json_schema(),
            }

            raw_response = self.client.messages.create(
                model=model_to_use,
                max_tokens=1024,
                tools=[tool],
                tool_choice={"type": "tool", "name": "structured_output"},
                messages=anthropic_messages,
            )

            tool_use = next(
                (block for block in raw_response.content if block.type == "tool_use"),
                None,
            )

            if not tool_use:
                raise ValueError("No tool use found in response")

            return schema.model_validate(tool_use.input)

        except Exception as e:
            self.logger.error(f"Error in AnthropicService.chat_with_schema(): {e}")
            raise
