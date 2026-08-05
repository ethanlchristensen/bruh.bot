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
                mem_cfg = config.memoryConfig
                permanent_cats = {"identity", "trait", "admin", "relationship"}

                mentioned_user_ids = [u.id for u in message.mentions if u.id != message.author.id and u.id != self.bot.user.id]
                mentioned_user_ids_dedup = list(dict.fromkeys(mentioned_user_ids))

                non_mentioned_ids = [message.author.id]
                for node in path:
                    author = node.get("author_name")
                    if author and author != self.bot.user.name and author != message.author.name:
                        user_id = config.usersToId.get(author)
                        if user_id:
                            uid_int = int(user_id)
                            if uid_int not in non_mentioned_ids and uid_int not in mentioned_user_ids_dedup:
                                non_mentioned_ids.append(uid_int)

                all_ids = list(dict.fromkeys(non_mentioned_ids + mentioned_user_ids_dedup))

                self.logger.info(f"Querying memories for {len(all_ids)} user(s): {', '.join(config.idToUsers.get(str(uid), str(uid)) for uid in all_ids)}, mentioned={len(mentioned_user_ids_dedup)}")

                sections = []

                per_user_limit = max(mem_cfg.maxInjectionCount // (len(mentioned_user_ids_dedup) + 1), 2)

                for uid in mentioned_user_ids_dedup:
                    user_name = config.idToUsers.get(str(uid)) or self._lookup_name(message, uid)
                    mems = await self.bot.memory_service.get_memories_for_user(
                        guild_id=message.guild.id,
                        user_id=uid,
                        limit=per_user_limit,
                    )
                    if mems:
                        lines = []
                        for mem in mems:
                            if mem.get("target_user_id") and mem["category"] == "relationship":
                                lines.append(f"- {mem['memory']} → <@{mem['target_user_id']}> ({mem['category']})")
                            else:
                                lines.append(f"- {mem['memory']} ({mem['category']})")
                        if lines:
                            sections.append(f"\n## ABOUT @{user_name}:\n" + "\n".join(lines))
                            self.logger.info(f"Injected {len(lines)} memories for mentioned user {user_name} (uid={uid})")

                remaining = mem_cfg.maxInjectionCount - sum(len(s.split("\n")) - 2 for s in sections)
                remaining = max(remaining, 0)

                if remaining > 0 and non_mentioned_ids:
                    other_ids = non_mentioned_ids if mentioned_user_ids_dedup else all_ids
                    if mem_cfg.semanticRetrieval and message.content.strip():
                        try:
                            msg_embedding = await self.bot.embedding_service.embed_one(message.content.strip(), message.guild.id)
                            if msg_embedding is not None:
                                semantic_results = await self.bot.memory_service.search_memories_semantic(
                                    guild_id=message.guild.id,
                                    query_embedding=msg_embedding,
                                    user_ids=other_ids,
                                    limit=remaining * 2,
                                    min_score=mem_cfg.retrievalMinScore,
                                )
                                permanent_from_semantic = [m for m in semantic_results if m["category"] in permanent_cats]
                                non_permanent_semantic = [m for m in semantic_results if m["category"] not in permanent_cats]

                                permanent_mems = await self.bot.memory_service.get_memories_for_users(
                                    guild_id=message.guild.id,
                                    user_ids=other_ids,
                                    limit=max(len(permanent_cats) * 3, 20),
                                )
                                permanent_all = []
                                for _uid, mems in permanent_mems.items():
                                    for m in mems:
                                        if m["category"] in permanent_cats:
                                            if m["_id"] not in {x["_id"] for x in permanent_from_semantic}:
                                                permanent_all.append(m)

                                all_results = permanent_from_semantic + permanent_all + non_permanent_semantic
                                seen_ids = set()
                                deduped = []
                                for m in all_results:
                                    if m["_id"] not in seen_ids:
                                        seen_ids.add(m["_id"])
                                        deduped.append(m)

                                selected = deduped[:remaining]

                                if selected:
                                    author_to_id = {str(message.author.id): message.author.name}
                                    for uid in non_mentioned_ids:
                                        if uid != message.author.id:
                                            author_to_id[str(uid)] = config.idToUsers.get(str(uid), str(uid))
                                    lines = []
                                    for mem in selected:
                                        uid_str = str(mem["user_id"])
                                        name = author_to_id.get(uid_str, uid_str)
                                        if mem.get("target_user_id") and mem["category"] == "relationship":
                                            lines.append(f"- [{name}]: {mem['memory']} → <@{mem['target_user_id']}> ({mem['category']})")
                                        else:
                                            lines.append(f"- [{name}]: {mem['memory']} ({mem['category']})")
                                    if lines:
                                        sections.append("\n## OTHER GROUNDING MEMORIES:\n" + "\n".join(lines))
                                        self.logger.info(f"Injected {len(lines)} general memory entries into context (semantic retrieval)")
                            else:
                                self.logger.info("Embedding generation failed, falling back to recency-based retrieval")
                                sections.append(await self._format_fallback_section(message, other_ids, mem_cfg, remaining))
                        except Exception:
                            self.logger.exception("Semantic memory retrieval failed, falling back")
                            sections.append(await self._format_fallback_section(message, other_ids, mem_cfg, remaining))
                    else:
                        sections.append(await self._format_fallback_section(message, other_ids, mem_cfg, remaining))

                if sections:
                    memories_section = "\n## GROUNDING MEMORIES:\nThese are known facts and observations about users in this conversation. Use them to personalize responses naturally.\n" + "\n".join(sections) + "\n"
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

    def _lookup_name(self, message: discord.Message, uid: int) -> str:
        for u in message.mentions:
            if u.id == uid:
                return u.display_name
        return str(uid)

    async def _format_fallback_section(
        self,
        message: discord.Message,
        user_ids: list[int],
        mem_cfg,
        remaining: int,
    ) -> str:
        memories_map = await self.bot.memory_service.get_memories_for_users(
            guild_id=message.guild.id,
            user_ids=user_ids,
            limit=remaining,
        )
        if memories_map:
            lines = []
            for uid_str, mems in memories_map.items():
                name = uid_str
                for mem in mems:
                    if mem.get("target_user_id") and mem["category"] == "relationship":
                        lines.append(f"- [{name}]: {mem['memory']} → <@{mem['target_user_id']}> ({mem['category']})")
                    else:
                        lines.append(f"- [{name}]: {mem['memory']} ({mem['category']})")
            if lines:
                self.logger.info(f"Injected {len(lines)} general memory entries into context (fallback)")
                return "\n## OTHER GROUNDING MEMORIES:\n" + "\n".join(lines)
        return ""
