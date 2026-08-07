import asyncio
import logging
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from bot.services.ai.gateway.gateway import get_mesh_gateway
from bot.services.ai.gateway.schemas.request import Message, MessagePart, NormalizedRequest

if TYPE_CHECKING:
    import discord

    from bot.bruh_bot import BruhBot

logger = logging.getLogger(__name__)

REPUTATION_TOOLS = [
    {
        "name": "record_reputation_event",
        "description": "Record a high-confidence harmful interaction directed at the bot. Never target the bot or a context-only message.",
        "parameters": {
            "type": "object",
            "properties": {
                "user_id": {"type": "integer"},
                "source_message_id": {"type": "integer"},
                "reason_code": {"type": "string", "enum": ["helpful_interaction", "respectful_interaction", "interaction_spam", "bot_targeted_abuse", "targeted_harassment", "threat_or_intimidation", "block_evasion"]},
                "severity": {"type": "integer", "enum": [1, 2, 3]},
                "confidence": {"type": "number"},
                "summary": {"type": "string"},
            },
            "required": ["user_id", "source_message_id", "reason_code", "severity", "confidence", "summary"],
        },
    }
]

SYSTEM_PROMPT = """You review staged Discord interactions with this bot for reputation events.
Bot messages marked context only explain the conversation but MUST NEVER be scored or targeted.
Record high-confidence, clearly harmful behavior directed at the bot: targeted abuse, harassment, threats, repeated interaction spam, or block evasion. You may also record clear, meaningful helpful or respectful interactions that demonstrate sustained good-faith engagement.
Do not score criticism, disagreement, ordinary profanity, protected-trait discussion, or negative sentiment alone.
Only target listed human participants and use their exact source message IDs. If no clear event exists, do not call tools."""


class ReputationExtractionService:
    def __init__(self, bot: "BruhBot"):
        self.bot = bot
        self._running = False
        self._task: asyncio.Task | None = None
        self._last_run: dict[str, float] = {}

    @property
    def q(self):
        return self.bot.reputation_queue_service

    async def enqueue_message(self, message: "discord.Message"):
        if not message.guild or message.author.bot:
            return
        config = await self.bot.config_service.get_config(str(message.guild.id))
        cfg = config.reputationConfig
        content = message.content.strip()
        if not cfg.enabled or len(content) < cfg.minMessageLength:
            return
        await self.q.enqueue(message.guild.id, message.channel.id, message.id, content, message.author.id, message.author.display_name, message.created_at)

    async def enqueue_bot_context(self, message: "discord.Message", content: str):
        if not message.guild or not content.strip():
            return
        config = await self.bot.config_service.get_config(str(message.guild.id))
        if config.reputationConfig.enabled:
            await self.q.enqueue(message.guild.id, message.channel.id, message.id, content.strip(), self.bot.user.id, self.bot.user.name, message.created_at, context_only=True)

    async def start_extraction_loops(self):
        self._running = True
        self._task = asyncio.create_task(self._main_loop())

    async def _main_loop(self):
        while self._running:
            try:
                for guild_id in await self.q.get_pending_guild_ids():
                    await self._process_guild(guild_id)
            except Exception:
                logger.exception("Reputation extraction loop failed")
            await asyncio.sleep(60)

    async def _process_guild(self, guild_id: int):
        config = await self.bot.config_service.get_config(str(guild_id))
        cfg = config.reputationConfig
        if not cfg.enabled:
            return
        now = datetime.now(UTC)
        if now.timestamp() - self._last_run.get(str(guild_id), 0) < cfg.extractionIntervalMinutes * 60:
            return
        count = await self.q.count(guild_id)
        oldest = await self.q.get_oldest_timestamp(guild_id)
        if oldest and oldest.tzinfo is None:
            oldest = oldest.replace(tzinfo=UTC)
        if not count or (count < cfg.minMessagesForExtraction and oldest and now - oldest < timedelta(minutes=cfg.maxExtractionWaitMinutes)):
            return
        batch = await self.q.fetch_batch(guild_id, cfg.maxMessagesPerExtraction)
        if not batch:
            return
        await self._extract(guild_id, batch, config)
        await self.q.delete_ids([row["_id_oid"] for row in batch])
        self._last_run[str(guild_id)] = now.timestamp()

    async def _extract(self, guild_id: int, batch: list[dict], config):
        participants = {row["author_id"] for row in batch if not row.get("context_only") and row["author_id"] != self.bot.user.id}
        transcript = "\n".join(f"[{row['author_name']}{' (context only)' if row.get('context_only') else ''} (msg:{row['message_id']})]: {row['content']}" for row in batch)
        prompt = f"## TRANSCRIPT\n{transcript}\n\n## ELIGIBLE HUMAN USER IDS\n{sorted(participants)}"
        cfg = config.reputationConfig
        provider_config = getattr(config.aiConfig, cfg.extractionProvider, None) or config.aiConfig.openrouter
        request_messages = [Message(role="system", parts=[MessagePart(type="text", text=SYSTEM_PROMPT)]), Message(role="user", parts=[MessagePart(type="text", text=prompt)])]
        for _ in range(cfg.maxToolRounds):
            response = await get_mesh_gateway().complete(NormalizedRequest(provider=cfg.extractionProvider, model=cfg.extractionModel or provider_config.preferredModel, messages=request_messages, tools=REPUTATION_TOOLS, temperature=0.1), credentials={"api_key": provider_config.get_api_key()})
            calls = [part for part in response.parts if part.type == "tool_call"]
            if not calls:
                return
            results = []
            for call in calls[: cfg.maxToolCallsPerBatch]:
                args = call.content["arguments"]
                if call.content["name"] != "record_reputation_event" or int(args.get("user_id", 0)) not in participants or int(args.get("source_message_id", 0)) not in {row["message_id"] for row in batch if not row.get("context_only")}:
                    result = {"ok": False, "error": "Invalid reputation target"}
                else:
                    result = await self.bot.reputation_service.record_event(guild_id=guild_id, channel_id=next(row["channel_id"] for row in batch if row["message_id"] == int(args["source_message_id"])), **args)
                results.append(MessagePart(type="tool_result", tool_call_id=call.content["id"], content=result))
            request_messages.append(Message(role="assistant", parts=[MessagePart(type="tool_call", tool_call_id=call.content["id"], name=call.content["name"], arguments=call.content["arguments"]) for call in calls]))
            request_messages.append(Message(role="tool", parts=results))
