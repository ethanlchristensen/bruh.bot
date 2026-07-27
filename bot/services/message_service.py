import base64
import logging
import re
from typing import TYPE_CHECKING

import aiohttp
import discord

from bot.services.ai.gateway.schemas.request import Message, MessagePart

if TYPE_CHECKING:
    from bot.bruh_bot import BruhBot


class MessageService:
    def __init__(self, bot: "BruhBot"):
        self.bot = bot
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
        """Build the message context for AI processing using the parent-pointer tree."""
        images = await self.process_message_images(message)
        messages = []

        config = await self.bot.config_service.get_config(str(message.guild.id))

        # 1. Determine parent_id
        if reference_message:
            parent_id = reference_message.id
        else:
            # Strict mode: treat as a brand new conversation root
            parent_id = None

        # 2. Save current user message
        await self.bot.chat_service.save_message(
            message_id=message.id,
            channel_id=message.channel.id,
            parent_id=parent_id,
            role="user",
            content=message.content,
            author_name=username,
        )

        # 3. Retrieve conversation path
        path = await self.bot.chat_service.get_conversation_path(message.id)

        # 3.5 Inject user memories into context
        memories_section = ""
        try:
            if config.memoryConfig.enabled:
                user_ids_to_query = [message.author.id]
                author_to_id = {str(message.author.id): message.author.name}

                for node in path:
                    author = node.get("author_name")
                    if author and author != self.bot.user.name and author != message.author.name:
                        user_id = config.usersToId.get(author)
                        if user_id:
                            uid_int = int(user_id)
                            if uid_int not in user_ids_to_query:
                                user_ids_to_query.append(uid_int)
                                author_to_id[str(uid_int)] = author

                for mentioned_user in message.mentions:
                    if mentioned_user.id != message.author.id and mentioned_user.id != self.bot.user.id and mentioned_user.id not in user_ids_to_query:
                        user_ids_to_query.append(mentioned_user.id)
                        author_to_id[str(mentioned_user.id)] = mentioned_user.name

                memories_map = await self.bot.memory_service.get_memories_for_users(
                    guild_id=message.guild.id,
                    user_ids=user_ids_to_query,
                    limit=config.memoryConfig.maxInjectionCount,
                )
                if memories_map:
                    lines = []
                    for uid_str, mems in memories_map.items():
                        name = author_to_id.get(uid_str, uid_str)
                        for mem in mems:
                            if mem.get("target_user_id") and mem["category"] == "relationship":
                                lines.append(f"- [{name}]: {mem['memory']} → <@{mem['target_user_id']}> ({mem['category']})")
                            else:
                                lines.append(f"- [{name}]: {mem['memory']} ({mem['category']})")
                    if lines:
                        memories_section = "\n## GROUNDING MEMORIES:\nThese are known facts and observations about users in this conversation. Use them to personalize responses naturally.\n\n" + "\n".join(lines) + "\n"
        except Exception:
            self.logger.exception("Error retrieving user memories for context")

        # 4. Add enhanced system prompt
        if main_prompt := config.aiConfig.systemPrompt:
            main_prompt = main_prompt.replace("{{BOTNAME}}", self.bot.user.name)

            # Add multi-user context instructions
            multi_user_prompt = f"""
{main_prompt}

MULTI-USER CHAT CONTEXT:
- You are in a Discord group chat with multiple users
- Messages are formatted as: [Username]: [Message Content]
- Pay close attention to the username before each message
- When responding, you may address specific users by name if appropriate
- IMPORTANT: DO NOT prepend your response with your name or brackets. Just send the message content directly. Your message is going straight to the discord server.{memories_section}
"""
            messages.append(Message(role="system", parts=[MessagePart(type="text", text=multi_user_prompt)]))

        # 5. Populate messages from conversation path
        for node in path:
            node_role = node["role"]
            node_content = node["content"]
            node_author = node.get("author_name")

            clean_content = self.replace_mentions(node_content).strip()
            clean_content = self.resolve_user_mentions(clean_content, config.idToUsers)

            if node_role == "assistant":
                text = f"[{self.bot.user.name}]: {clean_content}"
            else:
                text = f"[{node_author or 'user'}]: {clean_content}"

            parts = [MessagePart(type="text", text=text)]

            # Attach images only to the current message (the end of the chain)
            if node["_id"] == message.id:
                for img in images:
                    data_url = f"data:{img['type']};base64,{img['data']}"
                    parts.append(MessagePart(type="image", url=data_url))

            messages.append(Message(role=node_role, parts=parts))

        return messages

    def replace_mentions(self, text: str) -> str:
        """Replace bot mentions with empty string or 'bruh.bot'."""
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

    @staticmethod
    def resolve_user_mentions(text: str, id_to_users: dict[str, str]) -> str:
        """Resolve raw Discord mention tags to @displayname format."""

        def replace_mention(match: re.Match) -> str:
            user_id = match.group(1)
            name = id_to_users.get(user_id)
            return f"@{name}" if name else match.group(0)

        return re.sub(r"<@!?(\d+)>", replace_mention, text)

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
