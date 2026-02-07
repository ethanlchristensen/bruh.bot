import logging
from typing import TYPE_CHECKING

import pymongo
from bson import Int64

if TYPE_CHECKING:
    from bot.juno import Juno


class MongoMorningConfigService:
    """Service for managing morning message configurations in MongoDB."""

    def __init__(self, bot: "Juno"):
        self.bot = bot
        self.mongo_client = pymongo.MongoClient(self.bot.config_service.base.mongoUri)
        self.db = self.mongo_client[self.bot.config_service.base.mongoDbName]
        self.collection = self.db[self.bot.config_service.dynamic.mongoMorningConfigsCollectionName]
        self.logger = logging.getLogger(__name__)

        # Initialize collection with indexes
        self._ensure_indexes()
        self.logger.info(f"Initialized MongoMorningConfigService with collection {self.collection.name}")

    def _ensure_indexes(self):
        """Create indexes on the collection for faster retrieval."""
        try:
            # Create unique index on guild_id for fast lookups
            self.collection.create_index([("guild_id", pymongo.ASCENDING)], unique=True)
            self.logger.info("Created indexes on morning_configs collection")
        except pymongo.errors.OperationFailure as e:
            self.logger.warning(f"Could not create indexes: {e}")

    def get_config(self, guild_id: int) -> dict | None:
        """Get morning configuration for a guild.

        Args:
            guild_id: The Discord guild ID

        Returns:
            Dictionary with config data or None if not found
        """
        result = self.collection.find_one({"guild_id": Int64(guild_id)})
        if result:
            self.logger.debug(f"Retrieved morning config for guild {guild_id}")
            return {"hour": result.get("hour", 12), "minute": result.get("minute", 0), "timezone": result.get("timezone", "UTC"), "channel_id": result.get("channel_id"), "last_sent_date": result.get("last_sent_date")}
        return None

    def get_all_configs(self) -> dict[str, dict]:
        """Get all morning configurations.

        Returns:
            Dictionary mapping guild_id (as string) to config data
        """
        configs = {}
        for doc in self.collection.find():
            guild_id_str = str(doc["guild_id"])
            configs[guild_id_str] = {"hour": doc.get("hour", 12), "minute": doc.get("minute", 0), "timezone": doc.get("timezone", "UTC"), "channel_id": doc.get("channel_id"), "last_sent_date": doc.get("last_sent_date")}
        self.logger.debug(f"Retrieved {len(configs)} morning configs")
        return configs

    def set_channel(self, guild_id: int, channel_id: int) -> dict:
        """Set the channel for morning messages.

        Args:
            guild_id: The Discord guild ID
            channel_id: The Discord channel ID

        Returns:
            The updated config
        """
        result = self.collection.find_one_and_update(
            {"guild_id": Int64(guild_id)},
            {
                "$set": {"channel_id": Int64(channel_id)},
                "$setOnInsert": {
                    "guild_id": Int64(guild_id),
                    "hour": 12,
                    "minute": 0,
                    "timezone": "UTC",
                },
            },
            upsert=True,
            return_document=pymongo.ReturnDocument.AFTER,
        )
        self.logger.info(f"Set morning channel for guild {guild_id} to channel {channel_id}")
        return {"hour": result.get("hour", 12), "minute": result.get("minute", 0), "timezone": result.get("timezone", "UTC"), "channel_id": result.get("channel_id"), "last_sent_date": result.get("last_sent_date")}

    def set_time(self, guild_id: int, hour: int, minute: int, timezone: str) -> dict:
        """Set the time for morning messages.

        Args:
            guild_id: The Discord guild ID
            hour: Hour (0-23)
            minute: Minute (0-59)
            timezone: Timezone string (e.g., 'US/Eastern')

        Returns:
            The updated config
        """
        result = self.collection.find_one_and_update(
            {"guild_id": Int64(guild_id)},
            {
                "$set": {
                    "hour": hour,
                    "minute": minute,
                    "timezone": timezone,
                },
                "$setOnInsert": {
                    "guild_id": Int64(guild_id),
                },
            },
            upsert=True,
            return_document=pymongo.ReturnDocument.AFTER,
        )
        self.logger.info(f"Set morning time for guild {guild_id} to {hour}:{minute:02d} {timezone}")
        return {"hour": result.get("hour", 12), "minute": result.get("minute", 0), "timezone": result.get("timezone", "UTC"), "channel_id": result.get("channel_id"), "last_sent_date": result.get("last_sent_date")}

    def remove_config(self, guild_id: int) -> bool:
        """Remove morning configuration for a guild.

        Args:
            guild_id: The Discord guild ID

        Returns:
            True if config was removed, False if it didn't exist
        """
        result = self.collection.delete_one({"guild_id": Int64(guild_id)})
        removed = result.deleted_count > 0
        if removed:
            self.logger.info(f"Removed morning config for guild {guild_id}")
        else:
            self.logger.debug(f"No morning config found for guild {guild_id} to remove")
        return removed

    def update_last_sent_date(self, guild_id: int, date: str):
        """Update the last sent date for morning messages.

        Args:
            guild_id: The Discord guild ID
            date: Date string in 'YYYY-MM-DD' format
        """
        self.collection.update_one(
            {"guild_id": Int64(guild_id)},
            {"$set": {"last_sent_date": date}},
        )
        self.logger.debug(f"Updated last sent date for guild {guild_id} to {date}")
