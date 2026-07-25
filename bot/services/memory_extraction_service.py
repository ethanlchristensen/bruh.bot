import asyncio
import json
import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from bot.services.ai.gateway.gateway import get_mesh_gateway
from bot.services.ai.gateway.schemas.request import Message, MessagePart, NormalizedRequest
from bot.services.mongo_memory_service import CATEGORY_TTL_DAYS, VALID_CATEGORIES

if TYPE_CHECKING:
    import discord

    from bot.bruh_bot import BruhBot

EXTRACTION_SYSTEM_PROMPT = """You are a memory extraction system for a Discord bot. Your job is to analyze chat messages from a user and extract structured memories about them.

## MEMORY CATEGORIES AND RETENTION RULES:
- identity: Permanent (immutable facts like name, age, location, role). Never expires.
- trait: Permanent (personality traits, skills, profession, abilities). Never expires.
- preference: 90-day retention (likes, dislikes, favorites, preferences).
- opinion: 30-day retention (opinions on topics, beliefs, stances).
- relationship: Permanent (how they feel about other people, relationships). Include 'target_username' with the Discord display name of the person this memory is about.
- mood: 7-day retention (current emotional state, temporary feelings).
- fact: 90-day retention (general facts about the user).
- admin: Permanent (manually added by admins). YOU SHOULD NEVER GENERATE THIS CATEGORY.

## INSTRUCTIONS:
1. Review the user's CURRENT MEMORIES and their RECENT MESSAGES.
2. Determine what needs to change:
   - ADD new memories when you observe new facts/opinions/traits
   - UPDATE existing memories when something changes (e.g., "I hated Python" → "I love Python now")
   - DELETE memories that are contradicted by recent messages or clearly no longer true
3. Be conservative — only extract clear, meaningful information. Skip vague statements.
4. Assign confidence scores (0.0-1.0) based on how explicitly the user stated it.
5. For relationship memories, include 'target_username' so we know which user the relationship is about.
6. DO NOT create 'admin' category memories.

Return ONLY a valid JSON object with this exact structure:
{
  "actions": [
    {"action": "add", "memory": "fact about user", "category": "preference", "confidence": 0.9},
    {"action": "add", "memory": "dislikes Klim", "category": "relationship", "confidence": 0.85, "target_username": "Klim"},
    {"action": "update", "memory_id": "existing_memory_id_here", "new_memory": "updated fact", "category": "preference", "confidence": 0.85},
    {"action": "delete", "memory_id": "existing_memory_id_here", "reason": "contradicted by: new statement"}
  ]
}

If no changes are needed, return: {"actions": []}"""


class MemoryExtractionService:
    def __init__(self, bot: "BruhBot"):
        self.bot = bot
        self.logger = logging.getLogger(__name__)
        self._message_buffers: dict[str, dict[int, list[dict]]] = {}
        self._message_locks: dict[str, asyncio.Lock] = {}
        self._last_extraction: dict[str, dict[int, float]] = {}
        self._running = False
        self._main_task: asyncio.Task | None = None
        self._mood_task: asyncio.Task | None = None

    async def enqueue_message(self, message: "discord.Message"):
        guild_id = str(message.guild.id)
        user_id = message.author.id
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
            self._message_buffers[guild_id] = {}
            self._message_locks[guild_id] = asyncio.Lock()
        if guild_id not in self._last_extraction:
            self._last_extraction[guild_id] = {}

        user_id_str = str(user_id)
        if user_id_str not in self._message_buffers[guild_id]:
            self._message_buffers[guild_id][user_id_str] = []

        self._message_buffers[guild_id][user_id_str].append(
            {
                "content": content,
                "message_id": message.id,
                "timestamp": message.created_at.isoformat(),
            }
        )

    async def start_extraction_loops(self):
        self._running = True
        self._main_task = asyncio.create_task(self._main_loop())
        self._mood_task = asyncio.create_task(self._mood_loop())
        self.logger.info("Memory extraction loops started")

    async def stop_extraction_loops(self):
        self._running = False
        for task in (self._main_task, self._mood_task):
            if task:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        self.logger.info("Memory extraction loops stopped")

    async def _main_loop(self):
        while self._running:
            try:
                await self._process_all_guilds(category_filter=None)
            except Exception:
                self.logger.exception("Error in main extraction loop")
            await asyncio.sleep(60)

    async def _mood_loop(self):
        while self._running:
            try:
                await self._process_all_guilds(category_filter=["mood"])
            except Exception:
                self.logger.exception("Error in mood extraction loop")
            await asyncio.sleep(60)

    async def _process_all_guilds(self, category_filter: list[str] | None = None):
        guild_ids = list(self._message_buffers.keys())
        for guild_id in guild_ids:
            try:
                config = await self.bot.config_service.get_config(guild_id)
                mem_cfg = config.memoryConfig
                if not mem_cfg.enabled:
                    continue

                interval_minutes = mem_cfg.moodExtractionIntervalMinutes if category_filter == ["mood"] else mem_cfg.extractionIntervalMinutes
                if interval_minutes <= 0:
                    continue
                interval_seconds = interval_minutes * 60

                if guild_id not in self._message_locks:
                    continue

                async with self._message_locks[guild_id]:
                    if guild_id not in self._message_buffers:
                        continue

                    user_ids = list(self._message_buffers[guild_id].keys())
                    for user_id_str in user_ids:
                        try:
                            user_id = int(user_id_str)
                            now_ts = datetime.now(UTC).timestamp()
                            last = self._last_extraction.get(guild_id, {}).get(user_id_str, 0)
                            if now_ts - last < interval_seconds:
                                continue

                            messages = self._message_buffers[guild_id].get(user_id_str, [])
                            if len(messages) < (mem_cfg.minMessagesForExtraction if category_filter != ["mood"] else 3):
                                continue

                            messages_to_process = messages[-mem_cfg.maxMessagesPerExtraction :]
                            await self._extract_for_user(
                                guild_id=guild_id,
                                user_id=user_id,
                                messages=messages_to_process,
                                category_filter=category_filter,
                                mem_cfg=mem_cfg,
                            )
                            self._message_buffers[guild_id][user_id_str] = []
                            self._last_extraction.setdefault(guild_id, {})[user_id_str] = now_ts
                        except Exception:
                            self.logger.exception(f"Error processing user {user_id_str} in guild {guild_id}")
            except Exception:
                self.logger.exception(f"Error processing guild {guild_id}")

    async def _extract_for_user(
        self,
        guild_id: str,
        user_id: int,
        messages: list[dict],
        category_filter: list[str] | None,
        mem_cfg,
    ):
        guild = self.bot.get_guild(int(guild_id))
        username = str(user_id)
        if guild:
            member = guild.get_member(user_id)
            if member:
                username = member.name

        existing_memories = await self.bot.memory_service.get_memories_for_user(
            guild_id=int(guild_id),
            user_id=user_id,
            categories=category_filter or mem_cfg.enabledCategories,
        )

        memories_text = self._format_memories_for_prompt(existing_memories)
        messages_text = self._format_messages_for_prompt(messages)

        system_prompt = EXTRACTION_SYSTEM_PROMPT
        if category_filter:
            system_prompt += f"\n\nFOCUS: Only extract memories for these categories: {', '.join(category_filter)}. Ignore everything else."

        user_prompt = f"""## USER: {username}

## CURRENT MEMORIES:
{memories_text if memories_text else "(No existing memories yet)"}

## RECENT MESSAGES (newest first):
{messages_text}

Analyze these messages and return the JSON actions."""

        ai_cfg = (await self.bot.config_service.get_config(guild_id)).aiConfig
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
                                    "action": {"type": "string", "enum": ["add", "update", "delete"]},
                                    "memory": {"type": "string"},
                                    "category": {"type": "string", "enum": VALID_CATEGORIES},
                                    "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                                    "memory_id": {"type": "string"},
                                    "new_memory": {"type": "string"},
                                    "reason": {"type": "string"},
                                    "target_username": {"type": "string"},
                                },
                                "required": ["action"],
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
                Message(role="system", parts=[MessagePart(type="text", text=system_prompt)]),
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

            await self._apply_actions(guild_id=int(guild_id), user_id=user_id, actions=actions, existing_memories=existing_memories, mem_cfg=mem_cfg)

            self.logger.info(f"Extracted {len(actions)} memory actions for {username} in guild {guild_id}")
        except Exception:
            self.logger.exception(f"Error during memory extraction for {username} in guild {guild_id}")

    async def _apply_actions(
        self,
        guild_id: int,
        user_id: int,
        actions: list[dict],
        existing_memories: list[dict],
        mem_cfg,
    ):
        existing_ids = {m["_id"] for m in existing_memories}
        config = await self.bot.config_service.get_config(str(guild_id))

        for action in actions:
            try:
                action_type = action.get("action")

                if action_type == "add":
                    memory_text = action.get("memory", "").strip()
                    category = action.get("category", "fact")
                    confidence = float(action.get("confidence", 0.5))

                    if not memory_text or category not in VALID_CATEGORIES or category == "admin":
                        continue

                    target_user_id = None
                    if category == "relationship" and action.get("target_username"):
                        target_username = action["target_username"]
                        resolved_id = config.usersToId.get(target_username)
                        if resolved_id:
                            target_user_id = int(resolved_id)

                    await self.bot.memory_service.save_memory(
                        guild_id=guild_id,
                        user_id=user_id,
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
                        resolved_id = config.usersToId.get(action["target_username"])
                        if resolved_id:
                            target_user_id = int(resolved_id)

                    if memory_id not in existing_ids:
                        if new_memory and category in VALID_CATEGORIES:
                            await self.bot.memory_service.save_memory(
                                guild_id=guild_id,
                                user_id=user_id,
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

        await self.bot.memory_service.enforce_max_memories(
            guild_id=guild_id,
            user_id=user_id,
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
            lines.append(f"[{msg.get('timestamp', 'unknown')}] {msg['content']}")
        return "\n".join(lines)

    async def force_extract_all(self, guild_id: str) -> int:
        config = await self.bot.config_service.get_config(guild_id)
        mem_cfg = config.memoryConfig
        if not mem_cfg.enabled:
            return 0

        if guild_id not in self._message_buffers:
            return 0

        processed = 0
        user_ids = list(self._message_buffers[guild_id].keys())
        for user_id_str in user_ids:
            user_id = int(user_id_str)
            messages = self._message_buffers[guild_id].get(user_id_str, [])
            if not messages:
                continue

            messages_to_process = messages[-mem_cfg.maxMessagesPerExtraction :]
            try:
                await self._extract_for_user(
                    guild_id=guild_id,
                    user_id=user_id,
                    messages=messages_to_process,
                    category_filter=None,
                    mem_cfg=mem_cfg,
                )
                self._message_buffers[guild_id][user_id_str] = []
                self._last_extraction.setdefault(guild_id, {})[user_id_str] = datetime.now(UTC).timestamp()
                processed += 1
            except Exception:
                self.logger.exception(f"Error force-extracting user {user_id_str} in guild {guild_id}")

        return processed

    async def force_extract_user(self, guild_id: str, user_id: int) -> bool:
        config = await self.bot.config_service.get_config(guild_id)
        mem_cfg = config.memoryConfig

        user_id_str = str(user_id)
        messages = self._message_buffers.get(guild_id, {}).get(user_id_str, [])
        if not messages:
            return False

        messages_to_process = messages[-mem_cfg.maxMessagesPerExtraction :]
        await self._extract_for_user(
            guild_id=guild_id,
            user_id=user_id,
            messages=messages_to_process,
            category_filter=None,
            mem_cfg=mem_cfg,
        )
        self._message_buffers[guild_id][user_id_str] = []
        self._last_extraction.setdefault(guild_id, {})[user_id_str] = datetime.now(UTC).timestamp()
        return True
