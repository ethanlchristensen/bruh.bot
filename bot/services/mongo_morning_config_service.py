import logging
from typing import TYPE_CHECKING

from bson import Int64

if TYPE_CHECKING:
    from bot.juno import Juno


class MongoMorningConfigService:
    """Service for managing morning message configurations in MongoDB."""

    def __init__(self, bot: "Juno"):
        self.bot = bot
        self.collection = self.bot.config_service.db[self.bot.config_service.base.mongoMorningConfigsCollectionName]
        self.logger = logging.getLogger(__name__)

    async def initialize(self):
        """Initialize collection with indexes."""
        await self._ensure_indexes()
        self.logger.info(f"Initialized MongoMorningConfigService with collection {self.bot.config_service.base.mongoMorningConfigsCollectionName}")

    async def _ensure_indexes(self):
        """Create indexes on the collection for faster retrieval."""
        try:
            # Create unique index on guild_id for fast lookups
            await self.collection.create_index([("guild_id", 1)], unique=True)
            self.logger.info("Created indexes on morning_configs collection")
        except Exception as e:
            self.logger.warning(f"Could not create indexes: {e}")

    async def get_config(self, guild_id: int) -> dict | None:
        """Get morning configuration for a guild."""
        result = await self.collection.find_one({"guild_id": Int64(guild_id)})
        if result:
            self.logger.debug(f"Retrieved morning config for guild {guild_id}")
            return {"hour": result.get("hour", 12), "minute": result.get("minute", 0), "timezone": result.get("timezone", "UTC"), "channel_id": result.get("channel_id"), "last_sent_date": result.get("last_sent_date")}
        return None

    async def get_all_configs(self) -> dict[str, dict]:
        """Get all morning configurations."""
        configs = {}
        async for doc in self.collection.find():
            guild_id_str = str(doc["guild_id"])
            configs[guild_id_str] = {"hour": doc.get("hour", 12), "minute": doc.get("minute", 0), "timezone": doc.get("timezone", "UTC"), "channel_id": doc.get("channel_id"), "last_sent_date": doc.get("last_sent_date")}
        self.logger.debug(f"Retrieved {len(configs)} morning configs")
        return configs

    async def set_channel(self, guild_id: int, channel_id: int) -> dict:
        """Set the channel for morning messages."""
        await self.collection.find_one_and_update(
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
            return_document=True,
        )

        updated = await self.get_config(guild_id)
        self.logger.info(f"Set morning channel for guild {guild_id} to channel {channel_id}")
        return updated

    async def set_time(self, guild_id: int, hour: int, minute: int, timezone: str) -> dict:
        """Set the time for morning messages."""
        await self.collection.update_one(
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
        )
        updated = await self.get_config(guild_id)
        self.logger.info(f"Set morning time for guild {guild_id} to {hour}:{minute:02d} {timezone}")
        return updated

    async def remove_config(self, guild_id: int) -> bool:
        """Remove morning configuration for a guild."""
        result = await self.collection.delete_one({"guild_id": Int64(guild_id)})
        removed = result.deleted_count > 0
        if removed:
            self.logger.info(f"Removed morning config for guild {guild_id}")
        else:
            self.logger.debug(f"No morning config found for guild {guild_id} to remove")
        return removed

    async def update_last_sent_date(self, guild_id: int, date: str):
        """Update the last sent date for morning messages."""
        await self.collection.update_one(
            {"guild_id": Int64(guild_id)},
            {"$set": {"last_sent_date": date}},
        )
        self.logger.debug(f"Updated last sent date for guild {guild_id} to {date}")
