import os
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import discord
import pytz
from discord import app_commands
from discord.ext import commands, tasks

from bot.services.ai.types import Message
from bot.services.mongo_morning_config_service import MongoMorningConfigService
from bot.utils.decarators.admin_check import is_admin
from bot.utils.decarators.command_logging import log_command_usage
from bot.utils.decarators.global_block_check import is_globally_blocked

if TYPE_CHECKING:
    from bot.juno import Juno


class SchedulerCog(commands.Cog):
    def __init__(self, bot: "Juno"):
        self.bot = bot
        self.morning_config_service = MongoMorningConfigService(bot)
        self.bot.loop.create_task(self.morning_config_service.initialize())
        self.check.start()

    def cog_unload(self):
        self.check.cancel()

    @tasks.loop(seconds=30)
    async def check(self):
        """Check each guild's configured time and send messages when appropriate"""
        morning_configs = await self.morning_config_service.get_all_configs()
        if not morning_configs:
            return

        now_utc = datetime.now(UTC)

        for guild_id, config in morning_configs.items():
            try:
                # Get the configured time in the configured timezone
                guild_tz = config.get("timezone", "UTC")
                try:
                    tz = pytz.timezone(guild_tz)
                except pytz.exceptions.UnknownTimeZoneError:
                    self.bot.logger.warning(f"Unknown timezone for guild {guild_id}: {guild_tz}, defaulting to UTC")
                    tz = pytz.UTC

                # Get current time in the guild's timezone
                now_in_guild_tz = now_utc.astimezone(tz)

                # Check if we already sent a message today
                last_sent = config.get("last_sent_date")
                today = now_in_guild_tz.date().isoformat()

                if last_sent == today:
                    # Already sent today, skip
                    continue

                # Check if it's time to send the message
                if now_in_guild_tz.hour == config.get("hour", 12) and now_in_guild_tz.minute < config.get("minute", 0) + 1:  # 1-minute window to account for loop interval
                    channel_id = config.get("channel_id")
                    if not channel_id:
                        continue

                    guild = self.bot.get_guild(int(guild_id))
                    if not guild:
                        self.bot.logger.warning(f"Could not find guild with ID {guild_id}")
                        continue

                    channel = guild.get_channel(int(channel_id))
                    if not channel:
                        self.bot.logger.warning(f"Could not find channel {channel_id} in guild {guild.name}")
                        continue

                    # Get per-guild services and config
                    services = await self.bot.get_guild_services(guild_id)
                    ai_service = services["ai_service"]
                    guild_dynamic_config = await self.bot.config_service.get_config(guild_id)
                    prompts = self.bot.get_prompts(guild_dynamic_config.promptsPath)

                    # Generate motivational message
                    messages = [
                        Message(
                            role="user",
                            content="Generate a motivational morning message for a server or users. Feel free to thrown on curve ball quotes that don't really make sense.",
                        ),
                    ]

                    if main_prompt := prompts.get("main"):
                        self.bot.logger.info(f"Using main prompt for morning message in guild {guild.name}")
                        main_prompt = main_prompt.replace("{{BOTNAME}}", self.bot.user.name)
                        messages.insert(0, Message(role="system", content=main_prompt))

                    response = await ai_service.chat(messages=messages)

                    embed, emoji_file = self.bot.embed_service.create_morning_embed(message=response.content)
                    await channel.send(
                        embed=embed,
                        file=discord.File(os.path.join(os.getcwd(), "emojis", emoji_file), emoji_file),
                    )

                    # Mark as sent today
                    await self.morning_config_service.update_last_sent_date(guild_id, today)

                    self.bot.logger.info(f"Sent morning message to {channel.name} in {guild.name}")
            except Exception as e:
                self.bot.logger.error(f"Error sending morning message to guild {guild_id}: {e}")

    @check.before_loop
    async def before_check(self):
        await self.bot.wait_until_ready()

    @app_commands.command(
        name="set_morning_channel",
        description="Set the morning message channel for this server",
    )
    @app_commands.describe(channel="The channel where morning messages will be sent (defaults to current channel)")
    @log_command_usage()
    @is_admin()
    @is_globally_blocked()
    async def set_morning_channel(self, interaction: discord.Interaction, channel: discord.TextChannel = None):
        """Set the morning message channel for this guild"""
        if channel is None:
            channel = interaction.channel

        # Set channel using MongoDB service
        config = await self.morning_config_service.set_channel(interaction.guild.id, channel.id)

        timezone = config.get("timezone", "UTC")
        await interaction.followup.send(
            content=f"Morning messages will be sent to {channel.mention} at {config['hour']}:{config['minute']:02d} {timezone}",
            ephemeral=True,
        )

        self.bot.logger.info(f"Set morning channel for {interaction.guild.name} to {channel.name}")

    @app_commands.command(
        name="set_morning_time",
        description="Set the time for morning messages",
    )
    @app_commands.describe(
        hour="Hour (0-23)",
        minute="Minute (0-59)",
        timezone="Timezone (e.g., 'US/Eastern', 'Europe/London', defaults to UTC)",
    )
    @log_command_usage()
    @is_admin()
    @is_globally_blocked()
    async def set_morning_time(
        self,
        interaction: discord.Interaction,
        hour: int,
        minute: int = 0,
        timezone: str = "UTC",
    ):
        """Set the time for morning messages"""
        # Validate input
        if hour < 0 or hour > 23:
            await interaction.followup.send(content="Hour must be between 0 and 23.", ephemeral=True)
            return

        if minute < 0 or minute > 59:
            await interaction.followup.send(content="Minute must be between 0 and 59.", ephemeral=True)
            return

        # Validate timezone
        try:
            pytz.timezone(timezone)
        except pytz.exceptions.UnknownTimeZoneError:
            await interaction.followup.send(
                content=f"Unknown timezone: '{timezone}'. Please use a valid timezone like 'US/Eastern' or 'Europe/London'.",
                ephemeral=True,
            )
            return

        # Set time using MongoDB service
        config = await self.morning_config_service.set_time(interaction.guild.id, hour, minute, timezone)

        # Format response based on whether channel is set
        if "channel_id" in config and config["channel_id"]:
            channel = interaction.guild.get_channel(config["channel_id"])
            channel_mention = channel.mention if channel else "unknown channel"
            await interaction.followup.send(
                content=f"Morning messages will be sent to {channel_mention} at {hour}:{minute:02d} {timezone}",
                ephemeral=True,
            )
        else:
            await interaction.followup.send(
                content=f"Morning message time set to {hour}:{minute:02d} {timezone}, but no channel has been set yet. Use /set_morning_channel to complete setup.",
                ephemeral=True,
            )

        self.bot.logger.info(f"Set morning time for {interaction.guild.name} to {hour}:{minute:02d} {timezone}")

    @app_commands.command(
        name="remove_morning_channel",
        description="Remove morning messages for this server",
    )
    @log_command_usage()
    @is_admin()
    @is_globally_blocked()
    async def remove_morning_channel(self, interaction: discord.Interaction):
        """Remove morning messages for this guild"""
        removed = await self.morning_config_service.remove_config(interaction.guild.id)
        if removed:
            await interaction.followup.send(content="Morning messages disabled for this server.", ephemeral=True)
        else:
            await interaction.followup.send(
                content="Morning messages are not configured for this server.",
                ephemeral=True,
            )

    @app_commands.command(name="test_morning", description="Test the morning message functionality")
    @log_command_usage()
    @is_admin()
    @is_globally_blocked()
    async def test_morning_message(self, interaction: discord.Interaction):
        """Test the morning message functionality"""
        await interaction.followup.send(content="Sending test morning message...", ephemeral=True)

        try:
            guild_id = str(interaction.guild.id)
            services = await self.bot.get_guild_services(guild_id)
            ai_service = services["ai_service"]
            guild_dynamic_config = await self.bot.config_service.get_config(guild_id)
            prompts = self.bot.get_prompts(guild_dynamic_config.promptsPath)

            # Generate motivational message
            messages = [
                Message(
                    role="user",
                    content="Generate a motivational morning message (or un-motivational). You must be UNHINGED. Throw curve balls, odd ball quotes, etc!",
                ),
            ]

            if main_prompt := prompts.get("main"):
                self.bot.logger.info("Using main prompt for morning message")
                messages.insert(0, Message(role="system", content=main_prompt))

            response = await ai_service.chat(messages=messages)

            embed, emoji_file = self.bot.embed_service.create_morning_embed(message=response.content)

            await interaction.channel.send(
                embed=embed,
                file=discord.File(os.path.join(os.getcwd(), "emojis", emoji_file), emoji_file),
            )
            self.bot.logger.info(f"Sent test morning message to {interaction.channel.name} in {interaction.guild.name}")

        except Exception as e:
            await interaction.followup.send(f"Error testing morning message: {e}")
            self.bot.logger.error(f"Error in test morning message: {e}")

    @app_commands.command(
        name="list_timezones",
        description="List available timezones for morning message scheduling",
    )
    @log_command_usage()
    @is_admin()
    @is_globally_blocked()
    async def list_timezones(self, interaction: discord.Interaction):
        """List common timezones that can be used"""
        common_timezones = [
            "UTC",
            "US/Eastern",
            "US/Central",
            "US/Mountain",
            "US/Pacific",
            "Europe/London",
            "Europe/Berlin",
            "Europe/Moscow",
            "Asia/Tokyo",
            "Asia/Shanghai",
            "Australia/Sydney",
            "Pacific/Auckland",
        ]

        timezone_text = "**Available Timezones:**\n" + "\n".join(common_timezones)
        timezone_text += "\n\nFor a full list of timezones, see: https://en.wikipedia.org/wiki/List_of_tz_database_time_zones"

        await interaction.followup.send(content=timezone_text, ephemeral=True)


async def setup(bot: "Juno"):
    await bot.add_cog(SchedulerCog(bot))
