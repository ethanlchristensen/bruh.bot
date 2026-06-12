from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bot.juno import Juno

import discord
from discord import app_commands

from bot.services.ai.gateway.gateway import get_mesh_gateway
from bot.services.ai.gateway.schemas.request import Message, MessagePart, NormalizedRequest
from bot.utils.decarators.command_logging import log_command_usage
from bot.utils.decarators.global_block_check import is_globally_blocked


class ChatCommand(app_commands.Command):
    def __init__(self, tree: app_commands.CommandTree, args=None):
        @tree.command(name="chat", description="Command to chat will llms")
        @log_command_usage()
        @is_globally_blocked()
        async def chat(interaction: discord.Interaction, message: str):
            await interaction.response.defer(ephemeral=False)

            client: Juno = interaction.client
            config = (await client.config_service.get_config(str(interaction.guild.id))).aiConfig

            provider = config.preferredAiProvider
            provider_config = getattr(config, provider, None) or config.openrouter
            api_key = provider_config.get_api_key()
            preferred_model = provider_config.preferredModel

            # Construct gateway request
            req = NormalizedRequest(
                provider=provider,
                model=preferred_model,
                messages=[
                    Message(
                        role="user",
                        parts=[MessagePart(type="text", text=message)]
                    )
                ]
            )

            gateway = get_mesh_gateway()
            response = await gateway.complete(req, credentials={"api_key": api_key})
            content = "".join(part.content for part in response.parts if part.type == "text")

            await interaction.followup.send(content)
