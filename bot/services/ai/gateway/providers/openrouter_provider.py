import json
from collections.abc import AsyncIterator

import httpx

from bot.services.ai.gateway.exceptions import ProviderAPIError
from bot.services.ai.gateway.providers.ollama_provider import OllamaAdapter
from bot.services.ai.gateway.schemas.chunks import StreamChunk
from bot.services.ai.gateway.schemas.models import ModelCapabilities, ModelInfo
from bot.services.ai.gateway.schemas.request import NormalizedRequest
from bot.services.ai.gateway.schemas.response import NormalizedResponse, ResponsePart

_cached_models: list[ModelInfo] | None = None


class OpenRouterAdapter(OllamaAdapter):
    def __init__(self):
        super().__init__()
        self.base_url = "https://openrouter.ai/api/v1"

    def _get_headers(self, api_key: str) -> dict:
        return {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "X-Title": "bruh.bot",
        }

    def _extract_error_message(self, body: str) -> str:
        """Pull the human-readable message out of an OpenRouter error body."""
        try:
            data = json.loads(body)
            err = data.get("error")
            if isinstance(err, dict):
                return err.get("message") or json.dumps(err)
            if isinstance(err, str):
                return err
            return body or "Unknown error"
        except (json.JSONDecodeError, TypeError):
            return body or "Unknown error"

    async def stream(self, request: NormalizedRequest, api_key: str) -> AsyncIterator[StreamChunk]:
        url = f"{self.base_url}/chat/completions"
        payload = self._build_kwargs(request)
        payload["stream"] = True
        # OpenRouter-specific stream options if needed
        payload["stream_options"] = {"include_usage": True}

        async with httpx.AsyncClient(http2=True) as client:
            async with client.stream(
                "POST", url, json=payload, headers=self._get_headers(api_key), timeout=60.0
            ) as response:
                if response.is_error:
                    body = (await response.aread()).decode(errors="replace")
                    raise ProviderAPIError(
                        "openrouter",
                        self._extract_error_message(body),
                        status_code=response.status_code,
                    )
                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue

                    data_str = line[6:].strip()
                    if data_str == "[DONE]":
                        break

                    try:
                        data = json.loads(data_str)

                        returned_model = data.get("model")
                        actual_provider = None
                        if returned_model:
                            actual_provider = (
                                returned_model.split("/")[0]
                                if "/" in returned_model
                                else "openrouter"
                            )

                        # Handle usage/cost chunk
                        usage = data.get("usage")
                        if usage:
                            yield StreamChunk(
                                type="usage",
                                usage={
                                    "input_tokens": usage.get("prompt_tokens", 0),
                                    "output_tokens": usage.get("completion_tokens", 0),
                                    "cost": usage.get("cost", 0),
                                    "extra": usage,  # Keep everything else
                                },
                                actual_provider=actual_provider,
                            )
                            if not data.get("choices"):
                                continue

                        if not data.get("choices"):
                            continue

                        choice = data["choices"][0]
                        delta = choice.get("delta", {})
                        # Some providers might send 'message' in stream on the last chunk
                        msg_data = choice.get("message", {})

                        content = delta.get("content") or msg_data.get("content")
                        if content:
                            yield StreamChunk(
                                type="text_delta",
                                delta=content,
                                actual_provider=actual_provider,
                            )

                        audio = delta.get("audio") or msg_data.get("audio") or {}
                        if isinstance(audio, dict):
                            if audio.get("data"):
                                yield StreamChunk(
                                    type="audio_delta",
                                    audio_data=audio["data"],
                                    actual_provider=actual_provider,
                                )
                            if audio.get("transcript"):
                                yield StreamChunk(
                                    type="text_delta",
                                    delta=audio["transcript"],
                                    actual_provider=actual_provider,
                                )

                        if delta.get("reasoning"):
                            yield StreamChunk(
                                type="reasoning_delta",
                                delta=delta["reasoning"],
                                actual_provider=actual_provider,
                            )
                        elif delta.get("reasoning_content"):
                            yield StreamChunk(
                                type="reasoning_delta",
                                delta=delta["reasoning_content"],
                                actual_provider=actual_provider,
                            )

                        # Handle streaming images (OpenRouter multimodal)
                        if "images" in delta and delta["images"]:
                            for img_data in delta["images"]:
                                img_url = img_data.get("image_url", {}).get("url")
                                if img_url:
                                    # Detect if it's a reasoning image (usually inside reasoning_details in some versions)
                                    is_reasoning_img = "reasoning_details" in delta
                                    yield StreamChunk(
                                        type="reasoning_image" if is_reasoning_img else "image",
                                        image_url=img_url,
                                        actual_provider=actual_provider,
                                    )

                        if choice.get("finish_reason"):
                            yield StreamChunk(type="done", actual_provider=actual_provider)

                    except json.JSONDecodeError:
                        continue

    async def complete(self, request: NormalizedRequest, api_key: str) -> NormalizedResponse:
        # Check if the request contains audio modality (OpenRouter requires stream: True for audio output)
        if request.modalities and "audio" in request.modalities:
            # Aggregate stream chunks under the hood
            text_content = ""
            reasoning_content = ""
            images = []
            audio_data = ""
            usage = {}
            actual_provider = "openrouter"

            async for chunk in self.stream(request, api_key=api_key):
                if chunk.type == "text_delta" and chunk.delta:
                    text_content += chunk.delta
                elif chunk.type == "reasoning_delta" and chunk.delta:
                    reasoning_content += chunk.delta
                elif chunk.type == "image" and chunk.image_url:
                    images.append(chunk.image_url)
                elif chunk.type == "audio_delta" and chunk.audio_data:
                    audio_data += chunk.audio_data
                elif chunk.type == "usage" and chunk.usage:
                    usage = chunk.usage
                if chunk.actual_provider:
                    actual_provider = chunk.actual_provider

            parts = []
            if reasoning_content:
                parts.append(ResponsePart(type="reasoning", content=reasoning_content))
            if text_content:
                parts.append(ResponsePart(type="text", content=text_content))
            for img in images:
                parts.append(ResponsePart(type="image", content=img))
            if audio_data:
                # Format base64 audio with correct data url prefix
                if not audio_data.startswith("data:"):
                    audio_data = f"data:audio/wav;base64,{audio_data}"
                parts.append(ResponsePart(type="audio", content=audio_data))

            # Normalize usage format
            normalized_usage = (
                {
                    "input_tokens": usage.get("input_tokens", 0),
                    "output_tokens": usage.get("output_tokens", 0),
                    "cost": usage.get("cost", 0),
                    "extra": usage,
                }
                if usage
                else None
            )

            return NormalizedResponse(
                id="aggr-" + request.model,
                role="assistant",
                parts=parts,
                usage=normalized_usage,
                provider="openrouter",
                actual_provider=actual_provider,
                model=request.model,
                canonical_model=request.model,
            )

        url = f"{self.base_url}/chat/completions"
        payload = self._build_kwargs(request)

        async with httpx.AsyncClient(http2=True) as client:
            response = await client.post(
                url, json=payload, headers=self._get_headers(api_key), timeout=60.0
            )
            if response.is_error:
                raise ProviderAPIError(
                    "openrouter",
                    self._extract_error_message(response.text),
                    status_code=response.status_code,
                )
            data = response.json()

            choice = data["choices"][0]
            msg = choice["message"]
            parts = []

            reasoning = msg.get("reasoning") or msg.get("reasoning_content")
            if reasoning:
                parts.append(ResponsePart(type="reasoning", content=reasoning))

            if msg.get("content"):
                parts.append(ResponsePart(type="text", content=msg["content"]))

            # Handle potential multimodal output (OpenRouter specific)
            if isinstance(msg.get("content"), list):
                for part in msg["content"]:
                    if isinstance(part, dict):
                        if part.get("type") == "image_url":
                            parts.append(
                                ResponsePart(type="image", content=part["image_url"]["url"])
                            )
                        elif part.get("type") == "text":
                            parts.append(ResponsePart(type="text", content=part["text"]))

            # Parse markdown image links from text content just in case
            if msg.get("content") and isinstance(msg.get("content"), str):
                import re

                md_images = re.findall(r"!\[.*?\]\((.*?)\)", msg["content"])
                for img_url in md_images:
                    parts.append(ResponsePart(type="image", content=img_url))

            # Handle direct "images" key in message, choice, or root response (common in OpenRouter image models)
            images_list = msg.get("images") or choice.get("images") or data.get("images")
            if isinstance(images_list, list):
                for img in images_list:
                    if isinstance(img, str):
                        parts.append(ResponsePart(type="image", content=img))
                    elif isinstance(img, dict):
                        url = (
                            img.get("url")
                            or img.get("image_url", {}).get("url")
                            or img.get("b64_json")
                        )
                        if url:
                            parts.append(ResponsePart(type="image", content=url))

            # Handle OpenRouter/OpenAI audio output in non-streaming
            audio = msg.get("audio")
            if isinstance(audio, dict) and audio.get("data"):
                audio_data = audio["data"]
                if not audio_data.startswith("data:"):
                    audio_data = f"data:audio/wav;base64,{audio_data}"
                parts.append(ResponsePart(type="audio", content=audio_data))

            usage = data.get("usage", {})
            normalized_usage = {
                "input_tokens": usage.get("prompt_tokens", 0),
                "output_tokens": usage.get("completion_tokens", 0),
                "cost": usage.get("cost", 0),
                "extra": usage,
            }

            returned_model = data.get("model", request.model)
            actual_provider = (
                returned_model.split("/")[0] if "/" in returned_model else "openrouter"
            )

            return NormalizedResponse(
                id=data.get("id", ""),
                role="assistant",
                parts=parts,
                usage=normalized_usage,
                provider="openrouter",
                actual_provider=actual_provider,
                model=returned_model,
                canonical_model=request.model,
            )

    async def get_models(self, api_key: str) -> list[ModelInfo]:
        global _cached_models
        if _cached_models:
            return _cached_models

        headers = {
            "Authorization": f"Bearer {api_key}",
            "HTTP-Referer": "https://mesh.etchris.dev",
            "X-Title": "Mesh",
        }
        async with httpx.AsyncClient(http2=True) as client:
            try:
                resp = await client.get(f"{self.base_url}/models", headers=headers, timeout=10.0)
                resp.raise_for_status()
                data = resp.json().get("data", [])

                models = []
                for m in data:
                    # Map OpenRouter capabilities
                    params = m.get("supported_parameters", [])
                    architecture = m.get("architecture", {})
                    input_mods = architecture.get("input_modalities", [])
                    output_mods = architecture.get("output_modalities", [])
                    top_provider = m.get("top_provider", {})

                    # Detection based on modalities and params
                    has_vision = "image" in input_mods
                    has_tools = "tools" in params or "function_calling" in params
                    # Support both explicit param and name-based reasoning detection
                    is_reasoning = (
                        "reasoning" in params
                        or "include_reasoning" in params
                        or "reasoning" in m.get("name", "").lower()
                        or "thought" in m.get("name", "").lower()
                    )

                    caps = ModelCapabilities(
                        streaming=True,
                        tools=has_tools,
                        vision=has_vision,
                        reasoning=is_reasoning,
                        json_mode="structured_outputs" in params or "response_format" in params,
                        image_gen="image" in output_mods,
                        pdf="file" in input_mods or "pdf" in input_mods,
                        audio_input="audio" in input_mods,
                        audio_output="audio" in output_mods,
                        video_input="video" in input_mods,
                        video_output="video" in output_mods,
                    )

                    # Extract actual provider from ID (e.g. "anthropic/claude-3")
                    actual_provider = m["id"].split("/")[0] if "/" in m["id"] else "openrouter"

                    models.append(
                        ModelInfo(
                            id=m["id"],
                            canonical_id=m["id"],
                            display_name=m.get("name", m["id"]),
                            provider="openrouter",
                            actual_provider=actual_provider,
                            capabilities=caps,
                            context_window=m.get("context_length"),
                            max_output_tokens=top_provider.get("max_completion_tokens"),
                            description=m.get("description"),
                            pricing=m.get("pricing"),
                            knowledge_cutoff=m.get("knowledge_cutoff"),
                            created_at=m.get("created"),
                        )
                    )

                sorted_models = sorted(models, key=lambda x: x.id)
                _cached_models = sorted_models
                return sorted_models
            except Exception:
                return []
