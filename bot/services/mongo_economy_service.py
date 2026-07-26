import logging
import random
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from bson import Int64

from bot.services.config_service import EconomyConfig

if TYPE_CHECKING:
    from bot.bruh_bot import BruhBot


class MongoEconomyService:
    def __init__(self, bot: "BruhBot"):
        self.bot = bot
        self.collection = self.bot.config_service.col(self.bot.config_service.base.mongoUserProfilesCollectionName)
        self.logger = logging.getLogger(__name__)

    async def initialize(self):
        await self._ensure_indexes()

    async def _ensure_indexes(self):
        try:
            await self.collection.create_index([("guild_id", 1), ("user_id", 1)], unique=True)
            await self.collection.create_index("level")
            await self.collection.create_index("xp")
            await self.collection.create_index("bruh_coins")
            self.logger.info("Created indexes on UserProfiles collection")
        except Exception as e:
            self.logger.warning(f"Could not create indexes: {e}")

    @staticmethod
    def _calculate_level(xp: int) -> int:
        lo, hi = 0, int((6 * xp / 10) ** (1 / 3)) + 2
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if 10 * mid**3 + 135 * mid**2 + 455 * mid <= 6 * xp:
                lo = mid
            else:
                hi = mid - 1
        return lo

    @staticmethod
    def _xp_for_next_level(level: int) -> int:
        return 5 * (level**2) + 50 * level + 100

    async def _get_economy_config(self, guild_id: int) -> EconomyConfig:
        config = await self.bot.config_service.get_config(str(guild_id))
        return config.economyConfig

    async def _get_or_create_profile_raw(self, guild_id: int, user_id: int) -> dict:
        now = datetime.now(UTC)
        doc = await self.collection.find_one({"guild_id": Int64(guild_id), "user_id": Int64(user_id)})
        if not doc:
            doc = {
                "guild_id": Int64(guild_id),
                "user_id": Int64(user_id),
                "xp": 0,
                "level": 0,
                "bruh_coins": 0.0,
                "total_messages": 0,
                "total_images": 0,
                "total_reactions_given": 0,
                "total_bot_mentions": 0,
                "last_xp_grant": None,
                "last_daily_claim": None,
                "booster_active_until": None,
                "created_at": now,
                "updated_at": now,
            }
            await self.collection.insert_one(doc)
        else:
            defaults = {
                "xp": 0,
                "level": 0,
                "bruh_coins": 0.0,
                "total_messages": 0,
                "total_images": 0,
                "total_reactions_given": 0,
                "total_bot_mentions": 0,
                "last_xp_grant": None,
                "last_daily_claim": None,
                "booster_active_until": None,
            }
            missing = {k: v for k, v in defaults.items() if k not in doc}
            if missing:
                await self.collection.update_one(
                    {"_id": doc["_id"]},
                    {"$set": missing},
                )
                doc.update(missing)
        return doc

    async def get_profile(self, guild_id: int, user_id: int) -> dict:
        doc = await self._get_or_create_profile_raw(guild_id, user_id)
        doc["xp_for_next_level"] = self._xp_for_next_level(doc["level"])
        doc["xp_for_current_level"] = self._xp_for_next_level(doc["level"] - 1) if doc["level"] > 0 else 0
        return self._serialize_dates(doc)

    async def add_xp(self, guild_id: int, user_id: int, amount: int) -> tuple[int, int, int]:
        doc = await self._get_or_create_profile_raw(guild_id, user_id)
        old_level = doc.get("level", 0)
        new_xp = doc.get("xp", 0) + amount
        new_level = self._calculate_level(new_xp)
        now = datetime.now(UTC)
        await self.collection.update_one(
            {"guild_id": Int64(guild_id), "user_id": Int64(user_id)},
            {"$set": {"xp": new_xp, "level": new_level, "updated_at": now}},
        )
        return new_xp, old_level, new_level

    async def activate_booster(self, guild_id: int, user_id: int, hours: int) -> datetime:
        until = datetime.now(UTC) + timedelta(hours=hours)
        await self.collection.update_one(
            {"guild_id": Int64(guild_id), "user_id": Int64(user_id)},
            {"$set": {"booster_active_until": until, "updated_at": datetime.now(UTC)}},
            upsert=True,
        )
        return until

    async def add_coins(self, guild_id: int, user_id: int, amount: float) -> float:
        now = datetime.now(UTC)
        result = await self.collection.find_one_and_update(
            {"guild_id": Int64(guild_id), "user_id": Int64(user_id)},
            {"$inc": {"bruh_coins": amount}, "$set": {"updated_at": now}},
            upsert=True,
            return_document=True,
        )
        if result is None:
            await self._get_or_create_profile_raw(guild_id, user_id)
            result = await self.collection.find_one_and_update(
                {"guild_id": Int64(guild_id), "user_id": Int64(user_id)},
                {"$inc": {"bruh_coins": amount}, "$set": {"updated_at": now}},
                return_document=True,
            )
        return result.get("bruh_coins", 0.0) if result else 0.0

    async def deduct_coins(self, guild_id: int, user_id: int, amount: float) -> tuple[bool, float]:
        doc = await self._get_or_create_profile_raw(guild_id, user_id)
        current = doc.get("bruh_coins", 0.0)
        if current < amount:
            return False, current
        now = datetime.now(UTC)
        result = await self.collection.find_one_and_update(
            {"guild_id": Int64(guild_id), "user_id": Int64(user_id)},
            {"$inc": {"bruh_coins": -amount}, "$set": {"updated_at": now}},
            return_document=True,
        )
        new_balance = result.get("bruh_coins", 0.0) if result else 0.0
        return True, new_balance

    async def add_stat(self, guild_id: int, user_id: int, stat_field: str):
        now = datetime.now(UTC)
        await self.collection.update_one(
            {"guild_id": Int64(guild_id), "user_id": Int64(user_id)},
            {"$inc": {stat_field: 1}, "$set": {"updated_at": now}},
            upsert=True,
        )

    async def get_leaderboard(self, guild_id: int, sort_by: str = "xp", limit: int = 25) -> list[dict]:
        valid_sorts = {"xp": -1, "level": -1, "bruh_coins": -1}
        sort_order = valid_sorts.get(sort_by, -1)
        cursor = (
            self.collection.find(
                {"guild_id": Int64(guild_id)},
                {"user_id": 1, "xp": 1, "level": 1, "bruh_coins": 1, "total_messages": 1, "_id": 0},
            )
            .sort([(sort_by, sort_order)])
            .limit(limit)
        )
        results = []
        rank = 1
        async for doc in cursor:
            doc["rank"] = rank
            doc["level"] = doc.get("level", 0)
            doc["xp"] = doc.get("xp", 0)
            doc["bruh_coins"] = doc.get("bruh_coins", 0.0)
            doc["xp_for_next_level"] = self._xp_for_next_level(doc["level"])
            results.append(self._serialize_dates(doc))
            rank += 1
        return results

    async def get_rank(self, guild_id: int, user_id: int) -> int:
        profile = await self._get_or_create_profile_raw(guild_id, user_id)
        count = await self.collection.count_documents(
            {
                "guild_id": Int64(guild_id),
                "xp": {"$gt": profile["xp"]},
            }
        )
        return count + 1

    async def claim_daily(self, guild_id: int, user_id: int) -> tuple[bool, float, str]:
        econ_config = await self._get_economy_config(guild_id)
        doc = await self._get_or_create_profile_raw(guild_id, user_id)
        now = datetime.now(UTC)
        today_reset = datetime(now.year, now.month, now.day, 12, 0, 0, tzinfo=UTC)
        if now < today_reset:
            today_reset -= timedelta(days=1)
        last_claim = doc.get("last_daily_claim")
        if last_claim:
            if isinstance(last_claim, str):
                last_claim = datetime.fromisoformat(last_claim.replace("Z", "+00:00"))
            if last_claim.tzinfo is None:
                last_claim = last_claim.replace(tzinfo=UTC)
            if last_claim >= today_reset:
                next_reset = today_reset + timedelta(days=1)
                remaining = next_reset - now
                hours = remaining.seconds // 3600
                minutes = (remaining.seconds % 3600) // 60
                return False, 0.0, f"Already claimed today! Resets at 12:00 UTC (in {hours}h {minutes}m)."
        amount = round(random.uniform(econ_config.dailyCoinMin, econ_config.dailyCoinMax), 2)
        await self.collection.update_one(
            {"guild_id": Int64(guild_id), "user_id": Int64(user_id)},
            {"$inc": {"bruh_coins": amount}, "$set": {"last_daily_claim": now, "updated_at": now}},
        )
        return True, amount, ""

    async def set_xp(self, guild_id: int, user_id: int, amount: int) -> int:
        await self._get_or_create_profile_raw(guild_id, user_id)
        new_level = self._calculate_level(amount)
        now = datetime.now(UTC)
        await self.collection.update_one(
            {"guild_id": Int64(guild_id), "user_id": Int64(user_id)},
            {"$set": {"xp": amount, "level": new_level, "updated_at": now}},
        )
        return new_level

    async def set_coins(self, guild_id: int, user_id: int, amount: float):
        await self._get_or_create_profile_raw(guild_id, user_id)
        now = datetime.now(UTC)
        await self.collection.update_one(
            {"guild_id": Int64(guild_id), "user_id": Int64(user_id)},
            {"$set": {"bruh_coins": amount, "updated_at": now}},
        )

    async def set_level(self, guild_id: int, user_id: int, level: int):
        await self._get_or_create_profile_raw(guild_id, user_id)
        xp = self._xp_for_next_level(level - 1) if level > 0 else 0
        now = datetime.now(UTC)
        await self.collection.update_one(
            {"guild_id": Int64(guild_id), "user_id": Int64(user_id)},
            {"$set": {"xp": xp, "level": level, "updated_at": now}},
        )

    async def reset_profile(self, guild_id: int, user_id: int):
        now = datetime.now(UTC)
        await self.collection.update_one(
            {"guild_id": Int64(guild_id), "user_id": Int64(user_id)},
            {
                "$set": {
                    "xp": 0,
                    "level": 0,
                    "bruh_coins": 0.0,
                    "total_messages": 0,
                    "total_images": 0,
                    "total_reactions_given": 0,
                    "total_bot_mentions": 0,
                    "last_xp_grant": None,
                    "last_daily_claim": None,
                    "booster_active_until": None,
                    "updated_at": now,
                },
            },
        )

    async def handle_message_event(self, guild_id: int, user_id: int, config: EconomyConfig, has_attachment: bool, is_bot_mention: bool) -> tuple[int, int, bool]:
        if not config.xpEnabled:
            return 0, 0, False

        xp_awarded = random.randint(config.baseXpRange[0], config.baseXpRange[1])
        coins_awarded = round(random.uniform(config.messageCoinRange[0], config.messageCoinRange[1]), 2)

        if has_attachment:
            xp_awarded += config.imageXpBonus
            coins_awarded += config.imageCoinBonus
            await self.add_stat(guild_id, user_id, "total_images")

        if is_bot_mention:
            mention_xp = random.randint(config.mentionXpRange[0], config.mentionXpRange[1])
            mention_coins = round(random.uniform(config.mentionCoinRange[0], config.mentionCoinRange[1]), 2)
            xp_awarded += mention_xp
            coins_awarded += mention_coins
            await self.add_stat(guild_id, user_id, "total_bot_mentions")

        # Check for active XP booster
        doc = await self._get_or_create_profile_raw(guild_id, user_id)
        booster = doc.get("booster_active_until")
        if booster:
            if isinstance(booster, str):
                booster = datetime.fromisoformat(booster.replace("Z", "+00:00"))
            if booster.tzinfo is None:
                booster = booster.replace(tzinfo=UTC)
            if datetime.now(UTC) < booster:
                xp_awarded *= 2
            else:
                await self.collection.update_one(
                    {"guild_id": Int64(guild_id), "user_id": Int64(user_id)},
                    {"$set": {"booster_active_until": None}},
                )

        new_xp, old_level, new_level = await self.add_xp(guild_id, user_id, xp_awarded)
        await self.add_coins(guild_id, user_id, coins_awarded)
        await self.add_stat(guild_id, user_id, "total_messages")

        leveled_up = new_level > old_level
        return old_level, new_level, leveled_up

    async def handle_reaction_event(self, guild_id: int, user_id: int):
        config = await self._get_economy_config(guild_id)
        if not config.xpEnabled:
            return
        await self.add_xp(guild_id, user_id, config.reactionXp)
        await self.add_coins(guild_id, user_id, config.reactionCoin)
        await self.add_stat(guild_id, user_id, "total_reactions_given")

    @staticmethod
    def _serialize_dates(doc: dict) -> dict:
        for key in ("last_xp_grant", "last_daily_claim", "booster_active_until", "created_at", "updated_at"):
            val = doc.get(key)
            if isinstance(val, datetime):
                doc[key] = val.isoformat()
        return doc
