import logging
from abc import ABC, abstractmethod
from typing import TypeVar

from pydantic import BaseModel

from .types import AIChatResponse, Message

T = TypeVar("T", bound=BaseModel)

logger = logging.getLogger(__name__)


class BaseService(ABC):
    @abstractmethod
    async def chat(self, guild_id: int, model: str, messages: list[dict[str, str]], **kwargs) -> AIChatResponse:
        pass

    @abstractmethod
    async def chat_with_schema(self, guild_id: int, messages: list[Message], schema: type[T], model: str | None = None) -> T:
        """
        Sends a chat request with structured output based on a Pydantic schema.

        Args:
            messages: List of messages for the conversation
            schema: Pydantic model class defining the expected output structure
            model: Optional model name override

        Returns:
            Instance of the provided Pydantic model populated with the response
        """
        pass

    @staticmethod
    def map_message_to_provider(message: Message, provider: str):
        if provider == "ollama":
            mapped_message = {
                "role": message.role,
                "content": message.content,
            }

            if images := message.images:
                mapped_message["images"] = [image["data"] for image in images]

            return mapped_message
        elif provider == "openai":
            mapped_message = {
                "role": message.role,
                "content": [{"type": "text", "text": message.content}],
            }

            if images := message.images:
                mapped_message["content"].extend(
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{image['type']};base64,{image['data']}"},
                    }
                    for image in message.images
                )

            return mapped_message
        elif provider == "anthropic":
            # Anthropic requires content as string if no images, array if images
            if images := message.images:
                content_parts = []

                # Add text first
                if message.content:
                    content_parts.append({"type": "text", "text": message.content})

                # Add images
                for image in images:
                    content_parts.append(
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": image.get("type", "image/jpeg"),
                                "data": image.get("data", ""),
                            },
                        }
                    )

                mapped_message = {"role": message.role, "content": content_parts}
            else:
                mapped_message = {"role": message.role, "content": message.content}

            return mapped_message
        elif provider == "google":
            mapped_message = {
                "role": message.role,
                "parts": [{"text": message.content}],
            }

            if mapped_message["role"] in ["assistant", "system"]:
                mapped_message["role"] = "model"

            if images := message.images:
                for image in images:
                    mapped_message["parts"].append(
                        {
                            "inline_data": {
                                "mime_type": image.get("type", ""),
                                "data": image.get("data", ""),
                            }
                        }
                    )

            return mapped_message
