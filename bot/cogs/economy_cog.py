import logging
import random
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from bot.data.cosmetic_catalog import get_all_released, get_cosmetic
from bot.data.models import RARITY_COLORS, RARITY_DISPLAY_EMOJI, CosmeticRarity, CosmeticSlot
from bot.data.trading_card_models import RARITY_DISCORD_COLORS, TradingCardRarity
from bot.data.trading_card_models import RARITY_DISPLAY_EMOJI as TC_EMOJI
from bot.utils.decarators.admin_check import is_admin
from bot.utils.decarators.command_logging import log_command_usage
from bot.utils.decarators.global_block_check import is_globally_blocked

if TYPE_CHECKING:
    from bot.bruh_bot import BruhBot

# ── Gambling constants ───────────────────────────────────────────
SLOTS_EMOJIS = ["🍒", "🍋", "🍊", "🍇", "💎", "7️⃣", "🎰"]
MAX_BATCH_TURNS = 50
MYSTERY_BOX_COST = 500
COINFLIP_MIN = 10
COINFLIP_MAX = 10_000
DICE_MIN = 10
DICE_MAX = 5_000
SLOTS_MIN = 10
SLOTS_MAX = 5_000

XP_BOOSTER_DURATIONS = {
    "xp_booster_1": (1, 300),
    "xp_booster_6": (6, 1_500),
    "xp_booster_24": (24, 5_000),
}

MYSTERY_BOX = [
    ("coins", 100, 800, 0.40),
    ("xp", 50, 300, 0.25),
    ("coins_small", 10, 50, 0.20),
    ("jackpot", 1500, 3000, 0.10),
    ("dud", 0, 0, 0.05),
]

COSMETICS_PER_PAGE = 9
TRADE_EXPIRY_MINUTES = 5


# ── Game core logic ──────────────────────────────────────────────
def _roll_coinflip(choice: str) -> dict:
    result = random.choice(["heads", "tails"])
    return {"won": result == choice, "result": result}


def _roll_dice() -> dict:
    user_roll = random.randint(1, 6)
    bot_roll = random.randint(1, 6)
    diff = user_roll - bot_roll
    if diff >= 3:
        return {"result": "crushing", "multiplier": 2.6, "user_roll": user_roll, "bot_roll": bot_roll}
    elif diff >= 1:
        return {"result": "win", "multiplier": 1.4, "user_roll": user_roll, "bot_roll": bot_roll}
    elif diff == 0:
        return {"result": "tie", "multiplier": 1.0, "user_roll": user_roll, "bot_roll": bot_roll}
    else:
        return {"result": "loss", "multiplier": 0.0, "user_roll": user_roll, "bot_roll": bot_roll}


def _roll_slots() -> dict:
    reels = [random.choice(SLOTS_EMOJIS) for _ in range(3)]
    unique = len(set(reels))
    jackpot = reels[0] == "💎"
    seven = reels[0] == "7️⃣"
    slot = reels[0] == "🎰"
    if unique == 1:
        if jackpot:
            return {"result": "jackpot", "multiplier": 44, "reels": reels}
        elif seven:
            return {"result": "sevens", "multiplier": 22, "reels": reels}
        elif slot:
            return {"result": "grand", "multiplier": 9, "reels": reels}
        else:
            return {"result": "triple", "multiplier": 4, "reels": reels}
    elif unique == 2:
        return {"result": "pair", "multiplier": 1.85, "reels": reels}
    else:
        return {"result": "miss", "multiplier": 0, "reels": reels}


def _coins_embed(title: str, description: str) -> discord.Embed:
    embed = discord.Embed(title=title, description=description, color=0xFEE75C, timestamp=datetime.now(UTC))
    embed.set_footer(text="bruh.bot")
    return embed


# ── Paginated shop views ─────────────────────────────────────────
class CosmeticsShopView(discord.ui.View):
    def __init__(self, items: list, page: int = 0, slot_filter: str | None = None, rarity_filter: str | None = None):
        super().__init__(timeout=120)
        self.items = items
        self.page = page
        self.slot_filter = slot_filter
        self.rarity_filter = rarity_filter
        self.total_pages = max(1, (len(items) - 1) // COSMETICS_PER_PAGE + 1)
        if self.total_pages <= 1:
            self.prev_button.disabled = True
            self.next_button.disabled = True

    @discord.ui.button(label="◀ Previous", style=discord.ButtonStyle.secondary)
    async def prev_button(self, interaction: discord.Interaction, _button: discord.ui.Button):
        self.page = (self.page - 1) % self.total_pages
        await interaction.response.edit_message(embed=self._build_page(), view=self)

    @discord.ui.button(label="Next ▶", style=discord.ButtonStyle.secondary)
    async def next_button(self, interaction: discord.Interaction, _button: discord.ui.Button):
        self.page = (self.page + 1) % self.total_pages
        await interaction.response.edit_message(embed=self._build_page(), view=self)

    def _build_page(self) -> discord.Embed:
        start = self.page * COSMETICS_PER_PAGE
        page_items = self.items[start : start + COSMETICS_PER_PAGE]
        filter_desc = ""
        if self.slot_filter:
            filter_desc = f" (Slot: {self.slot_filter.replace('_', ' ').title()})"
        if self.rarity_filter:
            filter_desc = f" (Rarity: {self.rarity_filter.title()})"
        lines = []
        for cosmetic in page_items:
            emoji = RARITY_DISPLAY_EMOJI.get(cosmetic.rarity, "")
            lines.append(f"{emoji} **{cosmetic.name}** — 🪙 {cosmetic.price:,.2f}\n　`{cosmetic.id}` · {cosmetic.slot.value.replace('_', ' ').title()}")
        embed = _coins_embed(f"Cosmetics Shop{filter_desc}", "\n".join(lines) if lines else "No cosmetics found.")
        embed.add_field(name="Page", value=f"{self.page + 1}/{self.total_pages}", inline=True)
        embed.add_field(name="Total", value=str(len(self.items)), inline=True)
        embed.add_field(name="Preview & Buy", value="Use `/character preview <id>` to preview\nUse `/cosmetics buy <id>` to purchase", inline=False)
        return embed


class TradeConfirmView(discord.ui.View):
    def __init__(self, trade_id: str, initiator_id: int, recipient_id: int):
        super().__init__(timeout=TRADE_EXPIRY_MINUTES * 60)
        self.trade_id = trade_id
        self.initiator_id = initiator_id
        self.recipient_id = recipient_id
        self.accepted = False

    @discord.ui.button(label="Accept Trade", style=discord.ButtonStyle.success, emoji="✅")
    async def accept_button(self, interaction: discord.Interaction, _button: discord.ui.Button):
        if interaction.user.id != self.recipient_id:
            await interaction.response.send_message("Only the recipient can accept this trade.", ephemeral=True)
            return
        self.accepted = True
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(view=self)
        self.stop()

    @discord.ui.button(label="Decline", style=discord.ButtonStyle.danger, emoji="❌")
    async def decline_button(self, interaction: discord.Interaction, _button: discord.ui.Button):
        if interaction.user.id not in (self.initiator_id, self.recipient_id):
            await interaction.response.send_message("Only participants can decline.", ephemeral=True)
            return
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(view=self)
        self.stop()

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True


async def card_id_autocomplete(interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
    bot = interaction.client
    cards = bot.trading_card_catalog_service.get_all_released_cards()
    cur = current.lower().strip()

    matches = []
    for card in cards:
        if not cur:
            matches.append(card)
        elif cur in card.name.lower():
            matches.append(card)
        elif cur in card.card_id.lower():
            matches.append(card)
        elif cur in card.rarity.value:
            matches.append(card)

    # Sort: exact name starts first, then shorter names, then by number
    matches.sort(
        key=lambda c: (
            0 if cur and c.name.lower().startswith(cur) else 1,
            len(c.name),
            c.number,
        )
    )

    return [
        app_commands.Choice(
            name=f"#{card.number} {card.name} ({card.rarity.value.title()})",
            value=card.card_id,
        )
        for card in matches[:25]
    ]


async def pack_id_autocomplete(interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
    bot = interaction.client
    cur = current.lower()
    return [app_commands.Choice(name=f"{pk.name} — 🪙 {pk.price:,}", value=pk.pack_id) for pk in bot.trading_card_catalog_service.get_all_packs().values() if cur in pk.name.lower() or cur in pk.pack_id.lower()][:25]


async def set_id_autocomplete(interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
    bot = interaction.client
    cur = current.lower()
    series = bot.trading_card_catalog_service.get_series_list()
    return [app_commands.Choice(name=sid.replace("_", " ").title(), value=sid) for sid in sorted(series) if cur in sid.lower()][:25]


async def is_bruh_cards_enabled(bot, guild_id: int) -> bool:
    config = await bot.config_service.get_config(str(guild_id))
    return config.economyConfig.bruhCardsEnabled


class EconomyCog(commands.Cog):
    def __init__(self, bot: "BruhBot"):
        self.bot = bot
        self.logger = logging.getLogger(__name__)

    def _format_xp_progress(self, xp: int, level: int) -> str:
        from bot.services.mongo_economy_service import MongoEconomyService

        # XP is stored cumulatively, while _xp_for_next_level returns the cost of one level.
        xp_for_current = sum(MongoEconomyService._xp_for_next_level(current_level) for current_level in range(level))
        xp_for_next = xp_for_current + MongoEconomyService._xp_for_next_level(level)
        xp_in_level = xp - xp_for_current
        xp_needed = xp_for_next - xp_for_current
        bar_length = 10
        filled = min(max(int((xp_in_level / xp_needed) * bar_length), 0), bar_length) if xp_needed > 0 else bar_length
        empty = bar_length - filled
        bar = "█" * filled + "░" * empty
        return f"`{bar}` {xp_in_level}/{xp_needed} XP"

    # ── Root /economy group ─────────────────────────────────────
    economy = app_commands.Group(name="economy", description="bruh.bot economy — ranks, coins, gambling, cosmetics, cards, and more!")

    # ═══════════════════════════════════════════════════════════════
    # /economy rank
    # ═══════════════════════════════════════════════════════════════
    @economy.command(name="rank", description="View your or another user's level and XP.")
    @app_commands.describe(user="User to check rank for (defaults to you)")
    @log_command_usage()
    @is_globally_blocked()
    async def economy_rank(self, interaction: discord.Interaction, user: discord.Member | None = None):
        target = user or interaction.user
        profile = await self.bot.economy_service.get_profile(interaction.guild.id, target.id)
        rank = await self.bot.economy_service.get_rank(interaction.guild.id, target.id)
        xp_progress = self._format_xp_progress(profile["xp"], profile["level"])
        embed = self.bot.embed_service._create_base_embed(
            title=f"Rank — {target.display_name}",
            description=f"**Level {profile['level']}** (#{rank} on leaderboard)\n{xp_progress}",
        )
        embed.add_field(name="Total XP", value=f"{profile['xp']:,}", inline=True)
        embed.add_field(name="bruh.coins", value=f"🪙 {profile['bruh_coins']:.2f}", inline=True)
        embed.add_field(name="Messages Sent", value=str(profile["total_messages"]), inline=True)
        embed.set_thumbnail(url=target.display_avatar.url)
        await interaction.response.send_message(embed=embed, files=self.bot.embed_service.get_brand_files(embed=embed))

    # ═══════════════════════════════════════════════════════════════
    # /economy leaderboard
    # ═══════════════════════════════════════════════════════════════
    @economy.command(name="leaderboard", description="View the server XP or coin leaderboard.")
    @app_commands.describe(sort_by="Sort by xp, level, or coins")
    @app_commands.choices(
        sort_by=[
            app_commands.Choice(name="XP", value="xp"),
            app_commands.Choice(name="Level", value="level"),
            app_commands.Choice(name="Coins", value="bruh_coins"),
        ]
    )
    @log_command_usage()
    @is_globally_blocked()
    async def economy_leaderboard(self, interaction: discord.Interaction, sort_by: str = "xp"):
        entries = await self.bot.economy_service.get_leaderboard(interaction.guild.id, sort_by=sort_by)
        if not entries:
            return await interaction.response.send_message(
                embed=self.bot.embed_service.create_info_embed(title="Leaderboard", description="No one has earned XP yet. Start chatting!"),
                files=self.bot.embed_service.get_brand_files(),
            )
        sort_labels = {"xp": "XP", "level": "Level", "bruh_coins": "bruh.coins"}
        lines = []
        for entry in entries[:25]:
            member = interaction.guild.get_member(entry["user_id"])
            name = member.display_name if member else f"User {entry['user_id']}"
            rank = entry["rank"]
            lines.append(f"{'🥇' if rank == 1 else '🥈' if rank == 2 else '🥉' if rank == 3 else f'`#{rank}`'} **{name}** — Lv{entry['level']} ({entry['xp']:,} XP) · 🪙 {entry['bruh_coins']:.2f}")
        embed = self.bot.embed_service._create_base_embed(
            title=f"🏆 Leaderboard — {sort_labels.get(sort_by, sort_by)}",
            description="\n".join(lines),
        )
        top_member = interaction.guild.get_member(entries[0]["user_id"])
        if top_member:
            embed.set_thumbnail(url=top_member.display_avatar.url)
        await interaction.response.send_message(embed=embed, files=self.bot.embed_service.get_brand_files(embed=embed))

    # ═══════════════════════════════════════════════════════════════
    # /economy balance
    # ═══════════════════════════════════════════════════════════════
    @economy.command(name="balance", description="Check your bruh.coin balance.")
    @log_command_usage()
    @is_globally_blocked()
    async def economy_balance(self, interaction: discord.Interaction):
        profile = await self.bot.economy_service.get_profile(interaction.guild.id, interaction.user.id)
        embed = self.bot.embed_service._create_base_embed(
            title="💳 Balance",
            description=f"You have **🪙 {profile['bruh_coins']:.2f}** bruh.coins",
        )
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        await interaction.response.send_message(embed=embed, files=self.bot.embed_service.get_brand_files(embed=embed))

    # ═══════════════════════════════════════════════════════════════
    # /economy daily
    # ═══════════════════════════════════════════════════════════════
    @economy.command(name="daily", description="Claim your daily bruh.coin reward.")
    @log_command_usage()
    @is_globally_blocked()
    async def economy_daily(self, interaction: discord.Interaction):
        success, amount, cooldown_msg, next_reset = await self.bot.economy_service.claim_daily(interaction.guild.id, interaction.user.id)
        if success:
            reset_text = f"\nNext daily available <t:{int(next_reset.timestamp())}:R>." if next_reset else ""
            embed = self.bot.embed_service.create_success_embed(
                f"You claimed **🪙 {amount:.2f}** bruh.coins!{reset_text}",
                title="Daily Reward Claimed!",
            )
        else:
            embed = self.bot.embed_service.create_error_embed(cooldown_msg)
        await interaction.response.send_message(embed=embed, files=self.bot.embed_service.get_brand_files(embed=embed))

    # ═══════════════════════════════════════════════════════════════
    # /economy profile
    # ═══════════════════════════════════════════════════════════════
    @economy.command(name="profile", description="View a full profile card for yourself or another user.")
    @app_commands.describe(user="User to view (defaults to you)")
    @log_command_usage()
    @is_globally_blocked()
    async def economy_profile(self, interaction: discord.Interaction, user: discord.Member | None = None):
        target = user or interaction.user
        profile = await self.bot.economy_service.get_profile(interaction.guild.id, target.id)
        rank = await self.bot.economy_service.get_rank(interaction.guild.id, target.id)
        xp_progress = self._format_xp_progress(profile["xp"], profile["level"])
        joined_at = target.joined_at
        joined_str = f"<t:{int(joined_at.timestamp())}:R>" if joined_at else "Unknown"
        embed = self.bot.embed_service._create_base_embed(
            title=f"👤 {target.display_name}'s Profile",
            description=xp_progress,
        )
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.add_field(name="Level", value=str(profile["level"]), inline=True)
        embed.add_field(name="Rank", value=f"#{rank}", inline=True)
        embed.add_field(name="Total XP", value=f"{profile['xp']:,}", inline=True)
        embed.add_field(name="bruh.coins", value=f"🪙 {profile['bruh_coins']:.2f}", inline=True)
        embed.add_field(name="Messages", value=str(profile["total_messages"]), inline=True)
        embed.add_field(name="Images Sent", value=str(profile["total_images"]), inline=True)
        embed.add_field(name="Reactions Given", value=str(profile["total_reactions_given"]), inline=True)
        embed.add_field(name="Bot Mentions", value=str(profile["total_bot_mentions"]), inline=True)
        embed.add_field(name="Joined Server", value=joined_str, inline=False)
        await interaction.response.send_message(embed=embed, files=self.bot.embed_service.get_brand_files(embed=embed))

    # ═══════════════════════════════════════════════════════════════
    # /economy gift
    # ═══════════════════════════════════════════════════════════════
    @economy.command(name="gift", description="Send bruh.coins to another user.")
    @app_commands.describe(user="The user to send coins to", amount="Amount to send")
    @log_command_usage()
    @is_globally_blocked()
    async def economy_gift(self, interaction: discord.Interaction, user: discord.User, amount: int):
        await interaction.response.defer(ephemeral=True)
        guild_id = interaction.guild.id
        sender_id = interaction.user.id
        if amount < 1:
            return await interaction.followup.send(embed=_coins_embed("Invalid Amount", "Amount must be at least 1 coin."), ephemeral=True)
        if interaction.user.id == user.id:
            return await interaction.followup.send(embed=_coins_embed("Invalid Target", "You can't gift coins to yourself."), ephemeral=True)
        settlement = await self.bot.economy_service.settle_purchase(guild_id, sender_id, amount, "gift", reference_type="gift", reference_id=str(user.id))
        if not settlement["success"]:
            return await interaction.followup.send(embed=_coins_embed("Not Enough Coins", "You don't have enough coins to send that amount."), ephemeral=True)

        await self.bot.economy_service.add_coins(guild_id, user.id, settlement["net_amount"])
        tax_line = f"\n*(Tax: 🪙 {settlement['tax_amount']:.2f})*" if settlement["tax_amount"] > 0 else ""
        await interaction.followup.send(embed=_coins_embed("🎁 Gift Sent!", f"Sent **🪙 {settlement['net_amount']:.2f}** to {user.mention}.{tax_line}"), ephemeral=True)

    # ═══════════════════════════════════════════════════════════════
    # /shop  (subgroup)
    # ═══════════════════════════════════════════════════════════════
    shop_group = app_commands.Group(name="shop", description="Buy items and gamble with your bruh.coins!")

    @shop_group.command(name="buy", description="Buy an item from the shop.")
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
    async def shop_buy(self, interaction: discord.Interaction, item: str):
        await interaction.response.defer(ephemeral=True)
        guild_id = interaction.guild.id
        user_id = interaction.user.id
        if item == "mystery_box":
            cost = MYSTERY_BOX_COST
            settlement = await self.bot.economy_service.settle_purchase(guild_id, user_id, cost, "shop_mystery_box", reference_type="shop", reference_id="mystery_box")
            if not settlement["success"]:
                return await interaction.followup.send(embed=_coins_embed("Not Enough Coins", f"You need **{cost}** coins for a Mystery Box."), ephemeral=True)
            tax_line = f" *(Tax: 🪙 {settlement['tax_amount']:.2f})*" if settlement["tax_amount"] > 0 else ""
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
                await self.bot.economy_service.add_xp(guild_id, user_id, amount)
                await interaction.followup.send(embed=_coins_embed("🎁 Mystery Box", f"You found **{amount} XP** in the box!"), ephemeral=True)
            else:
                amount = round(random.uniform(lo, hi), 2)
                new_balance = await self.bot.economy_service.add_coins(guild_id, user_id, amount)
                label = "JACKPOT 🎉" if cat == "jackpot" else "Coins"
                await interaction.followup.send(embed=_coins_embed("🎁 Mystery Box", f"You found **🪙 {amount:.2f}**{' (' + label + ')' if cat == 'jackpot' else ''}!\nNew balance: **🪙 {new_balance:.2f}**"), ephemeral=True)
        elif item.startswith("xp_booster"):
            hours, cost = XP_BOOSTER_DURATIONS[item]
            settlement = await self.bot.economy_service.settle_purchase(guild_id, user_id, cost, "shop_xp_booster", reference_type="shop", reference_id=item)
            if not settlement["success"]:
                return await interaction.followup.send(embed=_coins_embed("Not Enough Coins", f"You need **{cost}** coins for an XP Booster."), ephemeral=True)
            tax_line = f" *(Tax: 🪙 {settlement['tax_amount']:.2f})*" if settlement["tax_amount"] > 0 else ""
            await self.bot.economy_service.activate_booster(guild_id, user_id, hours)
            await interaction.followup.send(embed=_coins_embed(f"⚡ XP Booster ({hours}h)", f"2x XP active for **{hours}** hour{'s' if hours > 1 else ''}! Go chat!{tax_line}"), ephemeral=True)

    @shop_group.command(name="status", description="Check your active boosters and coin balance.")
    @log_command_usage()
    @is_globally_blocked()
    async def shop_status(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        profile = await self.bot.economy_service.get_profile(interaction.guild.id, interaction.user.id)
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
        embed = _coins_embed("🏪 Shop Status", f"**Balance:** 🪙 {profile['bruh_coins']:.2f}\n**XP Booster:** {booster_text}")
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        await interaction.followup.send(embed=embed, ephemeral=True)

    # ═══════════════════════════════════════════════════════════════
    # /gamble  (subgroup)
    # ═══════════════════════════════════════════════════════════════
    gamble_group = app_commands.Group(name="gamble", description="Gamble your bruh.coins! Coinflip, dice, and slots.")

    @gamble_group.command(name="coinflip", description="Bet on a coin flip — double or nothing!")
    @app_commands.describe(amount="Amount to bet", choice="Heads or tails", turns=f"Number of turns to play (1-{MAX_BATCH_TURNS})")
    @app_commands.choices(choice=[app_commands.Choice(name="Heads", value="heads"), app_commands.Choice(name="Tails", value="tails")])
    @log_command_usage()
    @is_globally_blocked()
    async def gamble_coinflip(self, interaction: discord.Interaction, amount: int, choice: str, turns: int = 1):
        await interaction.response.defer()
        guild_id = interaction.guild.id
        user_id = interaction.user.id
        if amount < COINFLIP_MIN or amount > COINFLIP_MAX:
            return await interaction.followup.send(embed=_coins_embed("Invalid Bet", f"Bet must be between **{COINFLIP_MIN}** and **{COINFLIP_MAX}** coins."))
        config = await self.bot.config_service.get_config(str(guild_id))
        is_admin_user = str(user_id) in config.adminIds
        if not is_admin_user:
            remaining = await self.bot.economy_service.get_remaining_gambling_plays(guild_id, user_id, "coinflip")
            if remaining == 0:
                return await interaction.followup.send(embed=_coins_embed("Daily Limit Reached", "You've reached your daily coinflip limit."))
            actual_turns = turns if remaining < 0 else min(turns, remaining)
        else:
            actual_turns = turns
        if actual_turns == 1:
            settlement = await self.bot.economy_service.settle_purchase(guild_id, user_id, amount, "gambling_coinflip", reference_type="gambling", reference_id="coinflip")
            if not settlement["success"]:
                return await interaction.followup.send(embed=_coins_embed("Not Enough Coins", "You don't have enough coins for that bet."))
            if not is_admin_user:
                await self.bot.economy_service.increment_gambling_plays(guild_id, user_id, "coinflip")
            result = _roll_coinflip(choice)
            payout = amount * 2 if result["won"] else 0
            if result["won"]:
                await self.bot.economy_service.add_coins(guild_id, user_id, payout)
            profile = await self.bot.economy_service.get_profile(guild_id, user_id)
            tax_line = f"\n*(Tax: 🪙 {settlement['tax_amount']:.2f})*" if settlement["tax_amount"] > 0 else ""
            embed = _coins_embed(
                f"🪙 Coin Flip — {'You Won!' if result['won'] else 'Lost'}",
                f"Coin landed **{result['result'].upper()}** · You chose **{choice.upper()}**\n{interaction.user.mention}\n\n{'**+🪙 ' + f'{payout:.2f}' + '**' if result['won'] else 'Lost **🪙 ' + f'{amount:.2f}' + '**'}\nBalance: **🪙 {profile['bruh_coins']:.2f}**{tax_line}",
            )
            await interaction.followup.send(embed=embed)
        else:
            wins = 0
            losses = 0
            total_wagered = 0
            total_won = 0
            total_tax = 0.0
            stopped_early = False
            for _ in range(actual_turns):
                settlement = await self.bot.economy_service.settle_purchase(guild_id, user_id, amount, "gambling_coinflip", reference_type="gambling", reference_id="coinflip")
                if not settlement["success"]:
                    stopped_early = True
                    break
                if not is_admin_user:
                    await self.bot.economy_service.increment_gambling_plays(guild_id, user_id, "coinflip")
                total_wagered += amount
                total_tax += settlement["tax_amount"]
                result = _roll_coinflip(choice)
                if result["won"]:
                    wins += 1
                    total_won += amount * 2
                    await self.bot.economy_service.add_coins(guild_id, user_id, amount * 2)
                else:
                    losses += 1
            turns_played = wins + losses
            profile = await self.bot.economy_service.get_profile(guild_id, user_id)
            net = total_won - total_wagered
            title = f"🪙 Batch Coinflip — {choice.upper()} | {turns_played}/{actual_turns} turns {'(stopped: out of coins)' if stopped_early else ''} @ 🪙 {amount}/turn"
            desc = f"Wins: **{wins}** · Losses: **{losses}**\nWagered 🪙 {total_wagered:,.2f} · Won 🪙 {total_won:,.2f}\n━━━━━━━━━━━━━━━━━━━━━\nNet {'+' if net >= 0 else ''}🪙 {net:,.2f}  |  Balance 🪙 {profile['bruh_coins']:.2f}"
            if total_tax > 0:
                desc += f"\n*(Tax: 🪙 {total_tax:.2f})*"
            await interaction.followup.send(embed=_coins_embed(title, desc))

    @gamble_group.command(name="dice", description="Roll a die against the bot!")
    @app_commands.describe(bet="Amount to bet", turns=f"Number of turns to play (1-{MAX_BATCH_TURNS})")
    @log_command_usage()
    @is_globally_blocked()
    async def gamble_dice(self, interaction: discord.Interaction, bet: int, turns: int = 1):
        await interaction.response.defer()
        guild_id = interaction.guild.id
        user_id = interaction.user.id
        if bet < DICE_MIN or bet > DICE_MAX:
            return await interaction.followup.send(embed=_coins_embed("Invalid Bet", f"Bet must be between **{DICE_MIN}** and **{DICE_MAX}** coins."))
        config = await self.bot.config_service.get_config(str(guild_id))
        is_admin_user = str(user_id) in config.adminIds
        if not is_admin_user:
            remaining = await self.bot.economy_service.get_remaining_gambling_plays(guild_id, user_id, "dice")
            if remaining == 0:
                return await interaction.followup.send(embed=_coins_embed("Daily Limit Reached", "You've reached your daily dice limit."))
            actual_turns = turns if remaining < 0 else min(turns, remaining)
        else:
            actual_turns = turns
        if actual_turns == 1:
            settlement = await self.bot.economy_service.settle_purchase(guild_id, user_id, bet, "gambling_dice", reference_type="gambling", reference_id="dice")
            if not settlement["success"]:
                return await interaction.followup.send(embed=_coins_embed("Not Enough Coins", "You don't have enough coins for that bet."))
            if not is_admin_user:
                await self.bot.economy_service.increment_gambling_plays(guild_id, user_id, "dice")
            result = _roll_dice()
            payout = round(bet * result["multiplier"], 2)
            if payout > 0:
                await self.bot.economy_service.add_coins(guild_id, user_id, payout)
            profile = await self.bot.economy_service.get_profile(guild_id, user_id)
            titles = {"crushing": "🎲 Crushing Victory!", "win": "🎲 You Win!", "tie": "🎲 Tie!", "loss": "🎲 You Lost"}
            payout_line = f"**+🪙 {payout:.2f}**" if payout > 0 else f"Lost **🪙 {bet:.2f}**"
            tax_line = f"\n*(Tax: 🪙 {settlement['tax_amount']:.2f})*" if settlement["tax_amount"] > 0 else ""
            await interaction.followup.send(embed=_coins_embed(titles[result["result"]], f"{interaction.user.mention}\n**Your roll:** {result['user_roll']}\n**Bot's roll:** {result['bot_roll']}\n\n{payout_line}\nBalance: **🪙 {profile['bruh_coins']:.2f}**{tax_line}"))
        else:
            crushing = 0
            wins = 0
            ties = 0
            losses = 0
            total_wagered = 0
            total_won = 0
            total_tax = 0.0
            stopped_early = False
            for _ in range(actual_turns):
                settlement = await self.bot.economy_service.settle_purchase(guild_id, user_id, bet, "gambling_dice", reference_type="gambling", reference_id="dice")
                if not settlement["success"]:
                    stopped_early = True
                    break
                if not is_admin_user:
                    await self.bot.economy_service.increment_gambling_plays(guild_id, user_id, "dice")
                total_wagered += bet
                total_tax += settlement["tax_amount"]
                result = _roll_dice()
                payout = round(bet * result["multiplier"], 2)
                if payout > 0:
                    total_won += payout
                    await self.bot.economy_service.add_coins(guild_id, user_id, payout)
                if result["result"] == "crushing":
                    crushing += 1
                elif result["result"] == "win":
                    wins += 1
                elif result["result"] == "tie":
                    ties += 1
                else:
                    losses += 1
            turns_played = crushing + wins + ties + losses
            profile = await self.bot.economy_service.get_profile(guild_id, user_id)
            net = total_won - total_wagered
            title = f"🎲 Batch Dice — {turns_played}/{actual_turns} turns {'(stopped: out of coins)' if stopped_early else ''} @ 🪙 {bet}/turn"
            desc = f"Crushing: **{crushing}** · Wins: **{wins}** · Ties: **{ties}** · Losses: **{losses}**\nWagered 🪙 {total_wagered:,.2f} · Won 🪙 {total_won:,.2f}\n━━━━━━━━━━━━━━━━━━━━━\nNet {'+' if net >= 0 else ''}🪙 {net:,.2f}  |  Balance 🪙 {profile['bruh_coins']:.2f}"
            if total_tax > 0:
                desc += f"\n*(Tax: 🪙 {total_tax:.2f})*"
            await interaction.followup.send(embed=_coins_embed(title, desc))

    @gamble_group.command(name="slots", description="Play the slot machine!")
    @app_commands.describe(bet="Amount to bet", turns=f"Number of turns to play (1-{MAX_BATCH_TURNS})")
    @log_command_usage()
    @is_globally_blocked()
    async def gamble_slots(self, interaction: discord.Interaction, bet: int, turns: int = 1):
        await interaction.response.defer()
        guild_id = interaction.guild.id
        user_id = interaction.user.id
        if bet < SLOTS_MIN or bet > SLOTS_MAX:
            return await interaction.followup.send(embed=_coins_embed("Invalid Bet", f"Bet must be between **{SLOTS_MIN}** and **{SLOTS_MAX}** coins."))
        config = await self.bot.config_service.get_config(str(guild_id))
        is_admin_user = str(user_id) in config.adminIds
        if not is_admin_user:
            remaining = await self.bot.economy_service.get_remaining_gambling_plays(guild_id, user_id, "slots")
            if remaining == 0:
                return await interaction.followup.send(embed=_coins_embed("Daily Limit Reached", "You've reached your daily slots limit."))
            actual_turns = turns if remaining < 0 else min(turns, remaining)
        else:
            actual_turns = turns
        result_titles = {"jackpot": "💎💎💎 JACKPOT! 💎💎💎", "sevens": "7️⃣7️⃣7️⃣ SEVENS! 7️⃣7️⃣7️⃣", "grand": "🎰🎰🎰 GRAND PRIZE! 🎰🎰🎰", "triple": "🎰 Triple Match!", "pair": "🎰 Pair!", "miss": "🎰 No Match"}
        if actual_turns == 1:
            settlement = await self.bot.economy_service.settle_purchase(guild_id, user_id, bet, "gambling_slots", reference_type="gambling", reference_id="slots")
            if not settlement["success"]:
                return await interaction.followup.send(embed=_coins_embed("Not Enough Coins", "You don't have enough coins for that bet."))
            if not is_admin_user:
                await self.bot.economy_service.increment_gambling_plays(guild_id, user_id, "slots")
            result = _roll_slots()
            display = " | ".join(result["reels"])
            payout = round(bet * result["multiplier"], 2)
            if payout > 0:
                await self.bot.economy_service.add_coins(guild_id, user_id, payout)
            profile = await self.bot.economy_service.get_profile(guild_id, user_id)
            payout_line = f"**+🪙 {payout:.2f}**" if payout > 0 else f"Lost **🪙 {bet:.2f}**"
            tax_line = f"\n*(Tax: 🪙 {settlement['tax_amount']:.2f})*" if settlement["tax_amount"] > 0 else ""
            await interaction.followup.send(embed=_coins_embed(result_titles[result["result"]], f"{interaction.user.mention}\n`{display}`\n\n{payout_line}\nBalance: **🪙 {profile['bruh_coins']:.2f}**{tax_line}"))
        else:
            stats = {"jackpot": 0, "sevens": 0, "grand": 0, "triple": 0, "pair": 0, "miss": 0}
            total_wagered = 0
            total_won = 0
            total_tax = 0.0
            stopped_early = False
            for _ in range(actual_turns):
                settlement = await self.bot.economy_service.settle_purchase(guild_id, user_id, bet, "gambling_slots", reference_type="gambling", reference_id="slots")
                if not settlement["success"]:
                    stopped_early = True
                    break
                if not is_admin_user:
                    await self.bot.economy_service.increment_gambling_plays(guild_id, user_id, "slots")
                total_wagered += bet
                total_tax += settlement["tax_amount"]
                result = _roll_slots()
                stats[result["result"]] += 1
                payout = round(bet * result["multiplier"], 2)
                if payout > 0:
                    total_won += payout
                    await self.bot.economy_service.add_coins(guild_id, user_id, payout)
            turns_played = sum(stats.values())
            profile = await self.bot.economy_service.get_profile(guild_id, user_id)
            net = total_won - total_wagered
            title = f"🎰 Batch Slots — {turns_played}/{actual_turns} turns {'(stopped: out of coins)' if stopped_early else ''} @ 🪙 {bet}/turn"
            desc = (
                f"💎 Jackpot: **{stats['jackpot']}** · 7️⃣ Sevens: **{stats['sevens']}** · 🎰 Grand: **{stats['grand']}** · "
                f"Triple: **{stats['triple']}** · Pair: **{stats['pair']}** · Miss: **{stats['miss']}**\n"
                f"Wagered 🪙 {total_wagered:,.2f} · Won 🪙 {total_won:,.2f}\n"
                "━━━━━━━━━━━━━━━━━━━━━\n"
                f"Net {'+' if net >= 0 else ''}🪙 {net:,.2f}  |  Balance 🪙 {profile['bruh_coins']:.2f}"
            )
            if total_tax > 0:
                desc += f"\n*(Tax: 🪙 {total_tax:.2f})*"
            await interaction.followup.send(embed=_coins_embed(title, desc))

    # ═══════════════════════════════════════════════════════════════
    # /character  (subgroup)
    # ═══════════════════════════════════════════════════════════════
    character_group = app_commands.Group(name="character", description="Customize and view your bruh.bot character!")
    wardrobe_group = app_commands.Group(name="wardrobe", description="Manage your owned cosmetics.")

    @character_group.command(name="view", description="View your or another user's character.")
    @app_commands.describe(user="User whose character to view (defaults to you)")
    @log_command_usage()
    @is_globally_blocked()
    async def character_view(self, interaction: discord.Interaction, user: discord.Member | None = None):
        await interaction.response.defer()
        target = user or interaction.user
        equipped = await self.bot.inventory_service.get_equipped(interaction.guild.id, target.id)
        image_buffer = await self.bot.character_render_service.render_character(interaction.guild.id, target.id, equipped)
        equipped_list = []
        for slot in CosmeticSlot:
            item_id = equipped.get(slot.value)
            if item_id:
                cosmetic = get_cosmetic(item_id)
                if cosmetic:
                    equipped_list.append(f"**{slot.value.replace('_', ' ').title()}**: {RARITY_DISPLAY_EMOJI.get(cosmetic.rarity, '')} {cosmetic.name}")
        desc = "No cosmetics equipped." if not equipped_list else "\n".join(equipped_list)
        embed = self.bot.embed_service._create_base_embed(title=f"{target.display_name}'s Character", description=desc)
        embed.set_thumbnail(url=target.display_avatar.url)
        file = discord.File(image_buffer, filename="character.png")
        embed.set_image(url="attachment://character.png")
        await interaction.followup.send(embed=embed, file=file)

    @character_group.command(name="preview", description="Preview a cosmetic on your character before buying.")
    @app_commands.describe(item_id="The cosmetic ID to preview")
    @log_command_usage()
    @is_globally_blocked()
    async def character_preview(self, interaction: discord.Interaction, item_id: str):
        await interaction.response.defer(ephemeral=True)
        cosmetic = get_cosmetic(item_id)
        if not cosmetic:
            embed = self.bot.embed_service.create_error_embed(f"No cosmetic found with ID `{item_id}`.")
            return await interaction.followup.send(embed=embed, ephemeral=True, files=self.bot.embed_service.get_brand_files(embed=embed))
        image_buffer = await self.bot.character_render_service.render_preview(interaction.guild.id, interaction.user.id, item_id)
        if not image_buffer:
            embed = self.bot.embed_service.create_error_embed("Could not generate preview.")
            return await interaction.followup.send(embed=embed, ephemeral=True, files=self.bot.embed_service.get_brand_files(embed=embed))
        embed = discord.Embed(
            title=f"Preview: {RARITY_DISPLAY_EMOJI.get(cosmetic.rarity, '')} {cosmetic.name}",
            description=f"**Slot:** {cosmetic.slot.value.replace('_', ' ').title()}\n**Rarity:** {cosmetic.rarity.value.title()}\n**Price:** 🪙 {cosmetic.price:,.2f}",
            color=RARITY_COLORS.get(cosmetic.rarity, 0x5865F2),
            timestamp=datetime.now(UTC),
        )
        embed.set_footer(text="bruh.bot")
        file = discord.File(image_buffer, filename="preview.png")
        embed.set_image(url="attachment://preview.png")
        await interaction.followup.send(embed=embed, file=file, ephemeral=True)

    @wardrobe_group.command(name="equip", description="Equip a cosmetic you own.")
    @app_commands.describe(item_id="The cosmetic ID to equip")
    @log_command_usage()
    @is_globally_blocked()
    async def wardrobe_equip(self, interaction: discord.Interaction, item_id: str):
        await interaction.response.defer(ephemeral=True)
        success, msg = await self.bot.inventory_service.equip_item(interaction.guild.id, interaction.user.id, item_id)
        if success:
            self.bot.character_render_service.invalidate_cache(interaction.guild.id, interaction.user.id)
            embed = self.bot.embed_service.create_success_embed(msg, title="Equipped!")
        else:
            embed = self.bot.embed_service.create_error_embed(msg)
        await interaction.followup.send(embed=embed, ephemeral=True, files=self.bot.embed_service.get_brand_files(embed=embed))

    @wardrobe_group.command(name="unequip", description="Remove a cosmetic from a slot.")
    @app_commands.describe(slot="The slot to unequip")
    @app_commands.choices(slot=[app_commands.Choice(name=s.value.replace("_", " ").title(), value=s.value) for s in CosmeticSlot])
    @log_command_usage()
    @is_globally_blocked()
    async def wardrobe_unequip(self, interaction: discord.Interaction, slot: str):
        await interaction.response.defer(ephemeral=True)
        try:
            slot_enum = CosmeticSlot(slot)
        except ValueError:
            return await interaction.followup.send(
                embed=self.bot.embed_service.create_error_embed(f"Unknown slot: `{slot}`."),
                ephemeral=True,
                files=self.bot.embed_service.get_brand_files(),
            )
        await self.bot.inventory_service.unequip_slot(interaction.guild.id, interaction.user.id, slot_enum)
        self.bot.character_render_service.invalidate_cache(interaction.guild.id, interaction.user.id)
        embed = self.bot.embed_service.create_success_embed(f"Removed cosmetic from **{slot.replace('_', ' ').title()}** slot.", title="Unequipped")
        await interaction.followup.send(embed=embed, ephemeral=True, files=self.bot.embed_service.get_brand_files(embed=embed))

    @wardrobe_group.command(name="list", description="Browse your owned cosmetics.")
    @app_commands.describe(slot="Filter by slot (optional)", rarity="Filter by rarity (optional)")
    @app_commands.choices(slot=[app_commands.Choice(name=s.value.replace("_", " ").title(), value=s.value) for s in CosmeticSlot])
    @log_command_usage()
    @is_globally_blocked()
    async def wardrobe_list(self, interaction: discord.Interaction, slot: str | None = None, rarity: str | None = None):
        await interaction.response.defer(ephemeral=True)
        inventory = await self.bot.inventory_service.get_inventory(interaction.guild.id, interaction.user.id)
        owned = inventory["items"]
        equipped = inventory["equipped"]
        filtered = []
        for item in owned:
            cosmetic = get_cosmetic(item["item_id"])
            if not cosmetic:
                continue
            if slot and cosmetic.slot.value != slot:
                continue
            if rarity and cosmetic.rarity.value != rarity:
                continue
            filtered.append((cosmetic, item["quantity"]))
        if not filtered:
            embed = self.bot.embed_service.create_info_embed(title="Wardrobe", description="No cosmetics found matching your filters.\nBuy some from `/cosmetics shop`!")
            return await interaction.followup.send(embed=embed, ephemeral=True, files=self.bot.embed_service.get_brand_files(embed=embed))
        lines = []
        for cosmetic, qty in filtered:
            eq = " **[Equipped]**" if equipped.get(cosmetic.slot.value) == cosmetic.id else ""
            lines.append(f"{RARITY_DISPLAY_EMOJI.get(cosmetic.rarity, '')} `{cosmetic.id}` — **{cosmetic.name}** ({cosmetic.slot.value.replace('_', ' ').title()}){' x' + str(qty) if qty > 1 else ''}{eq}")
        embed = self.bot.embed_service._create_base_embed(title="Wardrobe", description="\n".join(lines))
        embed.add_field(name="Total Items", value=str(len(owned)), inline=True)
        embed.add_field(name="Equipped", value=str(sum(1 for v in equipped.values() if v)), inline=True)
        await interaction.followup.send(embed=embed, ephemeral=True)

    # ═══════════════════════════════════════════════════════════════
    # /cosmetics  (subgroup)
    # ═══════════════════════════════════════════════════════════════
    cosmetics_group = app_commands.Group(name="cosmetics", description="Browse and buy character cosmetics!")

    @cosmetics_group.command(name="shop", description="Browse available cosmetics in the shop.")
    @app_commands.describe(slot="Filter by slot (optional)", rarity="Filter by rarity (optional)")
    @app_commands.choices(
        slot=[app_commands.Choice(name=s.value.replace("_", " ").title(), value=s.value) for s in CosmeticSlot],
        rarity=[app_commands.Choice(name=r.value.title(), value=r.value) for r in CosmeticRarity],
    )
    @log_command_usage()
    @is_globally_blocked()
    async def cosmetics_shop(self, interaction: discord.Interaction, slot: str | None = None, rarity: str | None = None):
        await interaction.response.defer(ephemeral=True)
        items = get_all_released()
        if slot:
            items = [i for i in items if i.slot.value == slot]
        if rarity:
            items = [i for i in items if i.rarity.value == rarity]
        items = sorted(items, key=lambda x: (list(CosmeticRarity).index(x.rarity), x.price))
        if not items:
            return await interaction.followup.send(embed=_coins_embed("Shop", "No cosmetics match your filters."), ephemeral=True)
        view = CosmeticsShopView(items, slot_filter=slot, rarity_filter=rarity)
        await interaction.followup.send(embed=view._build_page(), view=view, ephemeral=True)

    @cosmetics_group.command(name="buy", description="Buy a cosmetic from the shop.")
    @app_commands.describe(item_id="The cosmetic ID to buy")
    @log_command_usage()
    @is_globally_blocked()
    async def cosmetics_buy(self, interaction: discord.Interaction, item_id: str):
        await interaction.response.defer(ephemeral=True)
        cosmetic = get_cosmetic(item_id)
        if not cosmetic:
            return await interaction.followup.send(embed=_coins_embed("Not Found", f"No cosmetic with ID `{item_id}`."), ephemeral=True)
        guild_id = interaction.guild.id
        user_id = interaction.user.id
        settlement = await self.bot.economy_service.settle_purchase(guild_id, user_id, cosmetic.price, "cosmetic_purchase", reference_type="cosmetic", reference_id=item_id)
        if not settlement["success"]:
            return await interaction.followup.send(embed=_coins_embed("Not Enough Coins", f"You need **🪙 {cosmetic.price:,.2f}** to buy {cosmetic.name}."), ephemeral=True)
        await self.bot.inventory_service.add_item(guild_id, user_id, item_id, "purchase")
        profile = await self.bot.economy_service.get_profile(guild_id, user_id)
        tax_note = f"\n*(Tax: 🪙 {settlement['tax_amount']:.2f})*" if settlement["tax_amount"] > 0 else ""
        embed = discord.Embed(
            title="Purchase Complete!",
            description=f"You bought {RARITY_DISPLAY_EMOJI.get(cosmetic.rarity, '')} **{cosmetic.name}** for 🪙 {cosmetic.price:,.2f}!{tax_note}\nNew balance: **🪙 {profile['bruh_coins']:.2f}**\n\nEquip it with `/wardrobe equip {item_id}`",
            color=RARITY_COLORS.get(cosmetic.rarity, 0x57F287),
            timestamp=datetime.now(UTC),
        )
        embed.set_footer(text="bruh.bot")
        await interaction.followup.send(embed=embed, ephemeral=True)

    @cosmetics_group.command(name="info", description="Get detailed info about a cosmetic.")
    @app_commands.describe(item_id="The cosmetic ID")
    @log_command_usage()
    @is_globally_blocked()
    async def cosmetics_info(self, interaction: discord.Interaction, item_id: str):
        await interaction.response.defer(ephemeral=True)
        cosmetic = get_cosmetic(item_id)
        if not cosmetic:
            return await interaction.followup.send(embed=_coins_embed("Not Found", f"No cosmetic with ID `{item_id}`."), ephemeral=True)
        embed = discord.Embed(
            title=f"{RARITY_DISPLAY_EMOJI.get(cosmetic.rarity, '')} {cosmetic.name}",
            description=cosmetic.description or "No description.",
            color=RARITY_COLORS.get(cosmetic.rarity, 0x5865F2),
            timestamp=datetime.now(UTC),
        )
        embed.set_footer(text="bruh.bot")
        embed.add_field(name="ID", value=f"`{cosmetic.id}`", inline=True)
        embed.add_field(name="Slot", value=cosmetic.slot.value.replace("_", " ").title(), inline=True)
        embed.add_field(name="Rarity", value=cosmetic.rarity.value.title(), inline=True)
        embed.add_field(name="Price", value=f"🪙 {cosmetic.price:,.2f}", inline=True)
        if cosmetic.collection:
            embed.add_field(name="Collection", value=cosmetic.collection, inline=True)
        await interaction.followup.send(embed=embed, ephemeral=True)

    @cosmetics_group.command(name="inventory", description="View your or another user's cosmetic inventory.")
    @app_commands.describe(user="User to view (defaults to you)")
    @log_command_usage()
    @is_globally_blocked()
    async def cosmetics_inventory(self, interaction: discord.Interaction, user: discord.Member | None = None):
        await interaction.response.defer()
        target = user or interaction.user
        inventory = await self.bot.inventory_service.get_inventory(interaction.guild.id, target.id)
        equipped = inventory["equipped"]
        owned = inventory["items"]
        if not owned:
            embed = self.bot.embed_service._create_base_embed(title=f"{target.display_name}'s Inventory", description="No cosmetics owned yet.\nCheck `/cosmetics shop` to start collecting!")
            embed.set_thumbnail(url=target.display_avatar.url)
            return await interaction.followup.send(embed=embed)
        lines = []
        for item in owned:
            cosmetic = get_cosmetic(item["item_id"])
            if not cosmetic:
                continue
            eq = " **[E]**" if equipped.get(cosmetic.slot.value) == cosmetic.id else ""
            lines.append(f"{RARITY_DISPLAY_EMOJI.get(cosmetic.rarity, '')} **{cosmetic.name}**{' x' + str(item['quantity']) if item['quantity'] > 1 else ''}{eq}")
        embed = self.bot.embed_service._create_base_embed(title=f"{target.display_name}'s Inventory", description="\n".join(lines))
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.add_field(name="Owned", value=str(len(owned)), inline=True)
        embed.add_field(name="Equipped", value=str(sum(1 for v in equipped.values() if v)), inline=True)
        await interaction.followup.send(embed=embed)

    # ═══════════════════════════════════════════════════════════════
    # /cosmetic-packs  (subgroup)
    # ═══════════════════════════════════════════════════════════════
    cosmetic_packs_group = app_commands.Group(name="cosmetic-packs", description="Collect and open packs that unlock character cosmetics!")

    @cosmetic_packs_group.command(name="shop", description="Browse available card packs that unlock cosmetics.")
    @log_command_usage()
    @is_globally_blocked()
    async def cosmetic_packs_shop(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        packs = self.bot.card_pack_service.get_all_packs()
        lines = []
        for _key, pack in packs.items():
            guaranteed = pack.get("guaranteed_rarity")
            g_text = f"Guaranteed: **{guaranteed.value.title()}** or better" if guaranteed else "No guaranteed rarity"
            lines.append(f"**{pack['name']}** — 🪙 {pack['price']:,}\n　{pack['description']}\n　{g_text} · {pack['cards_per_pack']} cards per pack\n　Buy with `/cosmetic-packs buy-pack`")
        embed = self.bot.embed_service._create_base_embed(title="Card Pack Shop", description="\n\n".join(lines))
        embed.add_field(name="How to Open", value="Buy packs with `/cosmetic-packs buy-pack`, then open them with `/cosmetic-packs open`!", inline=False)
        await interaction.followup.send(embed=embed, ephemeral=True, files=self.bot.embed_service.get_brand_files(embed=embed))

    @cosmetic_packs_group.command(name="buy-pack", description="Buy a card pack.")
    @app_commands.describe(pack_type="The type of pack to buy")
    @app_commands.choices(
        pack_type=[
            app_commands.Choice(name="Standard Pack (200 coins)", value="standard"),
            app_commands.Choice(name="Premium Pack (750 coins)", value="premium"),
        ]
    )
    @log_command_usage()
    @is_globally_blocked()
    async def cards_buy_pack(self, interaction: discord.Interaction, pack_type: str):
        await interaction.response.defer(ephemeral=True)
        result = await self.bot.card_pack_service.buy_pack(interaction.guild.id, interaction.user.id, pack_type)
        if not result["success"]:
            return await interaction.followup.send(embed=_coins_embed("Purchase Failed", result["error"]), ephemeral=True)
        await interaction.followup.send(embed=_coins_embed("Pack Purchased!", f"You bought a **{result['pack_name']}** for 🪙 {result['price']:,}!\n\nOpen it with `/cosmetic-packs open`"), ephemeral=True)

    @cosmetic_packs_group.command(name="open", description="Open an unopened card pack.")
    @app_commands.describe(pack_type="The type of pack to open")
    @app_commands.choices(
        pack_type=[
            app_commands.Choice(name="Standard Pack", value="standard"),
            app_commands.Choice(name="Premium Pack", value="premium"),
        ]
    )
    @log_command_usage()
    @is_globally_blocked()
    async def cards_open(self, interaction: discord.Interaction, pack_type: str):
        await interaction.response.defer(ephemeral=True)
        result = await self.bot.card_pack_service.open_pack(interaction.guild.id, interaction.user.id, pack_type)
        if not result["success"]:
            return await interaction.followup.send(embed=_coins_embed("Cannot Open", result["error"]), ephemeral=True)
        lines = []
        for i, (rarity_val, _card_id, cosmetic_id) in enumerate(zip(result["rarities"], result["card_ids"], result["cosmetic_ids"], strict=False)):
            rarity = CosmeticRarity(rarity_val)
            cosmetic = get_cosmetic(cosmetic_id)
            name = cosmetic.name if cosmetic else cosmetic_id
            unlocked = " **[NEW UNLOCK!]**" if cosmetic_id in result["new_unlocks"] else ""
            lines.append(f"{i + 1}. {RARITY_DISPLAY_EMOJI.get(rarity, '')} **{rarity.value.title()}** — {name}{unlocked}")
        embed = _coins_embed(f"Opening: {result['pack_name']}", "\n".join(lines))
        embed.add_field(name="New Cosmetics Unlocked", value=str(len(result["new_unlocks"]) or "None (duplicates added to collection)"), inline=True)
        embed.add_field(name="Total Cards", value=str(len(result["card_ids"])), inline=True)
        await interaction.followup.send(embed=embed, ephemeral=True)

    @cosmetic_packs_group.command(name="binder", description="View your or another user's card collection.")
    @app_commands.describe(user="User to view (defaults to you)")
    @log_command_usage()
    @is_globally_blocked()
    async def cards_binder(self, interaction: discord.Interaction, user: discord.Member | None = None):
        await interaction.response.defer()
        target = user or interaction.user
        inventory = await self.bot.inventory_service.get_inventory(interaction.guild.id, target.id)
        cards = inventory.get("cards", [])
        packs = inventory.get("card_packs_unopened", [])
        if not cards and not packs:
            embed = self.bot.embed_service._create_base_embed(title=f"{target.display_name}'s Card Binder", description="No cards collected yet.\nBuy packs with `/cosmetic-packs buy-pack`!")
            embed.set_thumbnail(url=target.display_avatar.url)
            return await interaction.followup.send(embed=embed)
        lines = []
        rarity_counts = dict.fromkeys(CosmeticRarity, 0)
        total_cards = 0
        for card in sorted(cards, key=lambda c: c.get("card_id", "")):
            cosmetic_id = card["card_id"].replace("card_", "")
            cosmetic = get_cosmetic(cosmetic_id)
            if cosmetic:
                qty = card.get("quantity", 1)
                rarity_counts[cosmetic.rarity] += qty
                total_cards += qty
                lines.append(f"{RARITY_DISPLAY_EMOJI.get(cosmetic.rarity, '')} **{cosmetic.name}**{' x' + str(qty) if qty > 1 else ''}")
        rarity_summary = " · ".join(f"{RARITY_DISPLAY_EMOJI.get(r, '')} {count}" for r, count in rarity_counts.items() if count > 0)
        embed = self.bot.embed_service._create_base_embed(title=f"{target.display_name}'s Card Binder", description="\n".join(lines[:25]) if lines else "No cards collected yet.")
        embed.set_thumbnail(url=target.display_avatar.url)
        if len(lines) > 25:
            embed.set_footer(text=f"bruh.bot · Showing 25 of {len(lines)} unique cards")
        embed.add_field(name="Total Cards", value=str(total_cards), inline=True)
        embed.add_field(name="Unique Cards", value=str(len(lines)), inline=True)
        embed.add_field(name="Unopened Packs", value=str(sum(p.get("quantity", 1) for p in packs)), inline=True)
        if rarity_summary:
            embed.insert_field_at(0, name="Collection", value=rarity_summary, inline=False)
        await interaction.followup.send(embed=embed)

    @cosmetic_packs_group.command(name="sell", description="Sell a duplicate card for coins.")
    @app_commands.describe(card_id="The card ID to sell", quantity="How many to sell")
    @log_command_usage()
    @is_globally_blocked()
    async def cards_sell(self, interaction: discord.Interaction, card_id: str, quantity: int = 1):
        await interaction.response.defer(ephemeral=True)
        cosmetic_id = card_id.replace("card_", "")
        cosmetic = get_cosmetic(cosmetic_id)
        if not cosmetic:
            return await interaction.followup.send(embed=_coins_embed("Invalid Card", "This card ID is not recognized."), ephemeral=True)
        success = await self.bot.inventory_service.remove_cards(interaction.guild.id, interaction.user.id, card_id, quantity)
        if not success:
            return await interaction.followup.send(embed=_coins_embed("Not Enough", f"You don't have {quantity} of this card."), ephemeral=True)
        config = await self.bot.config_service.get_config(str(interaction.guild.id))
        rate = config.economyConfig.cardSellbackRate
        sell_value = round(cosmetic.price * rate * quantity, 2)
        new_balance = await self.bot.economy_service.add_coins(interaction.guild.id, interaction.user.id, sell_value)
        await self.bot.economy_service.record_transaction(interaction.guild.id, interaction.user.id, "card_sellback", sell_value, new_balance, reference_type="card", reference_id=card_id)
        await interaction.followup.send(embed=_coins_embed("Cards Sold", f"Sold **{quantity}x {cosmetic.name}** card{'s' if quantity > 1 else ''} for 🪙 {sell_value:,.2f}\nNew balance: **🪙 {new_balance:,.2f}**"), ephemeral=True)

    # ═══════════════════════════════════════════════════════════════
    # /cosmetic-trade  (subgroup)
    # ═══════════════════════════════════════════════════════════════
    cosmetic_trade_group = app_commands.Group(name="cosmetic-trade", description="Trade cosmetics with other users!")

    @cosmetic_trade_group.command(name="offer", description="Offer a trade to another user.")
    @app_commands.describe(
        user="The user to trade with",
        give_items="Item IDs to give (comma-separated)",
        give_cards="Card IDs to give (comma-separated)",
        give_coins="Coins to give (optional)",
        want_items="Item IDs you want (comma-separated)",
        want_cards="Card IDs you want (comma-separated)",
        want_coins="Coins you want (optional)",
    )
    @log_command_usage()
    @is_globally_blocked()
    async def trade_offer(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        give_items: str = "",
        give_cards: str = "",
        give_coins: int = 0,
        want_items: str = "",
        want_cards: str = "",
        want_coins: int = 0,
    ):
        await interaction.response.defer(ephemeral=True)
        config = await self.bot.config_service.get_config(str(interaction.guild.id))
        if not config.economyConfig.tradingEnabled:
            return await interaction.followup.send(embed=_coins_embed("Trading Disabled", "Trading is currently disabled on this server."), ephemeral=True)
        if interaction.user.id == user.id:
            return await interaction.followup.send(embed=_coins_embed("Invalid Trade", "You can't trade with yourself."), ephemeral=True)
        if user.bot:
            return await interaction.followup.send(embed=_coins_embed("Invalid Trade", "You can't trade with bots."), ephemeral=True)
        if give_coins < 0 or want_coins < 0:
            return await interaction.followup.send(embed=_coins_embed("Invalid Trade", "Coin amounts cannot be negative."), ephemeral=True)

        give_item_list = [i.strip() for i in give_items.split(",") if i.strip()]
        give_card_list = [c.strip() for c in give_cards.split(",") if c.strip()]
        want_item_list = [i.strip() for i in want_items.split(",") if i.strip()]
        want_card_list = [c.strip() for c in want_cards.split(",") if c.strip()]

        if not any([give_item_list, give_card_list, give_coins > 0, want_item_list, want_card_list, want_coins > 0]):
            return await interaction.followup.send(embed=_coins_embed("Empty Trade", "You must specify at least one item, card, or coin amount."), ephemeral=True)

        init_inventory = await self.bot.inventory_service.get_inventory(interaction.guild.id, interaction.user.id)
        for item_id in give_item_list:
            owned = next((i for i in init_inventory["items"] if i["item_id"] == item_id), None)
            if not owned:
                return await interaction.followup.send(embed=_coins_embed("Invalid Trade", f"You don't own **{item_id}** to give."), ephemeral=True)
            cosmetic = get_cosmetic(item_id)
            if cosmetic and init_inventory["equipped"].get(cosmetic.slot.value) == item_id:
                return await interaction.followup.send(embed=_coins_embed("Invalid Trade", f"Unequip **{cosmetic.name}** before trading it."), ephemeral=True)
        for card_id in give_card_list:
            owned = next((c for c in init_inventory.get("cards", []) if c["card_id"] == card_id), None)
            if not owned:
                return await interaction.followup.send(embed=_coins_embed("Invalid Trade", f"You don't own **{card_id}** card."), ephemeral=True)

        if give_coins > 0:
            profile = await self.bot.economy_service.get_profile(interaction.guild.id, interaction.user.id)
            if profile["bruh_coins"] < give_coins:
                return await interaction.followup.send(embed=_coins_embed("Invalid Trade", f"You only have 🪙 {profile['bruh_coins']:.2f}."), ephemeral=True)

        trade_id = uuid.uuid4().hex[:12]

        def _format_side(items: list[str], cards: list[str], coins: int) -> str:
            lines = []
            for iid in items:
                c = get_cosmetic(iid)
                lines.append(f"- Cosmetic: **{c.name if c else iid}**")
            for cid in cards:
                c = get_cosmetic(cid.replace("card_", ""))
                lines.append(f"- Card: **{c.name if c else cid}**")
            if coins > 0:
                lines.append(f"- Coins: **🪙 {coins:,}**")
            return "\n".join(lines) if lines else "*Nothing*"

        give_str = _format_side(give_item_list, give_card_list, give_coins)
        want_str = _format_side(want_item_list, want_card_list, want_coins)

        embed = discord.Embed(
            title=f"Trade Offer from {interaction.user.display_name}",
            description=f"**{interaction.user.display_name}** offers:\n{give_str}\n\n**{interaction.user.display_name}** wants from {user.mention}:\n{want_str}\n\nExpires in {TRADE_EXPIRY_MINUTES} minutes.",
            color=0xFEE75C,
            timestamp=datetime.now(UTC),
        )
        embed.set_footer(text=f"bruh.bot · Trade ID: {trade_id}")

        view = TradeConfirmView(trade_id, interaction.user.id, user.id)
        await interaction.followup.send(embed=embed, ephemeral=True)
        await interaction.followup.send(f"{user.mention}, {interaction.user.display_name} wants to trade with you!", embed=embed, view=view)
        await view.wait()

        if view.accepted:
            if give_coins > 0:
                await self.bot.economy_service.deduct_coins(interaction.guild.id, interaction.user.id, give_coins)
                await self.bot.economy_service.record_transaction(interaction.guild.id, interaction.user.id, "trade_debit", -give_coins, 0.0, reference_type="trade", reference_id=trade_id)
            if want_coins > 0:
                success, _ = await self.bot.economy_service.deduct_coins(interaction.guild.id, user.id, want_coins)
                if not success:
                    return await interaction.followup.send(embed=_coins_embed("Trade Failed", f"{user.display_name} doesn't have enough coins."))
                await self.bot.economy_service.record_transaction(interaction.guild.id, user.id, "trade_debit", -want_coins, 0.0, reference_type="trade", reference_id=trade_id)
                await self.bot.economy_service.add_coins(interaction.guild.id, interaction.user.id, want_coins)
                await self.bot.economy_service.record_transaction(interaction.guild.id, interaction.user.id, "trade_credit", want_coins, 0.0, reference_type="trade", reference_id=trade_id)
            if give_coins > 0:
                await self.bot.economy_service.add_coins(interaction.guild.id, user.id, give_coins)
                await self.bot.economy_service.record_transaction(interaction.guild.id, user.id, "trade_credit", give_coins, 0.0, reference_type="trade", reference_id=trade_id)

            for item_id in give_item_list:
                await self.bot.inventory_service.remove_item(interaction.guild.id, interaction.user.id, item_id, 1)
                await self.bot.inventory_service.add_item(interaction.guild.id, user.id, item_id, "trade")
            for card_id in give_card_list:
                await self.bot.inventory_service.remove_cards(interaction.guild.id, interaction.user.id, card_id, 1)
                await self.bot.inventory_service.add_cards(interaction.guild.id, user.id, [card_id])
            for item_id in want_item_list:
                await self.bot.inventory_service.remove_item(interaction.guild.id, user.id, item_id, 1)
                await self.bot.inventory_service.add_item(interaction.guild.id, interaction.user.id, item_id, "trade")
            for card_id in want_card_list:
                await self.bot.inventory_service.remove_cards(interaction.guild.id, user.id, card_id, 1)
                await self.bot.inventory_service.add_cards(interaction.guild.id, interaction.user.id, [card_id])

            self.bot.character_render_service.invalidate_cache(interaction.guild.id, interaction.user.id)
            self.bot.character_render_service.invalidate_cache(interaction.guild.id, user.id)
            await interaction.followup.send(embed=_coins_embed("Trade Accepted!", f"Trade between {interaction.user.mention} and {user.mention} completed!"))
        else:
            await interaction.followup.send(embed=_coins_embed("Trade Declined", "The trade was declined or expired."))

    # ═══════════════════════════════════════════════════════════════
    # /economy admin commands
    # ═══════════════════════════════════════════════════════════════
    @economy.command(name="set-xp", description="[Admin] Set a user's total XP.")
    @app_commands.describe(user="The user", amount="New XP amount")
    @log_command_usage()
    @is_admin()
    @is_globally_blocked()
    async def economy_set_xp(self, interaction: discord.Interaction, user: discord.Member, amount: int):
        new_level = await self.bot.economy_service.set_xp(interaction.guild.id, user.id, amount)
        embed = self.bot.embed_service.create_success_embed(f"Set **{user.display_name}**'s XP to **{amount:,}** (Level {new_level}).", title="XP Updated")
        await interaction.followup.send(embed=embed, ephemeral=True, files=self.bot.embed_service.get_brand_files(embed=embed))

    @economy.command(name="set-coins", description="[Admin] Set a user's coin balance.")
    @app_commands.describe(user="The user", amount="New coin balance")
    @log_command_usage()
    @is_admin()
    @is_globally_blocked()
    async def economy_set_coins(self, interaction: discord.Interaction, user: discord.Member, amount: float):
        await self.bot.economy_service.set_coins(interaction.guild.id, user.id, amount)
        embed = self.bot.embed_service.create_success_embed(f"Set **{user.display_name}**'s coin balance to **🪙 {amount:.2f}**.", title="Coins Updated")
        await interaction.followup.send(embed=embed, ephemeral=True, files=self.bot.embed_service.get_brand_files(embed=embed))

    @economy.command(name="set-level", description="[Admin] Set a user's level.")
    @app_commands.describe(user="The user", level="New level")
    @log_command_usage()
    @is_admin()
    @is_globally_blocked()
    async def economy_set_level(self, interaction: discord.Interaction, user: discord.Member, level: int):
        await self.bot.economy_service.set_level(interaction.guild.id, user.id, level)
        embed = self.bot.embed_service.create_success_embed(f"Set **{user.display_name}**'s level to **{level}**.", title="Level Updated")
        await interaction.followup.send(embed=embed, ephemeral=True, files=self.bot.embed_service.get_brand_files(embed=embed))

    @economy.command(name="reset", description="[Admin] Reset a user's economy profile entirely.")
    @app_commands.describe(user="The user to reset")
    @log_command_usage()
    @is_admin()
    @is_globally_blocked()
    async def economy_reset(self, interaction: discord.Interaction, user: discord.Member):
        await self.bot.economy_service.reset_profile(interaction.guild.id, user.id)
        embed = self.bot.embed_service.create_success_embed(f"**{user.display_name}**'s economy profile has been reset.", title="Profile Reset")
        await interaction.followup.send(embed=embed, ephemeral=True, files=self.bot.embed_service.get_brand_files(embed=embed))

    @economy.command(name="give-coins", description="[Admin] Give coins to a user.")
    @app_commands.describe(user="The user", amount="Amount to give")
    @log_command_usage()
    @is_admin()
    @is_globally_blocked()
    async def economy_give_coins(self, interaction: discord.Interaction, user: discord.Member, amount: float):
        new_balance = await self.bot.economy_service.add_coins(interaction.guild.id, user.id, amount)
        embed = self.bot.embed_service.create_success_embed(f"Gave **🪙 {amount:.2f}** to **{user.display_name}**.\nNew balance: **🪙 {new_balance:.2f}**", title="Coins Given")
        await interaction.followup.send(embed=embed, ephemeral=True, files=self.bot.embed_service.get_brand_files(embed=embed))

    @economy.command(name="take-coins", description="[Admin] Remove coins from a user.")
    @app_commands.describe(user="The user", amount="Amount to take")
    @log_command_usage()
    @is_admin()
    @is_globally_blocked()
    async def economy_take_coins(self, interaction: discord.Interaction, user: discord.Member, amount: float):
        success, new_balance = await self.bot.economy_service.deduct_coins(interaction.guild.id, user.id, amount)
        if not success:
            embed = self.bot.embed_service.create_error_embed(f"{user.display_name} doesn't have enough coins (balance: 🪙 {new_balance:.2f}).")
        else:
            embed = self.bot.embed_service.create_success_embed(f"Took **🪙 {amount:.2f}** from **{user.display_name}**.\nNew balance: **🪙 {new_balance:.2f}**", title="Coins Taken")
        await interaction.followup.send(embed=embed, ephemeral=True, files=self.bot.embed_service.get_brand_files(embed=embed))

    @economy.command(name="grant-item", description="[Admin] Give a cosmetic item to a user.")
    @app_commands.describe(user="The user", item_id="Cosmetic ID to grant")
    @log_command_usage()
    @is_admin()
    @is_globally_blocked()
    async def economy_grant_item(self, interaction: discord.Interaction, user: discord.Member, item_id: str):
        cosmetic = get_cosmetic(item_id)
        if not cosmetic:
            embed = self.bot.embed_service.create_error_embed(f"No cosmetic found with ID `{item_id}`.")
            return await interaction.followup.send(embed=embed, ephemeral=True, files=self.bot.embed_service.get_brand_files(embed=embed))
        await self.bot.inventory_service.add_item(interaction.guild.id, user.id, item_id, "admin_grant")
        embed = self.bot.embed_service.create_success_embed(f"Granted {RARITY_DISPLAY_EMOJI.get(cosmetic.rarity, '')} **{cosmetic.name}** to **{user.display_name}**.", title="Item Granted")
        await interaction.followup.send(embed=embed, ephemeral=True, files=self.bot.embed_service.get_brand_files(embed=embed))

    @economy.command(name="take-item", description="[Admin] Remove a cosmetic item from a user.")
    @app_commands.describe(user="The user", item_id="Cosmetic ID to remove", quantity="How many to remove")
    @log_command_usage()
    @is_admin()
    @is_globally_blocked()
    async def economy_take_item(self, interaction: discord.Interaction, user: discord.Member, item_id: str, quantity: int = 1):
        cosmetic = get_cosmetic(item_id)
        name = cosmetic.name if cosmetic else item_id
        success = await self.bot.inventory_service.remove_item(interaction.guild.id, user.id, item_id, quantity)
        if not success:
            embed = self.bot.embed_service.create_error_embed(f"{user.display_name} doesn't have {quantity}x **{name}**.")
        else:
            embed = self.bot.embed_service.create_success_embed(f"Removed **{quantity}x {name}** from **{user.display_name}**.", title="Item Removed")
        await interaction.followup.send(embed=embed, ephemeral=True, files=self.bot.embed_service.get_brand_files(embed=embed))

    @economy.command(name="grant-pack", description="[Admin] Give card packs to a user.")
    @app_commands.describe(user="The user", pack_type="Type of pack", quantity="How many packs")
    @app_commands.choices(pack_type=[app_commands.Choice(name="Standard Pack", value="standard"), app_commands.Choice(name="Premium Pack", value="premium")])
    @log_command_usage()
    @is_admin()
    @is_globally_blocked()
    async def economy_grant_pack(self, interaction: discord.Interaction, user: discord.Member, pack_type: str, quantity: int = 1):
        pack_info = self.bot.card_pack_service.get_pack_info(pack_type)
        pack_name = pack_info["name"] if pack_info else pack_type
        for _ in range(quantity):
            await self.bot.inventory_service.add_card_pack(interaction.guild.id, user.id, pack_type)
        embed = self.bot.embed_service.create_success_embed(f"Gave **{quantity}x {pack_name}** to **{user.display_name}**.", title="Card Packs Granted")
        await interaction.followup.send(embed=embed, ephemeral=True, files=self.bot.embed_service.get_brand_files(embed=embed))

    @economy.command(name="grant-cards", description="[Admin] Give specific cards to a user.")
    @app_commands.describe(user="The user", rarity="Rarity of cards to grant", quantity="How many cards")
    @app_commands.choices(rarity=[app_commands.Choice(name=r.value.title(), value=r.value) for r in CosmeticRarity])
    @log_command_usage()
    @is_admin()
    @is_globally_blocked()
    async def economy_grant_cards(self, interaction: discord.Interaction, user: discord.Member, rarity: str, quantity: int = 1):
        rarity_enum = CosmeticRarity(rarity)
        candidates = [c for c in get_all_released() if c.rarity == rarity_enum] or get_all_released()
        if not candidates:
            embed = self.bot.embed_service.create_error_embed("No cosmetics in catalog to generate cards from.")
            return await interaction.followup.send(embed=embed, ephemeral=True, files=self.bot.embed_service.get_brand_files(embed=embed))
        card_ids = [f"card_{c.id}" for c in random.choices(candidates, k=quantity)]
        await self.bot.inventory_service.add_cards(interaction.guild.id, user.id, card_ids)
        embed = self.bot.embed_service.create_success_embed(f"Gave **{quantity}x {RARITY_DISPLAY_EMOJI.get(rarity_enum, '')} {rarity_enum.value.title()}** cards to **{user.display_name}**.", title="Cards Granted")
        await interaction.followup.send(embed=embed, ephemeral=True, files=self.bot.embed_service.get_brand_files(embed=embed))

    @economy.command(name="inspect", description="[Admin] Inspect a user's full inventory and character.")
    @app_commands.describe(user="The user to inspect")
    @log_command_usage()
    @is_admin()
    @is_globally_blocked()
    async def economy_inspect(self, interaction: discord.Interaction, user: discord.Member):
        inventory = await self.bot.inventory_service.get_inventory(interaction.guild.id, user.id)
        item_lines = []
        for item in inventory["items"]:
            cosmetic = get_cosmetic(item["item_id"])
            name = cosmetic.name if cosmetic else item["item_id"]
            rarity_label = f" ({cosmetic.rarity.value.title()})" if cosmetic else ""
            item_lines.append(f"- {name} x{item['quantity']}{rarity_label}")
        card_lines = []
        for card in inventory.get("cards", []):
            cosmetic = get_cosmetic(card["card_id"].replace("card_", ""))
            name = cosmetic.name if cosmetic else card["card_id"].replace("card_", "")
            card_lines.append(f"- {name} x{card['quantity']}")
        equipped_lines = []
        for slot in CosmeticSlot:
            item_id = inventory["equipped"].get(slot.value)
            if item_id:
                cosmetic = get_cosmetic(item_id)
                equipped_lines.append(f"  **{slot.value.replace('_', ' ').title()}**: {cosmetic.name if cosmetic else item_id}")
            else:
                equipped_lines.append(f"  **{slot.value.replace('_', ' ').title()}**: *(none)*")
        embed = self.bot.embed_service._create_base_embed(title=f"Inventory — {user.display_name}")
        embed.set_thumbnail(url=user.display_avatar.url)
        embed.add_field(name="Items", value="\n".join(item_lines[:15]) or "No items.", inline=False)
        if len(item_lines) > 15:
            embed.add_field(name="...", value=f"+{len(item_lines) - 15} more", inline=False)
        embed.add_field(name="Equipped", value="\n".join(equipped_lines), inline=False)
        embed.add_field(name="Cards", value="\n".join(card_lines[:10]) or "No cards.", inline=False)
        packs = inventory.get("card_packs_unopened", [])
        pack_summary = ", ".join(f"{p['pack_id']} x{p.get('quantity', 1)}" for p in packs) or "None"
        embed.add_field(name="Unopened Packs", value=pack_summary, inline=True)
        await interaction.followup.send(embed=embed, ephemeral=True, files=self.bot.embed_service.get_brand_files(embed=embed))

    @economy.command(name="reset-inventory", description="[Admin] Reset a user's entire inventory.")
    @app_commands.describe(user="The user to reset")
    @log_command_usage()
    @is_admin()
    @is_globally_blocked()
    async def economy_reset_inventory(self, interaction: discord.Interaction, user: discord.Member):
        await self.bot.inventory_service.reset_inventory(interaction.guild.id, user.id)
        self.bot.character_render_service.invalidate_cache(interaction.guild.id, user.id)
        embed = self.bot.embed_service.create_success_embed(f"**{user.display_name}**'s inventory has been reset.", title="Inventory Reset")
        await interaction.followup.send(embed=embed, ephemeral=True, files=self.bot.embed_service.get_brand_files(embed=embed))

    @economy.command(name="toggle", description="[Admin] Toggle an economy feature on or off.")
    @app_commands.describe(feature="Feature to toggle", enabled="Enable or disable")
    @app_commands.choices(
        feature=[
            app_commands.Choice(name="bruh.cards", value="bruhCardsEnabled"),
            app_commands.Choice(name="Cosmetics Shop", value="cosmeticsShopEnabled"),
            app_commands.Choice(name="Cosmetic Packs", value="cardPacksEnabled"),
            app_commands.Choice(name="Cosmetic Trading", value="tradingEnabled"),
            app_commands.Choice(name="Cosmetic Market", value="marketplaceEnabled"),
        ]
    )
    @log_command_usage()
    @is_admin()
    @is_globally_blocked()
    async def economy_toggle(self, interaction: discord.Interaction, feature: str, enabled: bool):
        guild_id = str(interaction.guild.id)
        config = await self.bot.config_service.get_config(guild_id)
        econ = config.economyConfig.model_dump()
        econ[feature] = enabled
        await self.bot.config_service.update(guild_id, {"economyConfig": econ})
        label = feature.replace("Enabled", "").replace("Shop", " Shop")
        status = "enabled" if enabled else "disabled"
        embed = self.bot.embed_service.create_success_embed(f"**{label}** has been **{status}**.", title="Feature Toggled")
        await interaction.followup.send(embed=embed, ephemeral=True, files=self.bot.embed_service.get_brand_files(embed=embed))

    # ═══════════════════════════════════════════════════════════════
    # /bruh-cards  (trading card subgroup)
    # ═══════════════════════════════════════════════════════════════
    bruh_cards_group = app_commands.Group(name="bruh-cards", description="Collect and trade bruh.cards!")

    @bruh_cards_group.command(name="inventory", description="Open your interactive bruh.cards dashboard.")
    @log_command_usage()
    @is_globally_blocked()
    async def bruh_cards_inventory(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        from bot.views.bruh_cards_view import BruhCardsInventoryView

        view = BruhCardsInventoryView(self.bot, interaction.guild.id, interaction.user.id)
        await view._refresh_data()
        view._update_buttons()
        await interaction.followup.send(embed=view._dashboard_embed(), view=view, ephemeral=True)

    @bruh_cards_group.command(name="shop", description="Browse available trading card packs.")
    @log_command_usage()
    @is_globally_blocked()
    async def bruh_cards_shop(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        packs = self.bot.trading_card_catalog_service.get_all_packs()
        if not packs:
            return await interaction.followup.send(
                embed=self.bot.embed_service.create_info_embed(title="Card Pack Shop", description="No packs are currently available."),
                ephemeral=True,
                files=self.bot.embed_service.get_brand_files(),
            )
        by_set: dict[str, list] = {}
        for key, pack in packs.items():
            by_set.setdefault(pack.series_id, []).append((key, pack))

        blocks = []
        for sid in sorted(by_set):
            set_display = sid.replace("_", " ").title()
            pk_lines = []
            for key, pack in by_set[sid]:
                guaranteed = pack.guaranteed_rarity
                g_text = f"Guaranteed: **{guaranteed.value.title()}**+" if guaranteed else "No guaranteed rarity"
                pk_lines.append(f"**{pack.name}** — 🪙 {pack.price:,}\n　{pack.description}\n　{g_text} · {pack.cards_per_pack} cards per pack\n　Buy: `/bruh-cards buy-pack {key}`")
            blocks.append(f"**{set_display}**\n" + "\n".join(pk_lines))

        embed = self.bot.embed_service._create_base_embed(
            title="Trading Card Shop",
            description="\n\n".join(blocks),
        )
        embed.add_field(
            name="Getting Started",
            value="Buy packs → open them → build your collection!\nView with `/bruh-cards inventory`",
            inline=False,
        )
        await interaction.followup.send(embed=embed, ephemeral=True, files=self.bot.embed_service.get_brand_files(embed=embed))

    @bruh_cards_group.command(name="buy-pack", description="Buy a trading card pack.")
    @app_commands.describe(pack_id="The pack to buy", quantity="How many to buy")
    @app_commands.autocomplete(pack_id=pack_id_autocomplete)
    @log_command_usage()
    @is_globally_blocked()
    async def bruh_cards_buy_pack(self, interaction: discord.Interaction, pack_id: str, quantity: app_commands.Range[int, 1, 10] = 1):
        await interaction.response.defer(ephemeral=True)
        pack_def = self.bot.trading_card_catalog_service.get_pack(pack_id)
        if not pack_def:
            return await interaction.followup.send(embed=_coins_embed("Invalid Pack", f"No pack with ID `{pack_id}`."), ephemeral=True)
        total_cost = pack_def.price * quantity
        settlement = await self.bot.economy_service.settle_purchase(
            interaction.guild.id,
            interaction.user.id,
            total_cost,
            "trading_card_pack_purchase",
            reference_type="trading_card_pack",
            reference_id=pack_id,
            metadata={"quantity": quantity, "pack_id": pack_id},
        )
        if not settlement["success"]:
            return await interaction.followup.send(
                embed=_coins_embed("Not Enough Coins", f"You need **🪙 {total_cost:,}** for {quantity}x {pack_def.name}. You have **🪙 {settlement['buyer_new_balance']:,.2f}**."),
                ephemeral=True,
            )
        for _ in range(quantity):
            await self.bot.trading_card_service.add_packs(interaction.guild.id, interaction.user.id, pack_id)
        tax_note = f"\n*(Tax: 🪙 {settlement['tax_amount']:.2f})*" if settlement["tax_amount"] > 0 else ""
        await interaction.followup.send(
            embed=_coins_embed(
                "Pack Purchased!",
                f"You bought **{quantity}x {pack_def.name}** for 🪙 {total_cost:,}!{tax_note}\nOpen with `/bruh-cards open {pack_id}`",
            ),
            ephemeral=True,
        )

    @bruh_cards_group.command(name="open", description="Open a trading card pack.")
    @app_commands.describe(pack_id="The pack to open")
    @app_commands.autocomplete(pack_id=pack_id_autocomplete)
    @log_command_usage()
    @is_globally_blocked()
    async def bruh_cards_open(self, interaction: discord.Interaction, pack_id: str):
        await interaction.response.defer(ephemeral=True)
        result = await self.bot.trading_card_service.open_pack(interaction.guild.id, interaction.user.id, pack_id)
        if not result["success"]:
            if result.get("refunded"):
                embed = self.bot.embed_service.create_success_embed(result["error"], title="Pack Refunded")
                return await interaction.followup.send(embed=embed, ephemeral=True, files=self.bot.embed_service.get_brand_files(embed=embed))
            return await interaction.followup.send(embed=_coins_embed("Cannot Open", result["error"]), ephemeral=True)
        pack_def = self.bot.trading_card_catalog_service.get_pack(pack_id)
        set_display = pack_def.series_id.replace("_", " ").title() if pack_def else "Unknown"
        lines = []
        for i, (card_id, rarity_val) in enumerate(zip(result["card_ids"], result["rarities"], strict=False)):
            try:
                rarity = TradingCardRarity(rarity_val)
            except ValueError:
                rarity = TradingCardRarity.COMMON
            card = self.bot.trading_card_catalog_service.get_card(card_id)
            name = card.name if card else card_id
            lines.append(f"{i + 1}. {TC_EMOJI.get(rarity, '')} **{rarity.value.title()}** — {name}")
        embed = discord.Embed(
            title=f"Opening: {result['pack_name']}",
            description="\n".join(lines),
            color=0x2C2F33,
            timestamp=datetime.now(UTC),
        )
        embed.set_footer(text="bruh.bot")
        if pack_def:
            stats = await self.bot.trading_card_service.get_collection_stats(interaction.guild.id, interaction.user.id, set_id=pack_def.series_id)
            embed.add_field(name="Collection", value=f"{stats['unique_cards']}/{stats['series_total']} {set_display} ({stats['completion_pct']}%)", inline=True)
        embed.add_field(name="Total Cards", value=str(len(result["card_ids"])), inline=True)
        await interaction.followup.send(embed=embed, ephemeral=True)

    @bruh_cards_group.command(name="collection", description="View your or another user's trading cards from a specific set.")
    @app_commands.describe(set_id="The card set to view", user="User to view (defaults to you)", rarity="Filter by rarity")
    @app_commands.autocomplete(set_id=set_id_autocomplete)
    @app_commands.choices(rarity=[app_commands.Choice(name=r.value.title(), value=r.value) for r in TradingCardRarity])
    @log_command_usage()
    @is_globally_blocked()
    async def bruh_cards_collection(self, interaction: discord.Interaction, set_id: str, user: discord.Member | None = None, rarity: str | None = None):
        await interaction.response.defer()
        target = user or interaction.user
        set_display = set_id.replace("_", " ").title()
        set_total = self.bot.trading_card_catalog_service.get_series_total(set_id)
        if set_total == 0:
            embed = self.bot.embed_service.create_error_embed(f"No cards found for set `{set_id}`.")
            return await interaction.followup.send(embed=embed, ephemeral=True, files=self.bot.embed_service.get_brand_files(embed=embed))

        stats = await self.bot.trading_card_service.get_collection_stats(interaction.guild.id, target.id, set_id=set_id)
        if stats["total_cards"] == 0:
            embed = self.bot.embed_service._create_base_embed(
                title=f"{target.display_name}'s Collection — {set_display}",
                description=f"No cards from {set_display} yet.\nBuy packs with `/bruh-cards inventory`.",
            )
            embed.set_thumbnail(url=target.display_avatar.url)
            return await interaction.followup.send(embed=embed)

        lines = []
        for entry in stats["cards"]:
            card = self.bot.trading_card_catalog_service.get_card(entry["card_id"])
            if not card:
                continue
            if card.series_id != set_id:
                continue
            if rarity and card.rarity.value != rarity:
                continue
            qty = entry.get("quantity", 1)
            display_rarity = card.rarity.value.title() if not rarity else None
            extra = f" · {display_rarity}" if display_rarity else ""
            lines.append(f"{TC_EMOJI.get(card.rarity, '')} **#{card.number} {card.name}**{extra}{' x' + str(qty) if qty > 1 else ''}")

        truncated = len(lines) > 20
        lines = lines[:20]

        rarity_summary = " · ".join(f"{TC_EMOJI.get(r, '')} {count}" for r, count in stats["rarity_counts"].items() if count > 0)
        embed = self.bot.embed_service._create_base_embed(
            title=f"{target.display_name}'s Collection — {set_display}",
            description="\n".join(lines) if lines else "No cards matching filters.",
        )
        embed.set_thumbnail(url=target.display_avatar.url)
        footer_parts = [f"{stats['unique_cards']}/{set_total} unique"]
        if truncated:
            total_unique = len([e for e in stats["cards"] if self.bot.trading_card_catalog_service.get_card(e["card_id"]) and self.bot.trading_card_catalog_service.get_card(e["card_id"]).series_id == set_id])
            footer_parts.append(f"showing 20 of {total_unique} cards")
        embed.set_footer(text=f"bruh.bot · {' · '.join(footer_parts)}")
        embed.insert_field_at(0, name=f"Overview ({stats['unique_cards']}/{set_total} · {stats['completion_pct']}%)", value=rarity_summary, inline=False)
        embed.add_field(name="Total Cards", value=str(stats["total_cards"]), inline=True)
        embed.add_field(name="Unopened Packs", value=str(sum(p.get("quantity", 1) for p in stats["unopened_packs"])), inline=True)
        await interaction.followup.send(embed=embed)

    @bruh_cards_group.command(name="show-collection", description="Show off your collected cards from a set as a grid image!")
    @app_commands.describe(set_id="The collection to show", user="Who to show (defaults to you)")
    @app_commands.autocomplete(set_id=set_id_autocomplete)
    @log_command_usage()
    @is_globally_blocked()
    async def bruh_cards_show_collection(self, interaction: discord.Interaction, set_id: str, user: discord.Member | None = None):
        await interaction.response.defer()
        target = user or interaction.user
        stats = await self.bot.trading_card_service.get_collection_stats(interaction.guild.id, target.id, set_id=set_id)
        owned_cards = stats.get("cards", [])
        if not owned_cards:
            owners = "your" if target.id == interaction.user.id else f"{target.display_name}'s"
            set_display = set_id.replace("_", " ").title()
            embed = self.bot.embed_service._create_base_embed(
                title=f"{target.display_name}'s {set_display} Collection",
                description=f"No cards from {set_display} in {owners} collection yet.",
            )
            embed.set_thumbnail(url=target.display_avatar.url)
            return await interaction.followup.send(embed=embed, files=self.bot.embed_service.get_brand_files(embed=embed))

        card_ids = [c["card_id"] for c in owned_cards]
        grid_buf = await self.bot.trading_card_render_service.render_collection_grid(card_ids)
        set_display = set_id.replace("_", " ").title()
        completion = f"{stats['unique_cards']}/{stats['series_total']} ({stats['completion_pct']}%)"

        if grid_buf:
            file = discord.File(grid_buf, filename="collection.png")
            embed = self.bot.embed_service._create_base_embed(
                title=f"{target.display_name}'s {set_display} Collection",
                description=f"{completion} complete",
            )
            embed.set_image(url="attachment://collection.png")
            embed.set_thumbnail(url=target.display_avatar.url)
            await interaction.followup.send(embed=embed, file=file)
        else:
            embed = self.bot.embed_service._create_base_embed(
                title=f"{target.display_name}'s {set_display} Collection",
                description=f"{completion} complete — no card art available.",
            )
            embed.set_thumbnail(url=target.display_avatar.url)
            await interaction.followup.send(embed=embed)

    @bruh_cards_group.command(name="leaderboard", description="Card collection leaderboard weighted by rarity.")
    @app_commands.describe(limit="How many users to show (max 25)")
    @log_command_usage()
    @is_globally_blocked()
    async def bruh_cards_leaderboard(self, interaction: discord.Interaction, limit: app_commands.Range[int, 1, 25] = 10):
        await interaction.response.defer()
        entries = await self.bot.trading_card_service.get_collection_leaderboard(interaction.guild.id, limit=limit)
        if not entries:
            return await interaction.followup.send(
                embed=self.bot.embed_service.create_info_embed(
                    title="Card Collection Leaderboard",
                    description="No one has collected any cards yet! Open some packs with `/bruh-cards open`.",
                ),
                files=self.bot.embed_service.get_brand_files(),
            )

        lines = []
        for i, entry in enumerate(entries, 1):
            member = interaction.guild.get_member(int(entry["user_id"]))
            name = member.display_name if member else f"User {entry['user_id']}"
            medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"`#{i}`"
            lines.append(f"{medal} **{name}** — 🏆 {entry['weighted_score']:,.2f} pts · {entry['total_cards']} cards")

        embed = self.bot.embed_service._create_base_embed(
            title="🏆 Card Collector Leaderboard",
            description="\n".join(lines),
        )
        top_member = interaction.guild.get_member(int(entries[0]["user_id"]))
        if top_member:
            embed.set_thumbnail(url=top_member.display_avatar.url)
        embed.add_field(
            name="Rarity Points",
            value="💫 24,500 · 💠 6,600 · 🟠 1,800 · 🟣 375 · 🔵 60 · 🟢 12 · ⬜ 2.4",
            inline=False,
        )
        embed.set_footer(text="Duplicates count! Each copy multiplies the rarity score.")
        await interaction.followup.send(embed=embed, files=self.bot.embed_service.get_brand_files(embed=embed))

    @app_commands.autocomplete(card_id=card_id_autocomplete)
    @bruh_cards_group.command(name="inspect", description="Show a trading card to the server with its image.")
    @app_commands.describe(card_id="The card to show")
    @app_commands.autocomplete(card_id=card_id_autocomplete)
    @log_command_usage()
    @is_globally_blocked()
    async def bruh_cards_inspect(self, interaction: discord.Interaction, card_id: str):
        await interaction.response.defer()
        card = self.bot.trading_card_catalog_service.get_card(card_id)
        if not card:
            return await interaction.followup.send(embed=_coins_embed("Not Found", f"No card with ID `{card_id}`."), ephemeral=True)
        owned = await self.bot.trading_card_service.get_card_quantity(interaction.guild.id, interaction.user.id, card_id)
        if owned == 0:
            return await interaction.followup.send(
                embed=_coins_embed("Not Owned", "You don't own this card yet. Open packs to collect it!"),
                ephemeral=True,
            )
        image_buffer = await self.bot.trading_card_render_service.render_card(card_id)
        color = RARITY_DISCORD_COLORS.get(card.rarity, 0x5865F2)
        embed = discord.Embed(
            title=f"#{card.number} {card.name}",
            description=f"*{interaction.user.display_name} is showing a card from their collection.*\n\n{card.description}",
            color=color,
            timestamp=datetime.now(UTC),
        )
        embed.set_footer(text="Use /bruh-cards inventory to open packs and build your collection!")
        embed.add_field(name="Rarity", value=f"{TC_EMOJI.get(card.rarity, '')} {card.rarity.value.title()}", inline=True)
        embed.add_field(name="Series", value=card.series_id.replace("_", " ").title(), inline=True)
        embed.add_field(name="Owned", value=f"{owned}x", inline=True)
        embed.add_field(name="Sellback", value=f"🪙 {card.sellback_value:,.2f}", inline=True)
        files = self.bot.embed_service.get_brand_files(embed=embed)
        if image_buffer:
            file = discord.File(image_buffer, filename="card.png")
            embed.set_image(url="attachment://card.png")
            files.append(file)
        await interaction.followup.send(embed=embed, files=files)

    @bruh_cards_group.command(name="sell", description="Sell a trading card for coins.")
    @app_commands.describe(card_id="The card to sell", quantity="How many to sell")
    @app_commands.autocomplete(card_id=card_id_autocomplete)
    @log_command_usage()
    @is_globally_blocked()
    async def bruh_cards_sell(self, interaction: discord.Interaction, card_id: str, quantity: app_commands.Range[int, 1, 100] = 1):
        await interaction.response.defer(ephemeral=True)
        result = await self.bot.trading_card_service.sell_cards(interaction.guild.id, interaction.user.id, card_id, quantity)
        if not result["success"]:
            return await interaction.followup.send(embed=_coins_embed("Cannot Sell", result["error"]), ephemeral=True)
        embed = _coins_embed(
            "Cards Sold",
            f"Sold **{quantity}x {result['card_name']}** for 🪙 {result['value']:,.2f}\nNew balance: **🪙 {result['balance']:,.2f}**",
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

    # ═══════════════════════════════════════════════════════════════
    # /card-trade  (independent trading card trade subgroup)
    # ═══════════════════════════════════════════════════════════════
    card_trade_group = app_commands.Group(name="bruh-card-trade", description="Trade bruh.cards!")

    @card_trade_group.command(name="offer", description="Offer a trading card trade.")
    @app_commands.describe(
        user="User to trade with",
        give_cards="Card IDs to give (comma-separated)",
        want_cards="Card IDs you want (comma-separated)",
        give_coins="Coins to give",
        want_coins="Coins you want",
    )
    @log_command_usage()
    @is_globally_blocked()
    async def card_trade_offer(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        give_cards: str = "",
        want_cards: str = "",
        give_coins: int = 0,
        want_coins: int = 0,
    ):
        await interaction.response.defer(ephemeral=True)
        config = await self.bot.config_service.get_config(str(interaction.guild.id))
        if not config.economyConfig.tradingCardTradingEnabled:
            return await interaction.followup.send(embed=_coins_embed("Trading Disabled", "Card trading is disabled."), ephemeral=True)
        if interaction.user.id == user.id:
            return await interaction.followup.send(embed=_coins_embed("Invalid", "Can't trade with yourself."), ephemeral=True)

        give_list = [c.strip() for c in give_cards.split(",") if c.strip()]
        want_list = [c.strip() for c in want_cards.split(",") if c.strip()]

        if not any([give_list, want_list, give_coins > 0, want_coins > 0]):
            return await interaction.followup.send(embed=_coins_embed("Empty Trade", "Specify at least one card or coin."), ephemeral=True)

        for cid in give_list:
            qty = await self.bot.trading_card_service.get_card_quantity(interaction.guild.id, interaction.user.id, cid)
            c = self.bot.trading_card_catalog_service.get_card(cid)
            if qty < 1:
                return await interaction.followup.send(embed=_coins_embed("Invalid", f"You don't own **{c.name if c else cid}**."), ephemeral=True)

        if give_coins > 0:
            profile = await self.bot.economy_service.get_profile(interaction.guild.id, interaction.user.id)
            if profile["bruh_coins"] < give_coins:
                return await interaction.followup.send(embed=_coins_embed("Invalid", f"Only 🪙 {profile['bruh_coins']:.2f}."), ephemeral=True)

        trade_id = uuid.uuid4().hex[:12]

        def _fmt(card_ids: list[str], coins: int) -> str:
            lines = []
            for cid in card_ids:
                c = self.bot.trading_card_catalog_service.get_card(cid)
                lines.append(f"- {TC_EMOJI.get(c.rarity, '')} **{c.name if c else cid}**")
            if coins > 0:
                lines.append(f"- 🪙 **{coins:,}**")
            return "\n".join(lines) if lines else "*Nothing*"

        embed = discord.Embed(
            title=f"Card Trade from {interaction.user.display_name}",
            description=f"**Gives:**\n{_fmt(give_list, give_coins)}\n\n**Wants:**\n{_fmt(want_list, want_coins)}",
            color=0xFEE75C,
            timestamp=datetime.now(UTC),
        )
        embed.set_footer(text=f"bruh.bot · Trade ID: {trade_id}")

        view = TradeConfirmView(trade_id, interaction.user.id, user.id)
        await interaction.followup.send(embed=embed, ephemeral=True)
        await interaction.followup.send(f"{user.mention}, {interaction.user.display_name} wants to trade cards!", embed=embed, view=view)
        await view.wait()

        if view.accepted:
            if give_coins > 0:
                await self.bot.economy_service.deduct_coins(interaction.guild.id, interaction.user.id, give_coins)
                await self.bot.economy_service.record_transaction(interaction.guild.id, interaction.user.id, "card_trade_debit", -give_coins, 0.0, reference_type="card_trade", reference_id=trade_id)
            if want_coins > 0:
                s, _ = await self.bot.economy_service.deduct_coins(interaction.guild.id, user.id, want_coins)
                if not s:
                    return await interaction.followup.send(embed=_coins_embed("Failed", f"{user.display_name} doesn't have enough coins."))
                await self.bot.economy_service.add_coins(interaction.guild.id, interaction.user.id, want_coins)
            if give_coins > 0:
                await self.bot.economy_service.add_coins(interaction.guild.id, user.id, give_coins)
            for cid in give_list:
                await self.bot.trading_card_service.remove_cards(interaction.guild.id, interaction.user.id, cid, 1)
                await self.bot.trading_card_service.add_cards(interaction.guild.id, user.id, [cid])
            for cid in want_list:
                await self.bot.trading_card_service.remove_cards(interaction.guild.id, user.id, cid, 1)
                await self.bot.trading_card_service.add_cards(interaction.guild.id, interaction.user.id, [cid])
            await interaction.followup.send(embed=_coins_embed("Trade Complete!", f"Trade between {interaction.user.mention} and {user.mention} done!"))
        else:
            await interaction.followup.send(embed=_coins_embed("Declined", "Trade declined or expired."))

    # ═══════════════════════════════════════════════════════════════
    # /market  (trading card marketplace subgroup)
    # ═══════════════════════════════════════════════════════════════
    market_group = app_commands.Group(name="bruh-card-market", description="Void Archive card marketplace!")

    @market_group.command(name="list", description="List a trading card for sale on the market.")
    @app_commands.describe(card_id="Card ID", quantity="Quantity", price_each="Price per card")
    @log_command_usage()
    @is_globally_blocked()
    async def market_list(self, interaction: discord.Interaction, card_id: str, quantity: int, price_each: float):
        await interaction.response.defer(ephemeral=True)
        result = await self.bot.card_market_service.list_card(interaction.guild.id, interaction.user.id, card_id, quantity, price_each)
        if not result["success"]:
            return await interaction.followup.send(embed=_coins_embed("Cannot List", result["error"]), ephemeral=True)
        await interaction.followup.send(
            embed=_coins_embed(
                "Listed!",
                f"**{quantity}x {result['card_name']}** at 🪙 {price_each:,.2f} each\nListing ID: `{result['listing_id']}`\nExpires in 72h.",
            ),
            ephemeral=True,
        )

    @market_group.command(name="browse", description="Browse active market listings.")
    @app_commands.describe(rarity="Filter by rarity", seller="Filter by seller")
    @app_commands.choices(rarity=[app_commands.Choice(name=r.value.title(), value=r.value) for r in TradingCardRarity])
    @log_command_usage()
    @is_globally_blocked()
    async def market_browse(self, interaction: discord.Interaction, rarity: str | None = None, seller: discord.Member | None = None):
        await interaction.response.defer(ephemeral=True)
        seller_id = seller.id if seller else None
        result = await self.bot.card_market_service.browse(
            interaction.guild.id,
            rarity=rarity,
            seller_id=seller_id,
        )
        if not result["listings"]:
            return await interaction.followup.send(embed=_coins_embed("Market", "No active listings found."), ephemeral=True)
        lines = []
        for listing in result["listings"]:
            seller_member = interaction.guild.get_member(listing["seller_id"])
            seller_name = seller_member.display_name if seller_member else f"User {listing['seller_id']}"
            lines.append(f"{TC_EMOJI.get(TradingCardRarity(listing['rarity']), '')} **{listing['card_name']}** · 🪙 {listing['price_each']:,.2f} x{listing['quantity_remaining']}\n　Seller: {seller_name} · ID: `{listing['listing_id']}`")
        embed = self.bot.embed_service._create_base_embed(
            title=f"Card Market (Page {result['page'] + 1}/{result['pages']})",
            description="\n\n".join(lines),
        )
        embed.add_field(name="Buy", value="Use `/market buy <listing_id> [qty]`", inline=False)
        await interaction.followup.send(embed=embed, ephemeral=True)

    @market_group.command(name="buy", description="Buy a market listing.")
    @app_commands.describe(listing_id="Listing ID to buy", quantity="How many to buy (all if omitted)")
    @log_command_usage()
    @is_globally_blocked()
    async def market_buy(self, interaction: discord.Interaction, listing_id: str, quantity: int = 0):
        await interaction.response.defer(ephemeral=True)
        result = await self.bot.card_market_service.buy(interaction.guild.id, interaction.user.id, listing_id, quantity)
        if not result["success"]:
            return await interaction.followup.send(embed=_coins_embed("Purchase Failed", result["error"]), ephemeral=True)
        tax_note = f"\n*(Tax: 🪙 {result.get('tax_amount', 0):.2f})*" if result.get("tax_amount", 0) > 0 else ""
        await interaction.followup.send(
            embed=_coins_embed(
                "Purchase Complete!",
                f"Bought **{result['quantity']}x {result['card_name']}** at 🪙 {result['price_each']:,.2f} each\nTotal: 🪙 {result['total_cost']:,.2f}{tax_note}",
            ),
            ephemeral=True,
        )

    @market_group.command(name="cancel", description="Cancel your market listing.")
    @app_commands.describe(listing_id="Listing ID to cancel")
    @log_command_usage()
    @is_globally_blocked()
    async def market_cancel(self, interaction: discord.Interaction, listing_id: str):
        await interaction.response.defer(ephemeral=True)
        result = await self.bot.card_market_service.cancel_listing(interaction.guild.id, interaction.user.id, listing_id)
        if not result["success"]:
            return await interaction.followup.send(embed=_coins_embed("Cannot Cancel", result["error"]), ephemeral=True)
        await interaction.followup.send(
            embed=_coins_embed("Cancelled", f"Returned **{result['quantity_returned']}x {result['card_name']}** to your collection."),
            ephemeral=True,
        )

    @market_group.command(name="mine", description="View your active market listings.")
    @log_command_usage()
    @is_globally_blocked()
    async def market_mine(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        listings = await self.bot.card_market_service.get_seller_listings(interaction.guild.id, interaction.user.id)
        if not listings:
            return await interaction.followup.send(embed=_coins_embed("Your Listings", "You have no active listings."), ephemeral=True)
        lines = []
        for listing in listings:
            lines.append(f"`{listing['listing_id']}` — **{listing['card_name']}** · 🪙 {listing['price_each']:,.2f} x{listing['quantity_remaining']}")
        await interaction.followup.send(embed=_coins_embed("Your Listings", "\n".join(lines)), ephemeral=True)

    # ═══════════════════════════════════════════════════════════════
    # /economy trading card admin commands
    # ═══════════════════════════════════════════════════════════════
    # /bruh-cards-admin  (admin group)
    # ═══════════════════════════════════════════════════════════════
    bruh_cards_admin_group = app_commands.Group(name="bruh-cards-admin", description="Admin tools for bruh.cards!")

    @bruh_cards_admin_group.command(name="grant", description="Give trading cards to a user.")
    @app_commands.describe(user="The user", card_id="Card ID", quantity="How many")
    @log_command_usage()
    @is_admin()
    @is_globally_blocked()
    async def bruh_cards_admin_grant(self, interaction: discord.Interaction, user: discord.Member, card_id: str, quantity: int = 1):
        card = self.bot.trading_card_catalog_service.get_card(card_id)
        if not card:
            embed = self.bot.embed_service.create_error_embed(f"No card found with ID `{card_id}`.")
            return await interaction.followup.send(embed=embed, ephemeral=True, files=self.bot.embed_service.get_brand_files(embed=embed))
        await self.bot.trading_card_service.add_cards(interaction.guild.id, user.id, [card_id] * quantity)
        embed = self.bot.embed_service.create_success_embed(
            f"Gave **{quantity}x {TC_EMOJI.get(card.rarity, '')} {card.name}** to **{user.display_name}**.",
            title="Cards Granted",
        )
        await interaction.followup.send(embed=embed, ephemeral=True, files=self.bot.embed_service.get_brand_files(embed=embed))

    @bruh_cards_admin_group.command(name="grant-pack", description="Give trading card packs to a user.")
    @app_commands.describe(user="The user", pack_id="Pack type", quantity="How many")
    @app_commands.choices(
        pack_id=[
            app_commands.Choice(name="Void Archive Pack", value="void_archive_standard"),
            app_commands.Choice(name="Void Archive Premium", value="void_archive_premium"),
        ]
    )
    @log_command_usage()
    @is_admin()
    @is_globally_blocked()
    async def bruh_cards_admin_grant_pack(self, interaction: discord.Interaction, user: discord.Member, pack_id: str, quantity: int = 1):
        await self.bot.trading_card_service.add_packs(interaction.guild.id, user.id, pack_id, quantity)
        pk = self.bot.trading_card_catalog_service.get_all_packs().get(pack_id, {})
        name = pk.name if pk else pack_id
        embed = self.bot.embed_service.create_success_embed(f"Gave **{quantity}x {name}** to **{user.display_name}**.", title="Packs Granted")
        await interaction.followup.send(embed=embed, ephemeral=True, files=self.bot.embed_service.get_brand_files(embed=embed))

    @bruh_cards_admin_group.command(name="inspect", description="Inspect a user's trading card collection.")
    @app_commands.describe(user="The user")
    @log_command_usage()
    @is_admin()
    @is_globally_blocked()
    async def bruh_cards_admin_inspect(self, interaction: discord.Interaction, user: discord.Member):
        stats = await self.bot.trading_card_service.get_collection_stats(interaction.guild.id, user.id)
        card_lines = []
        for entry in stats["cards"]:
            card = self.bot.trading_card_catalog_service.get_card(entry["card_id"])
            if card:
                card_lines.append(f"- {TC_EMOJI.get(card.rarity, '')} {card.name} x{entry.get('quantity', 1)}")
        embed = self.bot.embed_service._create_base_embed(title=f"Card Collection — {user.display_name}")
        embed.set_thumbnail(url=user.display_avatar.url)
        embed.add_field(name="Cards", value="\n".join(card_lines[:15]) or "None", inline=False)
        embed.add_field(name="Total", value=str(stats["total_cards"]), inline=True)
        embed.add_field(name="Unique", value=f"{stats['unique_cards']}/{stats['series_total']}", inline=True)
        embed.add_field(name="Packs", value=str(sum(p.get("quantity", 1) for p in stats["unopened_packs"])), inline=True)
        await interaction.followup.send(embed=embed, ephemeral=True, files=self.bot.embed_service.get_brand_files(embed=embed))

    @bruh_cards_admin_group.command(name="reset", description="Reset a user's trading card collection.")
    @app_commands.describe(user="The user")
    @log_command_usage()
    @is_admin()
    @is_globally_blocked()
    async def bruh_cards_admin_reset(self, interaction: discord.Interaction, user: discord.Member):
        await self.bot.trading_card_service.reset_collection(interaction.guild.id, user.id)
        embed = self.bot.embed_service.create_success_embed(f"**{user.display_name}**'s trading card collection has been reset.", title="Collection Reset")
        await interaction.followup.send(embed=embed, ephemeral=True, files=self.bot.embed_service.get_brand_files(embed=embed))

    @bruh_cards_admin_group.command(name="toggle", description="Toggle trading card features.")
    @app_commands.describe(feature="Feature", enabled="Enable/disable")
    @app_commands.choices(
        feature=[
            app_commands.Choice(name="Card Packs", value="tradingCardPacksEnabled"),
            app_commands.Choice(name="Card Trading", value="tradingCardTradingEnabled"),
            app_commands.Choice(name="Card Market", value="tradingCardMarketEnabled"),
        ]
    )
    @log_command_usage()
    @is_admin()
    @is_globally_blocked()
    async def bruh_cards_admin_toggle(self, interaction: discord.Interaction, feature: str, enabled: bool):
        guild_id = str(interaction.guild.id)
        config = await self.bot.config_service.get_config(guild_id)
        econ = config.economyConfig.model_dump()
        econ[feature] = enabled
        await self.bot.config_service.update(guild_id, {"economyConfig": econ})
        label = feature.replace("tradingCard", "").replace("trading", "").replace("Enabled", "")
        status = "enabled" if enabled else "disabled"
        embed = self.bot.embed_service.create_success_embed(f"**{label or feature}** has been **{status}**.", title="Feature Toggled")
        await interaction.followup.send(embed=embed, ephemeral=True, files=self.bot.embed_service.get_brand_files(embed=embed))

    @bruh_cards_admin_group.command(name="reload", description="Reload the trading card catalog from MongoDB.")
    @log_command_usage()
    @is_admin()
    @is_globally_blocked()
    async def bruh_cards_admin_reload(self, interaction: discord.Interaction):
        await self.bot.trading_card_catalog_service.reload_catalog()
        self.bot.trading_card_render_service.invalidate_cache()
        c = self.bot.trading_card_catalog_service
        sets = c.get_series_list()
        lines = []
        for sid in sorted(sets):
            ct = c.get_series_total(sid)
            pk_ct = len(c.get_packs_by_series(sid))
            lines.append(f"**{sid.replace('_', ' ').title()}**: {ct} cards, {pk_ct} packs")
        embed = self.bot.embed_service.create_success_embed(
            "Catalog reloaded!\n\n" + "\n".join(lines),
            title="Catalog Reloaded",
        )
        await interaction.followup.send(embed=embed, ephemeral=True, files=self.bot.embed_service.get_brand_files(embed=embed))

    @bruh_cards_admin_group.command(name="announce-set", description="Announce a trading card set with pack info and sample cards.")
    @app_commands.describe(set_id="The card set to announce", channel="The channel to announce in")
    @app_commands.autocomplete(set_id=set_id_autocomplete)
    @log_command_usage()
    @is_admin()
    @is_globally_blocked()
    async def bruh_cards_admin_announce_set(self, interaction: discord.Interaction, set_id: str, channel: discord.TextChannel):
        c = self.bot.trading_card_catalog_service
        cards = c.get_cards_by_series(set_id)
        if not cards:
            embed = self.bot.embed_service.create_error_embed(f"No released cards found for set `{set_id}`.")
            return await interaction.followup.send(embed=embed, ephemeral=True, files=self.bot.embed_service.get_brand_files(embed=embed))
        packs = c.get_packs_by_series(set_id)
        if not packs:
            embed = self.bot.embed_service.create_error_embed(f"No released packs found for set `{set_id}`.")
            return await interaction.followup.send(embed=embed, ephemeral=True, files=self.bot.embed_service.get_brand_files(embed=embed))

        eligible = [
            card
            for card in cards
            if card.rarity
            in (
                TradingCardRarity.BASIC,
                TradingCardRarity.COMMON,
                TradingCardRarity.RARE,
                TradingCardRarity.EPIC,
                TradingCardRarity.LEGENDARY,
            )
        ]
        if not eligible:
            eligible = cards
        sample_count = min(3, len(eligible))
        samples = random.sample(eligible, sample_count)

        set_display = set_id.replace("_", " ").title()

        pack_lines = []
        for pk in packs.values():
            guaranteed = pk.guaranteed_rarity
            g_text = f"Guaranteed: **{guaranteed.value.title()}**+" if guaranteed else "No guaranteed rarity"
            pack_lines.append(f"**{pk.name}** — 🪙 {pk.price:,}\n{pk.description}\n{g_text} · {pk.cards_per_pack} cards per pack\nBuy: `/bruh-cards buy-pack {pk.pack_id}`")

        overview_embed = self.bot.embed_service._create_base_embed(
            title=f"🃏 New Card Set: {set_display}",
            description=f"Check out the brand-new **{set_display}** collection!\n\n" + "\n\n".join(pack_lines),
        )
        overview_embed.add_field(
            name="How to Get Started",
            value="Open your collection with `/bruh-cards inventory`",
            inline=False,
        )

        sample_embeds = []
        files = self.bot.embed_service.get_brand_files(embed=overview_embed)
        for i, card in enumerate(samples):
            image_buffer = await self.bot.trading_card_render_service.render_card(card.card_id)
            color = RARITY_DISCORD_COLORS.get(card.rarity, 0x5865F2)
            sample_embed = discord.Embed(
                title=f"#{card.number} {card.name}",
                description=card.description or "",
                color=color,
            )
            sample_embed.add_field(name="Rarity", value=f"{TC_EMOJI.get(card.rarity, '')} {card.rarity.value.title()}", inline=True)
            sample_embed.add_field(name="Set", value=set_display, inline=True)
            if image_buffer:
                filename = f"sample-{i + 1}.png"
                file = discord.File(image_buffer, filename=filename)
                sample_embed.set_image(url=f"attachment://{filename}")
                files.append(file)
            sample_embeds.append(sample_embed)

        embeds = [overview_embed] + sample_embeds
        try:
            await channel.send(embeds=embeds, files=files)
        except discord.Forbidden:
            embed = self.bot.embed_service.create_error_embed(f"I don't have permission to send messages in {channel.mention}.")
            return await interaction.followup.send(embed=embed, ephemeral=True, files=self.bot.embed_service.get_brand_files(embed=embed))

        success_embed = self.bot.embed_service.create_success_embed(
            f"Set `{set_id}` announced in {channel.mention}!",
            title="Set Announced",
        )
        await interaction.followup.send(
            embed=success_embed,
            ephemeral=True,
            files=self.bot.embed_service.get_brand_files(embed=success_embed),
        )


async def setup(bot: "BruhBot"):
    await bot.add_cog(EconomyCog(bot))
