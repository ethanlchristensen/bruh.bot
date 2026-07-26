from datetime import UTC, date, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bot.bruh_bot import BruhBot

import discord
from discord import app_commands

from bot.utils.decarators.command_logging import log_command_usage
from bot.utils.decarators.global_block_check import is_globally_blocked


class SetUserLimitsModal(discord.ui.Modal, title="Set AI Usage Limits for User"):
    def __init__(self, user: discord.User, guild_id: int, usage_service):
        super().__init__()
        self.target_user = user
        self.guild_id = guild_id
        self.usage_service = usage_service

    per_minute = discord.ui.TextInput(
        label="Max Requests Per Minute",
        placeholder="5",
        default="5",
        required=True,
        min_length=1,
        max_length=4,
    )

    per_hour = discord.ui.TextInput(
        label="Max Requests Per Hour",
        placeholder="50",
        default="50",
        required=True,
        min_length=1,
        max_length=5,
    )

    async def on_submit(self, interaction: discord.Interaction):
        try:
            per_minute = int(self.per_minute.value)
            per_hour = int(self.per_hour.value)
        except ValueError:
            await interaction.response.send_message("Please enter valid numbers.", ephemeral=True)
            return

        if per_minute < 1 or per_hour < 1:
            await interaction.response.send_message("Limits must be at least 1.", ephemeral=True)
            return

        success = await self.usage_service.set_user_limits(self.target_user.id, self.guild_id, per_minute, per_hour)

        if success:
            embed = interaction.client.embed_service.create_success_embed(
                f"AI usage limits set for {self.target_user.mention}:\n- **{per_minute}** requests per minute\n- **{per_hour}** requests per hour",
                title="User AI Limits Updated",
            )
            await interaction.response.send_message(embed=embed, ephemeral=True, files=interaction.client.embed_service.get_brand_files(embed=embed))
        else:
            await interaction.response.send_message(f"Failed to update limits for {self.target_user.mention}.", ephemeral=True)


class SetGuildLimitsModal(discord.ui.Modal, title="Set Guild AI Usage Limits"):
    def __init__(self, guild_id: int, usage_service):
        super().__init__()
        self.guild_id = guild_id
        self.usage_service = usage_service

    per_minute = discord.ui.TextInput(
        label="Max Requests Per Minute (default)",
        placeholder="5",
        default="5",
        required=True,
        min_length=1,
        max_length=4,
    )

    per_hour = discord.ui.TextInput(
        label="Max Requests Per Hour (default)",
        placeholder="50",
        default="50",
        required=True,
        min_length=1,
        max_length=5,
    )

    async def on_submit(self, interaction: discord.Interaction):
        try:
            per_minute = int(self.per_minute.value)
            per_hour = int(self.per_hour.value)
        except ValueError:
            await interaction.response.send_message("Please enter valid numbers.", ephemeral=True)
            return

        if per_minute < 1 or per_hour < 1:
            await interaction.response.send_message("Limits must be at least 1.", ephemeral=True)
            return

        # Update guild defaults via config
        bot: BruhBot = interaction.client
        config = await bot.config_service.get_config(str(self.guild_id))
        ai_config_dict = config.aiConfig.model_dump()
        if "usageLimits" not in ai_config_dict:
            ai_config_dict["usageLimits"] = {}
        ai_config_dict["usageLimits"]["maxRequestsPerMinute"] = per_minute
        ai_config_dict["usageLimits"]["maxRequestsPerHour"] = per_hour
        await bot.config_service.update(str(self.guild_id), {"aiConfig": ai_config_dict})

        # Also update all existing user records
        count = await self.usage_service.set_guild_limits(self.guild_id, per_minute, per_hour)

        embed = interaction.client.embed_service.create_success_embed(
            f"Guild default AI usage limits set to:\n- **{per_minute}** requests per minute\n- **{per_hour}** requests per hour\n\nUpdated {count} existing user record(s).",
            title="Guild AI Limits Updated",
        )
        await interaction.response.send_message(embed=embed, ephemeral=True, files=interaction.client.embed_service.get_brand_files(embed=embed))


class AiUsageCommand:
    def __init__(self, tree: app_commands.CommandTree, args=None):
        ai_usage_group = app_commands.Group(
            name="ai_usage",
            description="Admin commands for managing AI usage rate limits",
            default_permissions=discord.Permissions(administrator=True),
        )

        @ai_usage_group.command(
            name="stats",
            description="View AI usage stats for a user",
        )
        @app_commands.describe(user="The user to check stats for")
        @log_command_usage()
        @is_globally_blocked()
        async def stats(interaction: discord.Interaction, user: discord.User):
            await interaction.response.defer(ephemeral=True)

            bot: BruhBot = interaction.client

            try:
                user_stats = await bot.ai_usage_service.get_user_stats(user.id, interaction.guild.id)

                status_icon = "🟢" if user_stats["enabled"] else "🔴"
                status_text = "Enabled" if user_stats["enabled"] else "Disabled"

                embed = interaction.client.embed_service.create_info_embed(
                    title=f"AI Usage Stats for {user.display_name}",
                    description=f"Rate limiting is currently **{status_text}** {status_icon}",
                    fields=[
                        ("Per Minute", f"**{user_stats['minute_count']}**/{user_stats['max_per_minute']} ({user_stats['remaining_minute']} remaining)", True),
                        ("Per Hour", f"**{user_stats['hour_count']}**/{user_stats['max_per_hour']} ({user_stats['remaining_hour']} remaining)", True),
                    ],
                )

                await interaction.followup.send(embed=embed, ephemeral=True, files=interaction.client.embed_service.get_brand_files(embed=embed))

            except Exception as e:
                bot.logger.error(f"Error viewing AI usage stats: {e}")
                await interaction.followup.send("Failed to fetch AI usage stats.", ephemeral=True)

        @ai_usage_group.command(
            name="set_user",
            description="Set AI usage limits for a specific user (opens a form)",
        )
        @app_commands.describe(user="The user to set limits for")
        @log_command_usage()
        @is_globally_blocked()
        async def set_user(interaction: discord.Interaction, user: discord.User):
            bot: BruhBot = interaction.client
            modal = SetUserLimitsModal(user, interaction.guild.id, bot.ai_usage_service)
            await interaction.response.send_modal(modal)

        @ai_usage_group.command(
            name="set_guild",
            description="Set default AI usage limits for the entire server (opens a form)",
        )
        @log_command_usage()
        @is_globally_blocked()
        async def set_guild(interaction: discord.Interaction):
            bot: BruhBot = interaction.client
            modal = SetGuildLimitsModal(interaction.guild.id, bot.ai_usage_service)
            await interaction.response.send_modal(modal)

        @ai_usage_group.command(
            name="reset_user",
            description="Reset AI usage counters for a specific user",
        )
        @app_commands.describe(user="The user to reset counters for")
        @log_command_usage()
        @is_globally_blocked()
        async def reset_user(interaction: discord.Interaction, user: discord.User):
            await interaction.response.defer(ephemeral=True)

            bot: BruhBot = interaction.client

            try:
                await bot.ai_usage_service.reset_user(user.id, interaction.guild.id)

                embed = interaction.client.embed_service.create_success_embed(
                    f"AI usage counters have been reset for {user.mention}",
                    title="User AI Usage Reset",
                )

                await interaction.followup.send(embed=embed, ephemeral=True, files=interaction.client.embed_service.get_brand_files(embed=embed))

            except Exception as e:
                bot.logger.error(f"Error resetting AI usage: {e}")
                await interaction.followup.send("Failed to reset AI usage counters.", ephemeral=True)

        @ai_usage_group.command(
            name="toggle",
            description="Enable or disable AI usage rate limiting",
        )
        @app_commands.describe(enabled="True to enable, False to disable")
        @log_command_usage()
        @is_globally_blocked()
        async def toggle(interaction: discord.Interaction, enabled: bool):
            await interaction.response.defer(ephemeral=True)

            bot: BruhBot = interaction.client

            try:
                await bot.ai_usage_service.set_limits_enabled(interaction.guild.id, enabled)

                status = "enabled" if enabled else "disabled"
                embed = interaction.client.embed_service.create_success_embed(
                    f"AI usage rate limiting has been **{status}**.",
                    title="AI Usage Limits Toggled",
                )

                await interaction.followup.send(embed=embed, ephemeral=True, files=interaction.client.embed_service.get_brand_files(embed=embed))

            except Exception as e:
                bot.logger.error(f"Error toggling AI usage limits: {e}")
                await interaction.followup.send("Failed to toggle AI usage limits.", ephemeral=True)

        @ai_usage_group.command(
            name="config",
            description="View current guild-level AI usage configuration",
        )
        @log_command_usage()
        @is_globally_blocked()
        async def config_view(interaction: discord.Interaction):
            await interaction.response.defer(ephemeral=True)

            bot: BruhBot = interaction.client

            try:
                config = await bot.config_service.get_config(str(interaction.guild.id))
                limits = config.aiConfig.usageLimits

                status_icon = "🟢" if limits.enabled else "🔴"
                status_text = "Enabled" if limits.enabled else "Disabled"

                embed = interaction.client.embed_service.create_info_embed(
                    title="AI Usage Rate Limit Configuration",
                    description=f"Status: **{status_text}** {status_icon}",
                    fields=[
                        ("Per Minute Default", str(limits.maxRequestsPerMinute), True),
                        ("Per Hour Default", str(limits.maxRequestsPerHour), True),
                        ("Commands", "`/ai_usage set_user` - Set per-user limits\n`/ai_usage set_guild` - Set guild defaults\n`/ai_usage toggle` - Enable/disable\n`/ai_usage reset_user` - Reset counters\n`/ai_usage stats` - View user stats", False),
                    ],
                )

                await interaction.followup.send(embed=embed, ephemeral=True, files=interaction.client.embed_service.get_brand_files(embed=embed))

            except Exception as e:
                bot.logger.error(f"Error viewing AI usage config: {e}")
                await interaction.followup.send("Failed to fetch AI usage config.", ephemeral=True)

        @ai_usage_group.command(
            name="leaderboard",
            description="Show the AI usage leaderboard by tokens and cost",
        )
        @app_commands.describe(days="Number of days to look back (leave blank for all time)")
        @log_command_usage()
        @is_globally_blocked()
        async def leaderboard(interaction: discord.Interaction, days: int | None = None):
            await interaction.response.defer(ephemeral=True)

            bot: BruhBot = interaction.client

            try:
                start_date = None
                end_date = date.today().isoformat()
                if days is not None:
                    from datetime import timedelta

                    start = datetime.now(UTC) - timedelta(days=days)
                    start_date = start.date().isoformat()

                entries = await bot.ai_usage_tracking_service.get_leaderboard(interaction.guild.id, start_date=start_date, end_date=end_date, limit=15)
                summary = await bot.ai_usage_tracking_service.get_leaderboard_summary(interaction.guild.id, start_date=start_date, end_date=end_date)

                if not entries:
                    embed = bot.embed_service.create_info_embed(
                        title="AI Usage Leaderboard",
                        description="No usage data available yet.",
                    )
                    await interaction.followup.send(embed=embed, ephemeral=True, files=bot.embed_service.get_brand_files(embed=embed))
                    return

                period = f"last {days} days" if days else "all time"
                fields = []
                for idx, entry in enumerate(entries[:10], 1):
                    user_id = entry["user_id"]
                    total_requests = entry["total_requests"]
                    total_input_tokens = entry["total_input_tokens"]
                    total_output_tokens = entry["total_output_tokens"]
                    cost_str = f"${entry['total_cost']:.4f}" if entry["total_cost"] > 0 else "$0.00"
                    fields.append(
                        (
                            f"#{idx} {entry.get('username', f'User {user_id}')}",
                            f"Requests: **{total_requests}** | Tokens: **{total_input_tokens}** in / **{total_output_tokens}** out | Cost: **{cost_str}**",
                            False,
                        )
                    )

                embed = bot.embed_service.create_info_embed(
                    title=f"AI Usage Leaderboard ({period})",
                    description=f"**{summary['total_requests']}** total requests — **${summary['total_cost']:.4f}** total cost",
                    fields=fields,
                )

                await interaction.followup.send(embed=embed, ephemeral=True, files=bot.embed_service.get_brand_files(embed=embed))

            except Exception as e:
                bot.logger.error(f"Error fetching leaderboard: {e}")
                await interaction.followup.send("Failed to fetch leaderboard.", ephemeral=True)

        @ai_usage_group.command(
            name="my_stats",
            description="View your own AI usage statistics",
        )
        @app_commands.describe(days="Number of days to look back (leave blank for all time)")
        @log_command_usage()
        @is_globally_blocked()
        async def my_stats(interaction: discord.Interaction, days: int | None = None):
            await interaction.response.defer(ephemeral=True)

            bot: BruhBot = interaction.client

            try:
                start_date = None
                end_date = date.today().isoformat()
                if days is not None:
                    from datetime import timedelta

                    start = datetime.now(UTC) - timedelta(days=days)
                    start_date = start.date().isoformat()

                usage = await bot.ai_usage_tracking_service.get_user_usage(interaction.user.id, interaction.guild.id, start_date=start_date, end_date=end_date)

                period = f"last {days} days" if days else "all time"
                cost_str = f"${usage['total_cost']:.4f}" if usage["total_cost"] > 0 else "$0.00"

                models_str = ""
                models_used = usage.get("models_used", {})
                if models_used:
                    top_models = sorted(models_used.items(), key=lambda x: x[1].get("cost", 0), reverse=True)[:3]
                    models_str = "\n".join(f"• **{m}**: {s.get('requests', 0)} req — ${s.get('cost', 0):.4f}" for m, s in top_models)

                embed = bot.embed_service.create_info_embed(
                    title=f"Your AI Usage ({period})",
                    description=f"Usage statistics for {interaction.user.display_name}",
                    fields=[
                        ("Total Requests", str(usage["total_requests"]), True),
                        ("Total Cost", cost_str, True),
                        ("Input Tokens", f"{usage['total_input_tokens']:,}", True),
                        ("Output Tokens", f"{usage['total_output_tokens']:,}", True),
                    ],
                )

                if models_str:
                    embed.add_field(name="Top Models", value=models_str, inline=False)

                await interaction.followup.send(embed=embed, ephemeral=True, files=bot.embed_service.get_brand_files(embed=embed))

            except Exception as e:
                bot.logger.error(f"Error fetching user usage: {e}")
                await interaction.followup.send("Failed to fetch your usage stats.", ephemeral=True)

        tree.add_command(ai_usage_group)
