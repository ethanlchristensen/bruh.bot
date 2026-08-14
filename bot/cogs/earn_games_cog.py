import contextlib
import random
import string
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from bot.utils.decarators.command_logging import log_command_usage
from bot.utils.decarators.global_block_check import is_globally_blocked

if TYPE_CHECKING:
    from bot.bruh_bot import BruhBot

HANGMAN_MAX_WRONG = 6
WORDLE_WORD_LENGTH = 5
WORDLE_MAX_GUESSES = 6

RPS_CHOICES = {
    "\U0001faa8": "rock",
    "\U0001f4c4": "paper",
    "\u2702\ufe0f": "scissors",
}
RPS_BEATS = {"rock": "scissors", "paper": "rock", "scissors": "paper"}
RPS_RESULT_LABELS = {"win": "You won!", "tie": "It's a tie!", "loss": "You lost."}


def _coins_embed(title: str, description: str) -> discord.Embed:
    embed = discord.Embed(title=title, description=description, color=0xFEE75C, timestamp=datetime.now(UTC))
    embed.set_footer(text="bruh.bot")
    return embed


def _random_coin(lo: float, hi: float) -> float:
    return round(random.uniform(lo, hi), 2)


def _rps_outcome(user_choice: str) -> tuple[str, str]:
    bot_choice = random.choice(list(RPS_CHOICES.values()))
    if user_choice == bot_choice:
        return "tie", bot_choice
    if RPS_BEATS[user_choice] == bot_choice:
        return "win", bot_choice
    return "loss", bot_choice


def _wordle_feedback(guess: str, word: str) -> str:
    result: list[str | None] = [None] * WORDLE_WORD_LENGTH
    remaining = list(word)
    for i, ch in enumerate(guess):
        if ch == word[i]:
            result[i] = "\U0001f7e9"
            remaining[i] = None
    for i, ch in enumerate(guess):
        if result[i] is None and ch in remaining:
            result[i] = "\U0001f7e8"
            remaining[remaining.index(ch)] = None
    return "".join("\u2b1b" if cell is None else cell for cell in result)


class RpsView(discord.ui.View):
    def __init__(self, cog: "EarnGamesCog", guild_id: int, user_id: int):
        super().__init__(timeout=60)
        self.cog = cog
        self.guild_id = guild_id
        self.user_id = user_id
        self.answered = False
        self.interaction: discord.Interaction | None = None

    async def _play(self, interaction: discord.Interaction, choice: str):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This isn't your game.", ephemeral=True)
            return
        if self.answered:
            await interaction.response.defer()
            return
        self.answered = True
        self.stop()

        result, bot_choice = _rps_outcome(choice)
        econ = (await self.cog.bot.config_service.get_config(str(self.guild_id))).economyConfig
        amount = {"win": econ.rpsWinCoin, "tie": econ.rpsTieCoin, "loss": econ.rpsLossCoin}[result]
        await self.cog.bot.earn_games_service.increment_plays(self.guild_id, self.user_id, "rps")
        reward = await self.cog.bot.earn_games_service.record_game_result(self.guild_id, self.user_id, amount, "rps", result)
        balance = reward.balance_after

        user_emoji = next(e for e, c in RPS_CHOICES.items() if c == choice)
        bot_emoji = next(e for e, c in RPS_CHOICES.items() if c == bot_choice)
        desc = f"{user_emoji} You  vs  Bot {bot_emoji}\n\n**{RPS_RESULT_LABELS[result]}**\n**+\U0001fa99 {reward.amount:.2f}**\nBalance: **\U0001fa99 {balance:.2f}**"
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(embed=_coins_embed("\u270a Rock-Paper-Scissors", desc), view=self)

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True
        if self.interaction is not None:
            with contextlib.suppress(Exception):
                await self.interaction.edit_original_response(view=self)

    @discord.ui.button(label="Rock", style=discord.ButtonStyle.primary, emoji="\U0001faa8")
    async def rock(self, interaction: discord.Interaction, _button: discord.ui.Button):
        await self._play(interaction, "rock")

    @discord.ui.button(label="Paper", style=discord.ButtonStyle.primary, emoji="\U0001f4c4")
    async def paper(self, interaction: discord.Interaction, _button: discord.ui.Button):
        await self._play(interaction, "paper")

    @discord.ui.button(label="Scissors", style=discord.ButtonStyle.primary, emoji="\u2702\ufe0f")
    async def scissors(self, interaction: discord.Interaction, _button: discord.ui.Button):
        await self._play(interaction, "scissors")


class TriviaView(discord.ui.View):
    def __init__(self, cog: "EarnGamesCog", guild_id: int, user_id: int, question: dict, timeout_seconds: int):
        super().__init__(timeout=timeout_seconds)
        self.cog = cog
        self.guild_id = guild_id
        self.user_id = user_id
        self.question = question
        self.answered = False
        self.interaction: discord.Interaction | None = None

    async def _answer(self, interaction: discord.Interaction, index: int):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This isn't your trivia question.", ephemeral=True)
            return
        if self.answered:
            await interaction.response.defer()
            return
        self.answered = True
        self.stop()
        await self._finalize(index == self.question["answer"], interaction)

    async def _finalize(self, correct: bool, interaction: discord.Interaction | None):
        econ = (await self.cog.bot.config_service.get_config(str(self.guild_id))).economyConfig
        if correct:
            amount = _random_coin(econ.triviaCorrectCoinMin, econ.triviaCorrectCoinMax)
            result = "correct"
        else:
            amount = econ.triviaIncorrectCoin
            result = "timeout" if interaction is None else "incorrect"

        await self.cog.bot.earn_games_service.increment_plays(self.guild_id, self.user_id, "trivia")
        reward = await self.cog.bot.earn_games_service.record_game_result(self.guild_id, self.user_id, amount, "trivia", result)
        balance = reward.balance_after

        answer = self.question["answer"]
        correct_text = self.question["options"][answer]
        if correct:
            desc = f"**Correct!** The answer was **{correct_text}**.\n**+\U0001fa99 {reward.amount:.2f}**\nBalance: **\U0001fa99 {balance:.2f}**"
        elif interaction is None:
            desc = f"\u23f0 **Time's up!** The answer was **{correct_text}**.\n**+\U0001fa99 {reward.amount:.2f}** (participation)\nBalance: **\U0001fa99 {balance:.2f}**"
        else:
            desc = f"**Wrong!** The answer was **{correct_text}**.\n**+\U0001fa99 {reward.amount:.2f}** (participation)\nBalance: **\U0001fa99 {balance:.2f}**"

        for child in self.children:
            child.disabled = True

        if interaction is not None:
            await interaction.response.edit_message(embed=_coins_embed("\U0001f3af Trivia", desc), view=self)
        elif self.interaction is not None:
            with contextlib.suppress(Exception):
                await self.interaction.edit_original_response(embed=_coins_embed("\U0001f3af Trivia", desc), view=self)

    async def on_timeout(self):
        if self.answered:
            return
        self.answered = True
        await self._finalize(False, None)

    @discord.ui.button(label="A", style=discord.ButtonStyle.primary)
    async def option_a(self, interaction: discord.Interaction, _button: discord.ui.Button):
        await self._answer(interaction, 0)

    @discord.ui.button(label="B", style=discord.ButtonStyle.primary)
    async def option_b(self, interaction: discord.Interaction, _button: discord.ui.Button):
        await self._answer(interaction, 1)

    @discord.ui.button(label="C", style=discord.ButtonStyle.primary)
    async def option_c(self, interaction: discord.Interaction, _button: discord.ui.Button):
        await self._answer(interaction, 2)

    @discord.ui.button(label="D", style=discord.ButtonStyle.primary)
    async def option_d(self, interaction: discord.Interaction, _button: discord.ui.Button):
        await self._answer(interaction, 3)


class HangmanModal(discord.ui.Modal, title="Guess a Letter"):
    letter = discord.ui.TextInput(
        label="Letter",
        placeholder="Enter a single letter (a\u2013z)",
        max_length=1,
        min_length=1,
        required=True,
    )

    def __init__(self, view: "HangmanView"):
        super().__init__()
        self.game_view = view

    async def on_submit(self, interaction: discord.Interaction):
        await self.game_view.process_guess(interaction, self.letter.value)


class HangmanView(discord.ui.View):
    def __init__(self, cog: "EarnGamesCog", guild_id: int, user_id: int):
        super().__init__(timeout=900)
        self.cog = cog
        self.guild_id = guild_id
        self.user_id = user_id
        self.finished = False

    @discord.ui.button(label="Guess", style=discord.ButtonStyle.primary, emoji="\U0001f524")
    async def guess_button(self, interaction: discord.Interaction, _button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This isn't your game.", ephemeral=True)
            return
        game = self.cog.hangman_games.get((self.guild_id, self.user_id))
        if not game or self.finished:
            await interaction.response.send_message("This game is over.", ephemeral=True)
            return
        await interaction.response.send_modal(HangmanModal(self))

    async def process_guess(self, interaction: discord.Interaction, letter: str):
        game = self.cog.hangman_games.get((self.guild_id, self.user_id))
        if not game or game.get("rewarded") or self.finished:
            await interaction.response.defer()
            return

        letter = letter.lower().strip()
        if len(letter) != 1 or letter not in string.ascii_lowercase:
            await interaction.response.send_message("Enter a single letter (a\u2013z).", ephemeral=True)
            return
        if letter in game["guessed"]:
            await interaction.response.send_message(f"You already guessed **{letter.upper()}**.", ephemeral=True)
            return

        game["guessed"].add(letter)
        if letter not in game["word"]:
            game["wrong"] += 1

        word = game["word"]
        if all(c in game["guessed"] for c in word):
            game["rewarded"] = True
            self.finished = True
            self.stop()
            for child in self.children:
                child.disabled = True
            econ = (await self.cog.bot.config_service.get_config(str(self.guild_id))).economyConfig
            amount = _random_coin(econ.hangmanWinCoinMin, econ.hangmanWinCoinMax)
            reward = await self.cog.bot.earn_games_service.record_game_result(self.guild_id, self.user_id, amount, "hangman", "win")
            balance = reward.balance_after
            self.cog.hangman_games.pop((self.guild_id, self.user_id), None)
            embed = _coins_embed("\U0001f389 You Won!", f"The word was **{word.upper()}**!\n**+\U0001fa99 {reward.amount:.2f}**\nBalance: **\U0001fa99 {balance:.2f}**")
            with contextlib.suppress(Exception):
                await interaction.response.edit_message(embed=embed, view=self)
            return

        if game["wrong"] >= HANGMAN_MAX_WRONG:
            game["rewarded"] = True
            self.finished = True
            self.stop()
            for child in self.children:
                child.disabled = True
            econ = (await self.cog.bot.config_service.get_config(str(self.guild_id))).economyConfig
            amount = econ.hangmanLossCoin
            reward = await self.cog.bot.earn_games_service.record_game_result(self.guild_id, self.user_id, amount, "hangman", "loss")
            balance = reward.balance_after
            self.cog.hangman_games.pop((self.guild_id, self.user_id), None)
            embed = _coins_embed("\U0001f480 Game Over", f"The word was **{word.upper()}**.\n**+\U0001fa99 {reward.amount:.2f}** (participation)\nBalance: **\U0001fa99 {balance:.2f}**")
            with contextlib.suppress(Exception):
                await interaction.response.edit_message(embed=embed, view=self)
            return

        with contextlib.suppress(Exception):
            await interaction.response.edit_message(embed=self.cog._hangman_embed(game), view=self)

    async def on_timeout(self):
        self.finished = True
        for child in self.children:
            child.disabled = True
        game = self.cog.hangman_games.get((self.guild_id, self.user_id))
        if game and game.get("message"):
            with contextlib.suppress(Exception):
                await game["message"].edit(view=self)


class WordleModal(discord.ui.Modal, title="Guess a Word"):
    word = discord.ui.TextInput(
        label="Word",
        placeholder="Enter a 5-letter word",
        max_length=5,
        min_length=5,
        required=True,
    )

    def __init__(self, view: "WordleView"):
        super().__init__()
        self.game_view = view

    async def on_submit(self, interaction: discord.Interaction):
        await self.game_view.process_guess(interaction, self.word.value)


class WordleView(discord.ui.View):
    def __init__(self, cog: "EarnGamesCog", guild_id: int, user_id: int):
        super().__init__(timeout=900)
        self.cog = cog
        self.guild_id = guild_id
        self.user_id = user_id
        self.finished = False

    @discord.ui.button(label="Guess", style=discord.ButtonStyle.primary, emoji="\U0001f524")
    async def guess_button(self, interaction: discord.Interaction, _button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This isn't your game.", ephemeral=True)
            return
        game = self.cog.wordle_games.get((self.guild_id, self.user_id))
        if not game or self.finished:
            await interaction.response.send_message("This game is over.", ephemeral=True)
            return
        await interaction.response.send_modal(WordleModal(self))

    async def process_guess(self, interaction: discord.Interaction, word: str):
        game = self.cog.wordle_games.get((self.guild_id, self.user_id))
        if not game or game.get("rewarded") or self.finished:
            await interaction.response.defer()
            return

        guess = word.lower().strip()
        if len(guess) != WORDLE_WORD_LENGTH or not guess.isalpha():
            await interaction.response.send_message(f"Guess a {WORDLE_WORD_LENGTH}-letter word.", ephemeral=True)
            return

        game["guesses"].append(guess)
        econ = (await self.cog.bot.config_service.get_config(str(self.guild_id))).economyConfig
        rewards = [float(x) for x in econ.wordleRewardsByGuessCount.split(",")] or [10.0]

        if guess == game["word"]:
            game["rewarded"] = True
            self.finished = True
            self.stop()
            for child in self.children:
                child.disabled = True
            used = len(game["guesses"])
            amount = rewards[used - 1] if used - 1 < len(rewards) - 1 else rewards[-1]
            reward = await self.cog.bot.earn_games_service.record_game_result(self.guild_id, self.user_id, amount, "wordle", f"win_guess_{used}")
            balance = reward.balance_after
            self.cog.wordle_games.pop((self.guild_id, self.user_id), None)
            grid = self.cog._wordle_grid(game)
            embed = _coins_embed("\U0001f389 You Got It!", f"{grid}\n\nSolved in **{used}** guess{'es' if used != 1 else ''}!\n**+\U0001fa99 {reward.amount:.2f}**\nBalance: **\U0001fa99 {balance:.2f}**")
            with contextlib.suppress(Exception):
                await interaction.response.edit_message(embed=embed, view=self)
            return

        if len(game["guesses"]) >= WORDLE_MAX_GUESSES:
            game["rewarded"] = True
            self.finished = True
            self.stop()
            for child in self.children:
                child.disabled = True
            amount = rewards[-1]
            reward = await self.cog.bot.earn_games_service.record_game_result(self.guild_id, self.user_id, amount, "wordle", "fail")
            balance = reward.balance_after
            self.cog.wordle_games.pop((self.guild_id, self.user_id), None)
            grid = self.cog._wordle_grid(game)
            embed = _coins_embed("\u274c Out of Guesses", f"{grid}\n\nThe word was **{game['word'].upper()}**.\n**+\U0001fa99 {reward.amount:.2f}** (participation)\nBalance: **\U0001fa99 {balance:.2f}**")
            with contextlib.suppress(Exception):
                await interaction.response.edit_message(embed=embed, view=self)
            return

        with contextlib.suppress(Exception):
            await interaction.response.edit_message(embed=self.cog._wordle_embed(game), view=self)

    async def on_timeout(self):
        self.finished = True
        for child in self.children:
            child.disabled = True
        game = self.cog.wordle_games.get((self.guild_id, self.user_id))
        if game and game.get("message"):
            with contextlib.suppress(Exception):
                await game["message"].edit(view=self)


class EarnGamesCog(commands.Cog):
    def __init__(self, bot: "BruhBot"):
        self.bot = bot
        self.hangman_games: dict[tuple[int, int], dict] = {}
        self.wordle_games: dict[tuple[int, int], dict] = {}

    async def _mini_games_enabled(self, interaction: discord.Interaction) -> bool:
        config = await self.bot.config_service.get_config(str(interaction.guild.id))
        if not config.economyConfig.miniGamesEnabled:
            await interaction.response.send_message(
                embed=_coins_embed("Mini-Games Disabled", "Play-to-earn games are disabled in this server."),
                ephemeral=True,
            )
            return False
        return True

    # ═══════════════════════════════════════════════════════════════
    # /earn rps
    # ═══════════════════════════════════════════════════════════════
    earn = app_commands.Group(name="earn", description="Play-to-earn mini-games to earn bruh.coins!")

    @earn.command(name="stats", description="View your earn-game wins, streaks, and coins earned.")
    @app_commands.describe(user="User to inspect (defaults to you)")
    @log_command_usage()
    @is_globally_blocked()
    async def earn_stats(self, interaction: discord.Interaction, user: discord.Member | None = None):
        target = user or interaction.user
        profile = await self.bot.economy_service.get_profile(interaction.guild.id, target.id)
        embed = _coins_embed(
            f"🎮 {target.display_name}'s Game Stats",
            f"**Games won:** {profile.get('earn_game_wins', 0):,}\n**Current streak:** {profile.get('earn_game_current_streak', 0):,}\n**Longest streak:** {profile.get('earn_game_longest_streak', 0):,}\n**Game coins earned:** 🪙 {profile.get('earn_game_coins_earned', 0.0):,.2f}",
        )
        embed.set_thumbnail(url=target.display_avatar.url)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @earn.command(name="leaderboard", description="Show the top earn-game players in this server.")
    @app_commands.describe(metric="Leaderboard metric", limit="How many users to show")
    @app_commands.choices(
        metric=[
            app_commands.Choice(name="Most games won", value="wins"),
            app_commands.Choice(name="Most game coins earned", value="coins"),
        ]
    )
    @log_command_usage()
    @is_globally_blocked()
    async def earn_leaderboard(
        self,
        interaction: discord.Interaction,
        metric: str = "wins",
        limit: app_commands.Range[int, 1, 25] = 10,
    ):
        entries = await self.bot.economy_service.get_game_leaderboard(interaction.guild.id, metric, limit)
        if not entries:
            await interaction.response.send_message(
                embed=_coins_embed("🎮 Game Leaderboard", "No completed earn games have been recorded yet."),
            )
            return

        lines = []
        for entry in entries:
            member = interaction.guild.get_member(int(entry["user_id"]))
            name = member.display_name if member else f"User {entry['user_id']}"
            rank = entry["rank"]
            medal = "🥇" if rank == 1 else "🥈" if rank == 2 else "🥉" if rank == 3 else f"`#{rank}`"
            if metric == "coins":
                value = f"🪙 {entry['earn_game_coins_earned']:,.2f} · {entry['earn_game_wins']:,} wins"
            else:
                value = f"{entry['earn_game_wins']:,} wins · {entry['earn_game_current_streak']:,} current streak"
            lines.append(f"{medal} **{name}** — {value}")

        embed = _coins_embed(
            f"🎮 Game Leaderboard — {'Coins Earned' if metric == 'coins' else 'Games Won'}",
            "\n".join(lines),
        )
        top_member = interaction.guild.get_member(int(entries[0]["user_id"]))
        if top_member:
            embed.set_thumbnail(url=top_member.display_avatar.url)
        await interaction.response.send_message(embed=embed)

    @earn.command(name="rps", description="Play rock-paper-scissors against the bot to earn coins!")
    @log_command_usage()
    @is_globally_blocked()
    async def earn_rps(self, interaction: discord.Interaction):
        if not await self._mini_games_enabled(interaction):
            return
        guild_id = interaction.guild.id
        user_id = interaction.user.id
        remaining = await self.bot.earn_games_service.get_remaining_plays(guild_id, user_id, "rps")
        if remaining == 0:
            await interaction.response.send_message(embed=_coins_embed("Daily Limit Reached", "You've reached your daily RPS limit."), ephemeral=True)
            return
        view = RpsView(self, guild_id, user_id)
        await interaction.response.send_message(embed=_coins_embed("\u270a Rock-Paper-Scissors", "Pick your move!"), view=view, ephemeral=True)
        view.interaction = interaction

    # ═══════════════════════════════════════════════════════════════
    # /earn trivia
    # ═══════════════════════════════════════════════════════════════
    @earn.command(name="trivia", description="Answer a daily trivia question to earn coins!")
    @log_command_usage()
    @is_globally_blocked()
    async def earn_trivia(self, interaction: discord.Interaction):
        if not await self._mini_games_enabled(interaction):
            return
        guild_id = interaction.guild.id
        user_id = interaction.user.id
        remaining = await self.bot.earn_games_service.get_remaining_plays(guild_id, user_id, "trivia")
        if remaining == 0:
            await interaction.response.send_message(embed=_coins_embed("Daily Limit Reached", "You've already played today's trivia."), ephemeral=True)
            return
        econ = (await self.bot.config_service.get_config(str(guild_id))).economyConfig
        question = self.bot.earn_games_service.get_random_trivia_question()
        if question is None:
            await interaction.response.send_message(embed=_coins_embed("No Questions Available", "Trivia questions haven't been seeded yet."), ephemeral=True)
            return
        labels = ["A", "B", "C", "D"]
        options_text = "\n".join(f"**{labels[i]}.** {opt}" for i, opt in enumerate(question["options"]))
        embed = _coins_embed(f"\U0001f3af Trivia \u2014 {question['category']}", f"{question['q']}\n\n{options_text}\n\nYou have **{econ.triviaTimeoutSeconds}** seconds!")
        view = TriviaView(self, guild_id, user_id, question, econ.triviaTimeoutSeconds)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        view.interaction = interaction

    # ═══════════════════════════════════════════════════════════════
    # /earn hangman
    # ═══════════════════════════════════════════════════════════════
    hangman = app_commands.Group(name="hangman", description="Play hangman to earn coins!", parent=earn)

    @hangman.command(name="start", description="Start a new hangman game.")
    @log_command_usage()
    @is_globally_blocked()
    async def hangman_start(self, interaction: discord.Interaction):
        if not await self._mini_games_enabled(interaction):
            return
        guild_id = interaction.guild.id
        user_id = interaction.user.id
        key = (guild_id, user_id)

        game = self.hangman_games.get(key)
        if game:
            old_view = game.get("view")
            if old_view:
                old_view.stop()
            view = HangmanView(self, guild_id, user_id)
            await interaction.response.send_message(embed=self._hangman_embed(game), view=view, ephemeral=True)
            game["message"] = await interaction.original_response()
            game["view"] = view
            return

        remaining = await self.bot.earn_games_service.get_remaining_plays(guild_id, user_id, "hangman")
        if remaining == 0:
            await interaction.response.send_message(embed=_coins_embed("Daily Limit Reached", "You've reached your daily hangman limit."), ephemeral=True)
            return

        word = self.bot.earn_games_service.get_random_hangman_word()
        if word is None:
            await interaction.response.send_message(embed=_coins_embed("No Words Available", "Hangman words haven't been seeded yet."), ephemeral=True)
            return
        word = word.lower()
        view = HangmanView(self, guild_id, user_id)
        await interaction.response.send_message(embed=self._hangman_embed({"word": word, "guessed": set(), "wrong": 0}), view=view, ephemeral=True)
        message = await interaction.original_response()
        await self.bot.earn_games_service.increment_plays(guild_id, user_id, "hangman")
        self.hangman_games[key] = {"word": word, "guessed": set(), "wrong": 0, "message": message, "view": view, "rewarded": False}

    async def hangman_guess_autocomplete(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        guild_id = interaction.guild_id
        if guild_id is None:
            return []
        game = self.hangman_games.get((guild_id, interaction.user.id))
        if not game:
            return []
        cur = current.lower().strip()
        remaining = [c for c in string.ascii_lowercase if c not in game["guessed"] and cur in c]
        return [app_commands.Choice(name=c.upper(), value=c) for c in remaining[:25]]

    @hangman.command(name="guess", description="Guess a letter in your hangman game.")
    @app_commands.describe(letter="A single letter (a-z)")
    @app_commands.autocomplete(letter=hangman_guess_autocomplete)
    @log_command_usage()
    @is_globally_blocked()
    async def hangman_guess(self, interaction: discord.Interaction, letter: str):
        if not await self._mini_games_enabled(interaction):
            return
        guild_id = interaction.guild.id
        user_id = interaction.user.id
        key = (guild_id, user_id)
        game = self.hangman_games.get(key)
        if not game:
            await interaction.response.send_message(embed=_coins_embed("No Active Game", "Start a game with `/earn hangman start`."), ephemeral=True)
            return

        letter = letter.lower().strip()
        if len(letter) != 1 or letter not in string.ascii_lowercase:
            await interaction.response.send_message(embed=_coins_embed("Invalid Guess", "Guess a single letter (a-z)."), ephemeral=True)
            return
        if letter in game["guessed"]:
            await interaction.response.send_message(embed=_coins_embed("Already Guessed", f"You already guessed **{letter.upper()}**."), ephemeral=True)
            return
        if game.get("rewarded"):
            await interaction.response.send_message(embed=_coins_embed("Game Over", "This game has already ended."), ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        game["guessed"].add(letter)
        if letter not in game["word"]:
            game["wrong"] += 1

        word = game["word"]
        if all(c in game["guessed"] for c in word):
            game["rewarded"] = True
            old_view = game.get("view")
            if old_view:
                old_view.stop()
            econ = (await self.bot.config_service.get_config(str(guild_id))).economyConfig
            amount = _random_coin(econ.hangmanWinCoinMin, econ.hangmanWinCoinMax)
            reward = await self.bot.earn_games_service.record_game_result(guild_id, user_id, amount, "hangman", "win")
            balance = reward.balance_after
            self.hangman_games.pop(key, None)
            embed = _coins_embed("\U0001f389 You Won!", f"The word was **{word.upper()}**!\n**+\U0001fa99 {reward.amount:.2f}**\nBalance: **\U0001fa99 {balance:.2f}**")
            with contextlib.suppress(Exception):
                await game["message"].edit(embed=embed, view=None)
            with contextlib.suppress(Exception):
                await interaction.delete_original_response()
            return

        if game["wrong"] >= HANGMAN_MAX_WRONG:
            game["rewarded"] = True
            old_view = game.get("view")
            if old_view:
                old_view.stop()
            econ = (await self.bot.config_service.get_config(str(guild_id))).economyConfig
            amount = econ.hangmanLossCoin
            reward = await self.bot.earn_games_service.record_game_result(guild_id, user_id, amount, "hangman", "loss")
            balance = reward.balance_after
            self.hangman_games.pop(key, None)
            embed = _coins_embed("\U0001f480 Game Over", f"The word was **{word.upper()}**.\n**+\U0001fa99 {reward.amount:.2f}** (participation)\nBalance: **\U0001fa99 {balance:.2f}**")
            with contextlib.suppress(Exception):
                await game["message"].edit(embed=embed, view=None)
            with contextlib.suppress(Exception):
                await interaction.delete_original_response()
            return

        old_view = game.get("view")
        if old_view and not old_view.finished:
            old_view.stop()
        new_view = HangmanView(self, guild_id, user_id)
        game["view"] = new_view
        with contextlib.suppress(Exception):
            await game["message"].edit(embed=self._hangman_embed(game), view=new_view)

        with contextlib.suppress(Exception):
            await interaction.delete_original_response()

    def _hangman_embed(self, game: dict) -> discord.Embed:
        word = game["word"]
        display = " ".join(c.upper() if c in game["guessed"] else "\uff3f" for c in word)
        guessed = " ".join(sorted(c.upper() for c in game["guessed"])) or "None"
        lives = HANGMAN_MAX_WRONG - game["wrong"]
        hearts = "\u2764\ufe0f" * lives
        black_hearts = "\U0001f5a4" * game["wrong"]
        desc = f"{display}\n\n**Guessed:** {guessed}\n**Lives left:** {hearts}{black_hearts}"
        return _coins_embed("\U0001f480 Hangman", desc)

    # ═══════════════════════════════════════════════════════════════
    # /earn wordle
    # ═══════════════════════════════════════════════════════════════
    wordle = app_commands.Group(name="wordle", description="Play a daily Wordle to earn coins!", parent=earn)

    @wordle.command(name="start", description="Start a new wordle game.")
    @log_command_usage()
    @is_globally_blocked()
    async def wordle_start(self, interaction: discord.Interaction):
        if not await self._mini_games_enabled(interaction):
            return
        guild_id = interaction.guild.id
        user_id = interaction.user.id
        key = (guild_id, user_id)

        game = self.wordle_games.get(key)
        if game:
            old_view = game.get("view")
            if old_view:
                old_view.stop()
            view = WordleView(self, guild_id, user_id)
            await interaction.response.send_message(embed=self._wordle_embed(game), view=view, ephemeral=True)
            game["message"] = await interaction.original_response()
            game["view"] = view
            return

        remaining = await self.bot.earn_games_service.get_remaining_plays(guild_id, user_id, "wordle")
        if remaining == 0:
            await interaction.response.send_message(embed=_coins_embed("Daily Limit Reached", "You've reached your daily wordle limit."), ephemeral=True)
            return

        word = self.bot.earn_games_service.get_random_wordle_word()
        if word is None:
            await interaction.response.send_message(embed=_coins_embed("No Words Available", "Wordle words haven't been seeded yet."), ephemeral=True)
            return
        word = word.lower()
        view = WordleView(self, guild_id, user_id)
        await interaction.response.send_message(embed=self._wordle_embed({"word": word, "guesses": []}), view=view, ephemeral=True)
        message = await interaction.original_response()
        await self.bot.earn_games_service.increment_plays(guild_id, user_id, "wordle")
        self.wordle_games[key] = {"word": word, "guesses": [], "message": message, "view": view, "rewarded": False}

    @wordle.command(name="guess", description="Guess a 5-letter word.")
    @app_commands.describe(word="Your 5-letter guess")
    @log_command_usage()
    @is_globally_blocked()
    async def wordle_guess(self, interaction: discord.Interaction, word: str):
        if not await self._mini_games_enabled(interaction):
            return
        guild_id = interaction.guild.id
        user_id = interaction.user.id
        key = (guild_id, user_id)
        game = self.wordle_games.get(key)
        if not game:
            await interaction.response.send_message(embed=_coins_embed("No Active Game", "Start a game with `/earn wordle start`."), ephemeral=True)
            return

        guess = word.lower().strip()
        if len(guess) != WORDLE_WORD_LENGTH or not guess.isalpha():
            await interaction.response.send_message(embed=_coins_embed("Invalid Guess", f"Guess a {WORDLE_WORD_LENGTH}-letter word."), ephemeral=True)
            return
        if game.get("rewarded"):
            await interaction.response.send_message(embed=_coins_embed("Game Over", "This game has already ended."), ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        game["guesses"].append(guess)
        econ = (await self.bot.config_service.get_config(str(guild_id))).economyConfig
        rewards = [float(x) for x in econ.wordleRewardsByGuessCount.split(",")] or [10.0]

        if guess == game["word"]:
            game["rewarded"] = True
            old_view = game.get("view")
            if old_view:
                old_view.stop()
            used = len(game["guesses"])
            amount = rewards[used - 1] if used - 1 < len(rewards) - 1 else rewards[-1]
            reward = await self.bot.earn_games_service.record_game_result(guild_id, user_id, amount, "wordle", f"win_guess_{used}")
            balance = reward.balance_after
            self.wordle_games.pop(key, None)
            grid = self._wordle_grid(game)
            embed = _coins_embed("\U0001f389 You Got It!", f"{grid}\n\nSolved in **{used}** guess{'es' if used != 1 else ''}!\n**+\U0001fa99 {reward.amount:.2f}**\nBalance: **\U0001fa99 {balance:.2f}**")
            with contextlib.suppress(Exception):
                await game["message"].edit(embed=embed, view=None)
            with contextlib.suppress(Exception):
                await interaction.delete_original_response()
            return

        if len(game["guesses"]) >= WORDLE_MAX_GUESSES:
            game["rewarded"] = True
            old_view = game.get("view")
            if old_view:
                old_view.stop()
            amount = rewards[-1]
            reward = await self.bot.earn_games_service.record_game_result(guild_id, user_id, amount, "wordle", "fail")
            balance = reward.balance_after
            self.wordle_games.pop(key, None)
            grid = self._wordle_grid(game)
            embed = _coins_embed("\u274c Out of Guesses", f"{grid}\n\nThe word was **{game['word'].upper()}**.\n**+\U0001fa99 {reward.amount:.2f}** (participation)\nBalance: **\U0001fa99 {balance:.2f}**")
            with contextlib.suppress(Exception):
                await game["message"].edit(embed=embed, view=None)
            with contextlib.suppress(Exception):
                await interaction.delete_original_response()
            return

        old_view = game.get("view")
        if old_view and not old_view.finished:
            old_view.stop()
        new_view = WordleView(self, guild_id, user_id)
        game["view"] = new_view
        with contextlib.suppress(Exception):
            await game["message"].edit(embed=self._wordle_embed(game), view=new_view)

        with contextlib.suppress(Exception):
            await interaction.delete_original_response()

    def _wordle_grid(self, game: dict) -> str:
        word = game["word"]
        return "\n".join(f"{g.upper()}  {_wordle_feedback(g, word)}" for g in game["guesses"])

    def _wordle_embed(self, game: dict) -> discord.Embed:
        remaining = WORDLE_MAX_GUESSES - len(game["guesses"])
        grid = ""
        if game["guesses"]:
            grid = self._wordle_grid(game) + "\n\n"
        desc = f"{grid}**{remaining}** guess{'es' if remaining != 1 else ''} left"
        return _coins_embed("\U0001f7e9 Wordle", desc)


async def setup(bot: "BruhBot"):
    await bot.add_cog(EarnGamesCog(bot))
