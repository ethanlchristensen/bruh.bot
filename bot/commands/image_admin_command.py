from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bot.bruh_bot import BruhBot

import discord
from discord import app_commands

from bot.utils.decarators.command_logging import log_command_usage
from bot.utils.decarators.global_block_check import is_globally_blocked


class ImageAdminCommand:
    def __init__(self, tree: app_commands.CommandTree, args=None):
        image_admin_group = app_commands.Group(
            name="image_admin",
            description="Admin commands for managing image generation limits",
            default_permissions=discord.Permissions(administrator=True),
        )

        @image_admin_group.command(
            name="reset_user",
            description="Reset image generation limit for a specific user",
        )
        @app_commands.describe(user="The user to reset limits for")
        @log_command_usage()
        @is_globally_blocked()
        async def reset_user(interaction: discord.Interaction, user: discord.User):
            """Reset a specific user's image generation limit."""
            await interaction.response.defer(ephemeral=True)

            bot: BruhBot = interaction.client

            try:
                bot.image_limit_service.reset_user(user_id=user.id, guild_id=interaction.guild.id)

                embed = interaction.client.embed_service.create_success_embed(f"Image generation limit has been reset for {user.mention}", title="User Limit Reset")

                await interaction.followup.send(embed=embed, ephemeral=True, files=interaction.client.embed_service.get_brand_files(embed=embed))

            except Exception as e:
                bot.logger.error(f"Error resetting user image limit: {e}")
                await interaction.followup.send("Failed to reset user image limit.", ephemeral=True)

        @image_admin_group.command(
            name="reset_all",
            description="Reset image generation limits for all users in this server",
        )
        @log_command_usage()
        @is_globally_blocked()
        async def reset_all(interaction: discord.Interaction):
            """Reset all users' image generation limits."""
            await interaction.response.defer(ephemeral=True)

            bot: BruhBot = interaction.client

            try:
                count = bot.image_limit_service.reset_all_users(guild_id=interaction.guild.id)

                embed = interaction.client.embed_service.create_success_embed(f"Image generation limits have been reset for {count} user(s)", title="All Limits Reset")

                await interaction.followup.send(embed=embed, ephemeral=True, files=interaction.client.embed_service.get_brand_files(embed=embed))

            except Exception as e:
                bot.logger.error(f"Error resetting all image limits: {e}")
                await interaction.followup.send("Failed to reset all image limits.", ephemeral=True)

        @image_admin_group.command(
            name="set_user_limit",
            description="Set the daily image generation limit for a specific user",
        )
        @app_commands.describe(user="The user to set the limit for", limit="The new maximum daily image limit for this user")
        @log_command_usage()
        @is_globally_blocked()
        async def set_user_limit(interaction: discord.Interaction, user: discord.User, limit: int):
            """Set the daily image generation limit for a specific user."""
            await interaction.response.defer(ephemeral=True)

            bot: BruhBot = interaction.client

            try:
                if limit < 1:
                    await interaction.followup.send("Limit must be at least 1.", ephemeral=True)
                    return

                success = bot.image_limit_service.set_user_limit(user.id, interaction.guild.id, limit)

                if success:
                    embed = interaction.client.embed_service.create_success_embed(f"Daily image limit for {user.mention} set to **{limit}** images", title="User Limit Updated")
                else:
                    embed = interaction.client.embed_service.create_error_embed(f"Failed to update limit for {user.mention}")

                await interaction.followup.send(embed=embed, ephemeral=True, files=interaction.client.embed_service.get_brand_files(embed=embed))

            except Exception as e:
                bot.logger.error(f"Error setting user image limit: {e}")
                await interaction.followup.send("Failed to set user image limit.", ephemeral=True)

        @image_admin_group.command(
            name="set_guild_limit",
            description="Set the daily image generation limit for all users in this server",
        )
        @app_commands.describe(limit="The new maximum daily image limit for all users")
        @log_command_usage()
        @is_globally_blocked()
        async def set_guild_limit(interaction: discord.Interaction, limit: int):
            """Set the daily image generation limit for all users in the guild."""
            await interaction.response.defer(ephemeral=True)

            bot: BruhBot = interaction.client

            try:
                if limit < 1:
                    await interaction.followup.send("Limit must be at least 1.", ephemeral=True)
                    return

                count = bot.image_limit_service.set_guild_limit(interaction.guild.id, limit)

                embed = interaction.client.embed_service.create_success_embed(f"Daily image limit set to **{limit}** for {count} user(s) in this server", title="Guild Limit Updated")
                embed.add_field(name="Note", value="New users will receive the default limit from config unless changed individually.", inline=False)

                await interaction.followup.send(embed=embed, ephemeral=True, files=interaction.client.embed_service.get_brand_files(embed=embed))

            except Exception as e:
                bot.logger.error(f"Error setting guild image limit: {e}")
                await interaction.followup.send("Failed to set guild image limit.", ephemeral=True)

        @image_admin_group.command(
            name="view_user_limit",
            description="View the daily image generation limit for a specific user",
        )
        @app_commands.describe(user="The user to check the limit for")
        @log_command_usage()
        @is_globally_blocked()
        async def view_user_limit(interaction: discord.Interaction, user: discord.User):
            """View the daily image generation limit for a specific user."""
            await interaction.response.defer(ephemeral=True)

            bot: BruhBot = interaction.client

            try:
                stats = bot.image_limit_service.get_user_stats(user.id, interaction.guild.id)
                user_limit = stats["max_daily_images"]
                count = stats["count"]
                remaining = stats["remaining"]

                embed = interaction.client.embed_service.create_info_embed(
                    title=f"Image Limit for {user.display_name}",
                    description=f"Current usage and limits for {user.mention}.",
                    fields=[
                        ("Daily Limit", str(user_limit), True),
                        ("Used Today", str(count), True),
                        ("Remaining", str(remaining), True),
                    ],
                )

                await interaction.followup.send(embed=embed, ephemeral=True, files=interaction.client.embed_service.get_brand_files(embed=embed))

            except Exception as e:
                bot.logger.error(f"Error viewing user image limit: {e}")
                await interaction.followup.send("Failed to view user image limit.", ephemeral=True)

        tree.add_command(image_admin_group)
