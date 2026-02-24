import base64
import logging
from typing import TYPE_CHECKING

import aiohttp
import discord

from bot.services import Message

if TYPE_CHECKING:
    from bot.juno import Juno


class MessageService:
    def __init__(self, bot: "Juno", prompts: dict):
        self.bot = bot
        self.prompts = prompts
        self.logger = logging.getLogger(__name__)

    async def get_reference_message(self, message: discord.Message) -> discord.Message | None:
        """Get the referenced message if this is a reply."""
        if not message.reference:
            return None

        try:
            return await message.channel.fetch_message(message.reference.message_id)
        except discord.NotFound:
            return None

    async def should_respond_to_message(self, message: discord.Message, reference_message: discord.Message | None) -> bool:
        """Check if the bot should respond to this message."""
        if not self.bot.user:
            return False

        bot_string = f"<@{self.bot.user.id}>"
        should_respond = bot_string in message.content or (reference_message and reference_message.author.id == self.bot.user.id)
        return should_respond

    async def should_delete_message(self, guild_id: int, message: discord.Message) -> bool:
        config = (await self.bot.config_service.get_config(str(guild_id))).deleteUserMessages
        if config.enabled and message.author.id in config.userIds:
            return True
        return False

    async def process_message_images(self, message: discord.Message) -> list[dict]:
        """Process and encode image attachments."""
        images = []
        for attachment in message.attachments:
            if attachment.content_type and attachment.content_type.startswith("image/"):
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.get(attachment.url) as resp:
                            if resp.status == 200:
                                img_bytes = await resp.read()
                                img_b64 = base64.b64encode(img_bytes).decode("utf-8")
                                images.append({"type": attachment.content_type, "data": img_b64})
                except Exception as e:
                    self.logger.error(f"Failed to process image attachment: {e}")
        return images

    async def build_message_context(self, message: discord.Message, reference_message: discord.Message | None, username: str) -> list[Message]:
        """Build the message context for AI processing."""
        images = await self.process_message_images(message)
        messages = []

        # Add enhanced system prompt
        if main_prompt := self.prompts.get("main"):
            main_prompt = main_prompt.replace("{{BOTNAME}}", self.bot.user.name)

            # Add multi-user context instructions
            multi_user_prompt = f"""
    {main_prompt}

    MULTI-USER CHAT CONTEXT:
    - You are in a Discord group chat with multiple users
    - Messages are formatted as: [Username]: [Message Content]
    - Each line represents a different message, possibly from different users
    - Pay close attention to the username before each message
    - When responding, you may address specific users by name if appropriate
    - IMPORTANT: DO NOT prepend your response with your name or brackets. Just send the message content directly. Your message is going straight to the discord server.
    """
            messages.append(Message(role="system", content=multi_user_prompt))

        # Get historical messages and format as transcript
        historical_msgs = await self.bot.discord_messages_service.get_last_n_messages_within_n_minutes(message=message, n=10, minutes=30)

        config = await self.bot.config_service.get_config(str(message.guild.id))

        if historical_msgs:
            transcript_lines = []
            for msg in historical_msgs:
                author_name = config.idToUsers.get(str(msg["author_id"]), msg["author_name"])
                content = self.replace_mentions(msg["content"]).strip()

                # Mark bot's own messages clearly
                if msg["author_id"] == self.bot.user.id:
                    transcript_lines.append(f"[{self.bot.user.name}]: {content}")
                else:
                    transcript_lines.append(f"[{author_name}]: {content}")

            # Add all historical messages as a single user message
            transcript = "RECENT CONVERSATION:\n" + "\n".join(transcript_lines)
            messages.append(Message(role="user", content=transcript))

        # Add reference message context if replying
        if reference_message:
            ref_username = config.idToUsers.get(str(reference_message.author.id), reference_message.author.name)
            ref_content = self.replace_mentions(reference_message.content).strip()

            # Format as part of the conversation flow
            reply_context = f"\nREPLYING TO:\n[{ref_username}]: {ref_content}"
            messages.append(Message(role="user", content=reply_context))

        # Add current message
        current_content = f"\nCURRENT MESSAGE:\n[{username}]: " + self.replace_mentions(message.content).strip()
        messages.append(Message(role="user", content=current_content, images=images))

        return messages

    def replace_mentions(self, text: str) -> str:
        """Replace bot mentions with empty string or 'Juno'."""
        if not self.bot.user:
            return text

        mention = f"<@{self.bot.user.id}>"
        parts = text.split(mention)
        if len(parts) <= 1:
            return text

        result = parts[0]
        for i, part in enumerate(parts[1:]):
            if i == 0:
                result += "" + part
            else:
                result += self.bot.user.name + " " + part

        return result

    async def get_image_attachment(self, message: discord.Message, reference_message: discord.Message | None = None) -> discord.Attachment | None:
        """Get image attachment from message or referenced message."""

        config = await self.bot.config_service.get_config(str(message.guild.id))

        # Check current message for images
        image_attachment = next(
            (att for att in message.attachments if att.content_type and att.content_type.startswith("image/")),
            None,
        )

        if image_attachment:
            self.logger.info(f"Found image in current message: {image_attachment.filename}")
            return image_attachment

        # Check referenced message for images (from any user, not just bot)
        if reference_message:
            image_attachment = next(
                (att for att in reference_message.attachments if att.content_type and att.content_type.startswith("image/")),
                None,
            )

            if image_attachment:
                author_name = config.idToUsers.get(str(reference_message.author.id), reference_message.author.name)
                self.logger.info(f"Found image in referenced message from {author_name}: {image_attachment.filename}")
                return image_attachment

        return None

    async def get_image_attachments(self, message: discord.Message, reference_message: discord.Message | None = None) -> list[discord.Attachment]:
        """Get all image attachments from message or referenced message."""

        config = await self.bot.config_service.get_config(str(message.guild.id))

        images = []

        # Check current message for images
        current_images = [att for att in message.attachments if att.content_type and att.content_type.startswith("image/")]

        if current_images:
            self.logger.info(f"Found {len(current_images)} image(s) in current message")
            images.extend(current_images)

        # Check referenced message for images (from any user, not just bot)
        if reference_message:
            ref_images = [att for att in reference_message.attachments if att.content_type and att.content_type.startswith("image/")]

            if ref_images:
                author_name = config.idToUsers.get(str(reference_message.author.id), reference_message.author.name)
                self.logger.info(f"Found {len(ref_images)} image(s) in referenced message from {author_name}")
                images.extend(ref_images)

        return images

    async def is_replying_to_bot_image(self, reference_message: discord.Message | None) -> bool:
        """Check if the user is replying to a bot message with an image."""
        if not reference_message or not self.bot.user:
            return False

        if reference_message.author.id != self.bot.user.id:
            return False

        has_image = any(att.content_type and att.content_type.startswith("image/") for att in reference_message.attachments)

        return has_image
