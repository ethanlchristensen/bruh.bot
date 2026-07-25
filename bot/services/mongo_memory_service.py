import logging
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from bson import Int64, ObjectId

if TYPE_CHECKING:
    from bot.juno import Juno

CATEGORY_TTL_DAYS: dict[str, int | None] = {
    "identity": None,
    "trait": None,
    "preference": 90,
    "opinion": 30,
    "relationship": None,
    "mood": 7,
    "fact": 90,
    "admin": None,
}

VALID_CATEGORIES = list(CATEGORY_TTL_DAYS.keys())


def _expires_at_for_category(category: str) -> datetime | None:
    ttl_days = CATEGORY_TTL_DAYS.get(category)
    if ttl_days is None:
        return None
    return datetime.now(UTC) + timedelta(days=ttl_days)


class MongoMemoryService:

    def __init__(self, bot: "Juno"):
        self.bot = bot
        self.collection = self.bot.config_service.db[self.bot.config_service.base.mongoUserMemoriesCollectionName]
        self.logger = logging.getLogger(__name__)

    async def initialize(self):
        await self._ensure_indexes()

    async def _ensure_indexes(self):
        try:
            await self.collection.create_index([("guild_id", 1), ("user_id", 1)])
            await self.collection.create_index("expires_at", expireAfterSeconds=0)
            await self.collection.create_index("source_message_id")
            self.logger.info(f"Created indexes on {self.bot.config_service.base.mongoUserMemoriesCollectionName} collection")
        except Exception as e:
            self.logger.warning(f"Could not create indexes on UserMemories: {e}")

    async def save_memory(
        self,
        guild_id: int,
        user_id: int,
        memory: str,
        category: str,
        confidence: float,
        source_message_id: int | None = None,
        created_by: str = "ai",
        target_user_id: int | None = None,
    ) -> str:
        memory = memory.strip()
        if not memory or category not in VALID_CATEGORIES:
            raise ValueError(f"Invalid category: {category}")

        existing = await self.collection.find_one(
            {"guild_id": Int64(guild_id), "user_id": Int64(user_id), "memory": memory}
        )
        now = datetime.now(UTC)
        expires_at = _expires_at_for_category(category)

        if existing:
            update_set: dict = {"category": category, "confidence": confidence, "updated_at": now, "expires_at": expires_at}
            if target_user_id is not None:
                update_set["target_user_id"] = Int64(target_user_id)
            await self.collection.update_one(
                {"_id": existing["_id"]},
                {"$set": update_set},
            )
            self.logger.info(f"Updated memory '{memory[:50]}...' (id={existing['_id']})")
            return str(existing["_id"])

        doc = {
            "guild_id": Int64(guild_id),
            "user_id": Int64(user_id),
            "memory": memory,
            "category": category,
            "confidence": confidence,
            "source_message_id": Int64(source_message_id) if source_message_id is not None else None,
            "target_user_id": Int64(target_user_id) if target_user_id is not None else None,
            "created_at": now,
            "updated_at": now,
            "created_by": created_by,
            "expires_at": expires_at,
        }
        result = await self.collection.insert_one(doc)
        self.logger.info(f"Inserted memory '{memory[:50]}...' (id={result.inserted_id})")
        return str(result.inserted_id)

    async def delete_memory(self, memory_id: str, guild_id: int) -> bool:
        result = await self.collection.delete_one({"_id": ObjectId(memory_id), "guild_id": Int64(guild_id)})
        if result.deleted_count > 0:
            self.logger.info(f"Deleted memory {memory_id}")
            return True
        return False

    async def clear_user_memories(self, guild_id: int, user_id: int) -> int:
        result = await self.collection.delete_many({"guild_id": Int64(guild_id), "user_id": Int64(user_id)})
        self.logger.info(f"Cleared {result.deleted_count} memories for user {user_id} in guild {guild_id}")
        return result.deleted_count

    async def get_memories_for_user(
        self,
        guild_id: int,
        user_id: int,
        limit: int = 50,
        categories: list[str] | None = None,
    ) -> list[dict]:
        query: dict = {
            "guild_id": Int64(guild_id),
            "user_id": Int64(user_id),
            "$or": [
                {"expires_at": None},
                {"expires_at": {"$gte": datetime.now(UTC)}},
            ],
        }
        if categories:
            query["category"] = {"$in": categories}

        cursor = self.collection.find(query).sort("created_at", -1).limit(limit)
        memories = []
        async for doc in cursor:
            doc["_id"] = str(doc["_id"])
            if doc.get("guild_id"):
                doc["guild_id"] = int(doc["guild_id"])
            if doc.get("user_id"):
                doc["user_id"] = int(doc["user_id"])
            if doc.get("source_message_id"):
                doc["source_message_id"] = int(doc["source_message_id"])
            if doc.get("target_user_id"):
                doc["target_user_id"] = int(doc["target_user_id"])
            memories.append(doc)
        return memories

    async def get_memories_for_users(
        self,
        guild_id: int,
        user_ids: list[int],
        limit: int = 10,
    ) -> dict[int, list[dict]]:
        if not user_ids:
            return {}

        query = {
            "guild_id": Int64(guild_id),
            "user_id": {"$in": [Int64(uid) for uid in user_ids]},
            "$or": [
                {"expires_at": None},
                {"expires_at": {"$gte": datetime.now(UTC)}},
            ],
        }

        all_memories = []
        cursor = self.collection.find(query).sort("created_at", -1)
        async for doc in cursor:
            doc["_id"] = str(doc["_id"])
            if doc.get("guild_id"):
                doc["guild_id"] = int(doc["guild_id"])
            if doc.get("user_id"):
                doc["user_id"] = int(doc["user_id"])
            if doc.get("source_message_id"):
                doc["source_message_id"] = int(doc["source_message_id"])
            if doc.get("target_user_id"):
                doc["target_user_id"] = int(doc["target_user_id"])
            all_memories.append(doc)

        permanent = [m for m in all_memories if m["category"] in ("identity", "trait", "admin", "relationship")]
        recent = [m for m in all_memories if m["category"] not in ("identity", "trait", "admin")]

        selected = list(permanent)
        remaining = limit - len(selected)
        if remaining > 0:
            selected.extend(recent[:remaining])

        result: dict[int, list[dict]] = {}
        for m in selected:
            uid = m["user_id"]
            if uid not in result:
                result[uid] = []
            result[uid].append(m)

        return result

    async def get_memory_by_id(self, memory_id: str, guild_id: int) -> dict | None:
        doc = await self.collection.find_one({"_id": ObjectId(memory_id), "guild_id": Int64(guild_id)})
        if doc:
            doc["_id"] = str(doc["_id"])
            if doc.get("guild_id"):
                doc["guild_id"] = int(doc["guild_id"])
            if doc.get("user_id"):
                doc["user_id"] = int(doc["user_id"])
            if doc.get("source_message_id"):
                doc["source_message_id"] = int(doc["source_message_id"])
            if doc.get("target_user_id"):
                doc["target_user_id"] = int(doc["target_user_id"])
        return doc

    async def count_user_memories(self, guild_id: int, user_id: int) -> int:
        query = {
            "guild_id": Int64(guild_id),
            "user_id": Int64(user_id),
            "$or": [
                {"expires_at": None},
                {"expires_at": {"$gte": datetime.now(UTC)}},
            ],
        }
        return await self.collection.count_documents(query)

    async def trash_expired_memories(self, guild_id: int, user_id: int) -> int:
        query = {
            "guild_id": Int64(guild_id),
            "user_id": Int64(user_id),
            "expires_at": {"$lt": datetime.now(UTC), "$ne": None},
        }
        result = await self.collection.delete_many(query)
        return result.deleted_count

    async def update_memory(
        self,
        memory_id: str,
        guild_id: int,
        new_memory: str | None = None,
        category: str | None = None,
        confidence: float | None = None,
        target_user_id: int | None = None,
    ) -> bool:
        update_fields: dict = {"updated_at": datetime.now(UTC)}
        if new_memory is not None:
            update_fields["memory"] = new_memory.strip()
        if category is not None:
            if category not in VALID_CATEGORIES:
                raise ValueError(f"Invalid category: {category}")
            update_fields["category"] = category
            update_fields["expires_at"] = _expires_at_for_category(category)
        if confidence is not None:
            update_fields["confidence"] = confidence
        if target_user_id is not None:
            update_fields["target_user_id"] = Int64(target_user_id)

        result = await self.collection.update_one(
            {"_id": ObjectId(memory_id), "guild_id": Int64(guild_id)},
            {"$set": update_fields},
        )
        return result.modified_count > 0

    async def enforce_max_memories(self, guild_id: int, user_id: int, max_memories: int) -> int:
        count = await self.count_user_memories(guild_id, user_id)
        if count <= max_memories:
            return 0

        excess = count - max_memories
        cursor = self.collection.find(
            {"guild_id": Int64(guild_id), "user_id": Int64(user_id)},
            sort=[("confidence", 1), ("created_at", 1)],
        ).limit(excess)

        ids_to_delete = []
        async for doc in cursor:
            if doc["category"] in ("identity", "admin"):
                continue
            ids_to_delete.append(doc["_id"])

        if ids_to_delete:
            result = await self.collection.delete_many({"_id": {"$in": ids_to_delete}})
            self.logger.info(f"Enforced max memories for user {user_id}: removed {result.deleted_count}")
            return result.deleted_count
        return 0
