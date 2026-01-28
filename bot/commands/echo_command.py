import discord
from discord import app_commands

from bot.utils.decarators.admin_check import is_admin
from bot.utils.decarators.command_logging import log_command_usage
from bot.utils.decarators.global_block_check import is_globally_blocked


class EchoCommand(app_commands.Command):
    def __init__(self, tree: app_commands.CommandTree, args=None):
        @tree.command(
            name="echo",
            description="Send a message as the bot with optional attachment",
        )
        @log_command_usage()
        @is_admin()
        @is_globally_blocked()
        async def echo(
            interaction: discord.Interaction,
            message: str | None = None,
            attachment: discord.Attachment | None = None,
        ):
            channel = interaction.channel
            # Prevent error if both message and attachment are missing
            if not message and not attachment:
                await interaction.followup.send(
                    "You must provide either a message or an attachment.",
                    ephemeral=True,
                )
                return

            if attachment:
                await channel.send(content=message or "", file=await attachment.to_file())
            else:
                await channel.send(content=message)
