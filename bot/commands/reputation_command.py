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
        group = app_commands.Group(name="reputation", description="Admin reputation management", default_permissions=discord.Permissions(administrator=True))

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
            embed = bot.embed_service.create_info_embed("Reputation Profile", f"{user.mention}\n\n**Score:** {profile['score']}\n**Status:** {profile['status']}\n\n**Recent audit entries:**\n{audit}")
            await interaction.followup.send(embed=embed, ephemeral=True, files=bot.embed_service.get_brand_files(embed=embed))

        @group.command(name="set-score", description="Set a user's reputation score")
        @app_commands.describe(user="The user to update", score="New non-negative score", reason="Reason for the manual adjustment")
        @log_command_usage()
        @is_admin()
        @is_globally_blocked()
        async def set_score(interaction: discord.Interaction, user: discord.User, score: app_commands.Range[int, 0], reason: str = "Manual admin adjustment"):
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
