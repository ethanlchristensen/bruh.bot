from pydantic import BaseModel


class ModelCapabilities(BaseModel):
    streaming: bool = True
    tools: bool = False
    vision: bool = False
    reasoning: bool = False
    json_mode: bool = False
    image_gen: bool = False
    pdf: bool = False
    audio_input: bool = False
    audio_output: bool = False
    video_input: bool = False
    video_output: bool = False


class ModelInfo(BaseModel):
    id: str
    canonical_id: str
    display_name: str | None = None
    provider: str
    actual_provider: str | None = None
    capabilities: ModelCapabilities
    context_window: int | None = None
    max_output_tokens: int | None = None
    description: str | None = None
    pricing: dict[str, str] | None = None
    knowledge_cutoff: str | None = None
    created_at: int | None = None
