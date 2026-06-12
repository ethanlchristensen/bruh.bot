from typing import Any, Literal

from pydantic import BaseModel

ChunkType = Literal[
    "text_delta",
    "reasoning_delta",
    "tool_call_delta",
    "tool_result",
    "image",
    "reasoning_image",
    "audio_delta",
    "usage",
    "done",
    "error",
]


class StreamChunk(BaseModel):
    type: ChunkType
    delta: str | None = None
    image_url: str | None = None
    audio_data: str | None = None
    transcript_delta: str | None = None
    tool_call: dict | None = None
    usage: dict[str, Any] | None = None
    actual_provider: str | None = None
    error: str | None = None
    metadata: dict | None = None
