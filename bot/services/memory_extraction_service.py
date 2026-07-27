import asyncio
import json
import logging
import re
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from bot.services.ai.gateway.gateway import get_mesh_gateway
from bot.services.ai.gateway.schemas.request import Message, MessagePart, NormalizedRequest
from bot.services.mongo_memory_service import CATEGORY_TTL_DAYS, VALID_CATEGORIES

if TYPE_CHECKING:
    import discord

    from bot.bruh_bot import BruhBot

EXTRACTION_SYSTEM_PROMPT = """You are a memory extraction system for a Discord bot. Your job is to analyze a group conversation and extract structured memories about multiple users.

## MEMORY CATEGORIES AND RETENTION RULES:
- identity: Permanent (immutable facts like name, age, location, role). Never expires.
- trait: Permanent (personality traits, skills, profession, abilities). Never expires.
- preference: 90-day retention (likes, dislikes, favorites, preferences).
- opinion: 30-day retention (opinions on topics, beliefs, stances).
- relationship: Permanent (how they feel about other people, relationships). Include 'target_username' with the Discord display name of the person this memory is about.
- mood: 7-day retention (current emotional state, temporary feelings).
- fact: 90-day retention (general facts about the user).
- admin: Permanent (manually added by admins). YOU SHOULD NEVER GENERATE THIS CATEGORY.

## WHAT TO EXTRACT:
Memories must be CORE to who the user IS — their identity, personality, likes/dislikes, opinions, skills, and relationships. Good examples:
- "is a software engineer" (identity)
- "loves dark humor and roasts people" (trait)
- "hates pineapple on pizza" (preference)
- "thinks AI will replace most jobs by 2030" (opinion)
- "dislikes Klim" (relationship)
- "plays guitar" (fact/skill)

## WHAT NOT TO EXTRACT — SKIP THESE ENTIRELY:
- **One-off actions**: sharing a link, posting a meme, saying "lol", greeting someone
- **Ephemeral chatter**: "shared a YouTube video", "posted a gif", "good morning", "how was your day"
- **Server logistics**: asking for roles, reporting bugs, asking bot commands, troubleshooting
- **Vague or generic statements**: "that's cool", "I agree", "nice", "same"
- **Conversational filler**: jokes without personality insight, reaction gifs, "based", "fr fr"
- **Transient states**: what they're currently doing/watching/eating right now (unless it reveals a strong preference/identity)
- **Anything that won't matter about this person a week from now**

## GOLDEN RULE:
Ask yourself: "Does this tell me something meaningful about WHO this person IS — their identity, personality, or tastes — not just what they casually DID?" If the answer is no, do NOT create a memory.

## INSTRUCTIONS:
1. Review the conversation transcript below. Messages are labeled with the speaker's name.
2. For EACH user, review their CURRENT MEMORIES alongside what they said.
3. Use conversational context — if one person says something and another agrees, that implies the second person shares that trait/preference/opinion too.
4. Determine what needs to change per user:
   - ADD new memories only when you observe facts/opinions/traits that reveal WHO the user IS
   - UPDATE existing memories when something changes (e.g., "I hated Python" → "I love Python now")
   - DELETE memories that are contradicted by recent messages or clearly no longer true
5. Be conservative — only extract clear, meaningful information about the user's identity. When in doubt, skip it.
6. Assign confidence scores (0.0-1.0) based on how explicitly the user stated it.
7. For relationship memories, include 'target_username' with the exact name from the KNOWN USERS list. If someone says "I hate Nolan" and "Nolan" appears in KNOWN USERS, set target_username to exactly "Nolan".
8. CRITICAL: Every action MUST include 'user_id' as a number — this is the Discord user ID telling us who the memory is about.
9. DO NOT create 'admin' category memories.
10. NEVER extract memories for the bot itself (the assistant/bot user in the conversation).

Return ONLY a valid JSON object with this exact structure:
{
  "actions": [
    {"user_id": 123, "action": "add", "memory": "loves Whoppers", "category": "preference", "confidence": 0.9},
    {"user_id": 456, "action": "add", "memory": "loves Whoppers", "category": "preference", "confidence": 0.85},
    {"user_id": 123, "action": "add", "memory": "dislikes Klim", "category": "relationship", "confidence": 0.85, "target_username": "Klim"},
    {"user_id": 456, "action": "update", "memory_id": "existing_memory_id_here", "new_memory": "updated fact", "category": "preference", "confidence": 0.85},
    {"user_id": 789, "action": "delete", "memory_id": "existing_memory_id_here", "reason": "contradicted by: new statement"}
  ]
}

If no changes are needed, return: {"actions": []}"""


class MemoryExtractionService:
    def __init__(self, bot: "BruhBot"):
        self.bot = bot
        self.logger = logging.getLogger(__name__)
        self._message_buffers: dict[str, list[dict]] = {}
        self._message_locks: dict[str, asyncio.Lock] = {}
        self._last_extraction: dict[str, float] = {}
        self._running = False
        self._main_task: asyncio.Task | None = None

    async def enqueue_message(self, message: "discord.Message"):
        guild_id = str(message.guild.id)
        config = await self.bot.config_service.get_config(guild_id)
        mem_cfg = config.memoryConfig

        if not mem_cfg.enabled:
            return

        if message.author.bot:
            return

        content = message.content.strip()
        if not content or len(content) < mem_cfg.minMessageLength:
            return

        if guild_id not in self._message_buffers:
            self._message_buffers[guild_id] = []
            self._message_locks[guild_id] = asyncio.Lock()
        if guild_id not in self._last_extraction:
            self._last_extraction[guild_id] = 0.0

        self._message_buffers[guild_id].append(
            {
                "content": content,
                "message_id": message.id,
                "timestamp": message.created_at.isoformat(),
                "author_id": message.author.id,
                "author_name": message.author.name,
            }
        )

    async def start_extraction_loops(self):
        self._running = True
        self._main_task = asyncio.create_task(self._main_loop())
        self.logger.info("Memory extraction loop started")

    async def stop_extraction_loops(self):
        self._running = False
        if self._main_task:
            self._main_task.cancel()
            try:
                await self._main_task
            except asyncio.CancelledError:
                pass
        self.logger.info("Memory extraction loop stopped")

    async def _main_loop(self):
        while self._running:
            try:
                await self._process_all_guilds()
            except Exception:
                self.logger.exception("Error in main extraction loop")
            await asyncio.sleep(60)

    async def _process_all_guilds(self):
        guild_ids = list(self._message_buffers.keys())
        for guild_id in guild_ids:
            try:
                config = await self.bot.config_service.get_config(guild_id)
                mem_cfg = config.memoryConfig
                if not mem_cfg.enabled:
                    continue

                interval_minutes = min(mem_cfg.extractionIntervalMinutes, mem_cfg.moodExtractionIntervalMinutes)
                if interval_minutes <= 0:
                    continue
                interval_seconds = interval_minutes * 60

                if guild_id not in self._message_locks:
                    continue

                async with self._message_locks[guild_id]:
                    if guild_id not in self._message_buffers:
                        continue

                    now_ts = datetime.now(UTC).timestamp()
                    last = self._last_extraction.get(guild_id, 0.0)
                    if now_ts - last < interval_seconds:
                        continue

                    all_messages = self._message_buffers[guild_id]
                    if len(all_messages) < mem_cfg.minMessagesForExtraction:
                        continue

                    messages_to_process = all_messages[-mem_cfg.maxMessagesPerExtraction :]
                    await self._extract_for_guild(
                        guild_id=guild_id,
                        messages=messages_to_process,
                        mem_cfg=mem_cfg,
                    )
                    self._message_buffers[guild_id] = []
                    self._last_extraction[guild_id] = now_ts
            except Exception:
                self.logger.exception(f"Error processing guild {guild_id}")

    async def _extract_for_guild(
        self,
        guild_id: str,
        messages: list[dict],
        mem_cfg,
    ):
        config = await self.bot.config_service.get_config(guild_id)
        id_to_users = config.idToUsers
        guild = self.bot.get_guild(int(guild_id))

        author_ids_in_batch = set()
        for msg in messages:
            author_id = msg.get("author_id")
            if author_id:
                author_ids_in_batch.add(int(author_id))
            for match in re.finditer(r"<@!?(\d+)>", msg.get("content", "")):
                mid = int(match.group(1))
                if mid != self.bot.user.id:
                    author_ids_in_batch.add(mid)

        author_memories = await self.bot.memory_service.get_memories_for_users(
            guild_id=int(guild_id),
            user_ids=list(author_ids_in_batch),
            limit=50,
        )

        existing_by_user: dict[int, list[dict]] = {}
        for uid_int, mems in author_memories.items():
            existing_by_user[uid_int] = mems

        conversation_lines = []
        for msg in messages:
            name = msg.get("author_name", str(msg.get("author_id", "unknown")))
            content = self._resolve_mentions_in_text(msg["content"], id_to_users)
            conversation_lines.append(f"[{name}]: {content}")
        transcript = "\n".join(conversation_lines)

        users_section_parts = []
        for uid_int in sorted(author_ids_in_batch):
            user_mems = existing_by_user.get(uid_int, [])
            canonical_name = id_to_users.get(str(uid_int))
            if not canonical_name and guild:
                member = guild.get_member(uid_int)
                if member:
                    canonical_name = member.name
            if not canonical_name:
                canonical_name = str(uid_int)

            mem_text = self._format_memories_for_prompt(user_mems)
            if mem_text:
                users_section_parts.append(f"## USER: {canonical_name} (user_id: {uid_int})\n{mem_text}")
            else:
                users_section_parts.append(f"## USER: {canonical_name} (user_id: {uid_int})\n(No existing memories yet)")

        users_section = "\n\n".join(users_section_parts)

        known_users = "\n".join(f"- {name}" for name in sorted(config.usersToId.keys())) if config.usersToId else "(no known users registered)"

        user_prompt = f"""## CONVERSATION TRANSCRIPT (newest first):
{transcript}

## EXISTING MEMORIES BY USER:
{users_section}

## KNOWN USERS IN THIS SERVER:
{known_users}

Analyze the conversation and existing memories above. For each user, determine what memories to add, update, or delete. When a name mentioned in conversation matches a known user, use that name as target_username for relationship memories. Return the JSON actions with user_id for every action."""

        ai_cfg = config.aiConfig
        provider = mem_cfg.extractionProvider
        provider_config = getattr(ai_cfg, provider, None) or ai_cfg.openrouter
        api_key = provider_config.get_api_key()
        model = mem_cfg.extractionModel or provider_config.preferredModel

        response_format = {
            "type": "json_schema",
            "json_schema": {
                "name": "MemoryExtraction",
                "schema": {
                    "type": "object",
                    "properties": {
                        "actions": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "user_id": {"type": "number"},
                                    "action": {"type": "string", "enum": ["add", "update", "delete"]},
                                    "memory": {"type": "string"},
                                    "category": {"type": "string", "enum": VALID_CATEGORIES},
                                    "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                                    "memory_id": {"type": "string"},
                                    "new_memory": {"type": "string"},
                                    "reason": {"type": "string"},
                                    "target_username": {"type": "string"},
                                },
                                "required": ["action", "user_id"],
                            },
                        }
                    },
                    "required": ["actions"],
                },
            },
        }

        req = NormalizedRequest(
            provider=provider,
            model=model,
            messages=[
                Message(role="system", parts=[MessagePart(type="text", text=EXTRACTION_SYSTEM_PROMPT)]),
                Message(role="user", parts=[MessagePart(type="text", text=user_prompt)]),
            ],
            response_format=response_format,
        )

        try:
            gateway = get_mesh_gateway()
            response = await gateway.complete(req, credentials={"api_key": api_key})
            content = "".join(part.content for part in response.parts if part.type == "text")
            result = json.loads(content)
            actions = result.get("actions", [])

            valid_author_ids = author_ids_in_batch
            sanitized_actions = []
            for action in actions:
                raw_uid = action.get("user_id")
                if raw_uid is None:
                    continue
                try:
                    uid_int = int(raw_uid)
                except (ValueError, TypeError, OverflowError):
                    self.logger.warning(f"Dropping action with non-integer user_id: {raw_uid}")
                    continue
                if uid_int not in valid_author_ids:
                    self.logger.warning(f"Dropping action with unknown user_id: {uid_int} (not in conversation)")
                    continue
                action["user_id"] = uid_int
                sanitized_actions.append(action)

            await self._apply_actions_batch(
                guild_id=int(guild_id),
                actions=sanitized_actions,
                existing_by_user=existing_by_user,
                mem_cfg=mem_cfg,
                id_to_users=id_to_users,
            )

            user_ids_in_actions = {a["user_id"] for a in sanitized_actions}
            self.logger.info(f"Extracted {len(sanitized_actions)} memory actions for {len(user_ids_in_actions)} users in guild {guild_id}")
        except Exception:
            self.logger.exception(f"Error during batch memory extraction for guild {guild_id}")

    async def _apply_actions_batch(
        self,
        guild_id: int,
        actions: list[dict],
        existing_by_user: dict[int, list[dict]],
        mem_cfg,
        id_to_users: dict[str, str],
    ):
        config_by_action = await self.bot.config_service.get_config(str(guild_id))

        for action in actions:
            try:
                action_type = action.get("action")
                user_id = action.get("user_id")
                if not user_id:
                    continue

                existing_memories = existing_by_user.get(int(user_id), [])
                existing_ids = {m["_id"] for m in existing_memories}

                if action_type == "add":
                    memory_text = action.get("memory", "").strip()
                    category = action.get("category", "fact")
                    confidence = float(action.get("confidence", 0.5))

                    if not memory_text or category not in VALID_CATEGORIES or category == "admin":
                        continue

                    target_user_id = None
                    if category == "relationship" and action.get("target_username"):
                        resolved_id = config_by_action.usersToId.get(action["target_username"])
                        if resolved_id:
                            target_user_id = int(resolved_id)

                    await self.bot.memory_service.save_memory(
                        guild_id=guild_id,
                        user_id=int(user_id),
                        memory=memory_text,
                        category=category,
                        confidence=confidence,
                        created_by="ai",
                        target_user_id=target_user_id,
                    )

                elif action_type == "update":
                    memory_id = action.get("memory_id", "")
                    new_memory = action.get("new_memory", "").strip()
                    category = action.get("category")
                    confidence = action.get("confidence")

                    target_user_id = None
                    if category == "relationship" and action.get("target_username"):
                        resolved_id = config_by_action.usersToId.get(action["target_username"])
                        if resolved_id:
                            target_user_id = int(resolved_id)

                    if memory_id not in existing_ids:
                        if new_memory and category in VALID_CATEGORIES:
                            await self.bot.memory_service.save_memory(
                                guild_id=guild_id,
                                user_id=int(user_id),
                                memory=new_memory,
                                category=category or "fact",
                                confidence=float(confidence or 0.5),
                                created_by="ai",
                                target_user_id=target_user_id,
                            )
                        continue

                    await self.bot.memory_service.update_memory(
                        memory_id=memory_id,
                        guild_id=guild_id,
                        new_memory=new_memory or None,
                        category=category,
                        confidence=float(confidence) if confidence else None,
                        target_user_id=target_user_id,
                    )

                elif action_type == "delete":
                    memory_id = action.get("memory_id", "")
                    reason = action.get("reason", "")
                    if memory_id in existing_ids:
                        await self.bot.memory_service.delete_memory(memory_id=memory_id, guild_id=guild_id)
                        self.logger.info(f"Deleted memory {memory_id}: {reason}")

            except Exception:
                self.logger.exception(f"Error applying action {action}")

        user_ids_in_actions = set()
        for a in actions:
            uid = a.get("user_id")
            if uid:
                user_ids_in_actions.add(int(uid))

        for uid in user_ids_in_actions:
            await self.bot.memory_service.enforce_max_memories(
                guild_id=guild_id,
                user_id=uid,
                max_memories=mem_cfg.maxMemoriesPerUser,
            )

    @staticmethod
    def _format_memories_for_prompt(memories: list[dict]) -> str:
        if not memories:
            return ""
        lines = []
        for m in memories:
            ttl = CATEGORY_TTL_DAYS.get(m.get("category", "fact"))
            expiry = f"expires in {ttl}d" if ttl else "permanent"
            lines.append(f"  [id={m['_id']}] [{m.get('category', 'fact')}, confidence={m.get('confidence', 0.5):.2f}, {expiry}] {m['memory']}")
        return "\n".join(lines)

    @staticmethod
    def _format_messages_for_prompt(messages: list[dict]) -> str:
        if not messages:
            return "(no messages)"
        lines = []
        for msg in messages[-50:]:
            name = msg.get("author_name", "unknown")
            lines.append(f"[{name}]: {msg['content']}")
        return "\n".join(lines)

    @staticmethod
    def _resolve_mentions_in_text(text: str, id_to_users: dict[str, str]) -> str:
        def replace_mention(match: re.Match) -> str:
            user_id = match.group(1)
            name = id_to_users.get(user_id)
            return f"@{name}" if name else match.group(0)

        return re.sub(r"<@!?(\d+)>", replace_mention, text)

    async def force_extract_all(self, guild_id: str) -> int:
        config = await self.bot.config_service.get_config(guild_id)
        mem_cfg = config.memoryConfig
        if not mem_cfg.enabled:
            return 0

        if guild_id not in self._message_buffers:
            return 0

        async with self._message_locks.get(guild_id, asyncio.Lock()):
            all_messages = self._message_buffers.get(guild_id, [])
            if not all_messages:
                return 0

            messages_to_process = all_messages[-mem_cfg.maxMessagesPerExtraction :]
            user_ids_in_batch = set()
            for msg in messages_to_process:
                aid = msg.get("author_id")
                if aid:
                    user_ids_in_batch.add(int(aid))

            await self._extract_for_guild(
                guild_id=guild_id,
                messages=messages_to_process,
                mem_cfg=mem_cfg,
            )
            self._message_buffers[guild_id] = []
            self._last_extraction[guild_id] = datetime.now(UTC).timestamp()

        return len(user_ids_in_batch)

    async def force_extract_user(self, guild_id: str, user_id: int) -> bool:
        config = await self.bot.config_service.get_config(guild_id)
        mem_cfg = config.memoryConfig

        user_id_int = int(user_id)
        all_messages = self._message_buffers.get(guild_id, [])
        user_messages = [m for m in all_messages if m.get("author_id") == user_id_int]
        if not user_messages:
            return False

        messages_to_process = user_messages[-mem_cfg.maxMessagesPerExtraction :]
        await self._extract_for_guild(
            guild_id=guild_id,
            messages=messages_to_process,
            mem_cfg=mem_cfg,
        )
        self._message_buffers[guild_id] = [m for m in self._message_buffers.get(guild_id, []) if m.get("author_id") != user_id_int]
        self._last_extraction[guild_id] = datetime.now(UTC).timestamp()
        return True
