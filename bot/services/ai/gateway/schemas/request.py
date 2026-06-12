from typing import Any, Literal

from pydantic import BaseModel

MessagePartType = Literal[
    "text",
    "image",
    "file",
    "audio",
    "tool_call",
    "tool_result",
]

MessageRole = Literal["system", "user", "assistant", "tool"]


class MessagePart(BaseModel):
    type: MessagePartType
    text: str | None = None
    url: str | None = None
    file_id: str | None = None
    detail: str | None = None
    tool_call_id: str | None = None
    name: str | None = None
    arguments: dict | None = None
    content: Any = None


class Message(BaseModel):
    role: MessageRole
    parts: list[MessagePart]


class NormalizedRequest(BaseModel):
    provider: str
    model: str
    messages: list[Message]
    stream: bool = True
    tools: list[dict] = []
    max_tokens: int | None = None
    temperature: float | None = None
    modalities: list[str] | None = None
    image_config: dict | None = None
    audio_config: dict | None = None
    response_format: dict | None = None
    metadata: dict | None = None
