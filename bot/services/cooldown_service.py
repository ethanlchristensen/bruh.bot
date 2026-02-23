import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from bson import Int64

if TYPE_CHECKING:
    from bot.juno import Juno


class CooldownService:
    def __init__(self, bot: "Juno"):
        self.bot = bot
        self.collection_name = self.bot.config_service.base.mongoCooldownCollectionName
        self.collection = self.bot.config_service.db[self.collection_name]
        self.logger = logging.getLogger(__name__)

    async def initialize(self):
        """Initialize collection with indexes."""
        await self._ensure_indexes()

    async def _ensure_indexes(self):
        """Create indexes for faster lookups and automatic cleanup."""
        try:
            await self.collection.create_index([("guild_id", 1), ("user_id", 1)], unique=True)

            await self.collection.create_index("last_interaction", expireAfterSeconds=86400)

            self.logger.info(f"Created indexes on {self.collection_name} collection")
        except Exception as e:
            self.logger.warning(f"Could not create indexes for {self.collection_name}: {e}")

    async def check_cooldown(self, user_id: int, guild_id: int, username: str) -> bool:
        """Check if user is on cooldown. Returns True if can proceed."""
        config = await self.bot.config_service.get_config(str(guild_id))

        if str(user_id) in config.cooldownBypassList:
            return True

        user_data = await self.collection.find_one({"guild_id": Int64(guild_id), "user_id": Int64(user_id)})

        if not user_data:
            return True

        last_interaction = user_data["last_interaction"]
        if last_interaction.tzinfo is None:
            last_interaction = last_interaction.replace(tzinfo=UTC)

        current_time = datetime.now(UTC)
        time_since_last = (current_time - last_interaction).total_seconds()

        if time_since_last < config.mentionCooldown:
            remaining_time = int(config.mentionCooldown - time_since_last)
            self.logger.info(f"⏰ Slow down! {username} is on cooldown for {remaining_time}s in guild {guild_id}.")
            return False

        return True

    async def update_cooldown(self, user_id: int, guild_id: int):
        """Update the last interaction time for a user in MongoDB."""
        await self.collection.update_one(
            {"guild_id": Int64(guild_id), "user_id": Int64(user_id)},
            {"$set": {"last_interaction": datetime.now(UTC)}},
            upsert=True,
        )
