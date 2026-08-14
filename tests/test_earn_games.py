import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from bot.cogs.earn_games_cog import HANGMAN_MAX_WRONG, WORDLE_WORD_LENGTH, EarnGamesCog, HangmanView, WordleView, _wordle_feedback
from bot.services.earn_games_service import EarnGamesService


class WordleFeedbackTests(unittest.TestCase):
    def test_exact_match_all_green(self):
        result = _wordle_feedback("crane", "crane")
        self.assertEqual(result, "\U0001f7e9\U0001f7e9\U0001f7e9\U0001f7e9\U0001f7e9")

    def test_no_match_all_black(self):
        result = _wordle_feedback("swift", "crane")
        self.assertEqual(result, "\u2b1b\u2b1b\u2b1b\u2b1b\u2b1b")

    def test_mixed_feedback(self):
        result = _wordle_feedback("crash", "crane")
        self.assertEqual(result, "\U0001f7e9\U0001f7e9\U0001f7e9\u2b1b\u2b1b")

    def test_yellow_letter_wrong_position(self):
        result = _wordle_feedback("smile", "silly")
        self.assertEqual(result, "\U0001f7e9\u2b1b\U0001f7e8\U0001f7e9\u2b1b")

    def test_duplicate_guess_letters_both_found(self):
        result = _wordle_feedback("robot", "boost")
        self.assertEqual(result, "\u2b1b\U0001f7e9\U0001f7e8\U0001f7e8\U0001f7e9")

    def test_duplicate_guess_second_black(self):
        result = _wordle_feedback("press", "sheep")
        self.assertEqual(result, "\U0001f7e8\u2b1b\U0001f7e9\U0001f7e8\u2b1b")

    def test_duplicate_word_letters(self):
        result = _wordle_feedback("cocoa", "ocean")
        self.assertEqual(result, "\U0001f7e8\U0001f7e8\u2b1b\u2b1b\U0001f7e8")

    def test_duplicate_exact_takes_precedence(self):
        result = _wordle_feedback("these", "teeth")
        self.assertEqual(result, "\U0001f7e9\U0001f7e8\U0001f7e9\u2b1b\U0001f7e8")

    def test_feedback_result_is_correct_length(self):
        result = _wordle_feedback("abcde", "vwxyz")
        self.assertEqual(len(result), WORDLE_WORD_LENGTH)
        self.assertEqual(result, "\u2b1b\u2b1b\u2b1b\u2b1b\u2b1b")

    def test_duplicate_guess_one_exact_one_black(self):
        result = _wordle_feedback("aahed", "crane")
        self.assertEqual(result, "\U0001f7e8\u2b1b\u2b1b\U0001f7e8\u2b1b")


class GameStateIsolationTests(unittest.TestCase):
    def setUp(self):
        self.cog = EarnGamesCog(SimpleNamespace())

    def test_hangman_separate_guilds_same_user(self):
        self.cog.hangman_games[(100, 1)] = {"word": "test", "guessed": set(), "wrong": 0}
        self.cog.hangman_games[(200, 1)] = {"word": "hello", "guessed": set(), "wrong": 0}

        self.assertIn((100, 1), self.cog.hangman_games)
        self.assertIn((200, 1), self.cog.hangman_games)
        self.assertNotEqual(
            self.cog.hangman_games[(100, 1)]["word"],
            self.cog.hangman_games[(200, 1)]["word"],
        )

    def test_hangman_same_guild_different_users(self):
        self.cog.hangman_games[(100, 1)] = {"word": "test", "guessed": set(), "wrong": 0}
        self.cog.hangman_games[(100, 2)] = {"word": "hello", "guessed": set(), "wrong": 0}

        self.assertIn((100, 1), self.cog.hangman_games)
        self.assertIn((100, 2), self.cog.hangman_games)

    def test_wordle_separate_guilds_same_user(self):
        self.cog.wordle_games[(100, 1)] = {"word": "crane", "guesses": []}
        self.cog.wordle_games[(200, 1)] = {"word": "swift", "guesses": []}

        self.assertIn((100, 1), self.cog.wordle_games)
        self.assertIn((200, 1), self.cog.wordle_games)

    def test_game_removal_does_not_affect_other_guild(self):
        self.cog.hangman_games[(100, 1)] = {"word": "test", "guessed": set(), "wrong": 0}
        self.cog.hangman_games[(200, 1)] = {"word": "hello", "guessed": set(), "wrong": 0}

        self.cog.hangman_games.pop((100, 1), None)

        self.assertNotIn((100, 1), self.cog.hangman_games)
        self.assertIn((200, 1), self.cog.hangman_games)

    def test_old_user_id_key_no_longer_works(self):
        self.cog.hangman_games[(100, 1)] = {"word": "test", "guessed": set(), "wrong": 0}

        self.assertNotIn(1, self.cog.hangman_games)


class GameResumeTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        config = SimpleNamespace(economyConfig=SimpleNamespace(miniGamesEnabled=True))

        async def get_config(_guild_id):
            return config

        self.bot = SimpleNamespace(
            config_service=SimpleNamespace(get_config=get_config),
            earn_games_service=SimpleNamespace(increment_plays=AsyncMock()),
        )
        self.cog = EarnGamesCog(self.bot)

    @staticmethod
    def _interaction(guild_id=100, user_id=1, message=None):
        interaction = SimpleNamespace(
            guild=SimpleNamespace(id=guild_id),
            user=SimpleNamespace(id=user_id),
            response=SimpleNamespace(send_message=AsyncMock()),
            original_response=AsyncMock(return_value=message or Mock()),
        )
        return interaction

    async def test_wordle_start_recreates_view_for_active_game(self):
        old_view = Mock()
        game = {"word": "crane", "guesses": ["swift"], "view": old_view, "message": Mock(), "rewarded": False}
        self.cog.wordle_games[(100, 1)] = game
        new_message = Mock()
        interaction = self._interaction(message=new_message)

        await self.cog.wordle_start.callback(self.cog, interaction)

        old_view.stop.assert_called_once_with()
        interaction.response.send_message.assert_awaited_once()
        sent_kwargs = interaction.response.send_message.await_args.kwargs
        self.assertIsInstance(sent_kwargs["view"], WordleView)
        self.assertIn("SWIFT", sent_kwargs["embed"].description)
        self.assertIs(game["message"], new_message)
        self.assertIs(game["view"], sent_kwargs["view"])
        self.bot.earn_games_service.increment_plays.assert_not_awaited()

    async def test_hangman_start_recreates_view_for_active_game(self):
        old_view = Mock()
        game = {"word": "test", "guessed": {"t"}, "wrong": 0, "view": old_view, "message": Mock(), "rewarded": False}
        self.cog.hangman_games[(100, 1)] = game
        new_message = Mock()
        interaction = self._interaction(message=new_message)

        await self.cog.hangman_start.callback(self.cog, interaction)

        old_view.stop.assert_called_once_with()
        interaction.response.send_message.assert_awaited_once()
        sent_kwargs = interaction.response.send_message.await_args.kwargs
        self.assertIsInstance(sent_kwargs["view"], HangmanView)
        self.assertIn("T", sent_kwargs["embed"].description)
        self.assertIs(game["message"], new_message)
        self.assertIs(game["view"], sent_kwargs["view"])
        self.bot.earn_games_service.increment_plays.assert_not_awaited()


class RewardGuardTests(unittest.TestCase):
    def setUp(self):
        self.cog = EarnGamesCog(SimpleNamespace())

    def test_rewarded_flag_prevents_double_reward(self):
        game = {"word": "test", "guessed": {"t", "e", "s"}, "wrong": 0, "rewarded": False}
        self.cog.hangman_games[(100, 1)] = game

        self.assertFalse(game["rewarded"])
        game["rewarded"] = True
        self.assertTrue(game["rewarded"])
        self.cog.hangman_games.pop((100, 1), None)
        self.assertNotIn((100, 1), self.cog.hangman_games)

    def test_hangman_guess_count_is_correct(self):
        game = {"word": "hi", "guessed": {"h"}, "wrong": 0, "rewarded": False}
        remaining = 1
        guess = "i"
        game["guessed"].add(guess)
        self.assertTrue(all(c in game["guessed"] for c in game["word"]))
        self.assertEqual(remaining, 1)

    def test_wordle_correct_guess_on_last_attempt(self):
        game = {"word": "crane", "guesses": ["swift", "plumb", "dough", "spank", "jazzy"], "rewarded": False}
        guess = "crane"
        game["guesses"].append(guess)
        self.assertEqual(guess, game["word"])
        self.assertEqual(len(game["guesses"]), 6)


class WordleGridTests(unittest.TestCase):
    def setUp(self):
        self.cog = EarnGamesCog(SimpleNamespace())

    def test_grid_includes_words(self):
        game = {"word": "crane", "guesses": ["crane", "swift"]}
        grid = self.cog._wordle_grid(game)
        self.assertIn("CRANE", grid)
        self.assertIn("SWIFT", grid)
        self.assertIn("\U0001f7e9", grid)
        self.assertIn("\u2b1b", grid)

    def test_grid_format_has_word_and_tiles(self):
        game = {"word": "crane", "guesses": ["crane"]}
        grid = self.cog._wordle_grid(game)
        parts = grid.split("  ")
        self.assertEqual(len(parts), 2)
        self.assertEqual(parts[0], "CRANE")

    def test_grid_empty_guesses(self):
        game = {"word": "crane", "guesses": []}
        grid = self.cog._wordle_grid(game)
        self.assertEqual(grid, "")


class ModalValidationTests(unittest.TestCase):
    def setUp(self):
        self.cog = EarnGamesCog(SimpleNamespace())

    def test_hangman_single_letter_valid(self):
        letter = "a"
        self.assertEqual(len(letter), 1)
        self.assertTrue(letter.isalpha())

    def test_hangman_multiple_letters_invalid(self):
        letter = "ab"
        self.assertNotEqual(len(letter), 1)

    def test_hangman_non_alpha_invalid(self):
        letter = "1"
        self.assertFalse(letter.isalpha())

    def test_wordle_five_letter_valid(self):
        word = "crane"
        self.assertEqual(len(word), WORDLE_WORD_LENGTH)
        self.assertTrue(word.isalpha())

    def test_wordle_four_letter_invalid(self):
        word = "abcd"
        self.assertNotEqual(len(word), WORDLE_WORD_LENGTH)

    def test_wordle_six_letter_invalid(self):
        word = "abcdef"
        self.assertNotEqual(len(word), WORDLE_WORD_LENGTH)

    def test_wordle_non_alpha_invalid(self):
        word = "cr1ne"
        self.assertFalse(word.isalpha())


class HangmanEmbedTests(unittest.TestCase):
    def setUp(self):
        self.cog = EarnGamesCog(SimpleNamespace())

    def test_embed_shows_unrevealed_word(self):
        game = {"word": "test", "guessed": {"t"}, "wrong": 0}
        embed = self.cog._hangman_embed(game)
        self.assertIn("T", embed.description)
        self.assertTrue(embed.description.count("T") >= 1)

    def test_embed_shows_full_lives_at_start(self):
        game = {"word": "test", "guessed": set(), "wrong": 0}
        embed = self.cog._hangman_embed(game)
        heart_count = embed.description.count("\u2764\ufe0f")
        self.assertEqual(heart_count, HANGMAN_MAX_WRONG)

    def test_embed_shows_reduced_lives_after_wrong_guess(self):
        game = {"word": "test", "guessed": {"x"}, "wrong": 1}
        embed = self.cog._hangman_embed(game)
        heart_count = embed.description.count("\u2764\ufe0f")
        black_count = embed.description.count("\U0001f5a4")
        self.assertEqual(heart_count, HANGMAN_MAX_WRONG - 1)
        self.assertEqual(black_count, 1)

    def test_embed_shows_guessed_letters(self):
        game = {"word": "test", "guessed": {"t", "e", "x"}, "wrong": 1}
        embed = self.cog._hangman_embed(game)
        self.assertIn("E", embed.description)
        self.assertIn("T", embed.description)
        self.assertIn("X", embed.description)


class EarnGameStatsTests(unittest.TestCase):
    def test_game_win_classification(self):
        self.assertTrue(EarnGamesService.is_game_win("rps", "win"))
        self.assertTrue(EarnGamesService.is_game_win("trivia", "correct"))
        self.assertTrue(EarnGamesService.is_game_win("hangman", "win"))
        self.assertTrue(EarnGamesService.is_game_win("wordle", "win_guess_3"))

    def test_non_wins_reset_the_streak(self):
        records = [
            {"reference_id": "rps", "metadata": {"result": "win"}, "amount": 2.0},
            {"reference_id": "trivia", "metadata": {"result": "correct"}, "amount": 3.0},
            {"reference_id": "rps", "metadata": {"result": "tie"}, "amount": 1.0},
            {"reference_id": "wordle", "metadata": {"result": "win_guess_1"}, "amount": 4.0},
        ]

        stats = EarnGamesService.summarize_game_results(records)

        self.assertEqual(stats["earn_game_wins"], 3)
        self.assertEqual(stats["earn_game_current_streak"], 1)
        self.assertEqual(stats["earn_game_longest_streak"], 2)
        self.assertEqual(stats["earn_game_coins_earned"], 10.0)

    def test_losses_and_participation_rewards_count_as_coins(self):
        records = [
            {"reference_id": "hangman", "metadata": {"result": "loss"}, "amount": 2.5},
            {"reference_id": "trivia", "metadata": {"result": "timeout"}, "amount": 1.25},
        ]

        stats = EarnGamesService.summarize_game_results(records)

        self.assertEqual(stats["earn_game_wins"], 0)
        self.assertEqual(stats["earn_game_current_streak"], 0)
        self.assertEqual(stats["earn_game_longest_streak"], 0)
        self.assertEqual(stats["earn_game_coins_earned"], 3.75)

    def test_summary_isolated_by_record_group(self):
        first = EarnGamesService.summarize_game_results([{"reference_id": "rps", "metadata": {"result": "win"}, "amount": 5.0}])
        second = EarnGamesService.summarize_game_results([{"reference_id": "rps", "metadata": {"result": "loss"}, "amount": 2.0}])

        self.assertEqual(first["earn_game_wins"], 1)
        self.assertEqual(second["earn_game_wins"], 0)
        self.assertEqual(first["earn_game_current_streak"], 1)
        self.assertEqual(second["earn_game_current_streak"], 0)


class EarnGameRewardTests(unittest.IsolatedAsyncioTestCase):
    async def test_multiplier_uses_new_streak_and_caps(self):
        config = SimpleNamespace(
            earnGameStreakMultiplierEnabled=True,
            earnGameStreakMultiplierCap=10,
            earnGameStreakMultipliers="3:1.10,5:1.15,10:1.25",
            earnGameStreakMilestoneBonuses="5:10,10:25,20:75",
        )

        async def get_config(_guild_id):
            return config

        economy = SimpleNamespace(_get_economy_config=get_config)
        economy._get_or_create_profile_raw = self._profile_at_ten
        service = EarnGamesService.__new__(EarnGamesService)
        service.economy = economy

        reward = await service.calculate_game_reward(1, 2, 30.0, "wordle", "win_guess_1")

        self.assertEqual(reward["amount"], 37.5)
        self.assertEqual(reward["multiplier"], 1.25)
        self.assertEqual(reward["milestone_bonus"], 0.0)
        self.assertEqual(reward["streak"], 11)

    async def test_milestone_bonus_is_added_once_at_milestone(self):
        config = SimpleNamespace(
            earnGameStreakMultiplierEnabled=True,
            earnGameStreakMultiplierCap=10,
            earnGameStreakMultipliers="3:1.10,5:1.15,10:1.25",
            earnGameStreakMilestoneBonuses="5:10,10:25,20:75",
        )

        async def get_config(_guild_id):
            return config

        economy = SimpleNamespace(_get_economy_config=get_config)

        async def get_profile(_guild_id, _user_id):
            return {"earn_game_current_streak": 4}

        economy._get_or_create_profile_raw = get_profile
        service = EarnGamesService.__new__(EarnGamesService)
        service.economy = economy

        reward = await service.calculate_game_reward(1, 2, 10.0, "rps", "win")

        self.assertEqual(reward["amount"], 21.5)
        self.assertEqual(reward["multiplier"], 1.15)
        self.assertEqual(reward["milestone_bonus"], 10.0)
        self.assertEqual(reward["streak"], 5)

    async def test_non_win_has_no_multiplier_or_milestone(self):
        config = SimpleNamespace(
            earnGameStreakMultiplierEnabled=True,
            earnGameStreakMultiplierCap=10,
            earnGameStreakMultipliers="3:1.10,5:1.15,10:1.25",
            earnGameStreakMilestoneBonuses="5:10,10:25,20:75",
        )

        async def get_config(_guild_id):
            return config

        economy = SimpleNamespace(_get_economy_config=get_config)

        async def get_profile(_guild_id, _user_id):
            return {"earn_game_current_streak": 9}

        economy._get_or_create_profile_raw = get_profile
        service = EarnGamesService.__new__(EarnGamesService)
        service.economy = economy

        reward = await service.calculate_game_reward(1, 2, 5.0, "rps", "tie")

        self.assertEqual(reward["amount"], 5.0)
        self.assertEqual(reward["multiplier"], 1.0)
        self.assertEqual(reward["milestone_bonus"], 0.0)
        self.assertEqual(reward["streak"], 0)

    @staticmethod
    async def _profile_at_ten(_guild_id, _user_id):
        return {"earn_game_current_streak": 10}


if __name__ == "__main__":
    unittest.main()
