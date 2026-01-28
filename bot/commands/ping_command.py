import discord
from discord import app_commands

from bot.utils.decarators.command_logging import log_command_usage
from bot.utils.decarators.global_block_check import is_globally_blocked


class PingCommand(app_commands.Command):
    def __init__(self, tree: app_commands.CommandTree, args=None):
        @tree.command(name="ping", description="Ping the bot to get it's latency.")
        @log_command_usage()
        @is_globally_blocked()
        async def ping(interaction: discord.Interaction):
            await interaction.response.send_message(f"Pong! {round(interaction.client.latency * 1000)}ms")
