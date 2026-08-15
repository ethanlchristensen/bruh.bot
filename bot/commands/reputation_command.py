from typing import TYPE_CHECKING

import discord
from discord import app_commands

from bot.utils.decarators.admin_check import is_admin
from bot.utils.decarators.command_logging import log_command_usage
from bot.utils.decarators.global_block_check import is_globally_blocked

if TYPE_CHECKING:
    from bot.bruh_bot import BruhBot


class ReputationCommand:
    def __init__(self, tree: app_commands.CommandTree, args=None):
        group = app_commands.Group(name="reputation", description="Reputation and moderation tools")

        @group.command(name="leaderboard", description="Show the lowest reputation scores in this server")
        @app_commands.describe(limit="How many users to show")
        @log_command_usage()
        @is_globally_blocked()
        async def leaderboard(interaction: discord.Interaction, limit: app_commands.Range[int, 1, 25] = 10):
            bot: BruhBot = interaction.client
            entries = await bot.reputation_service.get_leaderboard(interaction.guild.id, limit)
            if not entries:
                await interaction.response.send_message("No users have reputation penalties in this server.")
                return
            lines = []
            for index, entry in enumerate(entries, 1):
                member = interaction.guild.get_member(int(entry["user_id"]))
                name = member.display_name if member else f"User {entry['user_id']}"
                score = f"+{entry['score']}" if entry["score"] > 0 else str(entry["score"])
                lines.append(f"`{index}.` **{name}** - {score} points ({entry['status'].replace('_', ' ')})")
            embed = bot.embed_service.create_warning_embed("Reputation Leaderboard", "\n".join(lines))
            worst_member = interaction.guild.get_member(int(entries[0]["user_id"]))
            if worst_member:
                embed.set_thumbnail(url=worst_member.display_avatar.url)
            await interaction.response.send_message(embed=embed, files=bot.embed_service.get_brand_files(embed=embed))

        @group.command(name="me", description="View your reputation in this server")
        @log_command_usage()
        @is_globally_blocked()
        async def me(interaction: discord.Interaction):
            bot: BruhBot = interaction.client
            profile = await bot.reputation_service.get_profile(interaction.guild.id, interaction.user.id)
            events = await bot.reputation_service.get_recent_events(interaction.guild.id, interaction.user.id, 5)
            audit = "\n".join(f"- {event['summary']} ({event['score_delta']:+})" for event in events) or "No audit events."
            blocked_until = bot.reputation_service._as_utc(profile.get("blocked_until"))
            expiry = f"\n**Block remaining:** <t:{int(blocked_until.timestamp())}:R>" if blocked_until else ""
            block_count = profile.get("automatic_block_count", 0)
            block_history = f"\n**Automatic blocks:** {block_count}" if block_count else ""
            embed = bot.embed_service.create_info_embed("Your Reputation", f"**Score:** {profile['score']:+}\n**Status:** {profile['status'].replace('_', ' ')}{expiry}{block_history}\n\n**Recent audit entries:**\n{audit}")
            embed.set_thumbnail(url=interaction.user.display_avatar.url)
            await interaction.response.send_message(embed=embed, ephemeral=True, files=bot.embed_service.get_brand_files(embed=embed))

        @group.command(name="view", description="View a user's reputation and recent audit entries")
        @app_commands.describe(user="The user to inspect")
        @log_command_usage()
        @is_admin()
        @is_globally_blocked()
        async def view(interaction: discord.Interaction, user: discord.User):
            bot: BruhBot = interaction.client
            profile = await bot.reputation_service.get_profile(interaction.guild.id, user.id)
            events = await bot.reputation_service.get_recent_events(interaction.guild.id, user.id, 5)
            audit = "\n".join(f"- {event['summary']} ({event['score_delta']:+})" for event in events) or "No audit events."
            block_count = profile.get("automatic_block_count", 0)
            embed = bot.embed_service.create_info_embed("Reputation Profile", f"{user.mention}\n\n**Score:** {profile['score']}\n**Status:** {profile['status']}\n**Automatic blocks:** {block_count}\n\n**Recent audit entries:**\n{audit}")
            await interaction.followup.send(embed=embed, ephemeral=True, files=bot.embed_service.get_brand_files(embed=embed))

        @group.command(name="set-score", description="Set a user's reputation score")
        @app_commands.describe(user="The user to update", score="New signed score", reason="Reason for the manual adjustment")
        @log_command_usage()
        @is_admin()
        @is_globally_blocked()
        async def set_score(interaction: discord.Interaction, user: discord.User, score: app_commands.Range[int, -10000, 10000], reason: str = "Manual admin adjustment"):
            bot: BruhBot = interaction.client
            profile = await bot.reputation_service.set_score(interaction.guild.id, user.id, score, reason)
            await interaction.followup.send(f"Set {user.mention}'s reputation score to **{profile['score']}** ({profile['status']}).", ephemeral=True)

        @group.command(name="block", description="Manually block a user from bot interactions")
        @app_commands.describe(user="The user to block", reason="Reason for the block")
        @log_command_usage()
        @is_admin()
        @is_globally_blocked()
        async def block(interaction: discord.Interaction, user: discord.User, reason: str = "Manual admin block"):
            bot: BruhBot = interaction.client
            await bot.reputation_service.set_manual_block(interaction.guild.id, user.id, True, reason)
            await interaction.followup.send(f"Blocked {user.mention} from bot interactions.", ephemeral=True)

        @group.command(name="unblock", description="Restore a user's ability to interact with the bot")
        @app_commands.describe(user="The user to unblock", reason="Reason for the unblock")
        @log_command_usage()
        @is_admin()
        @is_globally_blocked()
        async def unblock(interaction: discord.Interaction, user: discord.User, reason: str = "Manual admin unblock"):
            bot: BruhBot = interaction.client
            await bot.reputation_service.set_manual_block(interaction.guild.id, user.id, False, reason)
            await interaction.followup.send(f"Unblocked {user.mention}.", ephemeral=True)

        tree.add_command(group)
