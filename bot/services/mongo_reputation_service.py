import logging
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from bson import Int64

if TYPE_CHECKING:
    from bot.bruh_bot import BruhBot


REPUTATION_DELTAS = {
    "helpful_interaction": {1: 1, 2: 2, 3: 3},
    "respectful_interaction": {1: 1, 2: 2, 3: 3},
    "interaction_spam": {1: -1, 2: -2, 3: -3},
    "bot_targeted_abuse": {1: -2, 2: -3, 3: -5},
    "targeted_harassment": {1: -3, 2: -5, 3: -8},
    "threat_or_intimidation": {1: -5, 2: -8, 3: -10},
    "block_evasion": {1: -2, 2: -3, 3: -5},
}


class MongoReputationService:
    def __init__(self, bot: "BruhBot"):
        self.bot = bot
        base = self.bot.config_service.base
        self.collection = self.bot.config_service.col(base.mongoReputationCollectionName)
        self.events = self.bot.config_service.col(base.mongoReputationEventsCollectionName)
        self.logger = logging.getLogger(__name__)

    async def initialize(self):
        await self.collection.create_index([("guild_id", 1), ("user_id", 1)], unique=True)
        await self.events.create_index([("guild_id", 1), ("source_message_id", 1), ("reason_code", 1)], unique=True)
        await self.events.create_index([("guild_id", 1), ("user_id", 1), ("created_at", -1)])
        await self._migrate_penalty_scores()

    async def _migrate_penalty_scores(self):
        """Convert profiles created by the original penalty-only score model."""
        async for profile in self.collection.find({"score_version": {"$ne": 2}}):
            guild_id = int(profile["guild_id"])
            config = await self.bot.config_service.get_config(str(guild_id))
            score = -abs(profile.get("score", 0))
            status = profile.get("status", "active")
            if status != "manual_blocked":
                status = "blocked" if score <= config.reputationConfig.blockThreshold else "warning" if score <= config.reputationConfig.warningThreshold else "active"
            await self.collection.update_one({"_id": profile["_id"]}, {"$set": {"score": score, "status": status, "score_version": 2, "updated_at": datetime.now(UTC)}})

    async def get_profile(self, guild_id: int, user_id: int) -> dict:
        now = datetime.now(UTC)
        await self.collection.update_one(
            {"guild_id": Int64(guild_id), "user_id": Int64(user_id)},
            {"$setOnInsert": {"guild_id": Int64(guild_id), "user_id": Int64(user_id), "score": 0, "score_version": 2, "status": "active", "blocked_until": None, "last_notice_at": None, "created_at": now}},
            upsert=True,
        )
        return await self.collection.find_one({"guild_id": Int64(guild_id), "user_id": Int64(user_id)})

    async def record_event(self, guild_id: int, user_id: int, source_message_id: int, channel_id: int, reason_code: str, severity: int, confidence: float, summary: str) -> dict:
        if user_id == self.bot.user.id or reason_code not in REPUTATION_DELTAS or not 1 <= severity <= 3:
            return {"ok": False, "error": "Invalid reputation event"}
        config = await self.bot.config_service.get_config(str(guild_id))
        if confidence < config.reputationConfig.minConfidence:
            return {"ok": False, "error": "Confidence below threshold"}
        delta = REPUTATION_DELTAS[reason_code][severity]
        now = datetime.now(UTC)
        event = {"guild_id": Int64(guild_id), "user_id": Int64(user_id), "source_message_id": Int64(source_message_id), "channel_id": Int64(channel_id), "reason_code": reason_code, "severity": severity, "confidence": confidence, "summary": summary[:300], "score_delta": delta, "source": "ai", "created_at": now}
        try:
            await self.events.insert_one(event)
        except Exception:
            return {"ok": False, "error": "Duplicate reputation event"}
        profile = await self.get_profile(guild_id, user_id)
        score = profile.get("score", 0) + delta
        status = "active"
        blocked_until = None
        if score <= config.reputationConfig.blockThreshold:
            status = "blocked"
            blocked_until = now + timedelta(hours=config.reputationConfig.blockDurationHours)
        elif score <= config.reputationConfig.warningThreshold:
            status = "warning"
        await self.collection.update_one({"_id": profile["_id"]}, {"$set": {"score": score, "status": status, "blocked_until": blocked_until, "updated_at": now}})
        return {"ok": True, "score": score, "status": status}

    async def can_respond(self, guild_id: int, user_id: int) -> tuple[bool, dict]:
        profile = await self.get_profile(guild_id, user_id)
        blocked_until = profile.get("blocked_until")
        if profile.get("status") == "manual_blocked":
            return False, profile
        if blocked_until and blocked_until > datetime.now(UTC):
            return False, profile
        if profile.get("status") == "blocked":
            await self.collection.update_one({"_id": profile["_id"]}, {"$set": {"status": "warning", "blocked_until": None}})
            profile["status"] = "warning"
        return True, profile

    async def get_recent_events(self, guild_id: int, user_id: int, limit: int = 3) -> list[dict]:
        return await self.events.find({"guild_id": Int64(guild_id), "user_id": Int64(user_id)}).sort("created_at", -1).limit(limit).to_list(length=limit)

    async def get_leaderboard(self, guild_id: int, limit: int = 10) -> list[dict]:
        cursor = self.collection.find({"guild_id": Int64(guild_id), "score": {"$lt": 0}}).sort("score", 1).limit(limit)
        return await cursor.to_list(length=limit)

    async def refresh_block(self, guild_id: int, user_id: int) -> dict:
        profile = await self.get_profile(guild_id, user_id)
        if profile.get("status") != "blocked":
            return profile
        config = await self.bot.config_service.get_config(str(guild_id))
        blocked_until = datetime.now(UTC) + timedelta(hours=config.reputationConfig.blockDurationHours)
        await self.collection.update_one({"_id": profile["_id"]}, {"$set": {"blocked_until": blocked_until, "updated_at": datetime.now(UTC)}})
        profile["blocked_until"] = blocked_until
        return profile

    async def should_send_notice(self, guild_id: int, user_id: int) -> bool:
        profile = await self.get_profile(guild_id, user_id)
        config = await self.bot.config_service.get_config(str(guild_id))
        last = profile.get("last_notice_at")
        if last and last > datetime.now(UTC) - timedelta(hours=config.reputationConfig.noticeCooldownHours):
            return False
        await self.collection.update_one({"_id": profile["_id"]}, {"$set": {"last_notice_at": datetime.now(UTC)}})
        return True

    async def set_score(self, guild_id: int, user_id: int, score: int, reason: str = "Manual admin adjustment") -> dict:
        profile = await self.get_profile(guild_id, user_id)
        config = await self.bot.config_service.get_config(str(guild_id))
        status = "active" if score > config.reputationConfig.warningThreshold else "warning"
        blocked_until = None
        if score <= config.reputationConfig.blockThreshold:
            status = "blocked"
            blocked_until = datetime.now(UTC) + timedelta(hours=config.reputationConfig.blockDurationHours)
        await self.collection.update_one({"_id": profile["_id"]}, {"$set": {"score": score, "status": status, "blocked_until": blocked_until, "updated_at": datetime.now(UTC)}})
        now = datetime.now(UTC)
        await self.events.insert_one({"guild_id": Int64(guild_id), "user_id": Int64(user_id), "source_message_id": Int64(int(now.timestamp() * 1_000_000)), "reason_code": "admin_adjustment", "summary": reason[:300], "score_delta": score - profile.get("score", 0), "source": "admin", "created_at": now})
        return await self.get_profile(guild_id, user_id)

    async def set_manual_block(self, guild_id: int, user_id: int, blocked: bool, reason: str = "Manual admin action") -> dict:
        profile = await self.get_profile(guild_id, user_id)
        status = "manual_blocked" if blocked else "active"
        await self.collection.update_one({"_id": profile["_id"]}, {"$set": {"status": status, "blocked_until": None, "updated_at": datetime.now(UTC)}})
        now = datetime.now(UTC)
        await self.events.insert_one({"guild_id": Int64(guild_id), "user_id": Int64(user_id), "source_message_id": Int64(int(now.timestamp() * 1_000_000)), "reason_code": "admin_block" if blocked else "admin_unblock", "summary": reason[:300], "score_delta": 0, "source": "admin", "created_at": now})
        return await self.get_profile(guild_id, user_id)
