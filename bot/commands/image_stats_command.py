from typing import TYPE_CHECKING

import discord
from discord import app_commands

from bot.utils.decarators.command_logging import log_command_usage
from bot.utils.decarators.global_block_check import is_globally_blocked

if TYPE_CHECKING:
    from bot.juno import Juno


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

            try:
                bot: Juno = interaction.client
                stats = await bot.image_limit_service.get_user_stats(user_id=interaction.user.id, guild_id=interaction.guild.id)

                embed = discord.Embed(
                    title="📊 Image Generation Stats",
                    color=discord.Color.blue(),
                )

                embed.add_field(
                    name="Images Generated Today",
                    value=f"{stats['count']}/{stats['max_daily_images']}",
                    inline=True,
                )

                embed.add_field(name="Remaining", value=f"{stats['remaining']} images", inline=True)

                # Format reset time
                if stats["reset_time"]:
                    reset_time = stats["reset_time"]
                    if hasattr(reset_time, "strftime"):
                        reset_str = reset_time.strftime("%I:%M %p %Z")
                    else:
                        reset_str = str(reset_time)
                    embed.add_field(name="Resets At", value=reset_str, inline=False)

                embed.set_footer(text=f"Requested by {interaction.user.name}")

                await interaction.followup.send(embed=embed, ephemeral=True)

            except Exception as e:
                bot = interaction.client
                bot.logger.error(f"Error fetching image stats: {e}")
                await interaction.followup.send("Failed to retrieve image generation stats.", ephemeral=True)
