from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bot.bruh_bot import BruhBot

import logging
import random

import discord
from discord import app_commands

from bot.utils.decarators.command_logging import log_command_usage
from bot.utils.decarators.global_block_check import is_globally_blocked

logger = logging.getLogger("bot")

# ── Shop Constants ──────────────────────────────────────────────
MYSTERY_BOX_COST = 500
COINFLIP_MIN = 10
COINFLIP_MAX = 10_000
DICE_MIN = 10
DICE_MAX = 5_000
SLOTS_MIN = 10
SLOTS_MAX = 5_000
GIFT_TAX_THRESHOLD = 1_000
GIFT_TAX_RATE = 0.05

XP_BOOSTER_DURATIONS = {
    "xp_booster_1": (1, 300),
    "xp_booster_6": (6, 1_500),
    "xp_booster_24": (24, 5_000),
}

SLOTS_EMOJIS = ["🍒", "🍋", "🍊", "🍇", "💎", "7️⃣", "🎰"]

MYSTERY_BOX = [
    ("coins", 100, 800, 0.40),
    ("xp", 50, 300, 0.25),
    ("coins_small", 10, 50, 0.20),
    ("jackpot", 1500, 3000, 0.10),
    ("dud", 0, 0, 0.05),
]


# ── Helpers ─────────────────────────────────────────────────────


def _get_bot(interaction: discord.Interaction) -> "BruhBot":
    return interaction.client  # type: ignore


def _coins_embed(title: str, description: str, fields: list = None) -> discord.Embed:
    embed = discord.Embed(title=title, description=description, color=0xFEE75C, timestamp=datetime.now())
    embed.set_footer(text="bruh.bot")
    if fields:
        for n, v, i in fields:
            embed.add_field(name=n, value=v, inline=i)
    return embed


def _balance_field(bot: "BruhBot", guild_id: int, user_id: int) -> str:
    """Return a formatted balance string for the footer."""
    return f"🪙 {bot.economy_service.get_profile(guild_id, user_id)['bruh_coins']:.2f}"


# ── Command Class ───────────────────────────────────────────────


class ShopCommands:
    def __init__(self, tree: app_commands.CommandTree, args=None):
        shop = app_commands.Group(name="shop", description="Buy items and gamble with your bruh.coins!")

        # ── /shop buy ──────────────────────────────────────────
        @shop.command(name="buy", description="Buy an item from the shop.")
        @app_commands.describe(item="The item to buy")
        @app_commands.choices(
            item=[
                app_commands.Choice(name="XP Booster (1h) — 300 coins", value="xp_booster_1"),
                app_commands.Choice(name="XP Booster (6h) — 1,500 coins", value="xp_booster_6"),
                app_commands.Choice(name="XP Booster (24h) — 5,000 coins", value="xp_booster_24"),
                app_commands.Choice(name="Mystery Box — 500 coins", value="mystery_box"),
            ]
        )
        @log_command_usage()
        @is_globally_blocked()
        async def buy(interaction: discord.Interaction, item: str):
            await interaction.response.defer(ephemeral=True)
            bot = _get_bot(interaction)
            guild_id = interaction.guild.id
            user_id = interaction.user.id

            if item == "mystery_box":
                cost = MYSTERY_BOX_COST
                success, _ = await bot.economy_service.deduct_coins(guild_id, user_id, cost)
                if not success:
                    return await interaction.followup.send(embed=_coins_embed("Not Enough Coins", f"You need **{cost}** coins for a Mystery Box."), ephemeral=True)

                # Roll on the loot table
                roll = random.random()
                cumulative = 0.0
                reward = None
                for category, lo, hi, prob in MYSTERY_BOX:
                    cumulative += prob
                    if roll < cumulative:
                        reward = (category, lo, hi)
                        break

                cat, lo, hi = reward
                if cat == "dud":
                    await interaction.followup.send(embed=_coins_embed("🎁 Mystery Box", "The box was empty... better luck next time!"), ephemeral=True)
                elif cat == "xp":
                    amount = random.randint(lo, hi)
                    await bot.economy_service.add_xp(guild_id, user_id, amount)
                    await interaction.followup.send(embed=_coins_embed("🎁 Mystery Box", f"You found **{amount} XP** in the box!"), ephemeral=True)
                else:
                    amount = round(random.uniform(lo, hi), 2)
                    new_balance = await bot.economy_service.add_coins(guild_id, user_id, amount)
                    label = "JACKPOT 🎉" if cat == "jackpot" else "Coins"
                    embed = _coins_embed("🎁 Mystery Box", f"You found **🪙 {amount:.2f}**{' (' + label + ')' if cat == 'jackpot' else ''}!\nNew balance: **🪙 {new_balance:.2f}**")
                    await interaction.followup.send(embed=embed, ephemeral=True)

            elif item.startswith("xp_booster"):
                hours, cost = XP_BOOSTER_DURATIONS[item]
                success, _ = await bot.economy_service.deduct_coins(guild_id, user_id, cost)
                if not success:
                    return await interaction.followup.send(embed=_coins_embed("Not Enough Coins", f"You need **{cost}** coins for an XP Booster."), ephemeral=True)

                await bot.economy_service.activate_booster(guild_id, user_id, hours)
                await interaction.followup.send(embed=_coins_embed(f"⚡ XP Booster ({hours}h)", f"2x XP active for **{hours}** hour{'s' if hours > 1 else ''}! Go chat!"), ephemeral=True)

        # ── /shop status ───────────────────────────────────────
        @shop.command(name="status", description="Check your active boosters and coin balance.")
        @log_command_usage()
        @is_globally_blocked()
        async def status(interaction: discord.Interaction):
            await interaction.response.defer(ephemeral=True)
            bot = _get_bot(interaction)
            profile = await bot.economy_service.get_profile(interaction.guild.id, interaction.user.id)

            booster = profile.get("booster_active_until")
            booster_text = "None active"
            if booster:
                if isinstance(booster, str):
                    booster = datetime.fromisoformat(booster.replace("Z", "+00:00"))
                remaining = booster - datetime.now(UTC)
                if remaining.total_seconds() > 0:
                    hours = int(remaining.total_seconds() // 3600)
                    mins = int((remaining.total_seconds() % 3600) // 60)
                    booster_text = f"⚡ **{hours}h {mins}m** remaining"

            embed = _coins_embed(
                "🏪 Shop Status",
                f"**Balance:** 🪙 {profile['bruh_coins']:.2f}\n**XP Booster:** {booster_text}",
            )
            embed.set_thumbnail(url=interaction.user.display_avatar.url)
            await interaction.followup.send(embed=embed, ephemeral=True)

        tree.add_command(shop)

        # ── /coinflip ──────────────────────────────────────────
        @tree.command(name="coinflip", description="Bet on a coin flip — double or nothing!")
        @app_commands.describe(amount="Amount to bet", choice="Heads or tails")
        @app_commands.choices(
            choice=[
                app_commands.Choice(name="Heads", value="heads"),
                app_commands.Choice(name="Tails", value="tails"),
            ]
        )
        @log_command_usage()
        @is_globally_blocked()
        async def coinflip(interaction: discord.Interaction, amount: int, choice: str):
            await interaction.response.defer(ephemeral=True)
            bot = _get_bot(interaction)
            guild_id = interaction.guild.id
            user_id = interaction.user.id

            if amount < COINFLIP_MIN or amount > COINFLIP_MAX:
                return await interaction.followup.send(embed=_coins_embed("Invalid Bet", f"Bet must be between **{COINFLIP_MIN}** and **{COINFLIP_MAX}** coins."), ephemeral=True)

            success, _ = await bot.economy_service.deduct_coins(guild_id, user_id, amount)
            if not success:
                return await interaction.followup.send(embed=_coins_embed("Not Enough Coins", "You don't have enough coins for that bet."), ephemeral=True)

            result = random.choice(["heads", "tails"])
            won = result == choice
            payout = amount * 2 if won else 0

            if won:
                await bot.economy_service.add_coins(guild_id, user_id, payout)
                profile = await bot.economy_service.get_profile(guild_id, user_id)
                embed = _coins_embed(
                    "🪙 Coin Flip — You Won!",
                    f"The coin landed on **{result.upper()}**!\nYou chose **{choice.upper()}**\n\n**+🪙 {payout:.2f}**\nNew balance: **🪙 {profile['bruh_coins']:.2f}**",
                )
            else:
                embed = _coins_embed(
                    "🪙 Coin Flip — Lost",
                    f"The coin landed on **{result.upper()}**.\nYou chose **{choice.upper()}**\n\nLost **🪙 {amount:.2f}**",
                )

            await interaction.followup.send(embed=embed, ephemeral=True)

        # ── /dice ──────────────────────────────────────────────
        @tree.command(name="dice", description="Roll a die against the bot!")
        @app_commands.describe(bet="Amount to bet")
        @log_command_usage()
        @is_globally_blocked()
        async def dice(interaction: discord.Interaction, bet: int):
            await interaction.response.defer(ephemeral=True)
            bot = _get_bot(interaction)
            guild_id = interaction.guild.id
            user_id = interaction.user.id

            if bet < DICE_MIN or bet > DICE_MAX:
                return await interaction.followup.send(embed=_coins_embed("Invalid Bet", f"Bet must be between **{DICE_MIN}** and **{DICE_MAX}** coins."), ephemeral=True)

            success, _ = await bot.economy_service.deduct_coins(guild_id, user_id, bet)
            if not success:
                return await interaction.followup.send(embed=_coins_embed("Not Enough Coins", "You don't have enough coins for that bet."), ephemeral=True)

            user_roll = random.randint(1, 6)
            bot_roll = random.randint(1, 6)
            diff = user_roll - bot_roll

            if diff >= 3:
                multiplier = 3
                title = "🎲 Dice — Crushing Victory!"
            elif diff >= 1:
                multiplier = 1.5
                title = "🎲 Dice — You Win!"
            elif diff == 0:
                multiplier = 1.0
                title = "🎲 Dice — Tie!"
            else:
                multiplier = 0.0
                title = "🎲 Dice — You Lost"

            payout = round(bet * multiplier, 2)
            if payout > 0:
                await bot.economy_service.add_coins(guild_id, user_id, payout)

            payout_line = f"**+🪙 {payout:.2f}**" if payout > 0 else f"Lost **🪙 {bet:.2f}**"
            embed = _coins_embed(
                title,
                f"**Your roll:** {user_roll}\n**Bot's roll:** {bot_roll}\n\n{payout_line}",
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

        # ── /slots ─────────────────────────────────────────────
        @tree.command(name="slots", description="Play the slot machine!")
        @app_commands.describe(bet="Amount to bet")
        @log_command_usage()
        @is_globally_blocked()
        async def slots(interaction: discord.Interaction, bet: int):
            await interaction.response.defer(ephemeral=True)
            bot = _get_bot(interaction)
            guild_id = interaction.guild.id
            user_id = interaction.user.id

            if bet < SLOTS_MIN or bet > SLOTS_MAX:
                return await interaction.followup.send(embed=_coins_embed("Invalid Bet", f"Bet must be between **{SLOTS_MIN}** and **{SLOTS_MAX}** coins."), ephemeral=True)

            success, _ = await bot.economy_service.deduct_coins(guild_id, user_id, bet)
            if not success:
                return await interaction.followup.send(embed=_coins_embed("Not Enough Coins", "You don't have enough coins for that bet."), ephemeral=True)

            reels = [random.choice(SLOTS_EMOJIS) for _ in range(3)]
            display = " | ".join(reels)

            # Pay table
            unique = len(set(reels))
            jackpot = reels[0] == "💎"
            seven = reels[0] == "7️⃣"
            slot = reels[0] == "🎰"

            if unique == 1:
                if jackpot:
                    multiplier = 50
                    title = "🎰 JACKPOT! 💎💎💎"
                elif seven:
                    multiplier = 25
                    title = "🎰 SEVENS! 7️⃣7️⃣7️⃣"
                elif slot:
                    multiplier = 10
                    title = "🎰 GRAND PRIZE!"
                else:
                    multiplier = 5
                    title = "🎰 Triple Match!"
            elif unique == 2:
                multiplier = 2
                title = "🎰 Pair!"
            else:
                multiplier = 0
                title = "🎰 No Match"

            payout = round(bet * multiplier, 2)
            if payout > 0:
                await bot.economy_service.add_coins(guild_id, user_id, payout)

            payout_line = f"**+🪙 {payout:.2f}**" if payout > 0 else f"Lost **🪙 {bet:.2f}**"
            embed = _coins_embed(title, f"`{display}`\n\n{payout_line}")
            await interaction.followup.send(embed=embed, ephemeral=True)

        # ── /gift ──────────────────────────────────────────────
        @tree.command(name="gift", description="Send bruh.coins to another user.")
        @app_commands.describe(user="The user to send coins to", amount="Amount to send")
        @log_command_usage()
        @is_globally_blocked()
        async def gift(interaction: discord.Interaction, user: discord.User, amount: int):
            await interaction.response.defer(ephemeral=True)
            bot = _get_bot(interaction)
            guild_id = interaction.guild.id
            sender_id = interaction.user.id
            receiver_id = user.id

            if amount < 1:
                return await interaction.followup.send(embed=_coins_embed("Invalid Amount", "Amount must be at least 1 coin."), ephemeral=True)

            if interaction.user.id == user.id:
                return await interaction.followup.send(embed=_coins_embed("Invalid Target", "You can't gift coins to yourself."), ephemeral=True)

            success, _ = await bot.economy_service.deduct_coins(guild_id, sender_id, amount)
            if not success:
                return await interaction.followup.send(embed=_coins_embed("Not Enough Coins", "You don't have enough coins to send that amount."), ephemeral=True)

            # Apply tax on large gifts
            taxed = amount
            if amount > GIFT_TAX_THRESHOLD:
                tax = round(amount * GIFT_TAX_RATE, 2)
                taxed = amount - tax
                # Tax is burned (not sent to anyone)

            await bot.economy_service.add_coins(guild_id, receiver_id, taxed)

            tax_line = f"\n*(Tax: 🪙 {tax:.2f} on gifts over {GIFT_TAX_THRESHOLD})*" if amount > GIFT_TAX_THRESHOLD else ""
            embed = _coins_embed(
                "🎁 Gift Sent!",
                f"Sent **🪙 {taxed:.2f}** to {user.mention}.{tax_line}",
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
