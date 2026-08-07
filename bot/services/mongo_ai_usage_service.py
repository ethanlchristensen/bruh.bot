import asyncio
import logging
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from bson import Int64

if TYPE_CHECKING:
    from bot.bruh_bot import BruhBot


class MongoAIUsageService:
    def __init__(self, bot: "BruhBot"):
        self.bot = bot
        self.collection = self.bot.config_service.col(self.bot.config_service.base.mongoAIUsageCollectionName)
        self.logger = logging.getLogger(__name__)
        self._request_locks: dict[tuple[int, int], asyncio.Lock] = {}

    async def initialize(self):
        await self._ensure_indexes()

    async def _ensure_indexes(self):
        try:
            await self.collection.create_index([("guild_id", 1), ("user_id", 1)], unique=True)
            await self.collection.create_index("minute_reset_at")
            await self.collection.create_index("hour_reset_at")
            self.logger.info(f"Created indexes on ${self.bot.config_service.base.mongoAIUsageCollectionName} collection")
        except Exception as e:
            self.logger.warning(f"Could not create indexes: {e}")

    async def _get_limits(self, guild_id: int) -> tuple[int, int, bool]:
        config = await self.bot.config_service.get_config(str(guild_id))
        limits = config.aiConfig.usageLimits
        return limits.maxRequestsPerMinute, limits.maxRequestsPerHour, limits.enabled

    def _sliding_minute_window(self) -> datetime:
        return datetime.now(UTC) + timedelta(minutes=1)

    def _sliding_hour_window(self) -> datetime:
        return datetime.now(UTC) + timedelta(hours=1)

    async def can_make_request(self, user_id: int, guild_id: int) -> tuple[bool, str]:
        per_minute, per_hour, enabled = await self._get_limits(guild_id)

        if not enabled:
            return True, ""

        now = datetime.now(UTC)
        user_data = await self.collection.find_one({"guild_id": Int64(guild_id), "user_id": Int64(user_id)})

        if not user_data:
            return True, ""

        user_per_minute = user_data.get("max_per_minute", per_minute) if user_data.get("custom_limits") else per_minute
        user_per_hour = user_data.get("max_per_hour", per_hour) if user_data.get("custom_limits") else per_hour

        minute_reset = user_data.get("minute_reset_at")
        if isinstance(minute_reset, str):
            minute_reset = datetime.fromisoformat(minute_reset)
        if minute_reset and minute_reset.tzinfo is None:
            minute_reset = minute_reset.replace(tzinfo=UTC)

        hour_reset = user_data.get("hour_reset_at")
        if isinstance(hour_reset, str):
            hour_reset = datetime.fromisoformat(hour_reset)
        if hour_reset and hour_reset.tzinfo is None:
            hour_reset = hour_reset.replace(tzinfo=UTC)

        minute_count = user_data.get("minute_count", 0)
        hour_count = user_data.get("hour_count", 0)

        if minute_reset and now >= minute_reset:
            minute_count = 0
        if hour_reset and now >= hour_reset:
            hour_count = 0

        if minute_count >= user_per_minute:
            remaining_seconds = int((minute_reset - now).total_seconds())
            return False, f"Rate limit reached: {user_per_minute} requests per minute. Try again in {remaining_seconds}s."

        if hour_count >= user_per_hour:
            remaining_seconds = int((hour_reset - now).total_seconds())
            remaining_minutes = remaining_seconds // 60
            return False, f"Rate limit reached: {user_per_hour} requests per hour. Try again in {remaining_minutes}m {remaining_seconds % 60}s."

        return True, ""

    async def increment_usage(self, user_id: int, guild_id: int):
        per_minute, per_hour, _ = await self._get_limits(guild_id)
        now = datetime.now(UTC)

        user_data = await self.collection.find_one({"guild_id": Int64(guild_id), "user_id": Int64(user_id)})

        if not user_data:
            await self.collection.update_one(
                {"guild_id": Int64(guild_id), "user_id": Int64(user_id)},
                {
                    "$set": {
                        "minute_count": 1,
                        "hour_count": 1,
                        "minute_reset_at": self._sliding_minute_window(),
                        "hour_reset_at": self._sliding_hour_window(),
                        "max_per_minute": per_minute,
                        "max_per_hour": per_hour,
                        "custom_limits": False,
                    },
                },
                upsert=True,
            )
            return

        now = datetime.now(UTC)

        minute_reset = user_data.get("minute_reset_at")
        if isinstance(minute_reset, str):
            minute_reset = datetime.fromisoformat(minute_reset)
        if minute_reset and minute_reset.tzinfo is None:
            minute_reset = minute_reset.replace(tzinfo=UTC)

        hour_reset = user_data.get("hour_reset_at")
        if isinstance(hour_reset, str):
            hour_reset = datetime.fromisoformat(hour_reset)
        if hour_reset and hour_reset.tzinfo is None:
            hour_reset = hour_reset.replace(tzinfo=UTC)

        update_fields = {}
        if not minute_reset or now >= minute_reset:
            update_fields["minute_count"] = 1
            update_fields["minute_reset_at"] = self._sliding_minute_window()
        else:
            update_fields["minute_count"] = user_data.get("minute_count", 0) + 1

        if not hour_reset or now >= hour_reset:
            update_fields["hour_count"] = 1
            update_fields["hour_reset_at"] = self._sliding_hour_window()
        else:
            update_fields["hour_count"] = user_data.get("hour_count", 0) + 1

        await self.collection.update_one(
            {"guild_id": Int64(guild_id), "user_id": Int64(user_id)},
            {"$set": update_fields},
        )

    async def consume_request(self, user_id: int, guild_id: int) -> tuple[bool, str]:
        """Reserve one request after checking limits to avoid concurrent bypasses."""
        lock = self._request_locks.setdefault((guild_id, user_id), asyncio.Lock())
        async with lock:
            allowed, message = await self.can_make_request(user_id, guild_id)
            if allowed:
                await self.increment_usage(user_id, guild_id)
            return allowed, message

    async def get_user_stats(self, user_id: int, guild_id: int) -> dict:
        per_minute, per_hour, enabled = await self._get_limits(guild_id)
        now = datetime.now(UTC)

        user_data = await self.collection.find_one({"guild_id": Int64(guild_id), "user_id": Int64(user_id)})

        if not user_data:
            return {
                "minute_count": 0,
                "hour_count": 0,
                "max_per_minute": per_minute,
                "max_per_hour": per_hour,
                "remaining_minute": per_minute,
                "remaining_hour": per_hour,
                "enabled": enabled,
            }

        user_per_minute = user_data.get("max_per_minute", per_minute) if user_data.get("custom_limits") else per_minute
        user_per_hour = user_data.get("max_per_hour", per_hour) if user_data.get("custom_limits") else per_hour

        minute_reset = user_data.get("minute_reset_at")
        hour_reset = user_data.get("hour_reset_at")

        minute_count = user_data.get("minute_count", 0)
        hour_count = user_data.get("hour_count", 0)

        if isinstance(minute_reset, datetime):
            if minute_reset.tzinfo is None:
                minute_reset = minute_reset.replace(tzinfo=UTC)
            if now >= minute_reset:
                minute_count = 0

        if isinstance(hour_reset, datetime):
            if hour_reset.tzinfo is None:
                hour_reset = hour_reset.replace(tzinfo=UTC)
            if now >= hour_reset:
                hour_count = 0

        return {
            "minute_count": minute_count,
            "hour_count": hour_count,
            "max_per_minute": user_per_minute,
            "max_per_hour": user_per_hour,
            "remaining_minute": max(0, user_per_minute - minute_count),
            "remaining_hour": max(0, user_per_hour - hour_count),
            "minute_reset_at": minute_reset,
            "hour_reset_at": hour_reset,
            "enabled": enabled,
        }

    async def reset_user(self, user_id: int, guild_id: int):
        result = await self.collection.update_one(
            {"guild_id": Int64(guild_id), "user_id": Int64(user_id)},
            {"$set": {"minute_count": 0, "hour_count": 0}},
        )

        if result.modified_count > 0:
            self.logger.info(f"Reset AI usage counts for user {user_id} in guild {guild_id}")
        else:
            self.logger.warning(f"No changes made when resetting user {user_id} in guild {guild_id}")

    async def set_user_limits(self, user_id: int, guild_id: int, per_minute: int, per_hour: int) -> bool:
        result = await self.collection.update_one(
            {"guild_id": Int64(guild_id), "user_id": Int64(user_id)},
            {"$set": {"max_per_minute": per_minute, "max_per_hour": per_hour, "custom_limits": True}},
            upsert=True,
        )

        if result.modified_count > 0 or result.upserted_id:
            self.logger.info(f"Set AI usage limits to {per_minute}/min, {per_hour}/hr for user {user_id} in guild {guild_id}")
            return True
        return False

    async def set_guild_limits(self, guild_id: int, per_minute: int, per_hour: int) -> int:
        result = await self.collection.update_many(
            {"guild_id": Int64(guild_id)},
            {"$set": {"max_per_minute": per_minute, "max_per_hour": per_hour, "custom_limits": False}},
        )

        self.logger.info(f"Updated AI usage limits to {per_minute}/min, {per_hour}/hr for {result.modified_count} users in guild {guild_id}")
        return result.modified_count

    async def set_limits_enabled(self, guild_id: int, enabled: bool) -> bool:
        config = await self.bot.config_service.get_config(str(guild_id))
        ai_config_dict = config.aiConfig.model_dump()
        if "usageLimits" not in ai_config_dict:
            ai_config_dict["usageLimits"] = {}
        ai_config_dict["usageLimits"]["enabled"] = enabled
        await self.bot.config_service.update(str(guild_id), {"aiConfig": ai_config_dict})
        return True
