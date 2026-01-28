import discord
from discord import app_commands

from bot.utils.decarators.admin_check import is_admin
from bot.utils.decarators.command_logging import log_command_usage
from bot.utils.decarators.global_block_check import is_globally_blocked


class SyncCommand(app_commands.Group):
    def __init__(self, tree: discord.app_commands.CommandTree, args=None):
        @tree.command(
            name="sync",
            description="Command to sync the slash commands with the guild.",
        )
        @log_command_usage()
        @is_admin()
        @is_globally_blocked()
        async def sync(interaction: discord.Interaction):
            try:
                await tree.sync()
                embed = discord.Embed()
                embed.color = 0x00FF00
                embed.title = "Command Tree synced!"
                embed.description = ""
                await interaction.followup.send(embed=embed, ephemeral=True)
            except Exception as e:
                embed = discord.Embed()
                embed.color = 0xFF0000
                embed.title = "Command Tree failed to sync!"
                embed.description = str(e)
                await interaction.followup.send(embed=embed, ephemeral=True)
