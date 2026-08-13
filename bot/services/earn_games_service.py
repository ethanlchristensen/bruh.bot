import logging
import random
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from bson import Int64

if TYPE_CHECKING:
    from bot.bruh_bot import BruhBot


GAME_FIELD_MAP = {
    "hangman": "hangman_plays_today",
    "trivia": "trivia_plays_today",
    "wordle": "wordle_plays_today",
    "rps": "rps_plays_today",
}

GAME_WIN_RESULTS = {
    "rps": {"win"},
    "trivia": {"correct"},
    "hangman": {"win"},
    "wordle": {"win"},
}


@dataclass(frozen=True)
class GameRewardResult:
    balance_after: float
    amount: float
    base_amount: float
    multiplier: float
    milestone_bonus: float
    streak: int


DATA_DATASETS = ("hangman_words", "wordle_words", "trivia_questions")


class EarnGamesService:
    def __init__(self, bot: "BruhBot"):
        self.bot = bot
        self.economy = bot.economy_service
        self.data_col = self.bot.config_service.col(self.bot.config_service.base.mongoEarnGamesDataCollectionName)
        self.logger = logging.getLogger(__name__)
        self.hangman_words: list[str] = []
        self.wordle_words: list[str] = []
        self.trivia_questions: list[dict] = []

    async def initialize(self):
        await self._ensure_data_indexes()
        await self.reload_data()

    async def _ensure_data_indexes(self):
        try:
            await self.data_col.create_index("dataset", unique=True)
        except Exception as e:
            self.logger.warning(f"Could not create earn-games data index: {e}")

    async def reload_data(self):
        datasets = {name: [] for name in DATA_DATASETS}
        async for doc in self.data_col.find({"dataset": {"$in": list(DATA_DATASETS)}}):
            datasets[doc["dataset"]] = doc.get("items", [])

        self.hangman_words = datasets["hangman_words"]
        self.wordle_words = datasets["wordle_words"]
        self.trivia_questions = datasets["trivia_questions"]
        self.logger.info(f"Loaded earn-games data: {len(self.hangman_words)} hangman, {len(self.wordle_words)} wordle, {len(self.trivia_questions)} trivia")

    def get_random_hangman_word(self) -> str | None:
        return random.choice(self.hangman_words) if self.hangman_words else None

    def get_random_wordle_word(self) -> str | None:
        return random.choice(self.wordle_words) if self.wordle_words else None

    def get_random_trivia_question(self) -> dict | None:
        return random.choice(self.trivia_questions) if self.trivia_questions else None

    async def get_remaining_plays(self, guild_id: int, user_id: int, game: str) -> int:
        config = await self.economy._get_economy_config(guild_id)
        limit_map = {
            "hangman": config.hangmanMaxPlaysPerDay,
            "trivia": config.triviaMaxPlaysPerDay,
            "wordle": config.wordleMaxPlaysPerDay,
            "rps": config.rpsMaxPlaysPerDay,
        }
        max_plays = limit_map.get(game, 0)
        if max_plays == 0:
            return -1

        field = GAME_FIELD_MAP.get(game)
        if not field:
            return 0

        doc = await self.economy._get_or_create_profile_raw(guild_id, user_id)
        now = datetime.now(UTC)
        today = now.strftime("%Y-%m-%d")
        play_date = doc.get("earn_games_play_date")
        if play_date != today:
            return max_plays

        played = doc.get(field, 0)
        return max(0, max_plays - played)

    async def increment_plays(self, guild_id: int, user_id: int, game: str):
        field = GAME_FIELD_MAP.get(game)
        if not field:
            return

        now = datetime.now(UTC)
        today = now.strftime("%Y-%m-%d")
        doc = await self.economy._get_or_create_profile_raw(guild_id, user_id)
        play_date = doc.get("earn_games_play_date")

        if play_date != today:
            await self.economy.collection.update_one(
                {"guild_id": Int64(guild_id), "user_id": Int64(user_id)},
                {"$set": {**dict.fromkeys(GAME_FIELD_MAP.values(), 0), "earn_games_play_date": today, "updated_at": now}},
            )

        await self.economy.collection.update_one(
            {"guild_id": Int64(guild_id), "user_id": Int64(user_id)},
            {"$inc": {field: 1}, "$set": {"earn_games_play_date": today, "updated_at": now}},
        )

    @staticmethod
    def is_game_win(game: str, result: str) -> bool:
        if game == "wordle":
            return result.startswith("win_guess_")
        return result in GAME_WIN_RESULTS.get(game, set())

    @staticmethod
    def _parse_streak_values(value: str, value_type: type[float] | type[int]) -> dict[int, float]:
        parsed: dict[int, float] = {}
        for item in value.split(","):
            try:
                threshold, reward = item.split(":", 1)
                parsed[int(threshold)] = value_type(reward)
            except (TypeError, ValueError):
                continue
        return parsed

    async def calculate_game_reward(self, guild_id: int, user_id: int, base_amount: float, game: str, result: str) -> dict:
        """Calculate the final reward using the streak after this result."""
        profile = await self.economy._get_or_create_profile_raw(guild_id, user_id)
        current_streak = profile.get("earn_game_current_streak", 0)
        won = self.is_game_win(game, result)
        streak = current_streak + 1 if won else 0
        config = await self.economy._get_economy_config(guild_id)
        multiplier = 1.0
        milestone_bonus = 0.0

        if won and config.earnGameStreakMultiplierEnabled:
            cap = max(1, config.earnGameStreakMultiplierCap)
            multiplier_values = self._parse_streak_values(config.earnGameStreakMultipliers, float)
            capped_streak = min(streak, cap)
            eligible = [threshold for threshold in multiplier_values if threshold <= capped_streak]
            if eligible:
                multiplier = multiplier_values[max(eligible)]

        if won:
            milestone_values = self._parse_streak_values(config.earnGameStreakMilestoneBonuses, float)
            milestone_bonus = milestone_values.get(streak, 0.0)

        amount = round(base_amount * multiplier + milestone_bonus, 2)
        return {
            "amount": amount,
            "base_amount": round(base_amount, 2),
            "multiplier": multiplier,
            "milestone_bonus": milestone_bonus,
            "streak": streak,
            "won": won,
        }

    @classmethod
    def summarize_game_results(cls, records: list[dict]) -> dict:
        """Rebuild aggregate stats from chronological earn-game ledger records."""
        wins = 0
        current_streak = 0
        longest_streak = 0
        coins_earned = 0.0
        for record in records:
            game = record.get("reference_id", "")
            result = record.get("metadata", {}).get("result", "")
            coins_earned += float(record.get("amount", 0.0))
            if cls.is_game_win(game, result):
                wins += 1
                current_streak += 1
                longest_streak = max(longest_streak, current_streak)
            else:
                current_streak = 0
        return {
            "earn_game_wins": wins,
            "earn_game_current_streak": current_streak,
            "earn_game_longest_streak": longest_streak,
            "earn_game_coins_earned": round(coins_earned, 2),
        }

    async def backfill_game_stats(self) -> int:
        """Rebuild stats for users with historical earn-game ledger entries."""
        cursor = self.economy.ledger.find({"kind": "earn_game_credit", "reference_type": "earn_game"}).sort([("guild_id", 1), ("user_id", 1), ("created_at", 1)])
        grouped: dict[tuple[int, int], list[dict]] = {}
        async for record in cursor:
            key = (int(record["guild_id"]), int(record["user_id"]))
            grouped.setdefault(key, []).append(record)

        for (guild_id, user_id), records in grouped.items():
            stats = self.summarize_game_results(records)
            await self.economy._get_or_create_profile_raw(guild_id, user_id)
            await self.economy.collection.update_one(
                {"guild_id": Int64(guild_id), "user_id": Int64(user_id)},
                {"$set": {**stats, "updated_at": datetime.now(UTC)}},
            )
        return len(grouped)

    async def record_game_result(
        self,
        guild_id: int,
        user_id: int,
        amount: float,
        game: str,
        result: str,
        idempotency_key: str = "",
    ) -> GameRewardResult:
        """Credit a completed game and atomically update its aggregate statistics."""
        if idempotency_key:
            existing = await self.economy.ledger.find_one({"idempotency_key": idempotency_key})
            if existing:
                metadata = existing.get("metadata", {})
                return GameRewardResult(
                    balance_after=existing.get("balance_after", 0.0),
                    amount=existing.get("amount", 0.0),
                    base_amount=metadata.get("base_amount", existing.get("amount", 0.0)),
                    multiplier=metadata.get("multiplier", 1.0),
                    milestone_bonus=metadata.get("milestone_bonus", 0.0),
                    streak=metadata.get("streak", 0),
                )

        reward = await self.calculate_game_reward(guild_id, user_id, amount, game, result)
        balance = await self.economy.add_coins(guild_id, user_id, reward["amount"])
        now = datetime.now(UTC)
        won = reward["won"]
        if won:
            pipeline = [
                {
                    "$set": {
                        "earn_game_wins": {"$add": [{"$ifNull": ["$earn_game_wins", 0]}, 1]},
                        "earn_game_current_streak": {"$add": [{"$ifNull": ["$earn_game_current_streak", 0]}, 1]},
                        "earn_game_coins_earned": {"$add": [{"$ifNull": ["$earn_game_coins_earned", 0.0]}, reward["amount"]]},
                        "updated_at": now,
                    }
                },
                {
                    "$set": {
                        "earn_game_longest_streak": {
                            "$max": [
                                {"$ifNull": ["$earn_game_longest_streak", 0]},
                                "$earn_game_current_streak",
                            ]
                        }
                    }
                },
            ]
        else:
            pipeline = [
                {
                    "$set": {
                        "earn_game_current_streak": 0,
                        "earn_game_coins_earned": {"$add": [{"$ifNull": ["$earn_game_coins_earned", 0.0]}, reward["amount"]]},
                        "updated_at": now,
                    }
                }
            ]
        await self.economy.collection.update_one(
            {"guild_id": Int64(guild_id), "user_id": Int64(user_id)},
            pipeline,
        )
        await self.economy.record_transaction(
            guild_id,
            user_id,
            "earn_game_credit",
            reward["amount"],
            balance,
            reference_type="earn_game",
            reference_id=game,
            idempotency_key=idempotency_key,
            metadata={
                "result": result,
                "won": won,
                "base_amount": reward["base_amount"],
                "multiplier": reward["multiplier"],
                "milestone_bonus": reward["milestone_bonus"],
                "streak": reward["streak"],
            },
        )
        return GameRewardResult(
            balance_after=balance,
            amount=reward["amount"],
            base_amount=reward["base_amount"],
            multiplier=reward["multiplier"],
            milestone_bonus=reward["milestone_bonus"],
            streak=reward["streak"],
        )

    async def grant_game_reward(self, guild_id: int, user_id: int, amount: float, game: str, result: str) -> float:
        """Backward-compatible alias for callers outside the earn-games cog."""
        return (await self.record_game_result(guild_id, user_id, amount, game, result)).balance_after
