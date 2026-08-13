import logging
import random
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

    async def grant_game_reward(self, guild_id: int, user_id: int, amount: float, game: str, result: str) -> float:
        balance = await self.economy.add_coins(guild_id, user_id, amount)
        await self.economy.record_transaction(
            guild_id,
            user_id,
            "earn_game_credit",
            amount,
            balance,
            reference_type="earn_game",
            reference_id=game,
            metadata={"result": result},
        )
        return balance
