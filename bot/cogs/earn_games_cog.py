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
    "🪨": "rock",
    "📄": "paper",
    "✂️": "scissors",
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
            result[i] = "🟩"
            remaining[i] = None
    for i, ch in enumerate(guess):
        if result[i] is None and ch in remaining:
            result[i] = "🟨"
            remaining[remaining.index(ch)] = None
    return "".join("⬛" if cell is None else cell for cell in result)


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
        balance = await self.cog.bot.earn_games_service.grant_game_reward(self.guild_id, self.user_id, amount, "rps", result)

        user_emoji = next(e for e, c in RPS_CHOICES.items() if c == choice)
        bot_emoji = next(e for e, c in RPS_CHOICES.items() if c == bot_choice)
        desc = f"{user_emoji} You  vs  Bot {bot_emoji}\n\n**{RPS_RESULT_LABELS[result]}**\n**+🪙 {amount:.2f}**\nBalance: **🪙 {balance:.2f}**"
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(embed=_coins_embed("✊ Rock-Paper-Scissors", desc), view=self)

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True
        if self.interaction is not None:
            try:
                await self.interaction.edit_original_response(view=self)
            except Exception:
                pass

    @discord.ui.button(label="Rock", style=discord.ButtonStyle.primary, emoji="🪨")
    async def rock(self, interaction: discord.Interaction, _button: discord.ui.Button):
        await self._play(interaction, "rock")

    @discord.ui.button(label="Paper", style=discord.ButtonStyle.primary, emoji="📄")
    async def paper(self, interaction: discord.Interaction, _button: discord.ui.Button):
        await self._play(interaction, "paper")

    @discord.ui.button(label="Scissors", style=discord.ButtonStyle.primary, emoji="✂️")
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
        balance = await self.cog.bot.earn_games_service.grant_game_reward(self.guild_id, self.user_id, amount, "trivia", result)

        answer = self.question["answer"]
        correct_text = self.question["options"][answer]
        if correct:
            desc = f"**Correct!** The answer was **{correct_text}**.\n**+🪙 {amount:.2f}**\nBalance: **🪙 {balance:.2f}**"
        elif interaction is None:
            desc = f"⏰ **Time's up!** The answer was **{correct_text}**.\n**+🪙 {amount:.2f}** (participation)\nBalance: **🪙 {balance:.2f}**"
        else:
            desc = f"**Wrong!** The answer was **{correct_text}**.\n**+🪙 {amount:.2f}** (participation)\nBalance: **🪙 {balance:.2f}**"

        for child in self.children:
            child.disabled = True

        if interaction is not None:
            await interaction.response.edit_message(embed=_coins_embed("🎯 Trivia", desc), view=self)
        elif self.interaction is not None:
            try:
                await self.interaction.edit_original_response(embed=_coins_embed("🎯 Trivia", desc), view=self)
            except Exception:
                pass

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


class EarnGamesCog(commands.Cog):
    def __init__(self, bot: "BruhBot"):
        self.bot = bot
        self.hangman_games: dict[int, dict] = {}
        self.wordle_games: dict[int, dict] = {}

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
        await interaction.response.send_message(embed=_coins_embed("✊ Rock-Paper-Scissors", "Pick your move!"), view=view)
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
        embed = _coins_embed(f"🎯 Trivia — {question['category']}", f"{question['q']}\n\n{options_text}\n\nYou have **{econ.triviaTimeoutSeconds}** seconds!")
        view = TriviaView(self, guild_id, user_id, question, econ.triviaTimeoutSeconds)
        await interaction.response.send_message(embed=embed, view=view)
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

        game = self.hangman_games.get(user_id)
        if game:
            await interaction.response.send_message(embed=self._hangman_embed(game), ephemeral=True)
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
        self.hangman_games[user_id] = {"word": word, "guessed": set(), "wrong": 0}
        await self.bot.earn_games_service.increment_plays(guild_id, user_id, "hangman")
        await interaction.response.send_message(embed=self._hangman_embed(self.hangman_games[user_id]))

    async def hangman_guess_autocomplete(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        game = self.hangman_games.get(interaction.user.id)
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
        user_id = interaction.user.id
        game = self.hangman_games.get(user_id)
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

        game["guessed"].add(letter)
        if letter not in game["word"]:
            game["wrong"] += 1

        word = game["word"]
        if all(c in game["guessed"] for c in word):
            econ = (await self.bot.config_service.get_config(str(interaction.guild.id))).economyConfig
            amount = _random_coin(econ.hangmanWinCoinMin, econ.hangmanWinCoinMax)
            balance = await self.bot.earn_games_service.grant_game_reward(interaction.guild.id, user_id, amount, "hangman", "win")
            self.hangman_games.pop(user_id, None)
            await interaction.response.send_message(embed=_coins_embed("🎉 You Won!", f"The word was **{word.upper()}**!\n**+🪙 {amount:.2f}**\nBalance: **🪙 {balance:.2f}**"))
            return

        if game["wrong"] >= HANGMAN_MAX_WRONG:
            econ = (await self.bot.config_service.get_config(str(interaction.guild.id))).economyConfig
            amount = econ.hangmanLossCoin
            balance = await self.bot.earn_games_service.grant_game_reward(interaction.guild.id, user_id, amount, "hangman", "loss")
            self.hangman_games.pop(user_id, None)
            await interaction.response.send_message(embed=_coins_embed("💀 Game Over", f"The word was **{word.upper()}**.\n**+🪙 {amount:.2f}** (participation)\nBalance: **🪙 {balance:.2f}**"))
            return

        await interaction.response.send_message(embed=self._hangman_embed(game))

    def _hangman_embed(self, game: dict) -> discord.Embed:
        word = game["word"]
        display = " ".join(c.upper() if c in game["guessed"] else "＿" for c in word)
        guessed = " ".join(sorted(c.upper() for c in game["guessed"])) or "None"
        lives = HANGMAN_MAX_WRONG - game["wrong"]
        desc = f"{display}\n\n**Guessed:** {guessed}\n**Lives left:** {'❤️' * lives}{'🖤' * game['wrong']}"
        return _coins_embed("💀 Hangman", desc)

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

        game = self.wordle_games.get(user_id)
        if game:
            await interaction.response.send_message(embed=self._wordle_embed(game), ephemeral=True)
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
        self.wordle_games[user_id] = {"word": word, "guesses": []}
        await self.bot.earn_games_service.increment_plays(guild_id, user_id, "wordle")
        await interaction.response.send_message(embed=self._wordle_embed(self.wordle_games[user_id]))

    @wordle.command(name="guess", description="Guess a 5-letter word.")
    @app_commands.describe(word="Your 5-letter guess")
    @log_command_usage()
    @is_globally_blocked()
    async def wordle_guess(self, interaction: discord.Interaction, word: str):
        if not await self._mini_games_enabled(interaction):
            return
        user_id = interaction.user.id
        game = self.wordle_games.get(user_id)
        if not game:
            await interaction.response.send_message(embed=_coins_embed("No Active Game", "Start a game with `/earn wordle start`."), ephemeral=True)
            return

        guess = word.lower().strip()
        if len(guess) != WORDLE_WORD_LENGTH or not guess.isalpha():
            await interaction.response.send_message(embed=_coins_embed("Invalid Guess", f"Guess a {WORDLE_WORD_LENGTH}-letter word."), ephemeral=True)
            return

        game["guesses"].append(guess)
        econ = (await self.bot.config_service.get_config(str(interaction.guild.id))).economyConfig
        rewards = [float(x) for x in econ.wordleRewardsByGuessCount.split(",")] or [10.0]

        if guess == game["word"]:
            used = len(game["guesses"])
            amount = rewards[used - 1] if used - 1 < len(rewards) - 1 else rewards[-1]
            balance = await self.bot.earn_games_service.grant_game_reward(interaction.guild.id, user_id, amount, "wordle", f"win_guess_{used}")
            self.wordle_games.pop(user_id, None)
            grid = self._wordle_grid(game)
            await interaction.response.send_message(embed=_coins_embed("🎉 You Got It!", f"{grid}\n\nSolved in **{used}** guess{'es' if used != 1 else ''}!\n**+🪙 {amount:.2f}**\nBalance: **🪙 {balance:.2f}**"))
            return

        if len(game["guesses"]) >= WORDLE_MAX_GUESSES:
            amount = rewards[-1]
            balance = await self.bot.earn_games_service.grant_game_reward(interaction.guild.id, user_id, amount, "wordle", "fail")
            self.wordle_games.pop(user_id, None)
            grid = self._wordle_grid(game)
            await interaction.response.send_message(embed=_coins_embed("❌ Out of Guesses", f"{grid}\n\nThe word was **{game['word'].upper()}**.\n**+🪙 {amount:.2f}** (participation)\nBalance: **🪙 {balance:.2f}**"))
            return

        await interaction.response.send_message(embed=self._wordle_embed(game))

    def _wordle_grid(self, game: dict) -> str:
        word = game["word"]
        return "\n".join(_wordle_feedback(g, word) for g in game["guesses"])

    def _wordle_embed(self, game: dict) -> discord.Embed:
        remaining = WORDLE_MAX_GUESSES - len(game["guesses"])
        grid = self._wordle_grid(game)
        desc = grid + "\n" if grid else ""
        desc += f"\n**{remaining}** guess{'es' if remaining != 1 else ''} left\n\nUse `/earn wordle guess` with a 5-letter word."
        return _coins_embed("🟩 Wordle", desc)


async def setup(bot: "BruhBot"):
    await bot.add_cog(EarnGamesCog(bot))
