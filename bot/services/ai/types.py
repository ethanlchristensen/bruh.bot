from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any, Literal

from PIL.Image import Image as PILImage
from pydantic import BaseModel, Field


class Role(StrEnum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


class Image:
    type: str
    data: str


@dataclass
class Message:
    role: Role
    content: str
    images: list[Image] | None = None
    name: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Message":
        return cls(
            role=data["role"],
            content=data["content"],
            name=data.get("name"),
            images=data.get("images", []),
        )

    def to_dict(self) -> dict[str, Any]:
        result = {"role": self.role, "content": self.content}
        if self.name:
            result["name"] = self.name
        if self.images:
            result["images"] = self.images
        return result


@dataclass
class AIChatResponse:
    model: str
    content: str
    raw_response: Any
    usage: dict[str, int] | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AIChatResponse":
        return cls(**data)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AIServiceConfig:
    host: str | None = None
    api_key: str | None = None
    model: str | None = None


class UserIntent(BaseModel):
    """Structured output for user intent classification"""

    intent: Literal["chat", "image_generation"] = Field(description="The user's intent: chat for conversation or image_generation for creating images")

    reasoning: str = Field(description="Brief explanation of why this intent was chosen")


@dataclass
class ImageGenerationResponse:
    text_response: str = "Here is your generated image"
    generated_image: PILImage | None = None
