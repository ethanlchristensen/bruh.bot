import discord
from discord import app_commands

from bot.services import AIChatResponse, Message
from bot.utils.decarators.command_logging import log_command_usage
from bot.utils.decarators.global_block_check import is_globally_blocked


class ChatCommand(app_commands.Command):
    def __init__(self, tree: app_commands.CommandTree, args=None):
        @tree.command(name="chat", description="Command to chat will llms")
        @log_command_usage()
        @is_globally_blocked()
        async def chat(interaction: discord.Interaction, message: str):
            await interaction.response.defer(ephemeral=False)

            response: AIChatResponse = await interaction.client.ai_service.chat(messages=[Message(role="user", content=message)])

            await interaction.followup.send(response.content)
