from typing import Any, Literal

from pydantic import BaseModel

ResponsePartType = Literal[
    "text",
    "reasoning",
    "tool_call",
    "tool_result",
    "image",
    "audio",
]


class ResponsePart(BaseModel):
    type: ResponsePartType
    content: Any


class NormalizedResponse(BaseModel):
    id: str
    role: Literal["assistant"]
    parts: list[ResponsePart]
    usage: dict[str, Any] | None = None
    provider: str
    actual_provider: str | None = None
    model: str
    canonical_model: str
    metadata: dict | None = None
