import discord
from discord import app_commands

from bot.utils.decarators.command_logging import log_command_usage
from bot.utils.decarators.global_block_check import is_globally_blocked


class PingCommand:
    def __init__(self, tree: app_commands.CommandTree, args=None):
        @tree.command(name="ping", description="Ping the bot to get it's latency.")
        @log_command_usage()
        @is_globally_blocked()
        async def ping(interaction: discord.Interaction):
            latency = round(interaction.client.latency * 1000)
            embed = interaction.client.embed_service.create_success_embed(f"📡 Signal Latency: **{latency}ms**", title="Pong!")
            await interaction.response.send_message(embed=embed)
