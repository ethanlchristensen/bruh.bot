import logging
from typing import TypeVar

import openai
from pydantic import BaseModel

from ..config_service import DynamicConfig
from .base_service import BaseService
from .types import AIChatResponse, Message

T = TypeVar("T", bound=BaseModel)


class OpenAIService(BaseService):
    def __init__(self, config: DynamicConfig):
        self.logger = logging.getLogger(__name__)
        self.client = openai.Client(api_key=config.aiConfig.openai.apiKey)
        self.default_model = config.aiConfig.openai.preferredModel
        self.logger.info(f"Intializing OpenAIService with default_model={self.default_model}")

    async def chat(self, messages: list[Message], model: str | None = None) -> AIChatResponse:
        try:
            model_to_use = model or self.default_model

            openai_messages = [self.map_message_to_provider(message, "openai") for message in messages]

            self.logger.info(f"Calling OpenAIService.chat() with model={model_to_use}")

            raw_response = self.client.chat.completions.create(model=model_to_use, messages=openai_messages)

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
            return {}

    async def chat_with_schema(self, messages: list[Message], schema: type[T], model: str | None = None) -> T:
        try:
            model_to_use = model or self.default_model

            openai_messages = [self.map_message_to_provider(message, "openai") for message in messages]

            self.logger.info(f"Calling OpenAIService.chat_with_schema() with model={model_to_use} and schema={schema.__name__}")

            raw_response = self.client.beta.chat.completions.parse(
                model=model_to_use,
                messages=openai_messages,
                response_format=schema,
            )

            return raw_response.choices[0].message.parsed
        except Exception as e:
            self.logger.error(f"Error in OpenAIService.chat_with_schema(): {e}")
            raise
