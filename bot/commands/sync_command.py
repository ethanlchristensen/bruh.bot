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
                embed = interaction.client.embed_service.create_success_embed("Commands synced successfully.", title="Commands Synced")
                await interaction.followup.send(embed=embed, ephemeral=True, files=interaction.client.embed_service.get_brand_files(embed=embed))
            except Exception as e:
                embed = interaction.client.embed_service.create_error_embed(str(e))
                await interaction.followup.send(embed=embed, ephemeral=True, files=interaction.client.embed_service.get_brand_files(embed=embed))
