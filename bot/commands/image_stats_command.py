from typing import TYPE_CHECKING

import discord
from discord import app_commands

from bot.utils.decarators.command_logging import log_command_usage
from bot.utils.decarators.global_block_check import is_globally_blocked

if TYPE_CHECKING:
    from bot.bruh_bot import BruhBot


class ImageStatsCommand:
    def __init__(self, tree: app_commands.CommandTree, args=None):
        @tree.command(
            name="image_stats",
            description="Check your remaining daily image generation limit",
        )
        @log_command_usage()
        @is_globally_blocked()
        async def image_stats(interaction: discord.Interaction):
            """Check the user's image generation stats."""
            await interaction.response.defer(ephemeral=True)

            bot: BruhBot = interaction.client

            try:
                stats = await bot.image_limit_service.get_user_stats(user_id=interaction.user.id, guild_id=interaction.guild.id)

                embed = interaction.client.embed_service.create_info_embed(
                    title="Image Generation Stats",
                    description="Your daily usage for this server.",
                    fields=[
                        ("Images Generated Today", f"{stats['count']}/{stats['max_daily_images']}", True),
                        ("Remaining", f"{stats['remaining']} images", True),
                    ],
                )

                if stats["reset_time"]:
                    reset_time = stats["reset_time"]
                    if hasattr(reset_time, "strftime"):
                        reset_str = reset_time.strftime("%I:%M %p %Z")
                    else:
                        reset_str = str(reset_time)
                    embed.add_field(name="Resets At", value=reset_str, inline=False)

                await interaction.followup.send(embed=embed, ephemeral=True, files=interaction.client.embed_service.get_brand_files(embed=embed))

            except Exception as e:
                bot.logger.error(f"Error fetching image stats: {e}")
                await interaction.followup.send("Failed to retrieve image generation stats.", ephemeral=True)
