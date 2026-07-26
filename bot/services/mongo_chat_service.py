import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from bson import Int64

if TYPE_CHECKING:
    from bot.bruh_bot import BruhBot


class MongoChatService:
    """Service for managing stateful chat conversations in MongoDB using a parent-pointer tree."""

    def __init__(self, bot: "BruhBot"):
        self.bot = bot
        self.collection = self.bot.config_service.col(self.bot.config_service.base.mongoChatThreadsCollectionName)
        self.logger = logging.getLogger(__name__)
        import asyncio

        try:
            loop = asyncio.get_running_loop()
            if loop.is_running():
                loop.create_task(self.initialize())
        except RuntimeError:
            pass  # No running event loop (e.g. during test imports)

    async def initialize(self):
        """Initialize collection with indexes."""
        await self._ensure_indexes()

    async def _ensure_indexes(self):
        """Create indexes on the collection for faster retrieval and TTL cleanup."""
        try:
            # TTL index to automatically delete records older than 48 hours
            await self.collection.create_index("created_at", expireAfterSeconds=172800)
            await self.collection.create_index("channel_id")
            self.logger.info(f"Created indexes on {self.bot.config_service.base.mongoChatThreadsCollectionName} collection")
        except Exception as e:
            self.logger.warning(f"Could not create indexes on ChatThreads: {e}")

    async def save_message(self, message_id: int, channel_id: int, parent_id: int | None, role: str, content: str, author_name: str | None = None):
        """Save a message turn into the threads collection."""
        try:
            doc = {
                "_id": Int64(message_id),
                "channel_id": Int64(channel_id),
                "parent_id": Int64(parent_id) if parent_id is not None else None,
                "role": role,
                "content": content,
                "author_name": author_name,
                "created_at": datetime.now(UTC),
            }
            await self.collection.replace_one({"_id": Int64(message_id)}, doc, upsert=True)
            self.logger.info(f"Saved chat message {message_id} (parent: {parent_id}) in thread DB")
        except Exception as e:
            self.logger.error(f"Error saving chat message {message_id}: {e}")

    async def get_last_bot_message_id(self, channel_id: int) -> int | None:
        """Find the ID of the most recent message by the bot in a given channel."""
        try:
            doc = await self.collection.find_one({"channel_id": Int64(channel_id), "role": "assistant"}, sort=[("_id", -1)])
            return int(doc["_id"]) if doc else None
        except Exception as e:
            self.logger.error(f"Error getting last bot message ID: {e}")
            return None

    async def get_conversation_path(self, message_id: int, chain: list | None = None, visited: set | None = None) -> list[dict]:
        """Recursively walks up the parent chain to build the full conversation path."""
        if chain is None:
            chain = []
        if visited is None:
            visited = set()

        if message_id in visited:
            self.logger.warning(f"Circular reference detected at message {message_id}!")
            return chain
        visited.add(message_id)

        try:
            msg = await self.collection.find_one({"_id": Int64(message_id)})
            if not msg:
                # Fallback / End of known history
                return chain

            # Insert at the beginning to maintain chronological order
            chain.insert(0, {"role": msg["role"], "content": msg["content"], "author_name": msg.get("author_name"), "parent_id": msg.get("parent_id"), "_id": int(msg["_id"])})

            parent_id = msg.get("parent_id")
            if parent_id is not None:
                return await self.get_conversation_path(int(parent_id), chain, visited)

        except Exception as e:
            self.logger.error(f"Error while fetching conversation path for {message_id}: {e}")

        return chain
