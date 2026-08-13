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
        self.ledger = self.bot.config_service.col(self.bot.config_service.base.mongoTransactionLedgerCollectionName)
        self.logger = logging.getLogger(__name__)

    async def initialize(self):
        await self._ensure_indexes()
        await self._ensure_ledger_indexes()

    async def _ensure_indexes(self):
        try:
            await self.collection.create_index([("guild_id", 1), ("user_id", 1)], unique=True)
            await self.collection.create_index("level")
            await self.collection.create_index("xp")
            await self.collection.create_index("bruh_coins")
            await self.collection.create_index([("guild_id", 1), ("earn_game_wins", -1)])
            await self.collection.create_index([("guild_id", 1), ("earn_game_coins_earned", -1)])
            self.logger.info("Created indexes on UserProfiles collection")
        except Exception as e:
            self.logger.warning(f"Could not create indexes: {e}")

    async def _ensure_ledger_indexes(self):
        try:
            await self.ledger.create_index([("guild_id", 1), ("created_at", -1)])
            await self.ledger.create_index([("guild_id", 1), ("user_id", 1), ("created_at", -1)])
            await self.ledger.create_index("idempotency_key", unique=True, sparse=True)
            self.logger.info("Created indexes on TransactionLedger collection")
        except Exception as e:
            self.logger.warning(f"Could not create ledger indexes: {e}")

    async def record_transaction(
        self,
        guild_id: int,
        user_id: int,
        kind: str,
        amount: float,
        balance_after: float,
        reference_type: str = "",
        reference_id: str = "",
        idempotency_key: str = "",
        metadata: dict | None = None,
    ):
        now = datetime.now(UTC)
        doc = {
            "guild_id": Int64(guild_id),
            "user_id": Int64(user_id),
            "kind": kind,
            "amount": amount,
            "balance_after": balance_after,
            "reference_type": reference_type,
            "reference_id": reference_id,
            "metadata": metadata or {},
            "created_at": now,
        }
        if idempotency_key:
            doc["idempotency_key"] = idempotency_key

        if idempotency_key:
            existing = await self.ledger.find_one({"idempotency_key": idempotency_key})
            if existing:
                return existing

        await self.ledger.insert_one(doc)
        return doc

    async def deduct_coins_atomic(self, guild_id: int, user_id: int, amount: float, idempotency_key: str = "") -> tuple[bool, float]:
        if idempotency_key:
            existing = await self.ledger.find_one({"idempotency_key": idempotency_key})
            if existing:
                doc = await self._get_or_create_profile_raw(guild_id, user_id)
                return True, doc.get("bruh_coins", 0.0)

        doc = await self._get_or_create_profile_raw(guild_id, user_id)
        current = doc.get("bruh_coins", 0.0)
        if current < amount:
            return False, current

        now = datetime.now(UTC)
        result = await self.collection.find_one_and_update(
            {"guild_id": Int64(guild_id), "user_id": Int64(user_id), "bruh_coins": {"$gte": amount}},
            {"$inc": {"bruh_coins": -amount}, "$set": {"updated_at": now}},
            return_document=True,
        )
        if result is None:
            return False, current

        new_balance = result.get("bruh_coins", 0.0)
        await self.record_transaction(
            guild_id,
            user_id,
            "debit",
            -amount,
            new_balance,
            idempotency_key=idempotency_key,
        )
        return True, new_balance

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
                "last_message_time": None,
                "spam_coin_penalty": 0.0,
                "booster_active_until": None,
                "coinflip_plays_today": 0,
                "dice_plays_today": 0,
                "slots_plays_today": 0,
                "gambling_play_date": None,
                "earn_games_play_date": None,
                "hangman_plays_today": 0,
                "trivia_plays_today": 0,
                "wordle_plays_today": 0,
                "rps_plays_today": 0,
                "earn_game_wins": 0,
                "earn_game_current_streak": 0,
                "earn_game_longest_streak": 0,
                "earn_game_coins_earned": 0.0,
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
                "last_message_time": None,
                "spam_coin_penalty": 0.0,
                "booster_active_until": None,
                "coinflip_plays_today": 0,
                "dice_plays_today": 0,
                "slots_plays_today": 0,
                "gambling_play_date": None,
                "earn_games_play_date": None,
                "hangman_plays_today": 0,
                "trivia_plays_today": 0,
                "wordle_plays_today": 0,
                "rps_plays_today": 0,
                "earn_game_wins": 0,
                "earn_game_current_streak": 0,
                "earn_game_longest_streak": 0,
                "earn_game_coins_earned": 0.0,
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
        await self._get_or_create_profile_raw(guild_id, user_id)
        until = datetime.now(UTC) + timedelta(hours=hours)
        await self.collection.update_one(
            {"guild_id": Int64(guild_id), "user_id": Int64(user_id)},
            {"$set": {"booster_active_until": until, "updated_at": datetime.now(UTC)}},
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
        balance = result.get("bruh_coins", 0.0) if result else 0.0
        await self.record_transaction(guild_id, user_id, "credit", amount, balance)
        return balance

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
        await self.record_transaction(guild_id, user_id, "debit", -amount, new_balance)
        return True, new_balance

    async def settle_purchase(
        self,
        guild_id: int,
        buyer_id: int,
        gross_amount: float,
        purchase_type: str,
        reference_type: str = "",
        reference_id: str = "",
        idempotency_key: str = "",
        metadata: dict | None = None,
    ) -> dict:
        if idempotency_key:
            existing = await self.ledger.find_one({"idempotency_key": idempotency_key})
            if existing:
                existing_metadata = existing.get("metadata", {})
                return {
                    "success": True,
                    "gross_amount": existing_metadata.get("gross_amount", gross_amount),
                    "tax_rate": existing_metadata.get("tax_rate", 0.0),
                    "tax_amount": existing_metadata.get("tax_amount", 0.0),
                    "admin_shares": existing_metadata.get("admin_shares", []),
                    "net_amount": existing_metadata.get("net_amount", gross_amount),
                    "buyer_new_balance": existing.get("balance_after", 0.0),
                }

        config = await self._get_economy_config(guild_id)
        tax_rate = getattr(config, "purchaseTaxRate", 0.02)
        guild_config = await self.bot.config_service.get_config(str(guild_id))
        configured_admin_ids = guild_config.adminIds

        active_admin_ids: list[int] = []
        guild = self.bot.get_guild(guild_id)
        if guild:
            for admin_id_str in configured_admin_ids:
                try:
                    admin_id = int(admin_id_str)
                    member = guild.get_member(admin_id)
                    if member:
                        active_admin_ids.append(admin_id)
                except (ValueError, TypeError):
                    pass

        tax_amount = 0.0
        admin_shares: list[dict] = []
        net_amount = gross_amount

        if tax_rate > 0 and active_admin_ids:
            tax_amount = round(gross_amount * tax_rate, 2)
            if tax_amount > 0:
                net_amount = round(gross_amount - tax_amount, 2)
                base_share = tax_amount // len(active_admin_ids)
                remainder_cents = int(round((tax_amount - base_share * len(active_admin_ids)) * 100))
                for i, admin_id in enumerate(sorted(active_admin_ids)):
                    share = base_share + (0.01 if i < remainder_cents else 0.0)
                    share = round(share, 2)
                    if share > 0:
                        admin_shares.append({"admin_id": admin_id, "share": share})

        success, buyer_balance = await self.deduct_coins(guild_id, buyer_id, gross_amount)
        if not success:
            return {
                "success": False,
                "error": f"Insufficient coins. Need {gross_amount:.2f}, have {buyer_balance:.2f}.",
                "gross_amount": gross_amount,
                "tax_rate": tax_rate,
                "tax_amount": 0.0,
                "admin_shares": [],
                "net_amount": gross_amount,
                "buyer_new_balance": buyer_balance,
            }

        for share_info in admin_shares:
            await self.add_coins(guild_id, share_info["admin_id"], share_info["share"])
            await self.record_transaction(
                guild_id,
                share_info["admin_id"],
                f"{purchase_type}_admin_tax_credit",
                share_info["share"],
                0.0,
                reference_type=reference_type,
                reference_id=reference_id,
                metadata={"buyer_id": buyer_id, "gross_amount": gross_amount, "tax_rate": tax_rate},
            )

        await self.record_transaction(
            guild_id,
            buyer_id,
            f"{purchase_type}_debit",
            -gross_amount,
            buyer_balance,
            reference_type=reference_type,
            reference_id=reference_id,
            idempotency_key=idempotency_key,
            metadata={
                **(metadata or {}),
                "gross_amount": gross_amount,
                "tax_rate": tax_rate,
                "tax_amount": tax_amount,
                "admin_shares": admin_shares,
                "net_amount": net_amount,
            },
        )

        return {
            "success": True,
            "gross_amount": gross_amount,
            "tax_rate": tax_rate,
            "tax_amount": tax_amount,
            "admin_shares": admin_shares,
            "net_amount": net_amount,
            "buyer_new_balance": buyer_balance,
        }

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
                {"user_id": 1, "xp": 1, "level": 1, "bruh_coins": 1, "total_messages": 1, "total_images": 1, "total_reactions_given": 1, "_id": 0},
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
            doc["total_messages"] = doc.get("total_messages", 0)
            doc["total_images"] = doc.get("total_images", 0)
            doc["total_reactions_given"] = doc.get("total_reactions_given", 0)
            doc["xp_for_next_level"] = self._xp_for_next_level(doc["level"])
            results.append(self._serialize_dates(doc))
            rank += 1
        return results

    async def get_game_leaderboard(self, guild_id: int, sort_by: str = "wins", limit: int = 25) -> list[dict]:
        sort_fields = {
            "wins": "earn_game_wins",
            "coins": "earn_game_coins_earned",
        }
        field = sort_fields.get(sort_by, "earn_game_wins")
        cursor = (
            self.collection.find(
                {"guild_id": Int64(guild_id), field: {"$gt": 0}},
                {"user_id": 1, "earn_game_wins": 1, "earn_game_current_streak": 1, "earn_game_longest_streak": 1, "earn_game_coins_earned": 1, "_id": 0},
            )
            .sort([(field, -1), ("user_id", 1)])
            .limit(max(1, min(limit, 25)))
        )
        results = []
        rank = 1
        async for doc in cursor:
            doc["rank"] = rank
            doc["earn_game_wins"] = doc.get("earn_game_wins", 0)
            doc["earn_game_current_streak"] = doc.get("earn_game_current_streak", 0)
            doc["earn_game_longest_streak"] = doc.get("earn_game_longest_streak", 0)
            doc["earn_game_coins_earned"] = doc.get("earn_game_coins_earned", 0.0)
            results.append(doc)
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

    async def claim_daily(self, guild_id: int, user_id: int) -> tuple[bool, float, str, datetime | None]:
        econ_config = await self._get_economy_config(guild_id)
        doc = await self._get_or_create_profile_raw(guild_id, user_id)
        now = datetime.now(UTC)
        today_reset = datetime(now.year, now.month, now.day, 6, 0, 0, tzinfo=UTC)
        if now < today_reset:
            today_reset -= timedelta(days=1)
        next_reset = today_reset + timedelta(days=1)
        last_claim = doc.get("last_daily_claim")
        if last_claim:
            if isinstance(last_claim, str):
                last_claim = datetime.fromisoformat(last_claim.replace("Z", "+00:00"))
            if last_claim.tzinfo is None:
                last_claim = last_claim.replace(tzinfo=UTC)
            if last_claim >= today_reset:
                return False, 0.0, f"Already claimed today! Resets <t:{int(next_reset.timestamp())}:R>.", next_reset
        amount = round(random.uniform(econ_config.dailyCoinMin, econ_config.dailyCoinMax), 2)
        await self.collection.update_one(
            {"guild_id": Int64(guild_id), "user_id": Int64(user_id)},
            {"$inc": {"bruh_coins": amount}, "$set": {"last_daily_claim": now, "updated_at": now}},
        )
        return True, amount, "", next_reset

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

    async def get_remaining_gambling_plays(self, guild_id: int, user_id: int, game: str) -> int:
        config = await self._get_economy_config(guild_id)
        limit_map = {
            "coinflip": config.gamblingMaxCoinflipsPerDay,
            "dice": config.gamblingMaxDicePerDay,
            "slots": config.gamblingMaxSlotsPerDay,
        }
        max_plays = limit_map.get(game, 0)
        if max_plays == 0:
            return -1

        field_map = {
            "coinflip": "coinflip_plays_today",
            "dice": "dice_plays_today",
            "slots": "slots_plays_today",
        }
        field = field_map.get(game)
        if not field:
            return 0

        doc = await self._get_or_create_profile_raw(guild_id, user_id)
        now = datetime.now(UTC)
        today = now.strftime("%Y-%m-%d")
        play_date = doc.get("gambling_play_date")
        if play_date != today:
            return max_plays

        played = doc.get(field, 0)
        return max(0, max_plays - played)

    async def increment_gambling_plays(self, guild_id: int, user_id: int, game: str):
        field_map = {
            "coinflip": "coinflip_plays_today",
            "dice": "dice_plays_today",
            "slots": "slots_plays_today",
        }
        field = field_map.get(game)
        if not field:
            return

        now = datetime.now(UTC)
        today = now.strftime("%Y-%m-%d")
        doc = await self._get_or_create_profile_raw(guild_id, user_id)
        play_date = doc.get("gambling_play_date")

        if play_date != today:
            await self.collection.update_one(
                {"guild_id": Int64(guild_id), "user_id": Int64(user_id)},
                {"$set": {"coinflip_plays_today": 0, "dice_plays_today": 0, "slots_plays_today": 0, "gambling_play_date": today, "updated_at": now}},
            )

        await self.collection.update_one(
            {"guild_id": Int64(guild_id), "user_id": Int64(user_id)},
            {"$inc": {field: 1}, "$set": {"gambling_play_date": today, "updated_at": now}},
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
                    "earn_game_wins": 0,
                    "earn_game_current_streak": 0,
                    "earn_game_longest_streak": 0,
                    "earn_game_coins_earned": 0.0,
                    "last_xp_grant": None,
                    "last_daily_claim": None,
                    "last_message_time": None,
                    "spam_coin_penalty": 0.0,
                    "booster_active_until": None,
                    "updated_at": now,
                },
            },
        )

    async def handle_message_event(self, guild_id: int, user_id: int, config: EconomyConfig, has_attachment: bool, is_bot_mention: bool) -> tuple[int, int, bool]:
        if not config.xpEnabled:
            return 0, 0, False

        now = datetime.now(UTC)
        doc = await self._get_or_create_profile_raw(guild_id, user_id)

        penalty = doc.get("spam_coin_penalty", 0.0)
        last_msg_time = doc.get("last_message_time")
        if last_msg_time:
            if isinstance(last_msg_time, str):
                last_msg_time = datetime.fromisoformat(last_msg_time.replace("Z", "+00:00"))
            if last_msg_time.tzinfo is None:
                last_msg_time = last_msg_time.replace(tzinfo=UTC)
            elapsed = (now - last_msg_time).total_seconds()
            if elapsed < config.spamCoinThreshold:
                penalty = min(config.spamCoinPenaltyMax, penalty + config.spamCoinPenaltyIncrement)
            else:
                penalty = max(0.0, penalty - elapsed * config.spamCoinPenaltyRecovery)

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
        booster = doc.get("booster_active_until")
        if booster:
            if isinstance(booster, str):
                booster = datetime.fromisoformat(booster.replace("Z", "+00:00"))
            if booster.tzinfo is None:
                booster = booster.replace(tzinfo=UTC)
            if now < booster:
                xp_awarded *= 2
            else:
                await self.collection.update_one(
                    {"guild_id": Int64(guild_id), "user_id": Int64(user_id)},
                    {"$set": {"booster_active_until": None}},
                )

        coins_awarded = round(coins_awarded * (1.0 - penalty), 2)

        new_xp, old_level, new_level = await self.add_xp(guild_id, user_id, xp_awarded)
        await self.add_coins(guild_id, user_id, coins_awarded)
        await self.add_stat(guild_id, user_id, "total_messages")

        await self.collection.update_one(
            {"guild_id": Int64(guild_id), "user_id": Int64(user_id)},
            {"$set": {"spam_coin_penalty": penalty, "last_message_time": now, "updated_at": now}},
        )

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
