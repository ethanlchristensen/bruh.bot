# bruh.bot — Play-to-Earn Games Plan

## Overview

Add interactive "mini-games" that let Discord users earn bruh.coins without risking
their existing balance.  These games sit alongside the **gambling** family (coinflip,
dice, slots) — which are high-risk/high-reward — and provide a **safe, time-gated**
coin drip that helps newer or more casual users afford card packs and cosmetics
without needing to grind messages or gamble.

---

## Current State (baseline for balance)

| Source                          | Coin range        | Frequency / limit                               |
| ------------------------------- | ----------------- | ----------------------------------------------- |
| Message                         | 1.00 – 3.00       | Per message (XP cooldown throttled)             |
| Image attachment bonus          | +3.00             | Per image posted                                |
| Reaction                        | +1.00             | Per reaction (with cooldown)                    |
| Bot mention                     | 2.00 – 5.00       | Per mention (cooldown)                          |
| `/economy daily`                | 50.00 – 100.00    | Once per day (resets 06:00 UTC)                 |
| Coinflip (gamble)               | 10 – 10,000 bet   | 10 plays / day default, 2x win                  |
| Dice (gamble)                   | 10 – 5,000 bet    | 10 plays / day default, 1.4x–2.6x win           |
| Slots (gamble)                  | variable bet      | 10 plays / day default, 1.85x–44x win           |

| Sink                            | Cost              |
| ------------------------------- | ----------------- |
| Standard Card Pack (3 cards)    | 200 coins         |
| Premium Card Pack (3, R+)      | 750 coins         |
| Mystery Box                     | 500 coins         |
| Cosmetics shop                  | varies by rarity  |

---

## Philosophy

- **Skill/play-based, not gambling.**  Users don't wager coins — they play.
- **Heavily cooldown-gated.**  Prevents farming/botting and keeps the economy
  tight.
- **Configurable.**  Every limit, reward, and cooldown is a field on
  `EconomyConfig`.
- **Tracked per-user per-day**, using the same pattern as the existing gambling
  daily counters (`coinflip_plays_today`, etc.) in the user profile document.
- **Small rewards.**  A few coins per win so the dopamine loop is there, but
  nobody gets rich from games alone.

---

## Proposed Games

### 1. `/earn hangman` — Hangman

- **Cooldown:** 3 plays per day (configurable)
- **How it works:**
  - Bot picks a random word from a curated list (~200+ words, family-friendly).
  - Displays underscores + already-guessed letters in an embed.
  - User types `/earn hangman guess [letter]` — slash command autocomplete for
    the remaining letters.
  - 6 wrong guesses = game over; full word revealed = win.
- **Reward:**
  - Win: 8–15 coins (random within configured range)
  - Loss: 2 coins (participation, configurable)
- **Tracked field:** `hangman_plays_today`

### 2. `/earn trivia` — Daily Trivia

- **Cooldown:** 1 play per day (configurable)
- **How it works:**
  - Bot pulls a random trivia question from a local JSON pool (~500+ questions,
    4 multiple choice each).
  - Embeds the question with interactive buttons (A, B, C, D).
  - 15-second timer (configurable).
- **Reward:**
  - Correct: 10–25 coins
  - Wrong/timed-out: 3 coins
- **Tracked field:** `trivia_plays_today`
- **Future:** Could use the AI orchestrator to generate fresh questions, but
  JSON pool is simpler/faster for v1.

### 3. `/earn wordle` — Wordle Clone

- **Cooldown:** 1 play per day (configurable)
- **How it works:**
  - Bot picks a 5-letter word from the curated list.
  - User gets 6 guesses via slash commands (`/earn wordle guess [word]`).
  - Embed updates after each guess with colored emoji squares (🟩 exact,
    🟨 wrong position, ⬛ not in word) — mimics the popular format.
  - Game persists across Discord restarts via an in-memory dict
    `{user_id: {word, guesses, ...}}` (acceptable for ephemeral games — if
    the bot restarts, the user loses that round but doesn't lose coins).
- **Reward (by guess count):**
  - Guess 1: 30 coins
  - Guess 2–3: 20 coins
  - Guess 4–6: 10 coins
  - Fail: 3 coins
- **Tracked field:** `wordle_plays_today`

### 4. `/earn rps` — Rock-Paper-Scissors (Play-to-Earn)

- **Cooldown:** 5 plays per day (configurable)
- **How it works:**
  - User picks rock/paper/scissors via buttons.
  - Bot picks randomly.
  - Embed shows both choices + result.
- **Reward:**
  - Win: 5 coins
  - Tie: 2 coins
  - Loss: 1 coin
- **Tracked field:** `rps_plays_today`
- **Why separate from dice/coinflip:** No coin risk, lower reward ceiling.
  The gamification is in the streak, not the stake.

---

## Implementation Blueprint

### A. New `EconomyConfig` fields (in `bot/services/config_service.py`)

```python
# ── Play-to-Earn Games ────────────────────────────────────────────
miniGamesEnabled: bool = True
hangmanMaxPlaysPerDay: int = 3
hangmanWinCoinMin: float = 8.0
hangmanWinCoinMax: float = 15.0
hangmanLossCoin: float = 2.0
triviaMaxPlaysPerDay: int = 1
triviaCorrectCoinMin: float = 10.0
triviaCorrectCoinMax: float = 25.0
triviaIncorrectCoin: float = 3.0
triviaTimeoutSeconds: int = 15
wordleMaxPlaysPerDay: int = 1
wordleRewardsByGuessCount: str = "30,20,20,10,10,10,3"  # comma-separated, last = fail
rpsMaxPlaysPerDay: int = 5
rpsWinCoin: float = 5.0
rpsTieCoin: float = 2.0
rpsLossCoin: float = 1.0
```

### B. New user-profile fields (in `_get_or_create_profile_raw`)

```python
"earn_games_play_date": None,       # YYYY-MM-DD for daily reset
"hangman_plays_today": 0,
"trivia_plays_today": 0,
"wordle_plays_today": 0,
"rps_plays_today": 0,
```

### C. New service: `bot/services/earn_games_service.py`

- `get_remaining_plays(guild_id, user_id, game)` — mirrors
  `get_remaining_gambling_plays`.
- `increment_plays(guild_id, user_id, game)` — mirrors
  `increment_gambling_plays`.
- `grant_game_reward(guild_id, user_id, amount, game, result)` — calls
  `add_coins` + `record_transaction` with `reference_type="earn_game"` and
  `reference_id=[game]`.
- No new MongoDB collection needed — counters live on the existing user profile
  document.

### D. New Cog: `bot/cogs/earn_games_cog.py`

```python
class EarnGamesCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # ephemeral game state (lost on restart, acceptable)
        self.hangman_games: dict[int, dict] = {}  # user_id -> game
        self.wordle_games: dict[int, dict] = {}   # user_id -> game
```

Follows the same patterns as `economy_cog.py`:
- `@log_command_usage()`, `@is_globally_blocked()` decorators.
- Cooldown checks before every play.
- Uses `_coins_embed()` or `embed_service` for consistent UI.
- `discord.ui.View` with buttons for interactive games (trivia, rps).
- Slash commands grouped under `/earn`.

### E. Static data files

| File                                       | Contents                                  |
| ------------------------------------------ | ----------------------------------------- |
| `bot/data/hangman_words.json`              | `["apple", "banana", ...]` (200+ words)   |
| `bot/data/trivia_questions.json`           | `[{q, options[], answer, category}]` (500+) |
| `bot/data/wordle_words.json`               | Same as hangman but 5-letter subset       |

---

## Balance Analysis

### Daily coin ceiling per game (at max plays, all wins)

| Game    | Max plays | Best reward | Max daily haul |
| ------- | --------- | ----------- | --------------- |
| Hangman | 3         | 15.0        | 45.00           |
| Trivia  | 1         | 25.0        | 25.00           |
| Wordle  | 1         | 30.0        | 30.00           |
| RPS     | 5         | 5.0         | 25.00           |
| **Total** |          |             | **125.00**      |

### Time-to-standard-pack comparison

| Method                           | Estimated effort                      |
| -------------------------------- | ------------------------------------- |
| Messages only (avg 2 coins)      | ~100 messages                         |
| Daily claim only                 | ~2-4 days                             |
| **All earn games + daily claim** | **~125-225 coins/day → 1 pack/day**   |
| Gambling (risky)                 | Minutes (if lucky) or bankrupt         |

### Why this balance works

- A dedicated player playing all games perfectly earns **~125 coins/day** from
  games + **50-100 from daily** = **175-225/day** — enough for ~1 standard pack
  or ~1 cheap cosmetic per day.
- A premium pack (750 coins) still takes **3-4 days of dedicated play**.
- Casual players who only do trivia + daily get ~60-125/day — a pack every 2-3 days.
- The cooldowns prevent botting/farming at scale.
- All values are guild-configurable, so admins can tighten or loosen per community.

---

## Recommended Rollout Order

1. **RPS** — simplest to implement, good for validating the pattern (service,
   cog, config, profile fields, daily tracking).
2. **Trivia** — button interactions + timer, validates the View-with-timeout pattern.
3. **Hangman** — slash-command guess loop, validates autocomplete + stateful game.
4. **Wordle** — most complex UI (emoji grid), builds on hangman patterns.

Each game adds ~150-250 lines to the cog and ~20 lines to the service.  All
four games together are roughly a 600-900 line addition total.

---

## Anti-Abuse Protections

1. **Daily per-user caps** — stored server-side in MongoDB, not bypassable.
2. **Existing `spam_coin_penalty` system** — if a user is flagged for spam, the
   penalty field reduces *all* coin earnings proportionally (games, messages, etc.).
3. **`is_globally_blocked()` decorator** — carries forward automatically.
4. **Transaction ledger** — every game reward writes to the existing ledger
   with `reference_type="earn_game"` + `reference_id="hangman|trivia|wordle|rps"`,
   making every coin earned auditable.
5. **No new persistent state** beyond profile counters — if the bot restarts,
   in-flight games are lost but no coins were wagered, so there's no harm.