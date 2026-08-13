import logging
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


class EarnGamesService:
    def __init__(self, bot: "BruhBot"):
        self.bot = bot
        self.economy = bot.economy_service
        self.logger = logging.getLogger(__name__)

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
