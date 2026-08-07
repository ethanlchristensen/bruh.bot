import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from bson import Int64, ObjectId

if TYPE_CHECKING:
    from bot.bruh_bot import BruhBot

QUEUE_TTL_DAYS = 7


class MongoExtractionQueueService:
    def __init__(self, bot: "BruhBot"):
        self.bot = bot
        self.collection = self.bot.config_service.col(self.bot.config_service.base.mongoMemoryQueueCollectionName)
        self.logger = logging.getLogger(__name__)

    async def initialize(self):
        await self._ensure_indexes()

    async def _ensure_indexes(self):
        try:
            await self.collection.create_index([("guild_id", 1), ("message_id", 1)], unique=True)
            await self.collection.create_index([("guild_id", 1), ("timestamp", 1)])
            try:
                await self.collection.create_index("created_at", expireAfterSeconds=QUEUE_TTL_DAYS * 86400)
            except Exception:
                self.logger.warning("Could not create TTL index on created_at; may need a MongoDB version that supports it")
            self.logger.info(f"Created indexes on {self.bot.config_service.base.mongoMemoryQueueCollectionName} collection")
        except Exception as e:
            self.logger.warning(f"Could not create indexes on extraction queue: {e}")

    async def enqueue(
        self,
        guild_id: int,
        message_id: int,
        content: str,
        author_id: int,
        author_name: str,
        timestamp: datetime,
        context_only: bool = False,
    ):
        doc = {
            "guild_id": Int64(guild_id),
            "message_id": Int64(message_id),
            "content": content,
            "author_id": Int64(author_id),
            "author_name": author_name,
            "timestamp": timestamp,
            "context_only": context_only,
            "created_at": datetime.now(UTC),
        }
        try:
            await self.collection.update_one(
                {"guild_id": Int64(guild_id), "message_id": Int64(message_id)},
                {"$set": doc},
                upsert=True,
            )
        except Exception:
            self.logger.exception(f"Failed to enqueue message {message_id} for guild {guild_id}")

    async def count(self, guild_id: int) -> int:
        return await self.collection.count_documents({"guild_id": Int64(guild_id), "context_only": {"$ne": True}})

    async def fetch_batch(self, guild_id: int, limit: int) -> list[dict]:
        cursor = self.collection.find({"guild_id": Int64(guild_id)}).sort("timestamp", 1)
        docs = []
        user_message_count = 0

        async for doc in cursor:
            if doc.get("context_only"):
                if user_message_count:
                    docs.append(doc)
                continue

            if user_message_count >= limit:
                break

            docs.append(doc)
            user_message_count += 1

        for doc in docs:
            doc["_id_oid"] = doc["_id"]
            doc["_id"] = str(doc["_id"])
            if doc.get("guild_id"):
                doc["guild_id"] = int(doc["guild_id"])
            if doc.get("message_id"):
                doc["message_id"] = int(doc["message_id"])
            if doc.get("author_id"):
                doc["author_id"] = int(doc["author_id"])
        return docs

    async def delete_ids(self, ids: list[ObjectId]):
        if not ids:
            return
        await self.collection.delete_many({"_id": {"$in": ids}})

    async def get_oldest_timestamp(self, guild_id: int):
        doc = await self.collection.find_one(
            {"guild_id": Int64(guild_id), "context_only": {"$ne": True}},
            sort=[("timestamp", 1)],
            projection={"timestamp": 1},
        )
        if doc:
            return doc["timestamp"]
        return None

    async def get_pending_guild_ids(self) -> list[int]:
        agg = await self.collection.aggregate(
            [
                {"$match": {"context_only": {"$ne": True}}},
                {"$group": {"_id": "$guild_id"}},
                {"$sort": {"_id": 1}},
            ]
        ).to_list(length=200)
        return [int(g["_id"]) for g in agg if g["_id"] is not None]

    async def fetch_for_user(self, guild_id: int, author_id: int, limit: int) -> list[dict]:
        cursor = self.collection.find({"guild_id": Int64(guild_id), "author_id": Int64(author_id), "context_only": {"$ne": True}}).sort("timestamp", 1).limit(limit)
        docs = await cursor.to_list(length=limit)
        for doc in docs:
            doc["_id_oid"] = doc["_id"]
            doc["_id"] = str(doc["_id"])
            if doc.get("guild_id"):
                doc["guild_id"] = int(doc["guild_id"])
            if doc.get("message_id"):
                doc["message_id"] = int(doc["message_id"])
            if doc.get("author_id"):
                doc["author_id"] = int(doc["author_id"])
        return docs

    async def delete_for_user(self, guild_id: int, author_id: int) -> int:
        result = await self.collection.delete_many({"guild_id": Int64(guild_id), "author_id": Int64(author_id)})
        return result.deleted_count
