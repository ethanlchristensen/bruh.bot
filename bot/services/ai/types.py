from dataclasses import dataclass
from typing import Literal

from PIL.Image import Image as PILImage
from pydantic import BaseModel, Field


class UserIntent(BaseModel):
    """Structured output for user intent classification"""

    intent: Literal["chat", "image_generation"] = Field(description="The user's intent: chat for conversation or image_generation for creating images")

    reasoning: str = Field(description="Brief explanation of why this intent was chosen")


@dataclass
class ImageGenerationResponse:
    text_response: str = "Here is your generated image"
    generated_image: PILImage | None = None
