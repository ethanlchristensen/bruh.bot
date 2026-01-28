import discord
from discord import app_commands

from bot.utils.decarators.admin_check import is_admin
from bot.utils.decarators.command_logging import log_command_usage
from bot.utils.decarators.global_block_check import is_globally_blocked


class ReplyCommand(app_commands.Command):
    def __init__(self, tree: app_commands.CommandTree, args=None):
        @tree.command(
            name="reply",
            description="Reply to a message as the bot with optional attachment and text",
        )
        @log_command_usage()
        @is_admin()
        @is_globally_blocked()
        async def reply(
            interaction: discord.Interaction,
            message_id: str,
            message: str | None = None,
            attachment: discord.Attachment | None = None,
        ):
            channel = interaction.channel

            # Prevent error if both message and attachment are missing
            if not message and not attachment:
                await interaction.followup.send(
                    "You must provide either a message or an attachment.",
                    ephemeral=True,
                )
                return

            try:
                target_message = await channel.fetch_message(int(message_id))
            except discord.NotFound:
                await interaction.followup.send(
                    "Message not found in this channel. Please ensure the Message ID is correct.",
                    ephemeral=True,
                )
                return
            except ValueError:
                await interaction.followup.send(
                    "Invalid Message ID. Please provide a numeric ID.",
                    ephemeral=True,
                )
                return

            try:
                file_to_send = None
                if attachment:
                    file_to_send = await attachment.to_file()

                await target_message.reply(
                    content=message or "",
                    file=file_to_send,
                    mention_author=False,  # Set to True if you want the bot to mention the original author
                )
                await interaction.followup.send("Reply sent!", ephemeral=True)
            except Exception as e:
                await interaction.followup.send(f"An error occurred: {e}", ephemeral=True)
