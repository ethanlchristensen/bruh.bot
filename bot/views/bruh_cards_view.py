from datetime import UTC, datetime
from typing import TYPE_CHECKING

import discord

from bot.data.trading_card_models import RARITY_DISPLAY_EMOJI, TradingCardRarity

if TYPE_CHECKING:
    from bot.bruh_bot import BruhBot

CARDS_PER_PAGE = 8
MARKET_PER_PAGE = 6
VIEW_TIMEOUT = 600


def _rarity_emoji(rarity: TradingCardRarity | str) -> str:
    if isinstance(rarity, str):
        try:
            rarity = TradingCardRarity(rarity)
        except ValueError:
            return ""
    return RARITY_DISPLAY_EMOJI.get(rarity, "")


class BruhCardsInventoryView(discord.ui.View):
    def __init__(self, bot: "BruhBot", guild_id: int, user_id: int):
        super().__init__(timeout=VIEW_TIMEOUT)
        self.bot = bot
        self.guild_id = guild_id
        self.user_id = user_id
        self.screen: str = "dashboard"
        self.binder_page: int = 0
        self.binder_rarity: str | None = None
        self.market_page: int = 0
        self.market_rarity: str | None = None
        self.market_selected: str | None = None
        self.catalog_page: int = 0
        self.catalog_rarity: str | None = None
        self._stats = None
        self._owned_packs = None

    @property
    def _catalog(self):
        return self.bot.trading_card_catalog_service

    def _is_caller(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.user_id

    async def _check_owner(self, interaction: discord.Interaction) -> bool:
        if not self._is_caller(interaction):
            await interaction.response.send_message("This is not your inventory.", ephemeral=True)
            return False
        if not await self._is_enabled():
            await interaction.response.send_message("bruh.cards is not enabled for this server.", ephemeral=True)
            return False
        return True

    async def _is_enabled(self) -> bool:
        from bot.cogs.economy_cog import is_bruh_cards_enabled

        return await is_bruh_cards_enabled(self.bot, self.guild_id)

    async def _refresh_data(self):
        self._stats = await self.bot.trading_card_service.get_collection_stats(self.guild_id, self.user_id)
        self._owned_packs = self._stats.get("unopened_packs", [])

    def _dashboard_embed(self) -> discord.Embed:
        s = self._stats
        packs = self._owned_packs

        set_lines = []
        for sid, count in s.get("set_counts", {}).items():
            set_total = self._catalog.get_series_total(sid)
            set_pct = round(count / set_total * 100, 1) if set_total else 0
            display = sid.replace("_", " ").title()
            set_lines.append(f"**{display}**: {count}/{set_total} ({set_pct}%)")

        pack_lines = []
        for p in packs:
            pk = self._catalog.get_pack(p["pack_id"])
            name = pk.name if pk else p["pack_id"]
            pack_lines.append(f"• **{name}** x{p.get('quantity', 1)}")

        desc_parts = []
        if set_lines:
            desc_parts.append("\n".join(set_lines))
        if pack_lines:
            desc_parts.append("\n**Unopened Packs**\n" + "\n".join(pack_lines))

        embed = discord.Embed(
            title="bruh.cards Vault",
            description="\n".join(desc_parts) if desc_parts else "No cards or packs yet.",
            color=0x2C2F33,
            timestamp=datetime.now(UTC),
        )
        embed.set_footer(text="bruh.bot · bruh.cards")
        embed.add_field(name="Cards", value=f"{s['unique_cards']} unique · {s['total_cards']} total", inline=True)
        embed.add_field(name="Overall", value=f"{s['completion_pct']}%", inline=True)
        return embed

    def _collection_page_embed(self) -> discord.Embed:
        s = self._stats
        cards = s.get("cards", [])
        filtered = []
        for entry in cards:
            card = self._catalog.get_card(entry["card_id"])
            if not card:
                continue
            if self.binder_rarity and card.rarity.value != self.binder_rarity:
                continue
            filtered.append((card, entry.get("quantity", 1)))

        total_pages = max(1, (len(filtered) - 1) // CARDS_PER_PAGE + 1)
        start = self.binder_page * CARDS_PER_PAGE
        page_items = filtered[start : start + CARDS_PER_PAGE]

        lines = []
        for card, qty in page_items:
            lines.append(f"{_rarity_emoji(card.rarity)} **#{card.number} {card.name}**{' x' + str(qty) if qty > 1 else ''}")

        rarity_label = f" · {self.binder_rarity.title()}" if self.binder_rarity else ""
        embed = discord.Embed(
            title=f"Collection{rarity_label}",
            description="\n".join(lines) if lines else "No cards matching filter.",
            color=0x2C2F33,
            timestamp=datetime.now(UTC),
        )
        embed.set_footer(text=f"bruh.bot · Page {self.binder_page + 1}/{total_pages} · {s['unique_cards']} unique owned")
        return embed

    def _shop_embed(self) -> discord.Embed:
        packs = self._catalog.get_all_packs()
        lines = []
        for pk in packs.values():
            g = pk.guaranteed_rarity
            g_text = f"Guaranteed: **{g.value.title()}**+" if g else "No guarantee"
            set_display = pk.series_id.replace("_", " ").title()
            lines.append(f"**{pk.name}** ({set_display}) — 🪙 {pk.price:,}\n　{pk.description}\n　{g_text} · {pk.cards_per_pack} cards")
        embed = discord.Embed(
            title="Card Pack Shop",
            description="\n\n".join(lines) if lines else "No packs available.",
            color=0x2C2F33,
            timestamp=datetime.now(UTC),
        )
        embed.set_footer(text="bruh.bot · bruh.cards")
        return embed

    def _market_embed(self, listings: list[dict], total: int) -> discord.Embed:
        total_pages = max(1, (total - 1) // MARKET_PER_PAGE + 1)
        lines = []
        for entry in listings:
            set_label = ""
            card = self._catalog.get_card(entry["card_id"])
            if card:
                set_label = f" · {card.series_id.replace('_', ' ').title()}"
            lines.append(f"{_rarity_emoji(entry['rarity'])} **{entry['card_name']}**{set_label} · 🪙 {entry['price_each']:,.2f} x{entry['quantity_remaining']}\n　Seller ID: `{entry['seller_id']}` · Listing: `{entry['listing_id']}`")
        rarity_label = f" · {self.market_rarity.title()}" if self.market_rarity else ""
        embed = discord.Embed(
            title=f"Card Market{rarity_label}",
            description="\n\n".join(lines) if lines else "No active listings.",
            color=0x2C2F33,
            timestamp=datetime.now(UTC),
        )
        embed.set_footer(text=f"bruh.bot · Page {self.market_page + 1}/{total_pages}")
        return embed

    def _catalog_embed(self) -> discord.Embed:
        all_cards = self._catalog.get_all_released_cards()
        owned_ids = {c["card_id"]: c.get("quantity", 1) for c in (self._stats.get("cards", []) if self._stats else [])}

        if self.catalog_rarity:
            try:
                r = TradingCardRarity(self.catalog_rarity)
                all_cards = [c for c in all_cards if c.rarity == r]
            except ValueError:
                pass

        total_pages = max(1, (len(all_cards) - 1) // CARDS_PER_PAGE + 1)
        start = self.catalog_page * CARDS_PER_PAGE
        page_items = all_cards[start : start + CARDS_PER_PAGE]

        lines = []
        for card in page_items:
            qty = owned_ids.get(card.card_id, 0)
            set_label = card.series_id.replace("_", " ").title()
            own_str = f" x{qty}" if qty > 0 else " 🔒"
            lines.append(f"{_rarity_emoji(card.rarity)} **#{card.number} {card.name}** ({set_label}){own_str}")

        rarity_label = f" · {self.catalog_rarity.title()}" if self.catalog_rarity else ""
        embed = discord.Embed(
            title=f"Card Catalog{rarity_label}",
            description="\n".join(lines) if lines else "No cards match filter.",
            color=0x2C2F33,
            timestamp=datetime.now(UTC),
        )
        total_all = len(self._catalog.get_all_released_cards())
        embed.set_footer(text=f"bruh.bot · Page {self.catalog_page + 1}/{total_pages} · {total_all} cards total")
        embed.add_field(name="Owned", value=f"{len(owned_ids)} unique", inline=True)
        return embed

    # ── Button callbacks ──
    @discord.ui.button(label="Open Pack", style=discord.ButtonStyle.success, emoji="🎴", row=0)
    async def open_pack_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check_owner(interaction):
            return
        await self._refresh_data()
        if not self._owned_packs:
            await interaction.response.send_message("You have no unopened packs. Buy some first!", ephemeral=True)
            return
        options = []
        for p in self._owned_packs:
            pk = self._catalog.get_pack(p["pack_id"])
            name = pk.name if pk else p["pack_id"]
            qty = p.get("quantity", 1)
            options.append(discord.SelectOption(label=f"{name} x{qty}", value=p["pack_id"]))
        select = PackSelectView(self, options[:25])
        await interaction.response.send_message("Choose a pack to open:", view=select, ephemeral=True)

    @discord.ui.button(label="Collection", style=discord.ButtonStyle.primary, emoji="📖", row=0)
    async def view_collection_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check_owner(interaction):
            return
        await self._refresh_data()
        self.screen = "collection"
        self._update_buttons()
        await interaction.response.edit_message(embed=self._collection_page_embed(), view=self)

    @discord.ui.button(label="Shop", style=discord.ButtonStyle.secondary, emoji="🛒", row=0)
    async def browse_shop_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check_owner(interaction):
            return
        self.screen = "shop"
        self._update_buttons()
        await interaction.response.edit_message(embed=self._shop_embed(), view=self)

    @discord.ui.button(label="Market", style=discord.ButtonStyle.secondary, emoji="🏪", row=0)
    async def view_market_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check_owner(interaction):
            return
        self.screen = "market"
        self.market_page = 0
        self._update_buttons()
        result = await self.bot.card_market_service.browse(self.guild_id, rarity=self.market_rarity, page=0, per_page=MARKET_PER_PAGE)
        await interaction.response.edit_message(embed=self._market_embed(result["listings"], result["total"]), view=self)

    @discord.ui.button(label="Catalog", style=discord.ButtonStyle.secondary, emoji="📚", row=0)
    async def browse_catalog_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check_owner(interaction):
            return
        self.screen = "catalog"
        self.catalog_page = 0
        self._update_buttons()
        await interaction.response.edit_message(embed=self._catalog_embed(), view=self)

    @discord.ui.button(label="Refresh", style=discord.ButtonStyle.primary, emoji="🔄", row=1)
    async def refresh_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check_owner(interaction):
            return
        await self._refresh_data()
        self.screen = "dashboard"
        self._update_buttons()
        await interaction.response.edit_message(embed=self._dashboard_embed(), view=self)

    @discord.ui.button(label="Close", style=discord.ButtonStyle.danger, emoji="✖", row=1)
    async def close_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check_owner(interaction):
            return
        self.stop()
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(view=self)

    # ── Navigation ──
    @discord.ui.button(label="◀ Prev", style=discord.ButtonStyle.secondary, row=2, custom_id="bruhcards_prev")
    async def prev_page_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check_owner(interaction):
            return
        if self.screen == "collection":
            self.binder_page = max(0, self.binder_page - 1)
            await interaction.response.edit_message(embed=self._collection_page_embed(), view=self)
        elif self.screen == "catalog":
            self.catalog_page = max(0, self.catalog_page - 1)
            await interaction.response.edit_message(embed=self._catalog_embed(), view=self)
        elif self.screen == "market":
            self.market_page = max(0, self.market_page - 1)
            result = await self.bot.card_market_service.browse(self.guild_id, rarity=self.market_rarity, page=self.market_page, per_page=MARKET_PER_PAGE)
            await interaction.response.edit_message(embed=self._market_embed(result["listings"], result["total"]), view=self)

    @discord.ui.button(label="Next ▶", style=discord.ButtonStyle.secondary, row=2, custom_id="bruhcards_next")
    async def next_page_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check_owner(interaction):
            return
        if self.screen == "collection":
            s = self._stats
            cards = s.get("cards", [])
            filtered = [c for c in cards if not self.binder_rarity or self._catalog.get_card(c["card_id"]).rarity.value == self.binder_rarity]
            max_page = max(0, (len(filtered) - 1) // CARDS_PER_PAGE)
            self.binder_page = min(max_page, self.binder_page + 1)
            await interaction.response.edit_message(embed=self._collection_page_embed(), view=self)
        elif self.screen == "catalog":
            all_cards = self._catalog.get_all_released_cards()
            if self.catalog_rarity:
                try:
                    r = TradingCardRarity(self.catalog_rarity)
                    all_cards = [c for c in all_cards if c.rarity == r]
                except ValueError:
                    pass
            max_page = max(0, (len(all_cards) - 1) // CARDS_PER_PAGE)
            self.catalog_page = min(max_page, self.catalog_page + 1)
            await interaction.response.edit_message(embed=self._catalog_embed(), view=self)
        elif self.screen == "market":
            self.market_page += 1
            result = await self.bot.card_market_service.browse(self.guild_id, rarity=self.market_rarity, page=self.market_page, per_page=MARKET_PER_PAGE)
            await interaction.response.edit_message(embed=self._market_embed(result["listings"], result["total"]), view=self)

    @discord.ui.button(label="Back", style=discord.ButtonStyle.secondary, emoji="↩", row=2, custom_id="bruhcards_back")
    async def back_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check_owner(interaction):
            return
        await self._refresh_data()
        self.screen = "dashboard"
        self._update_buttons()
        await interaction.response.edit_message(embed=self._dashboard_embed(), view=self)

    @discord.ui.button(label="Rarity Filter", style=discord.ButtonStyle.primary, row=3, custom_id="bruhcards_filter")
    async def rarity_filter_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check_owner(interaction):
            return
        current = None
        if self.screen == "collection":
            current = self.binder_rarity
        elif self.screen == "market":
            current = self.market_rarity
        elif self.screen == "catalog":
            current = self.catalog_rarity
        options = [discord.SelectOption(label="All", value="all", default=not current)]
        for r in TradingCardRarity:
            options.append(discord.SelectOption(label=r.value.title(), value=r.value, default=current == r.value))
        select = RarityFilterSelect(self, options[:25])
        await interaction.response.send_message("Filter by rarity:", view=select, ephemeral=True)

    @discord.ui.button(label="Buy Pack", style=discord.ButtonStyle.success, emoji="💳", row=3, custom_id="bruhcards_buypack")
    async def buy_pack_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check_owner(interaction):
            return
        packs = self._catalog.get_all_packs()
        if not packs:
            await interaction.response.send_message("No packs available.", ephemeral=True)
            return
        options = [discord.SelectOption(label=f"{pk.name} — 🪙 {pk.price:,}", value=pk.pack_id, description=pk.description[:50] if pk.description else "") for pk in packs.values()][:25]
        view = ShopBuyView(self, options)
        await interaction.response.send_message("Choose a pack to buy:", view=view, ephemeral=True)

    @discord.ui.button(label="Inspect Card", style=discord.ButtonStyle.primary, emoji="🔍", row=3, custom_id="bruhcards_inspect")
    async def inspect_card_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check_owner(interaction):
            return
        options = []
        if self.screen == "collection":
            cards_data = self._stats.get("cards", []) if self._stats else []
            filtered = []
            for entry in cards_data:
                card = self._catalog.get_card(entry["card_id"])
                if not card or (self.binder_rarity and card.rarity.value != self.binder_rarity):
                    continue
                filtered.append((card, entry.get("quantity", 1)))
            start = self.binder_page * CARDS_PER_PAGE
            page_items = filtered[start : start + CARDS_PER_PAGE]
            for card, qty in page_items:
                options.append(discord.SelectOption(label=f"#{card.number} {card.name}", value=card.card_id, description=f"Owned: {qty}x"))
        elif self.screen == "catalog":
            all_cards = self._catalog.get_all_released_cards()
            if self.catalog_rarity:
                try:
                    r = TradingCardRarity(self.catalog_rarity)
                    all_cards = [c for c in all_cards if c.rarity == r]
                except ValueError:
                    pass
            start = self.catalog_page * CARDS_PER_PAGE
            page_items = all_cards[start : start + CARDS_PER_PAGE]
            for c in page_items:
                options.append(discord.SelectOption(label=f"#{c.number} {c.name}", value=c.card_id, description=c.rarity.value.title()))
        else:
            return
        if not options:
            await interaction.response.send_message("No cards on this page.", ephemeral=True)
            return
        select = CardInspectSelect(self, options[:25])
        await interaction.response.send_message("Choose a card to inspect:", view=select, ephemeral=True)

    def _update_buttons(self):
        is_dash = self.screen == "dashboard"
        is_collection = self.screen == "collection"
        is_shop = self.screen == "shop"
        is_market = self.screen == "market"
        is_catalog = self.screen == "catalog"

        self.open_pack_btn.visible = is_dash
        self.view_collection_btn.visible = is_dash
        self.browse_shop_btn.visible = is_dash
        self.view_market_btn.visible = is_dash
        self.browse_catalog_btn.visible = is_dash

        self.prev_page_btn.visible = is_collection or is_market or is_catalog
        self.next_page_btn.visible = is_collection or is_market or is_catalog
        self.back_btn.visible = is_collection or is_shop or is_market or is_catalog
        self.rarity_filter_btn.visible = is_collection or is_market or is_catalog
        self.buy_pack_btn.visible = is_shop
        self.inspect_card_btn.visible = is_collection or is_catalog

        self.refresh_btn.visible = is_dash
        self.close_btn.visible = True

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True


class PackSelectView(discord.ui.View):
    def __init__(self, parent: BruhCardsInventoryView, options: list[discord.SelectOption]):
        super().__init__(timeout=60)
        self.parent = parent
        select = discord.ui.Select(placeholder="Choose a pack to open...", options=options)
        select.callback = self.open_callback
        self.add_item(select)

    async def open_callback(self, interaction: discord.Interaction):
        if not self.parent._is_caller(interaction):
            return
        pack_id = interaction.data["values"][0]
        await interaction.response.defer(ephemeral=True)

        result = await self.parent.bot.trading_card_service.open_pack(self.parent.guild_id, self.parent.user_id, pack_id)
        if not result["success"]:
            await interaction.followup.send(f"Failed: {result['error']}", ephemeral=True)
            return

        pack_def = self.parent._catalog.get_pack(pack_id)
        pack_name = pack_def.name if pack_def else pack_id

        lines = []
        files = []
        for i, (card_id, rarity_val) in enumerate(zip(result["card_ids"], result["rarities"], strict=False)):
            try:
                rarity = TradingCardRarity(rarity_val)
            except ValueError:
                rarity = TradingCardRarity.COMMON
            card = self.parent._catalog.get_card(card_id)
            name = card.name if card else card_id
            lines.append(f"{i + 1}. {_rarity_emoji(rarity)} **{rarity.value.title()}** — {name}")

            img_buf = await self.parent.bot.trading_card_render_service.render_card(card_id)
            if img_buf:
                safe = card.name.lower().replace(" ", "_").replace("'", "") if card else card_id
                files.append(discord.File(img_buf, filename=f"{safe}.png"))

        embed = discord.Embed(
            title=f"Opening: {pack_name}",
            description="\n".join(lines),
            color=0x2C2F33,
            timestamp=datetime.now(UTC),
        )
        embed.set_footer(text="bruh.bot · bruh.cards")
        await self.parent._refresh_data()
        stats = self.parent._stats
        embed.add_field(name="Collection", value=f"{stats['unique_cards']} unique ({stats['completion_pct']}%)", inline=True)

        if files:
            await interaction.followup.send(embed=embed, files=files, ephemeral=True)
        else:
            await interaction.followup.send(embed=embed, ephemeral=True)
        self.stop()


class RarityFilterSelect(discord.ui.View):
    def __init__(self, parent: BruhCardsInventoryView, options: list[discord.SelectOption]):
        super().__init__(timeout=60)
        self.parent = parent
        select = discord.ui.Select(placeholder="Choose rarity...", options=options, max_values=1)
        select.callback = self.filter_callback
        self.add_item(select)

    async def filter_callback(self, interaction: discord.Interaction):
        if not self.parent._is_caller(interaction):
            return
        value = interaction.data["values"][0]
        if value == "all":
            self.parent.binder_rarity = None
            self.parent.market_rarity = None
            self.parent.catalog_rarity = None
        elif self.parent.screen == "collection":
            self.parent.binder_rarity = value
        elif self.parent.screen == "catalog":
            self.parent.catalog_rarity = value
        else:
            self.parent.market_rarity = value

        self.parent.binder_page = 0
        self.parent.market_page = 0
        self.parent.catalog_page = 0

        if self.parent.screen == "collection":
            await interaction.response.edit_message(embed=self.parent._collection_page_embed(), view=self.parent)
        elif self.parent.screen == "catalog":
            await interaction.response.edit_message(embed=self.parent._catalog_embed(), view=self.parent)
        elif self.parent.screen == "market":
            result = await self.parent.bot.card_market_service.browse(
                self.parent.guild_id,
                rarity=self.parent.market_rarity,
                page=0,
                per_page=MARKET_PER_PAGE,
            )
            await interaction.response.edit_message(embed=self.parent._market_embed(result["listings"], result["total"]), view=self.parent)
        self.stop()


class CardInspectSelect(discord.ui.View):
    def __init__(self, parent: BruhCardsInventoryView, options: list[discord.SelectOption]):
        super().__init__(timeout=60)
        self.parent = parent
        select = discord.ui.Select(placeholder="Choose a card to inspect...", options=options, max_values=1)
        select.callback = self.inspect_callback
        self.add_item(select)

    async def inspect_callback(self, interaction: discord.Interaction):
        if not self.parent._is_caller(interaction):
            return
        card_id = interaction.data["values"][0]
        await interaction.response.defer(ephemeral=True)
        card = self.parent._catalog.get_card(card_id)
        if not card:
            await interaction.followup.send("Card not found.", ephemeral=True)
            return
        owned = await self.parent.bot.trading_card_service.get_card_quantity(self.parent.guild_id, self.parent.user_id, card_id)
        image_buffer = await self.parent.bot.trading_card_render_service.render_card(card_id)
        from bot.data.trading_card_models import RARITY_DISCORD_COLORS

        display = card.series_id.replace("_", " ").title()
        embed = discord.Embed(
            title=f"#{card.number} {card.name}",
            description=card.description,
            color=RARITY_DISCORD_COLORS.get(card.rarity, 0x5865F2),
            timestamp=datetime.now(UTC),
        )
        embed.set_footer(text=f"bruh.bot · {display}")
        embed.add_field(name="Rarity", value=f"{_rarity_emoji(card.rarity)} {card.rarity.value.title()}", inline=True)
        embed.add_field(name="Set", value=display, inline=True)
        embed.add_field(name="Owned", value=f"{owned}x", inline=True)
        embed.add_field(name="Sellback", value=f"🪙 {card.sellback_value:,.2f}", inline=True)
        if image_buffer:
            file = discord.File(image_buffer, filename="card.png")
            embed.set_image(url="attachment://card.png")
            await interaction.followup.send(embed=embed, file=file, ephemeral=True)
        else:
            await interaction.followup.send(embed=embed, ephemeral=True)
        self.stop()


class ShopBuyView(discord.ui.View):
    def __init__(self, parent: BruhCardsInventoryView, options: list[discord.SelectOption]):
        super().__init__(timeout=60)
        self.parent = parent
        select = discord.ui.Select(placeholder="Choose a pack to buy...", options=options)
        select.callback = self.buy_callback
        self.add_item(select)

    async def buy_callback(self, interaction: discord.Interaction):
        if not self.parent._is_caller(interaction):
            return
        pack_id = interaction.data["values"][0]
        result = await self.parent.bot.trading_card_service.buy_pack(self.parent.guild_id, self.parent.user_id, pack_id)
        if not result["success"]:
            await interaction.response.send_message(f"Failed: {result['error']}", ephemeral=True)
            return
        await interaction.response.send_message(f"Bought **{result['pack_name']}** for 🪙 {result['price']:,}!", ephemeral=True)
        await self.parent._refresh_data()
        self.stop()
