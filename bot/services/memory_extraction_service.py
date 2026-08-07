import asyncio
import logging
import re
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from bot.services.ai.gateway.gateway import get_mesh_gateway
from bot.services.ai.gateway.schemas.request import Message, MessagePart, NormalizedRequest
from bot.services.memory_tools import MEMORY_TOOL_SCHEMAS, MemoryToolExecutor

if TYPE_CHECKING:
    import discord

    from bot.bruh_bot import BruhBot

EXTRACTION_SYSTEM_PROMPT = """You are a memory extraction system for a Discord bot. Your job is to analyze a group conversation and maintain structured memories about multiple users using the tools provided.

## MEMORY CATEGORIES AND RETENTION RULES:
- identity: Permanent (immutable facts like name, age, location, role). Never expires.
- trait: Permanent (personality traits, skills, profession, abilities). Never expires.
- preference: 90-day retention (likes, dislikes, favorites, preferences).
- opinion: 30-day retention (opinions on topics, beliefs, stances).
- relationship: Permanent (how they feel about other people, relationships). Include 'target_username' with the Discord display name of the person this memory is about.
- mood: 7-day retention (current emotional state, temporary feelings).
- fact: 90-day retention (general facts about the user).
- admin: Permanent (manually added by admins). YOU MUST NEVER CREATE 'admin' CATEGORY MEMORIES.

## WHAT TO EXTRACT:
Memories must be CORE to who the user IS — their identity, personality, likes/dislikes, opinions, skills, and relationships. Good examples:
- "is a software engineer" (identity)
- "loves dark humor and roasts people" (trait)
- "hates pineapple on pizza" (preference)
- "thinks AI will replace most jobs by 2030" (opinion)
- "dislikes Klim" (relationship)
- "plays guitar" (fact/skill)

## WHAT NOT TO EXTRACT — SKIP THESE ENTIRELY:
- One-off actions: sharing a link, posting a meme, saying "lol", greeting someone
- Ephemeral chatter: "shared a YouTube video", "posted a gif", "good morning", "how was your day"
- Server logistics: asking for roles, reporting bugs, asking bot commands, troubleshooting
- Vague/generic statements: "that's cool", "I agree", "nice", "same"
- Conversational filler: jokes without personality insight, reaction gifs, "based", "fr fr"
- Transient states: what they're currently doing/watching/eating right now (unless it reveals a strong preference/identity)
- Anything that won't matter about this person a week from now

## GOLDEN RULE:
Ask yourself: "Does this tell me something meaningful about WHO this person IS — their identity, personality, or tastes — not just what they casually DID?" If the answer is no, do NOT add a memory.

## WORKFLOW — USE YOUR TOOLS:
The conversation transcript will be provided in a user message along with the list of participating users.

1. **Search before you add**: For each observation you want to record, first call `search_memories` to check if you already know something similar. If a highly relevant existing memory exists (score > 0.90), call `update_memory` instead of `add_memory` to refine it.

2. **Get the full picture**: For users you haven't learned much about yet, call `get_user_memories` to see all their existing memories before making decisions.

3. **Add new insights**: When you discover a new meaningful fact/trait/preference about someone, call `add_memory` with appropriate category and confidence (0.9+ for explicit statements, 0.5-0.7 for implied).

4. **Update when facts change**: If a user says something that contradicts or supersedes an existing memory, call `update_memory` with the corrected information.

5. **Remove contradictions**: If a user explicitly disavows something you stored as a memory, call `remove_memory` with a reason.

6. **Be conservative**: Only extract clear, meaningful information about the user's identity. When in doubt, skip it. It's better to miss a weak signal than to store noise.

7. **MULTI-USER AWARENESS**: Use conversational context — if one person says something and another agrees, that implies the second person shares that trait/preference/opinion too. Process ALL users in the conversation, not just one.

8. Bot messages are context only. NEVER extract, update, remove, search, or otherwise perform memory operations for the bot. Focus only on the human users from the provided user list.

9. NEVER create 'admin' category memories — those are manually added by server admins only.

10. For relationship memories, use `target_username` matching names from the KNOWN USERS list exactly.

After you have finished analyzing the transcript and applied all necessary changes, simply stop calling tools and output a brief summary of what you changed."""


class MemoryExtractionService:
    def __init__(self, bot: "BruhBot"):
        self.bot = bot
        self.logger = logging.getLogger(__name__)
        self._message_locks: dict[str, asyncio.Lock] = {}
        self._last_extraction: dict[str, float] = {}
        self._last_was_bot: set[str] = set()
        self._running = False
        self._main_task: asyncio.Task | None = None

    @property
    def q(self):
        return self.bot.extraction_queue_service

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

        if guild_id not in self._message_locks:
            self._message_locks[guild_id] = asyncio.Lock()
        if guild_id not in self._last_extraction:
            self._last_extraction[guild_id] = 0.0

        self._last_was_bot.discard(guild_id)

        await self.q.enqueue(
            guild_id=message.guild.id,
            message_id=message.id,
            content=content,
            author_id=message.author.id,
            author_name=message.author.display_name,
            timestamp=message.created_at,
        )

    async def enqueue_bot_context(self, message: "discord.Message", content: str):
        """Stage bot responses as transcript context, skipping runs of consecutive bot messages."""
        if not message.guild or not content.strip():
            return

        gid = str(message.guild.id)
        if gid in self._last_was_bot:
            return

        config = await self.bot.config_service.get_config(gid)
        if not config.memoryConfig.enabled:
            return

        self._last_was_bot.add(gid)

        await self.q.enqueue(
            guild_id=message.guild.id,
            message_id=message.id,
            content=content.strip()[:2000],
            author_id=self.bot.user.id,
            author_name=self.bot.user.name,
            timestamp=message.created_at,
            context_only=True,
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
        guild_ids = []
        if self.bot.guilds:
            guild_ids = [g.id for g in self.bot.guilds]
        else:
            guild_ids = await self.q.get_pending_guild_ids()

        for guild_id in guild_ids:
            try:
                config = await self.bot.config_service.get_config(str(guild_id))
                mem_cfg = config.memoryConfig
                if not mem_cfg.enabled:
                    continue

                interval_minutes = min(mem_cfg.extractionIntervalMinutes, mem_cfg.moodExtractionIntervalMinutes)
                if interval_minutes <= 0:
                    continue

                interval_seconds = interval_minutes * 60
                gid = str(guild_id)

                if gid not in self._message_locks:
                    self._message_locks[gid] = asyncio.Lock()
                if gid not in self._last_extraction:
                    self._last_extraction[gid] = 0.0

                async with self._message_locks[gid]:
                    now_ts = datetime.now(UTC).timestamp()
                    last = self._last_extraction.get(gid, 0.0)
                    if now_ts - last < interval_seconds:
                        continue

                    count = await self.q.count(guild_id)
                    if count == 0:
                        continue

                    if count < mem_cfg.minMessagesForExtraction:
                        oldest = await self.q.get_oldest_timestamp(guild_id)
                        if oldest is None:
                            continue
                        age_minutes = (datetime.now(UTC) - oldest.replace(tzinfo=UTC)).total_seconds() / 60
                        if age_minutes < mem_cfg.maxExtractionWaitMinutes:
                            continue

                    messages_to_process = await self.q.fetch_batch(guild_id, mem_cfg.maxMessagesPerExtraction)
                    if not messages_to_process:
                        continue

                    await self._extract_for_guild(
                        guild_id=gid,
                        messages=messages_to_process,
                        mem_cfg=mem_cfg,
                    )

                    oids = [m["_id_oid"] for m in messages_to_process if m.get("_id_oid")]
                    await self.q.delete_ids(oids)
                    self._last_was_bot.discard(gid)
                    self._last_extraction[gid] = now_ts
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
            if msg.get("context_only"):
                continue
            author_id = msg.get("author_id")
            if author_id:
                author_ids_in_batch.add(int(author_id))
            for match in re.finditer(r"<@!?(\d+)>", msg.get("content", "")):
                mid = int(match.group(1))
                if mid != self.bot.user.id:
                    author_ids_in_batch.add(mid)

        conversation_lines = []
        for msg in messages:
            name = msg.get("author_name", str(msg.get("author_id", "unknown")))
            content = self._resolve_mentions_in_text(msg["content"], id_to_users, guild)
            msg_id = msg.get("message_id")
            context_marker = " (context only)" if msg.get("context_only") else ""
            if msg_id is not None:
                conversation_lines.append(f"[{name}{context_marker} (msg:{msg_id})]: {content}")
            else:
                conversation_lines.append(f"[{name}{context_marker}]: {content}")
        transcript = "\n".join(conversation_lines)

        participants = []
        for uid_int in sorted(author_ids_in_batch):
            canonical_name = id_to_users.get(str(uid_int))
            if not canonical_name and guild:
                member = guild.get_member(uid_int)
                if member:
                    canonical_name = member.display_name
            if not canonical_name:
                canonical_name = str(uid_int)
            participants.append(f"- {canonical_name} (user_id: {uid_int})")

        known_users = "\n".join(f"- {name}" for name in sorted(config.usersToId.keys())) if config.usersToId else "(no known users registered)"

        user_prompt = f"""## CONVERSATION TRANSCRIPT (newest first):
{transcript}

## PARTICIPATING USERS:
{chr(10).join(participants)}

## KNOWN USERS IN THIS SERVER (for relationship target_username matching):
{known_users}

Analyze the conversation transcript above. Follow your workflow: search for existing memories first, then add/update/remove as needed. Process ALL participating users."""

        ai_cfg = config.aiConfig
        provider = mem_cfg.extractionProvider
        provider_config = getattr(ai_cfg, provider, None) or ai_cfg.openrouter
        api_key = provider_config.get_api_key()
        model = mem_cfg.extractionModel or provider_config.preferredModel

        executor = MemoryToolExecutor(
            bot=self.bot,
            guild_id=int(guild_id),
            valid_user_ids=author_ids_in_batch,
            id_to_users=id_to_users,
            users_to_id=config.usersToId,
            mem_cfg=mem_cfg,
        )

        messages_list: list[Message] = [
            Message(role="system", parts=[MessagePart(type="text", text=EXTRACTION_SYSTEM_PROMPT)]),
            Message(role="user", parts=[MessagePart(type="text", text=user_prompt)]),
        ]

        max_rounds = mem_cfg.maxToolRounds
        total_tool_calls = 0
        touched_users: set[int] = set()

        try:
            gateway = get_mesh_gateway()

            for _round in range(max_rounds):
                req = NormalizedRequest(
                    provider=provider,
                    model=model,
                    messages=messages_list,
                    tools=MEMORY_TOOL_SCHEMAS,
                    temperature=0.3,
                )

                response = await gateway.complete(req, credentials={"api_key": api_key})

                tool_call_parts = [p for p in response.parts if p.type == "tool_call"]
                text_parts = [p for p in response.parts if p.type == "text"]

                if not tool_call_parts:
                    summary = "".join(p.content for p in text_parts) if text_parts else "(no summary)"
                    self.logger.info(f"Extraction complete for guild {guild_id} after {_round + 1} rounds: {summary[:200]}")
                    break

                assistant_parts = [MessagePart(type="tool_call", tool_call_id=tc.content["id"], name=tc.content["name"], arguments=tc.content["arguments"]) for tc in tool_call_parts]
                if text_parts:
                    assistant_parts.insert(0, MessagePart(type="text", text="".join(p.content for p in text_parts)))
                messages_list.append(Message(role="assistant", parts=assistant_parts))

                tool_results = []
                for tc in tool_call_parts:
                    if total_tool_calls >= mem_cfg.maxToolCallsPerBatch:
                        self.logger.warning(f"Hit max tool calls ({mem_cfg.maxToolCallsPerBatch}) for guild {guild_id}")
                        break

                    result = await executor.execute(tc.content["name"], tc.content["arguments"])
                    total_tool_calls += 1

                    if result.get("ok") or result.get("count") is not None or result.get("memories") is not None:
                        if tc.content["name"] in ("add_memory", "update_memory", "remove_memory"):
                            uid = tc.content["arguments"].get("user_id")
                            if uid:
                                touched_users.add(int(uid))
                            elif tc.content["name"] == "remove_memory":
                                pass

                    tool_results.append(
                        MessagePart(
                            type="tool_result",
                            tool_call_id=tc.content["id"],
                            content=result,
                        )
                    )

                if tool_results:
                    messages_list.append(Message(role="tool", parts=tool_results))

                if total_tool_calls >= mem_cfg.maxToolCallsPerBatch:
                    self.logger.warning(f"Stopping extraction for guild {guild_id} after {total_tool_calls} tool calls")
                    break

            stats = executor._stats
            self.logger.info(
                f"Extraction stats for guild {guild_id}: {total_tool_calls} tool calls in {_round + 1} rounds (search={stats['search_calls']}, get={stats['get_calls']}, add={stats['add_calls']}, update={stats['update_calls']}, remove={stats['remove_calls']}, deduped={stats['deduped_adds']}, errors={stats['errors']})"
            )

            all_touched = touched_users | {uid for uid in author_ids_in_batch if uid in touched_users or stats.get("add_calls", 0) + stats.get("update_calls", 0) + stats.get("remove_calls", 0) > 0}
            if not all_touched:
                all_touched = author_ids_in_batch

            for uid in all_touched:
                await self.bot.memory_service.enforce_max_memories(
                    guild_id=int(guild_id),
                    user_id=uid,
                    max_memories=mem_cfg.maxMemoriesPerUser,
                )

        except Exception:
            self.logger.exception(f"Error during memory extraction for guild {guild_id}")

    @staticmethod
    def _resolve_mentions_in_text(text: str, id_to_users: dict[str, str], guild=None) -> str:
        def replace_mention(match: re.Match) -> str:
            user_id = match.group(1)
            member = guild.get_member(int(user_id)) if guild else None
            name = member.display_name if member else id_to_users.get(user_id)
            return f"@{name}" if name else match.group(0)

        return re.sub(r"<@!?(\d+)>", replace_mention, text)

    async def force_extract_all(self, guild_id: str) -> int:
        config = await self.bot.config_service.get_config(guild_id)
        mem_cfg = config.memoryConfig
        if not mem_cfg.enabled:
            return 0

        guild_id_int = int(guild_id)

        count = await self.q.count(guild_id_int)
        if count == 0:
            return 0

        async with self._message_locks.get(guild_id, asyncio.Lock()):
            messages_to_process = await self.q.fetch_batch(guild_id_int, mem_cfg.maxMessagesPerExtraction)
            if not messages_to_process:
                return 0

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

            oids = [m["_id_oid"] for m in messages_to_process if m.get("_id_oid")]
            await self.q.delete_ids(oids)
            self._last_was_bot.discard(guild_id)
            self._last_extraction[guild_id] = datetime.now(UTC).timestamp()

        return len(user_ids_in_batch)

    async def force_extract_user(self, guild_id: str, user_id: int) -> bool:
        config = await self.bot.config_service.get_config(guild_id)
        mem_cfg = config.memoryConfig

        user_id_int = int(user_id)
        guild_id_int = int(guild_id)

        user_messages = await self.q.fetch_for_user(guild_id_int, user_id_int, mem_cfg.maxMessagesPerExtraction)
        if not user_messages:
            return False

        messages_to_process = user_messages
        await self._extract_for_guild(
            guild_id=guild_id,
            messages=messages_to_process,
            mem_cfg=mem_cfg,
        )

        oids = [m["_id_oid"] for m in messages_to_process if m.get("_id_oid")]
        await self.q.delete_ids(oids)
        self._last_was_bot.discard(guild_id)
        self._last_extraction[guild_id] = datetime.now(UTC).timestamp()
        return True
