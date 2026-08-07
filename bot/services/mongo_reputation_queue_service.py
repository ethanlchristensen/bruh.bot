import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from bson import Int64, ObjectId

if TYPE_CHECKING:
    from bot.bruh_bot import BruhBot


class MongoReputationQueueService:
    def __init__(self, bot: "BruhBot"):
        self.bot = bot
        self.collection = self.bot.config_service.col(self.bot.config_service.base.mongoReputationQueueCollectionName)
        self.logger = logging.getLogger(__name__)

    async def initialize(self):
        await self.collection.create_index([("guild_id", 1), ("message_id", 1)], unique=True)
        await self.collection.create_index([("guild_id", 1), ("channel_id", 1), ("timestamp", 1)])
        await self.collection.create_index("created_at", expireAfterSeconds=604800)

    async def enqueue(self, guild_id: int, channel_id: int, message_id: int, content: str, author_id: int, author_name: str, timestamp: datetime, context_only: bool = False):
        doc = {
            "guild_id": Int64(guild_id),
            "channel_id": Int64(channel_id),
            "message_id": Int64(message_id),
            "content": content,
            "author_id": Int64(author_id),
            "author_name": author_name,
            "timestamp": timestamp,
            "context_only": context_only,
            "created_at": datetime.now(UTC),
        }
        await self.collection.update_one({"guild_id": Int64(guild_id), "message_id": Int64(message_id)}, {"$set": doc}, upsert=True)

    async def count(self, guild_id: int) -> int:
        return await self.collection.count_documents({"guild_id": Int64(guild_id), "context_only": {"$ne": True}})

    async def get_oldest_timestamp(self, guild_id: int):
        doc = await self.collection.find_one({"guild_id": Int64(guild_id), "context_only": {"$ne": True}}, sort=[("timestamp", 1)])
        return doc.get("timestamp") if doc else None

    async def get_pending_guild_ids(self) -> list[int]:
        rows = await self.collection.distinct("guild_id", {"context_only": {"$ne": True}})
        return [int(guild_id) for guild_id in rows]

    async def fetch_batch(self, guild_id: int, limit: int) -> list[dict]:
        cursor = self.collection.find({"guild_id": Int64(guild_id)}).sort("timestamp", 1)
        docs = []
        user_count = 0
        async for doc in cursor:
            if doc.get("context_only"):
                if user_count:
                    docs.append(doc)
                continue
            if user_count >= limit:
                break
            docs.append(doc)
            user_count += 1
        for doc in docs:
            doc["_id_oid"] = doc["_id"]
            doc["message_id"] = int(doc["message_id"])
            doc["author_id"] = int(doc["author_id"])
        return docs

    async def delete_ids(self, ids: list[ObjectId]):
        if ids:
            await self.collection.delete_many({"_id": {"$in": ids}})
