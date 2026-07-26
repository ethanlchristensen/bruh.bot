import logging
from datetime import UTC, date, datetime
from typing import TYPE_CHECKING

from bson import Int64

if TYPE_CHECKING:
    from bot.bruh_bot import BruhBot


class MongoAIUsageTrackingService:
    def __init__(self, bot: "BruhBot"):
        self.bot = bot
        self.collection = self.bot.config_service.col(self.bot.config_service.base.mongoAIUsageTrackingCollectionName)
        self.logger = logging.getLogger(__name__)

    async def initialize(self):
        await self._ensure_indexes()

    async def _ensure_indexes(self):
        try:
            await self.collection.create_index([("guild_id", 1), ("user_id", 1), ("date", 1)], unique=True)
            await self.collection.create_index([("guild_id", 1), ("date", 1), ("total_cost", -1)])
            self.logger.info(f"Created indexes on {self.bot.config_service.base.mongoAIUsageTrackingCollectionName} collection")
        except Exception as e:
            self.logger.warning(f"Could not create indexes: {e}")

    async def track_usage(self, user_id: int, guild_id: int, input_tokens: int, output_tokens: int, cost: float, model: str):
        today = date.today().isoformat()
        model_key = model or "unknown"

        update = {
            "$inc": {
                "total_requests": 1,
                "total_input_tokens": input_tokens,
                "total_output_tokens": output_tokens,
                "total_cost": cost,
                f"models_used.{model_key}.requests": 1,
                f"models_used.{model_key}.input_tokens": input_tokens,
                f"models_used.{model_key}.output_tokens": output_tokens,
                f"models_used.{model_key}.cost": cost,
            },
            "$set": {"last_updated": datetime.now(UTC)},
        }

        try:
            await self.collection.update_one(
                {"guild_id": Int64(guild_id), "user_id": Int64(user_id), "date": today},
                update,
                upsert=True,
            )
        except Exception as e:
            self.logger.error(f"Failed to track usage for user {user_id}: {e}")

    async def get_leaderboard(self, guild_id: int, start_date: str | None = None, end_date: str | None = None, limit: int = 25) -> list[dict]:
        match: dict = {"guild_id": Int64(guild_id)}
        if start_date and end_date:
            match["date"] = {"$gte": start_date, "$lte": end_date}
        elif start_date:
            match["date"] = {"$gte": start_date}
        elif end_date:
            match["date"] = {"$lte": end_date}

        # Pass 1: aggregate totals across all dates
        pipeline = [
            {"$match": match},
            {
                "$group": {
                    "_id": "$user_id",
                    "total_requests": {"$sum": "$total_requests"},
                    "total_input_tokens": {"$sum": "$total_input_tokens"},
                    "total_output_tokens": {"$sum": "$total_output_tokens"},
                    "total_cost": {"$sum": "$total_cost"},
                },
            },
            {"$sort": {"total_cost": -1}},
            {"$limit": limit},
            {
                "$project": {
                    "user_id": {"$toString": "$_id"},
                    "total_requests": 1,
                    "total_input_tokens": 1,
                    "total_output_tokens": 1,
                    "total_cost": 1,
                },
            },
        ]

        cursor = self.collection.aggregate(pipeline)
        results = []
        user_ids: list[str] = []
        async for doc in cursor:
            doc["models_used"] = {}
            config = await self.bot.config_service.get_config(str(guild_id))
            username = config.idToUsers.get(doc["user_id"])
            doc["username"] = username or f"User {doc['user_id']}"
            results.append(doc)
            user_ids.append(doc["user_id"])

        if not results:
            return results

        # Pass 2: aggregate per-model stats for the same users
        model_match = {**match, "user_id": {"$in": [Int64(int(uid)) for uid in user_ids]}}
        model_pipeline = [
            {"$match": model_match},
            {
                "$project": {
                    "user_id": 1,
                    "models_array": {"$objectToArray": {"$ifNull": ["$models_used", {}]}},
                }
            },
            {"$unwind": "$models_array"},
            {
                "$group": {
                    "_id": {"user_id": "$user_id", "model": "$models_array.k"},
                    "requests": {"$sum": {"$ifNull": ["$models_array.v.requests", 0]}},
                    "input_tokens": {"$sum": {"$ifNull": ["$models_array.v.input_tokens", 0]}},
                    "output_tokens": {"$sum": {"$ifNull": ["$models_array.v.output_tokens", 0]}},
                    "cost": {"$sum": {"$ifNull": ["$models_array.v.cost", 0]}},
                },
            },
        ]

        model_cursor = self.collection.aggregate(model_pipeline)
        models_by_user: dict[str, dict] = {}
        async for doc in model_cursor:
            uid = str(doc["_id"]["user_id"])
            if uid not in models_by_user:
                models_by_user[uid] = {}
            models_by_user[uid][doc["_id"]["model"]] = {
                "requests": doc["requests"],
                "input_tokens": doc["input_tokens"],
                "output_tokens": doc["output_tokens"],
                "cost": doc["cost"],
            }

        for r in results:
            r["models_used"] = models_by_user.get(r["user_id"], {})

        return results

    async def get_leaderboard_summary(self, guild_id: int, start_date: str | None = None, end_date: str | None = None) -> dict:
        match: dict = {"guild_id": Int64(guild_id)}
        if start_date and end_date:
            match["date"] = {"$gte": start_date, "$lte": end_date}
        elif start_date:
            match["date"] = {"$gte": start_date}
        elif end_date:
            match["date"] = {"$lte": end_date}

        pipeline = [
            {"$match": match},
            {
                "$group": {
                    "_id": None,
                    "total_requests": {"$sum": "$total_requests"},
                    "total_cost": {"$sum": "$total_cost"},
                    "total_input_tokens": {"$sum": "$total_input_tokens"},
                    "total_output_tokens": {"$sum": "$total_output_tokens"},
                },
            },
        ]

        cursor = self.collection.aggregate(pipeline)
        async for doc in cursor:
            return {
                "total_requests": doc["total_requests"],
                "total_cost": doc["total_cost"],
                "total_input_tokens": doc["total_input_tokens"],
                "total_output_tokens": doc["total_output_tokens"],
            }

        return {"total_requests": 0, "total_cost": 0, "total_input_tokens": 0, "total_output_tokens": 0}

    async def get_user_usage(self, user_id: int, guild_id: int, start_date: str | None = None, end_date: str | None = None) -> dict:
        match: dict = {"guild_id": Int64(guild_id), "user_id": Int64(user_id)}
        if start_date and end_date:
            match["date"] = {"$gte": start_date, "$lte": end_date}
        elif start_date:
            match["date"] = {"$gte": start_date}
        elif end_date:
            match["date"] = {"$lte": end_date}

        # Pass 1: aggregate totals across all dates
        pipeline = [
            {"$match": match},
            {
                "$group": {
                    "_id": "$user_id",
                    "total_requests": {"$sum": "$total_requests"},
                    "total_input_tokens": {"$sum": "$total_input_tokens"},
                    "total_output_tokens": {"$sum": "$total_output_tokens"},
                    "total_cost": {"$sum": "$total_cost"},
                },
            },
        ]

        cursor = self.collection.aggregate(pipeline)
        result = None
        async for doc in cursor:
            result = {
                "user_id": str(doc["_id"]),
                "total_requests": doc["total_requests"],
                "total_input_tokens": doc["total_input_tokens"],
                "total_output_tokens": doc["total_output_tokens"],
                "total_cost": doc["total_cost"],
                "models_used": {},
            }

        if not result:
            return {"user_id": str(user_id), "total_requests": 0, "total_input_tokens": 0, "total_output_tokens": 0, "total_cost": 0, "models_used": {}}

        # Pass 2: aggregate per-model stats
        model_pipeline = [
            {"$match": match},
            {
                "$project": {
                    "models_array": {"$objectToArray": {"$ifNull": ["$models_used", {}]}},
                }
            },
            {"$unwind": "$models_array"},
            {
                "$group": {
                    "_id": "$models_array.k",
                    "requests": {"$sum": {"$ifNull": ["$models_array.v.requests", 0]}},
                    "input_tokens": {"$sum": {"$ifNull": ["$models_array.v.input_tokens", 0]}},
                    "output_tokens": {"$sum": {"$ifNull": ["$models_array.v.output_tokens", 0]}},
                    "cost": {"$sum": {"$ifNull": ["$models_array.v.cost", 0]}},
                },
            },
        ]

        model_cursor = self.collection.aggregate(model_pipeline)
        async for doc in model_cursor:
            result["models_used"][doc["_id"]] = {
                "requests": doc["requests"],
                "input_tokens": doc["input_tokens"],
                "output_tokens": doc["output_tokens"],
                "cost": doc["cost"],
            }

        return result
