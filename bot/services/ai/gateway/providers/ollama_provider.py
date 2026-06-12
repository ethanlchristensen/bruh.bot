import json
from collections.abc import AsyncIterator

from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionChunk

from bot.services.ai.gateway.providers.base import ProviderAdapter
from bot.services.ai.gateway.schemas.chunks import StreamChunk
from bot.services.ai.gateway.schemas.models import ModelCapabilities, ModelInfo
from bot.services.ai.gateway.schemas.request import MessagePart, NormalizedRequest
from bot.services.ai.gateway.schemas.response import NormalizedResponse, ResponsePart
from bot.services.ai.gateway.utils import parse_data_url

_cached_models_by_endpoint: dict[str, list[ModelInfo]] = {}


class OllamaAdapter(ProviderAdapter):
    # Normalized -> OpenAI format
    def _build_messages(self, request: NormalizedRequest) -> list[dict]:
        result = []
        for msg in request.messages:
            # System messages are plain strings
            if msg.role == "system":
                result.append({"role": "system", "content": self._extract_text(msg.parts)})
                continue

            # Tool result messages map to role="tool"
            if msg.role == "tool":
                for part in msg.parts:
                    if part.type == "tool_result":
                        result.append(
                            {
                                "role": "tool",
                                "tool_call_id": part.tool_call_id,
                                "content": json.dumps(part.content),
                            }
                        )
                continue

            # User/assistant: may be multimodal
            content = self._build_content_blocks(msg.parts)
            openai_msg: dict = {"role": msg.role, "content": content}

            # Attach tool_calls array if assistant is calling tools
            tool_calls = self._extract_tool_calls(msg.parts)
            if tool_calls:
                openai_msg["tool_calls"] = tool_calls

            result.append(openai_msg)

        return result

    def _build_content_blocks(self, parts: list[MessagePart]) -> list[dict] | str:
        blocks = []
        for part in parts:
            if part.type == "text":
                blocks.append({"type": "text", "text": part.text})
            elif part.type == "image":
                blocks.append(
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": part.url,
                            "detail": part.detail or "auto",
                        },
                    }
                )
            elif part.type == "audio":
                parsed = parse_data_url(part.url)
                if parsed:
                    mime_type, b64_data = parsed
                    format_ext = mime_type.split("/")[-1] if mime_type else "wav"
                    if format_ext == "mpeg":
                        format_ext = "mp3"
                    blocks.append(
                        {
                            "type": "input_audio",
                            "input_audio": {
                                "data": b64_data,
                                "format": format_ext,
                            },
                        }
                    )
            elif part.type == "file":
                blocks.append(
                    {
                        "type": "file",
                        "file": {"file_id": part.file_id},
                    }
                )

        if len(blocks) == 1 and blocks[0]["type"] == "text":
            return blocks[0]["text"]
        return blocks

    def _extract_text(self, parts: list[MessagePart]) -> str:
        return " ".join(p.text for p in parts if p.type == "text" and p.text)

    def _extract_tool_calls(self, parts: list[MessagePart]) -> list[dict]:
        calls = []
        for part in parts:
            if part.type == "tool_call":
                calls.append(
                    {
                        "id": part.tool_call_id,
                        "type": "function",
                        "function": {
                            "name": part.name,
                            "arguments": json.dumps(part.arguments),
                        },
                    }
                )
        return calls

    def _build_tools(self, request: NormalizedRequest) -> list[dict]:
        return [
            {
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool.get("description", ""),
                    "parameters": tool.get("parameters", {}),
                },
            }
            for tool in request.tools
        ]

    def _build_kwargs(self, request: NormalizedRequest) -> dict:
        kwargs: dict = {"model": request.model, "messages": self._build_messages(request)}
        if request.max_tokens:
            kwargs["max_completion_tokens"] = request.max_tokens
        if request.temperature is not None:
            kwargs["temperature"] = request.temperature
        if request.tools:
            kwargs["tools"] = self._build_tools(request)
            kwargs["tool_choice"] = "auto"

        if request.modalities:
            kwargs["modalities"] = request.modalities

        if request.audio_config:
            kwargs["audio"] = request.audio_config

        if request.response_format:
            kwargs["response_format"] = request.response_format

        if request.image_config:
            img_cfg = {**request.image_config}
            kwargs["image_config"] = img_cfg
            kwargs.update(img_cfg)

        if request.model.startswith("o"):
            kwargs.pop("temperature", None)
        return kwargs

    def _chunk_to_normalized(self, chunk: ChatCompletionChunk) -> StreamChunk | None:
        if not chunk.choices:
            if chunk.usage:
                return StreamChunk(
                    type="usage",
                    usage={
                        "input_tokens": chunk.usage.prompt_tokens,
                        "output_tokens": chunk.usage.completion_tokens,
                    },
                )
            return None

        choice = chunk.choices[0]
        delta = choice.delta

        if delta.content:
            return StreamChunk(type="text_delta", delta=delta.content)

        if delta.tool_calls:
            tc = delta.tool_calls[0]
            return StreamChunk(
                type="tool_call_delta",
                tool_call={
                    "index": tc.index,
                    "id": tc.id,
                    "name": tc.function.name if tc.function else None,
                    "arguments_delta": tc.function.arguments if tc.function else None,
                },
            )

        if choice.finish_reason in ("stop", "length", "tool_calls", "content_filter"):
            return StreamChunk(type="done")

        return None

    def _response_to_normalized(self, response, request: NormalizedRequest) -> NormalizedResponse:
        choice = response.choices[0]
        msg = choice.message
        parts: list[ResponsePart] = []

        if hasattr(msg, "reasoning_content") and msg.reasoning_content:
            parts.append(ResponsePart(type="reasoning", content=msg.reasoning_content))

        if msg.content:
            parts.append(ResponsePart(type="text", content=msg.content))

        for tc in msg.tool_calls or []:
            parts.append(
                ResponsePart(
                    type="tool_call",
                    content={
                        "id": tc.id,
                        "name": tc.function.name,
                        "arguments": json.loads(tc.function.arguments),
                    },
                )
            )

        return NormalizedResponse(
            id=response.id,
            role="assistant",
            parts=parts,
            usage={
                "input_tokens": response.usage.prompt_tokens,
                "output_tokens": response.usage.completion_tokens,
            },
            provider="ollama",
            model=response.model,
            canonical_model=request.model,
        )

    def _get_client(self, api_key: str) -> AsyncOpenAI:
        base_url = api_key
        if base_url:
            if not base_url.startswith("http://") and not base_url.startswith("https://"):
                base_url = "http://" + base_url
            if not base_url.endswith("/v1") and not base_url.endswith("/v1/"):
                base_url = base_url.rstrip("/") + "/v1"
        return AsyncOpenAI(api_key="ollama", base_url=base_url)

    # Public Interfaces
    async def stream(self, request: NormalizedRequest, api_key: str) -> AsyncIterator[StreamChunk]:
        client = self._get_client(api_key)
        kwargs = self._build_kwargs(request)

        stream = await client.chat.completions.create(
            **kwargs,
            stream=True,
            stream_options={"include_usage": True},
        )

        async for chunk in stream:
            normalized = self._chunk_to_normalized(chunk)
            if normalized:
                yield normalized

    async def complete(self, request: NormalizedRequest, api_key: str) -> NormalizedResponse:
        client = self._get_client(api_key)
        kwargs = self._build_kwargs(request)

        response = await client.chat.completions.create(**kwargs)
        return self._response_to_normalized(response, request)

    async def get_models(self, api_key: str) -> list[ModelInfo]:
        endpoint = api_key
        if not endpoint:
            return []

        if not endpoint.startswith("http://") and not endpoint.startswith("https://"):
            endpoint = "http://" + endpoint
        endpoint = endpoint.rstrip("/")

        cache_key = endpoint
        global _cached_models_by_endpoint
        if cache_key in _cached_models_by_endpoint:
            return _cached_models_by_endpoint[cache_key]

        try:
            import logging

            import httpx
            prov_logger = logging.getLogger("api.config")

            async with httpx.AsyncClient() as client:
                resp = await client.get(f"{endpoint}/api/tags", timeout=5.0)
                resp.raise_for_status()
                data = resp.json()

                models = []
                for m in data.get("models", []):
                    model_name = m.get("name")
                    is_reasoning = any(p in model_name.lower() for p in ["thinking", "reasoning", "deepseek-r1"])
                    models.append(
                        ModelInfo(
                            id=model_name,
                            canonical_id=model_name,
                            display_name=model_name,
                            provider="ollama",
                            context_window=None,
                            max_output_tokens=None,
                            capabilities=ModelCapabilities(
                                streaming=True,
                                tools=True,
                                vision=True,
                                reasoning=is_reasoning,
                                json_mode=True,
                            ),
                        )
                    )

                models_sorted = sorted(models, key=lambda m: m.id)
                _cached_models_by_endpoint[cache_key] = models_sorted
                return models_sorted
        except Exception as e:
            prov_logger.warning(f"Error fetching native Ollama models from {endpoint}: {e}")
            return []
