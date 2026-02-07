import logging
from datetime import datetime, time, timedelta
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

import discord
import pymongo
from bson import Int64

if TYPE_CHECKING:
    from bot.juno import Juno


class MongoImageLimitService:
    """Service for managing daily image generation limits in MongoDB."""

    def __init__(self, bot: "Juno", max_daily_images: int):
        self.bot = bot
        self.default_max_daily_images = max_daily_images  # Default from config
        self.mongo_client = pymongo.MongoClient(self.bot.config_service.base.mongoUri)
        self.db = self.mongo_client[self.bot.config_service.base.mongoDbName]
        self.collection = self.db[self.bot.config_service.dynamic.mongoImageLimitsCollectionName]
        self.timezone = ZoneInfo("America/Chicago")  # Central Time
        self.logger = logging.getLogger(__name__)

        # Initialize collection with indexes
        self._ensure_indexes()
        self.logger.info(f"Initialized MongoImageLimitService with default daily limit of {self.default_max_daily_images} images")

    def _ensure_indexes(self):
        """Create indexes on the collection for faster retrieval."""
        try:
            # Create compound index on guild_id and user_id for fast lookups
            self.collection.create_index([("guild_id", pymongo.ASCENDING), ("user_id", pymongo.ASCENDING)], unique=True)
            # Create index on reset_time for potential cleanup queries
            self.collection.create_index([("reset_time", pymongo.ASCENDING)])
            self.logger.info("Created indexes on ImageLimits collection")
        except pymongo.errors.OperationFailure as e:
            self.logger.warning(f"Could not create indexes: {e}")

    def _get_next_reset_time(self) -> datetime:
        """Get the next midnight Central time."""
        now = datetime.now(self.timezone)

        # Get today's midnight
        today_midnight = datetime.combine(now.date(), time(0, 0, 0), tzinfo=self.timezone)

        # If we're past midnight today, get tomorrow's midnight
        if now >= today_midnight:
            next_midnight = today_midnight + timedelta(days=1)
        else:
            next_midnight = today_midnight

        return next_midnight

    def can_generate_image(self, user: discord.User, guild: discord.Guild) -> tuple[bool, str]:
        """Check if user can generate an image. Returns (can_generate, message).

        Args:
            user: The Discord user requesting image generation
            guild: The Discord guild where the request was made

        Returns:
            Tuple of (can_generate: bool, error_message: str)
        """
        now = datetime.now(self.timezone)

        # Get or initialize user usage
        user_data = self.collection.find_one({"guild_id": Int64(guild.id), "user_id": Int64(user.id)})

        if not user_data:
            # Initialize new user with default limit from config
            next_reset = self._get_next_reset_time()
            self.collection.insert_one(
                {
                    "guild_id": Int64(guild.id),
                    "user_id": Int64(user.id),
                    "count": 0,
                    "max_daily_images": self.default_max_daily_images,
                    "reset_time": next_reset,
                }
            )
            self.logger.info(f"Initialized image limit tracking for {user.name} in guild {guild.name} with limit {self.default_max_daily_images}")
            return True, ""

        # Parse reset time
        reset_time = user_data["reset_time"]
        if isinstance(reset_time, str):
            reset_time = datetime.fromisoformat(reset_time)

        # Ensure reset_time is timezone-aware
        if reset_time.tzinfo is None:
            reset_time = reset_time.replace(tzinfo=self.timezone)

        # Reset if past reset time
        if now >= reset_time:
            next_reset = self._get_next_reset_time()
            self.collection.update_one(
                {"guild_id": Int64(guild.id), "user_id": Int64(user.id)},
                {"$set": {"count": 0, "reset_time": next_reset}},
            )
            self.logger.info(f"Reset daily image count for {user.name} in guild {guild.name}")
            return True, ""

        # Check limit (use per-user limit from DB, or default if not set)
        count = user_data.get("count", 0)
        user_limit = user_data.get("max_daily_images", self.default_max_daily_images)
        self.logger.info(f"[CAN GENERATE IMAGE] - {user.name} has generated {count}/{user_limit} images today")

        if count >= user_limit:
            time_until_reset = reset_time - now
            hours = int(time_until_reset.total_seconds() // 3600)
            minutes = int((time_until_reset.total_seconds() % 3600) // 60)
            return False, f"Daily image limit reached ({user_limit} images). Resets in {hours}h {minutes}m. Use the `/image_stats` command to check your usage."

        return True, ""

    def increment_usage(self, user_id: int, guild_id: int):
        """Increment the user's daily image count.

        Args:
            user_id: The Discord user ID
            guild_id: The Discord guild ID
        """
        result = self.collection.update_one(
            {"guild_id": Int64(guild_id), "user_id": Int64(user_id)},
            {"$inc": {"count": 1}},
        )

        if result.modified_count > 0:
            # Get updated count for logging
            user_data = self.collection.find_one({"guild_id": Int64(guild_id), "user_id": Int64(user_id)})
            count = user_data.get("count", 0) if user_data else 0
            self.logger.info(f"Incremented image count for user {user_id} in guild {guild_id} to {count}")
        else:
            self.logger.warning(f"Failed to increment image count for user {user_id} in guild {guild_id}")

    def get_remaining_images(self, user_id: int, guild_id: int) -> int:
        """Get the number of remaining images for a user.

        Args:
            user_id: The Discord user ID
            guild_id: The Discord guild ID

        Returns:
            Number of remaining images the user can generate today
        """
        user_data = self.collection.find_one({"guild_id": Int64(guild_id), "user_id": Int64(user_id)})

        if not user_data:
            return self.default_max_daily_images

        count = user_data.get("count", 0)
        user_limit = user_data.get("max_daily_images", self.default_max_daily_images)
        return max(0, user_limit - count)

    def get_user_stats(self, user_id: int, guild_id: int) -> dict:
        """Get detailed stats for a user.

        Args:
            user_id: The Discord user ID
            guild_id: The Discord guild ID

        Returns:
            Dictionary with user stats including count, remaining, max_daily_images, and reset_time
        """
        user_data = self.collection.find_one({"guild_id": Int64(guild_id), "user_id": Int64(user_id)})

        if not user_data:
            return {
                "count": 0,
                "remaining": self.default_max_daily_images,
                "max_daily_images": self.default_max_daily_images,
                "reset_time": self._get_next_reset_time(),
            }

        count = user_data.get("count", 0)
        user_limit = user_data.get("max_daily_images", self.default_max_daily_images)
        return {
            "count": count,
            "remaining": max(0, user_limit - count),
            "max_daily_images": user_limit,
            "reset_time": user_data.get("reset_time"),
        }

    def reset_user(self, user_id: int, guild_id: int):
        """Reset a specific user's daily image count.

        Args:
            user_id: The Discord user ID
            guild_id: The Discord guild ID
        """
        next_reset = self._get_next_reset_time()
        result = self.collection.update_one(
            {"guild_id": Int64(guild_id), "user_id": Int64(user_id)},
            {"$set": {"count": 0, "reset_time": next_reset}},
            upsert=True,
        )

        if result.modified_count > 0 or result.upserted_id:
            self.logger.info(f"Reset image count for user {user_id} in guild {guild_id}")
        else:
            self.logger.warning(f"No changes made when resetting user {user_id} in guild {guild_id}")

    def reset_all_users(self, guild_id: int) -> int:
        """Reset all users' daily image counts in a guild.

        Args:
            guild_id: The Discord guild ID

        Returns:
            Number of users reset
        """
        next_reset = self._get_next_reset_time()
        result = self.collection.update_many(
            {"guild_id": Int64(guild_id)},
            {"$set": {"count": 0, "reset_time": next_reset}},
        )

        self.logger.info(f"Reset image counts for {result.modified_count} users in guild {guild_id}")
        return result.modified_count

    def set_user_limit(self, user_id: int, guild_id: int, new_limit: int) -> bool:
        """Set the daily image limit for a specific user.

        Args:
            user_id: The Discord user ID
            guild_id: The Discord guild ID
            new_limit: The new maximum daily image limit for this user

        Returns:
            True if successful, False otherwise
        """
        result = self.collection.update_one(
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

    def set_guild_limit(self, guild_id: int, new_limit: int) -> int:
        """Set the daily image limit for all users in a guild.

        Args:
            guild_id: The Discord guild ID
            new_limit: The new maximum daily image limit for all users

        Returns:
            Number of users updated
        """
        result = self.collection.update_many(
            {"guild_id": Int64(guild_id)},
            {"$set": {"max_daily_images": new_limit}},
        )

        self.logger.info(f"Updated image limit to {new_limit} for {result.modified_count} users in guild {guild_id}")
        return result.modified_count

    def get_user_limit(self, user_id: int, guild_id: int) -> int:
        """Get the daily image limit for a specific user.

        Args:
            user_id: The Discord user ID
            guild_id: The Discord guild ID

        Returns:
            The user's daily image limit
        """
        user_data = self.collection.find_one({"guild_id": Int64(guild_id), "user_id": Int64(user_id)})

        if not user_data:
            return self.default_max_daily_images

        return user_data.get("max_daily_images", self.default_max_daily_images)
