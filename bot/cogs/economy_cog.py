import logging
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from bot.utils.decarators.admin_check import is_admin
from bot.utils.decarators.command_logging import log_command_usage
from bot.utils.decarators.global_block_check import is_globally_blocked

if TYPE_CHECKING:
    from bot.bruh_bot import BruhBot


class EconomyCog(commands.Cog):
    def __init__(self, bot: "BruhBot"):
        self.bot = bot
        self.logger = logging.getLogger(__name__)

    def _format_xp_progress(self, xp: int, level: int) -> str:
        from bot.services.mongo_economy_service import MongoEconomyService

        xp_for_current = MongoEconomyService._xp_for_next_level(level - 1) if level > 0 else 0
        xp_for_next = MongoEconomyService._xp_for_next_level(level)
        xp_in_level = xp - xp_for_current
        xp_needed = xp_for_next - xp_for_current
        bar_length = 10
        filled = int((xp_in_level / xp_needed) * bar_length) if xp_needed > 0 else bar_length
        empty = bar_length - filled
        bar = "█" * filled + "░" * empty
        return f"`{bar}` {xp_in_level}/{xp_needed} XP"

    @app_commands.command(name="rank", description="View your or another user's level and XP.")
    @app_commands.describe(user="User to check rank for (defaults to you)")
    @log_command_usage()
    @is_globally_blocked()
    async def rank(self, interaction: discord.Interaction, user: discord.Member | None = None):
        target = user or interaction.user
        profile = await self.bot.economy_service.get_profile(interaction.guild.id, target.id)
        rank = await self.bot.economy_service.get_rank(interaction.guild.id, target.id)

        xp_progress = self._format_xp_progress(profile["xp"], profile["level"])

        embed = self.bot.embed_service._create_base_embed(
            title=f"Rank — {target.display_name}",
            description=f"**Level {profile['level']}** (#{rank} on leaderboard)\n{xp_progress}",
        )
        embed.add_field(name="Total XP", value=f"{profile['xp']:,}", inline=True)
        embed.add_field(name="bruh.coins", value=f"🪙 {profile['bruh_coins']:.2f}", inline=True)
        embed.add_field(name="Messages Sent", value=str(profile["total_messages"]), inline=True)
        embed.set_thumbnail(url=target.display_avatar.url)
        await interaction.response.send_message(embed=embed, files=self.bot.embed_service.get_brand_files(embed=embed))

    @app_commands.command(name="leaderboard", description="View the server XP or coin leaderboard.")
    @app_commands.describe(sort_by="Sort by xp, level, or coins")
    @app_commands.choices(
        sort_by=[
            app_commands.Choice(name="XP", value="xp"),
            app_commands.Choice(name="Level", value="level"),
            app_commands.Choice(name="Coins", value="bruh_coins"),
        ]
    )
    @log_command_usage()
    @is_globally_blocked()
    async def leaderboard(self, interaction: discord.Interaction, sort_by: str = "xp"):
        entries = await self.bot.economy_service.get_leaderboard(interaction.guild.id, sort_by=sort_by)
        if not entries:
            embed = self.bot.embed_service.create_info_embed(
                title="Leaderboard",
                description="No one has earned XP yet. Start chatting!",
            )
            await interaction.response.send_message(embed=embed, files=self.bot.embed_service.get_brand_files(embed=embed))
            return

        sort_labels = {"xp": "XP", "level": "Level", "bruh_coins": "bruh.coins"}
        description_lines = []
        for entry in entries[:25]:
            user_id = entry["user_id"]
            member = interaction.guild.get_member(user_id)
            name = member.display_name if member else f"User {user_id}"
            rank_emoji = "🥇" if entry["rank"] == 1 else "🥈" if entry["rank"] == 2 else "🥉" if entry["rank"] == 3 else f"`#{entry['rank']}`"
            line = f"{rank_emoji} **{name}** — Lv{entry['level']} ({entry['xp']:,} XP) · 🪙 {entry['bruh_coins']:.2f}"
            description_lines.append(line)

        embed = self.bot.embed_service._create_base_embed(
            title=f"🏆 Leaderboard — {sort_labels.get(sort_by, sort_by)}",
            description="\n".join(description_lines),
        )
        await interaction.response.send_message(embed=embed, files=self.bot.embed_service.get_brand_files(embed=embed))

    @app_commands.command(name="balance", description="Check your bruh.coin balance.")
    @log_command_usage()
    @is_globally_blocked()
    async def balance(self, interaction: discord.Interaction):
        profile = await self.bot.economy_service.get_profile(interaction.guild.id, interaction.user.id)
        embed = self.bot.embed_service._create_base_embed(
            title="💳 Balance",
            description=f"You have **🪙 {profile['bruh_coins']:.2f}** bruh.coins",
        )
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        await interaction.response.send_message(embed=embed, files=self.bot.embed_service.get_brand_files(embed=embed))

    @app_commands.command(name="daily", description="Claim your daily bruh.coin reward.")
    @log_command_usage()
    @is_globally_blocked()
    async def daily(self, interaction: discord.Interaction):
        success, amount, cooldown_msg = await self.bot.economy_service.claim_daily(interaction.guild.id, interaction.user.id)
        if success:
            embed = self.bot.embed_service.create_success_embed(
                f"You claimed **🪙 {amount:.2f}** bruh.coins!\nCome back in 24 hours for more.",
                title="Daily Reward Claimed!",
            )
        else:
            embed = self.bot.embed_service.create_error_embed(cooldown_msg)
        await interaction.response.send_message(embed=embed, files=self.bot.embed_service.get_brand_files(embed=embed))

    @app_commands.command(name="profile", description="View a full profile card for yourself or another user.")
    @app_commands.describe(user="User to view (defaults to you)")
    @log_command_usage()
    @is_globally_blocked()
    async def profile(self, interaction: discord.Interaction, user: discord.Member | None = None):
        target = user or interaction.user
        profile = await self.bot.economy_service.get_profile(interaction.guild.id, target.id)
        rank = await self.bot.economy_service.get_rank(interaction.guild.id, target.id)

        xp_progress = self._format_xp_progress(profile["xp"], profile["level"])

        joined_at = target.joined_at
        joined_str = f"<t:{int(joined_at.timestamp())}:R>" if joined_at else "Unknown"

        embed = self.bot.embed_service._create_base_embed(
            title=f"👤 {target.display_name}'s Profile",
            description=xp_progress,
        )
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.add_field(name="Level", value=str(profile["level"]), inline=True)
        embed.add_field(name="Rank", value=f"#{rank}", inline=True)
        embed.add_field(name="Total XP", value=f"{profile['xp']:,}", inline=True)
        embed.add_field(name="bruh.coins", value=f"🪙 {profile['bruh_coins']:.2f}", inline=True)
        embed.add_field(name="Messages", value=str(profile["total_messages"]), inline=True)
        embed.add_field(name="Images Sent", value=str(profile["total_images"]), inline=True)
        embed.add_field(name="Reactions Given", value=str(profile["total_reactions_given"]), inline=True)
        embed.add_field(name="Bot Mentions", value=str(profile["total_bot_mentions"]), inline=True)
        embed.add_field(name="Joined Server", value=joined_str, inline=False)
        await interaction.response.send_message(embed=embed, files=self.bot.embed_service.get_brand_files(embed=embed))

    economy_group = app_commands.Group(name="economy", description="Admin economy management commands.")

    @economy_group.command(name="leaderboard", description="View the coin leaderboard (richest users).")
    @log_command_usage()
    @is_globally_blocked()
    async def economy_leaderboard(self, interaction: discord.Interaction):
        entries = await self.bot.economy_service.get_leaderboard(interaction.guild.id, sort_by="bruh_coins")
        if not entries:
            embed = self.bot.embed_service.create_info_embed(
                title="🏪 Coin Leaderboard",
                description="No one has earned coins yet. Start chatting!",
            )
            await interaction.response.send_message(embed=embed, files=self.bot.embed_service.get_brand_files(embed=embed))
            return

        description_lines = []
        for entry in entries[:25]:
            user_id = entry["user_id"]
            member = interaction.guild.get_member(user_id)
            name = member.display_name if member else f"User {user_id}"
            rank_emoji = "🥇" if entry["rank"] == 1 else "🥈" if entry["rank"] == 2 else "🥉" if entry["rank"] == 3 else f"`#{entry['rank']}`"
            line = f"{rank_emoji} **{name}** — 🪙 {entry['bruh_coins']:.2f} (Lv{entry['level']})"
            description_lines.append(line)

        embed = self.bot.embed_service._create_base_embed(
            title="🏪 Coin Leaderboard",
            description="\n".join(description_lines),
        )
        await interaction.response.send_message(embed=embed, files=self.bot.embed_service.get_brand_files(embed=embed))

    @economy_group.command(name="set-xp", description="Set a user's total XP.")
    @app_commands.describe(user="The user", amount="New XP amount")
    @log_command_usage()
    @is_admin()
    @is_globally_blocked()
    async def economy_set_xp(self, interaction: discord.Interaction, user: discord.Member, amount: int):
        new_level = await self.bot.economy_service.set_xp(interaction.guild.id, user.id, amount)
        embed = self.bot.embed_service.create_success_embed(
            f"Set **{user.display_name}**'s XP to **{amount:,}** (Level {new_level}).",
            title="XP Updated",
        )
        await interaction.followup.send(embed=embed, ephemeral=True, files=self.bot.embed_service.get_brand_files(embed=embed))

    @economy_group.command(name="set-coins", description="Set a user's coin balance.")
    @app_commands.describe(user="The user", amount="New coin balance")
    @log_command_usage()
    @is_admin()
    @is_globally_blocked()
    async def economy_set_coins(self, interaction: discord.Interaction, user: discord.Member, amount: float):
        await self.bot.economy_service.set_coins(interaction.guild.id, user.id, amount)
        embed = self.bot.embed_service.create_success_embed(
            f"Set **{user.display_name}**'s coin balance to **🪙 {amount:.2f}**.",
            title="Coins Updated",
        )
        await interaction.followup.send(embed=embed, ephemeral=True, files=self.bot.embed_service.get_brand_files(embed=embed))

    @economy_group.command(name="set-level", description="Set a user's level.")
    @app_commands.describe(user="The user", level="New level")
    @log_command_usage()
    @is_admin()
    @is_globally_blocked()
    async def economy_set_level(self, interaction: discord.Interaction, user: discord.Member, level: int):
        await self.bot.economy_service.set_level(interaction.guild.id, user.id, level)
        embed = self.bot.embed_service.create_success_embed(
            f"Set **{user.display_name}**'s level to **{level}**.",
            title="Level Updated",
        )
        await interaction.followup.send(embed=embed, ephemeral=True, files=self.bot.embed_service.get_brand_files(embed=embed))

    @economy_group.command(name="reset", description="Reset a user's economy profile entirely.")
    @app_commands.describe(user="The user to reset")
    @log_command_usage()
    @is_admin()
    @is_globally_blocked()
    async def economy_reset(self, interaction: discord.Interaction, user: discord.Member):
        await self.bot.economy_service.reset_profile(interaction.guild.id, user.id)
        embed = self.bot.embed_service.create_success_embed(
            f"**{user.display_name}**'s economy profile has been reset.",
            title="Profile Reset",
        )
        await interaction.followup.send(embed=embed, ephemeral=True, files=self.bot.embed_service.get_brand_files(embed=embed))

    @economy_group.command(name="give-coins", description="Give coins to a user.")
    @app_commands.describe(user="The user", amount="Amount to give")
    @log_command_usage()
    @is_admin()
    @is_globally_blocked()
    async def economy_give_coins(self, interaction: discord.Interaction, user: discord.Member, amount: float):
        new_balance = await self.bot.economy_service.add_coins(interaction.guild.id, user.id, amount)
        embed = self.bot.embed_service.create_success_embed(
            f"Gave **🪙 {amount:.2f}** to **{user.display_name}**.\nNew balance: **🪙 {new_balance:.2f}**",
            title="Coins Given",
        )
        await interaction.followup.send(embed=embed, ephemeral=True, files=self.bot.embed_service.get_brand_files(embed=embed))

    @economy_group.command(name="take-coins", description="Remove coins from a user.")
    @app_commands.describe(user="The user", amount="Amount to take")
    @log_command_usage()
    @is_admin()
    @is_globally_blocked()
    async def economy_take_coins(self, interaction: discord.Interaction, user: discord.Member, amount: float):
        success, new_balance = await self.bot.economy_service.deduct_coins(interaction.guild.id, user.id, amount)
        if not success:
            embed = self.bot.embed_service.create_error_embed(f"{user.display_name} doesn't have enough coins (balance: 🪙 {new_balance:.2f}).")
        else:
            embed = self.bot.embed_service.create_success_embed(
                f"Took **🪙 {amount:.2f}** from **{user.display_name}**.\nNew balance: **🪙 {new_balance:.2f}**",
                title="Coins Taken",
            )
        await interaction.followup.send(embed=embed, ephemeral=True, files=self.bot.embed_service.get_brand_files(embed=embed))


async def setup(bot: "BruhBot"):
    await bot.add_cog(EconomyCog(bot))
