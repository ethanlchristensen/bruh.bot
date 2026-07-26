import logging
from datetime import datetime
from typing import TYPE_CHECKING

from bson import Int64

if TYPE_CHECKING:
    import discord

    from bot.bruh_bot import BruhBot


class MongoGuildMemberService:
    def __init__(self, bot: "BruhBot"):
        self.bot = bot
        self.collection = self.bot.config_service.col(self.bot.config_service.base.mongoGuildMembersCollectionName)
        self.logger = logging.getLogger(__name__)

    async def initialize(self):
        await self._ensure_indexes()

    async def _ensure_indexes(self):
        try:
            await self.collection.create_index([("guild_id", 1), ("user_id", 1)], unique=True)
            await self.collection.create_index([("guild_id", 1), ("display_name", "text")])
            self.logger.info("Created indexes on GuildMembers collection")
        except Exception as e:
            self.logger.warning(f"Could not create indexes: {e}")

    async def upsert_member(self, member: "discord.Member"):
        avatar_url = str(member.display_avatar.url) if member.display_avatar else ""
        doc = {
            "guild_id": Int64(member.guild.id),
            "user_id": Int64(member.id),
            "username": member.name,
            "display_name": member.display_name,
            "global_name": member.global_name,
            "discriminator": member.discriminator,
            "avatar_url": avatar_url,
            "joined_at": member.joined_at.timestamp() if member.joined_at else None,
            "updated_at": datetime.utcnow(),
        }
        await self.collection.update_one(
            {"guild_id": Int64(member.guild.id), "user_id": Int64(member.id)},
            {"$set": doc},
            upsert=True,
        )

    async def upsert_user(self, user: "discord.User", guild: "discord.Guild"):
        member = guild.get_member(user.id)
        if member:
            await self.upsert_member(member)
            return

        avatar_url = str(user.display_avatar.url) if user.display_avatar else ""
        doc = {
            "guild_id": Int64(guild.id),
            "user_id": Int64(user.id),
            "username": user.name,
            "display_name": user.display_name or user.global_name or user.name,
            "global_name": user.global_name,
            "discriminator": user.discriminator,
            "avatar_url": avatar_url,
            "joined_at": None,
            "updated_at": datetime.utcnow(),
        }
        await self.collection.update_one(
            {"guild_id": Int64(guild.id), "user_id": Int64(user.id)},
            {"$set": doc},
            upsert=True,
        )

    async def sync_all_members(self, guild: "discord.Guild"):
        count = 0
        async for member in guild.fetch_members(limit=None):
            await self.upsert_member(member)
            count += 1
        self.logger.info(f"Synced {count} members for guild {guild.name} ({guild.id})")
        return count

    async def get_member(self, guild_id: int, user_id: int) -> dict | None:
        doc = await self.collection.find_one(
            {"guild_id": Int64(guild_id), "user_id": Int64(user_id)},
            {"_id": 0},
        )
        return doc

    async def get_members(self, guild_id: int, search: str | None = None, limit: int = 1000) -> list[dict]:
        query: dict = {"guild_id": Int64(guild_id)}
        if search:
            query["$text"] = {"$search": search}
        cursor = self.collection.find(query, {"_id": 0}).limit(limit).sort("display_name", 1)
        return await cursor.to_list(length=limit)

    async def get_member_names(self, guild_id: int) -> dict[int, dict]:
        cursor = self.collection.find(
            {"guild_id": Int64(guild_id)},
            {"user_id": 1, "display_name": 1, "username": 1, "global_name": 1, "avatar_url": 1, "_id": 0},
        )
        result = {}
        async for doc in cursor:
            uid = doc["user_id"]
            result[uid] = {
                "display_name": doc.get("display_name", ""),
                "username": doc.get("username", ""),
                "global_name": doc.get("global_name"),
                "avatar_url": doc.get("avatar_url", ""),
            }
        return result

    async def _serialize(self, doc: dict) -> dict:
        if doc.get("guild_id"):
            doc["guild_id"] = str(doc["guild_id"])
        if doc.get("user_id"):
            doc["user_id"] = str(doc["user_id"])
        return doc
