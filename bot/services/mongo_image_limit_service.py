import logging
from datetime import datetime, time, timedelta
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

import discord
from bson import Int64

if TYPE_CHECKING:
    from bot.juno import Juno


class MongoImageLimitService:
    """Service for managing daily image generation limits in MongoDB."""

    def __init__(self, bot: "Juno"):
        self.bot = bot
        self.collection = self.bot.config_service.db[self.bot.config_service.base.mongoImageLimitsCollectionName]
        self.timezone = ZoneInfo("America/Chicago")
        self.logger = logging.getLogger(__name__)

    async def initialize(self):
        """Initialize collection with indexes."""
        await self._ensure_indexes()

    async def _ensure_indexes(self):
        """Create indexes on the collection for faster retrieval."""
        try:
            await self.collection.create_index([("guild_id", 1), ("user_id", 1)], unique=True)
            await self.collection.create_index([("reset_time", 1)])
            self.logger.info(f"Created indexes on ${self.bot.config_service.base.mongoImageLimitsCollectionName} collection")
        except Exception as e:
            self.logger.warning(f"Could not create indexes: {e}")

    def _get_next_reset_time(self) -> datetime:
        """Get the next midnight Central time."""
        now = datetime.now(self.timezone)
        today_midnight = datetime.combine(now.date(), time(0, 0, 0), tzinfo=self.timezone)
        if now >= today_midnight:
            next_midnight = today_midnight + timedelta(days=1)
        else:
            next_midnight = today_midnight
        return next_midnight

    async def can_generate_image(self, message: discord.Message) -> tuple[bool, str]:
        now = datetime.now(self.timezone)
        user_data = await self.collection.find_one({"guild_id": Int64(message.guild.id), "user_id": Int64(message.author.id)})
        max_daily_images = (await self.bot.config_service.get_config(str(message.guild.id))).aiConfig.imageGeneration.maxDailyImages

        if not user_data:
            next_reset = self._get_next_reset_time()
            await self.collection.insert_one(
                {
                    "guild_id": Int64(message.guild.id),
                    "user_id": Int64(message.author.id),
                    "count": 0,
                    "max_daily_images": max_daily_images,
                    "reset_time": next_reset,
                }
            )
            self.logger.info(f"Initialized image limit tracking for {message.author.name} in guild {message.guild.name} with limit {max_daily_images}")
            return True, ""

        reset_time = user_data["reset_time"]
        if isinstance(reset_time, str):
            reset_time = datetime.fromisoformat(reset_time)

        if reset_time.tzinfo is None:
            reset_time = reset_time.replace(tzinfo=self.timezone)

        if now >= reset_time:
            next_reset = self._get_next_reset_time()
            await self.collection.update_one(
                {"guild_id": Int64(message.guild.id), "user_id": Int64(message.author.id)},
                {"$set": {"count": 0, "reset_time": next_reset}},
            )
            self.logger.info(f"Reset daily image count for {message.author.name} in guild {message.guild.name}")
            return True, ""

        count = user_data.get("count", 0)
        user_limit = user_data.get("max_daily_images", max_daily_images)
        self.logger.info(f"[CAN GENERATE IMAGE] - {message.author.name} has generated {count}/{user_limit} images today")

        if count >= user_limit:
            time_until_reset = reset_time - now
            hours = int(time_until_reset.total_seconds() // 3600)
            minutes = int((time_until_reset.total_seconds() % 3600) // 60)
            return False, f"Daily image limit reached ({user_limit} images). Resets in {hours}h {minutes}m. Use the `/image_stats` command to check your usage."

        return True, ""

    async def increment_usage(self, user_id: int, guild_id: int):
        """Increment the user's daily image count."""
        result = await self.collection.update_one(
            {"guild_id": Int64(guild_id), "user_id": Int64(user_id)},
            {"$inc": {"count": 1}},
        )

        if result.modified_count > 0:
            user_data = await self.collection.find_one({"guild_id": Int64(guild_id), "user_id": Int64(user_id)})
            count = user_data.get("count", 0) if user_data else 0
            self.logger.info(f"Incremented image count for user {user_id} in guild {guild_id} to {count}")
        else:
            self.logger.warning(f"Failed to increment image count for user {user_id} in guild {guild_id}")

    async def get_remaining_images(self, user_id: int, guild_id: int) -> int:
        """Get the number of remaining images for a user."""
        user_data = await self.collection.find_one({"guild_id": Int64(guild_id), "user_id": Int64(user_id)})
        max_daily_images = (await self.bot.config_service.get_config(str(guild_id))).aiConfig.maxDailyImages

        if not user_data:
            return max_daily_images

        count = user_data.get("count", 0)
        user_limit = user_data.get("max_daily_images", max_daily_images)
        return max(0, user_limit - count)

    async def get_user_stats(self, user_id: int, guild_id: int) -> dict:
        """Get detailed stats for a user."""
        user_data = await self.collection.find_one({"guild_id": Int64(guild_id), "user_id": Int64(user_id)})
        max_daily_images = (await self.bot.config_service.get_config(str(guild_id))).aiConfig.imageGeneration.maxDailyImages

        if not user_data:
            return {
                "count": 0,
                "remaining": max_daily_images,
                "max_daily_images": max_daily_images,
                "reset_time": self._get_next_reset_time(),
            }

        count = user_data.get("count", 0)
        user_limit = user_data.get("max_daily_images", max_daily_images)
        return {
            "count": count,
            "remaining": max(0, user_limit - count),
            "max_daily_images": user_limit,
            "reset_time": user_data.get("reset_time"),
        }

    async def reset_user(self, user_id: int, guild_id: int):
        """Reset a specific user's daily image count."""
        next_reset = self._get_next_reset_time()
        result = await self.collection.update_one(
            {"guild_id": Int64(guild_id), "user_id": Int64(user_id)},
            {"$set": {"count": 0, "reset_time": next_reset}},
            upsert=True,
        )

        if result.modified_count > 0 or result.upserted_id:
            self.logger.info(f"Reset image count for user {user_id} in guild {guild_id}")
        else:
            self.logger.warning(f"No changes made when resetting user {user_id} in guild {guild_id}")

    async def reset_all_users(self, guild_id: int) -> int:
        """Reset all users' daily image counts in a guild."""
        next_reset = self._get_next_reset_time()
        result = await self.collection.update_many(
            {"guild_id": Int64(guild_id)},
            {"$set": {"count": 0, "reset_time": next_reset}},
        )

        self.logger.info(f"Reset image counts for {result.modified_count} users in guild {guild_id}")
        return result.modified_count

    async def set_user_limit(self, user_id: int, guild_id: int, new_limit: int) -> bool:
        """Set the daily image limit for a specific user."""
        result = await self.collection.update_one(
            {"guild_id": Int64(guild_id), "user_id": Int64(user_id)},
            {"$set": {"max_daily_images": new_limit}},
            upsert=True,
        )

        if result.modified_count > 0 or result.upserted_id:
            self.logger.info(f"Set image limit to {new_limit} for user {user_id} in guild {guild_id}")
            return True
        else:
            self.logger.warning(f"Failed to set image limit for user {user_id} in guild {guild_id}")
            return False

    async def set_guild_limit(self, guild_id: int, new_limit: int) -> int:
        """Set the daily image limit for all users in a guild."""
        result = await self.collection.update_many(
            {"guild_id": Int64(guild_id)},
            {"$set": {"max_daily_images": new_limit}},
        )

        self.logger.info(f"Updated image limit to {new_limit} for {result.modified_count} users in guild {guild_id}")
        return result.modified_count

    async def get_user_limit(self, user_id: int, guild_id: int) -> int:
        """Get the daily image limit for a specific user."""
        user_data = await self.collection.find_one({"guild_id": Int64(guild_id), "user_id": Int64(user_id)})
        max_daily_images = (await self.bot.config_service.get_config(str(guild_id))).aiConfig.maxDailyImages

        if not user_data:
            return max_daily_images

        return user_data.get("max_daily_images", max_daily_images)
