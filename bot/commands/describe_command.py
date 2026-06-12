import base64
import logging

import discord
from discord import app_commands
from pydantic import BaseModel, Field

from bot.services.ai.gateway.gateway import get_mesh_gateway
from bot.services.ai.gateway.schemas.request import Message, MessagePart, NormalizedRequest
from bot.utils.decarators.command_logging import log_command_usage
from bot.utils.decarators.global_block_check import is_globally_blocked

logger = logging.getLogger("bot")


class DescribeResponse(BaseModel):
    description1: str = Field(description="First description of the image in Midjourney style, detailing style, lighting, composition, and subject.")
    description2: str = Field(description="Second description of the image in a different style, prompt format.")
    description3: str = Field(description="Third description of the image focusing on mood, colors, and prompt descriptors.")
    description4: str = Field(description="Fourth description of the image, highly detailed Midjourney style prompt.")


class DescribeCommand:
    def __init__(self, tree: app_commands.CommandTree, args=None):
        @tree.command(name="describe", description="Generate 4 Midjourney-style prompt descriptions from an image.")
        @app_commands.describe(image="The image you want to describe.")
        @log_command_usage()
        @is_globally_blocked()
        async def describe(interaction: discord.Interaction, image: discord.Attachment):
            # Defer response since describing can take a while
            await interaction.response.defer()

            # Verify file is an image
            if not image.content_type or not image.content_type.startswith("image/"):
                await interaction.followup.send("Please upload a valid image file (PNG or JPEG).", ephemeral=True)
                return

            try:
                # Read image bytes and encode to base64
                image_bytes = await image.read()
                img_b64 = base64.b64encode(image_bytes).decode()
                data_url = f"data:{image.content_type};base64,{img_b64}"

                # Fetch AI config
                guild_id = str(interaction.guild_id) if interaction.guild_id else "default"
                config_service = interaction.client.config_service
                config = await config_service.get_config(guild_id)

                orchestrator_config = config.aiConfig.orchestrator
                ai_cfg = config.aiConfig

                provider = orchestrator_config.preferredAiProvider
                provider_config = getattr(ai_cfg, provider, None) or ai_cfg.openrouter
                api_key = provider_config.get_api_key()
                preferred_model = orchestrator_config.preferredModel or provider_config.preferredModel

                # Ensure model supports vision dynamically
                supports_vision = False
                gateway = get_mesh_gateway()
                try:
                    if provider == "ollama":
                        ollama_endpoint = getattr(provider_config, "endpoint", "http://localhost:11434")
                        models = await gateway.get_models("ollama", credentials={"endpoint": ollama_endpoint})
                    else:
                        models = await gateway.get_models("openrouter", credentials={"api_key": api_key})

                    model_info = next((m for m in models if m.id == preferred_model), None)
                    if model_info:
                        supports_vision = model_info.capabilities.vision
                except Exception as e:
                    logger.warning(f"Error fetching model list for vision check in describe command: {e}")

                # Fallback to string name check
                if not supports_vision:
                    model_lower = preferred_model.lower()
                    supports_vision = "gemini" in model_lower or "gpt-4o" in model_lower or "claude-3" in model_lower or "vision" in model_lower or "pixtral" in model_lower or "llava" in model_lower

                if not supports_vision:
                    logger.info(f"Orchestration model '{preferred_model}' does not support image input. Overriding to OpenRouter with 'google/gemini-3.1-flash-lite' for /describe command.")
                    provider = "openrouter"
                    provider_config = ai_cfg.openrouter
                    api_key = provider_config.get_api_key()
                    preferred_model = "google/gemini-3.1-flash-lite"

                # Define structured output format
                response_format = {"type": "json_schema", "json_schema": {"name": "DescribeResponse", "schema": DescribeResponse.model_json_schema()}}

                system_prompt = "You are a Midjourney prompt generation expert. Describe the uploaded image in 4 different distinct prompt styles. Return your response strictly conforming to the JSON schema."

                # Construct request
                req = NormalizedRequest(
                    provider=provider,
                    model=preferred_model,
                    messages=[
                        Message(role="system", parts=[MessagePart(type="text", text=system_prompt)]),
                        Message(role="user", parts=[MessagePart(type="text", text="Please generate 4 distinct Midjourney-style prompt descriptions for this image."), MessagePart(type="image", url=data_url)]),
                    ],
                    response_format=response_format,
                )

                response = await gateway.complete(req, credentials={"api_key": api_key})
                content = "".join(part.content for part in response.parts if part.type == "text")
                result = DescribeResponse.model_validate_json(content)

                # Create elegant embed
                embed = interaction.client.embed_service.create_success_embed(message=(f"1️⃣ {result.description1}\n\n2️⃣ {result.description2}\n\n3️⃣ {result.description3}\n\n4️⃣ {result.description4}"), title="🎨 Image Descriptions")
                embed.set_image(url=image.url)
                embed.set_footer(text=f"Described using {preferred_model} via {provider}")

                await _send_reply_or_followup(interaction, embed)

            except Exception as e:
                logger.error(f"Error executing /describe command: {e}", exc_info=True)
                embed_err = interaction.client.embed_service.create_error_embed(f"An error occurred while describing the image: {str(e)}")
                await _send_reply_or_followup(interaction, embed_err)


async def _send_reply_or_followup(interaction: discord.Interaction, embed: discord.Embed):
    if interaction.is_expired():
        # Session expired, send as channel message
        await interaction.channel.send(embed=embed)
    else:
        await interaction.followup.send(embed=embed)
