import logging
import random
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from bson import Int64

from bot.data.trading_card_models import (
    DEFAULT_DROP_TABLE,
    TradingCardRarity,
)

if TYPE_CHECKING:
    from bot.bruh_bot import BruhBot


class MongoTradingCardService:
    def __init__(self, bot: "BruhBot"):
        self.bot = bot
        self.collections_col = self.bot.config_service.col("TradingCardCollections")
        self.logger = logging.getLogger(__name__)

    async def initialize(self):
        await self._ensure_indexes()

    async def _ensure_indexes(self):
        try:
            await self.collections_col.create_index([("guild_id", 1), ("user_id", 1)], unique=True)
            self.logger.info("Created indexes on TradingCardCollections")
        except Exception as e:
            self.logger.warning(f"Could not create trading card collection indexes: {e}")

    async def _get_or_create(self, guild_id: int, user_id: int) -> dict:
        now = datetime.now(UTC)
        doc = await self.collections_col.find_one({"guild_id": Int64(guild_id), "user_id": Int64(user_id)})
        if not doc:
            doc = {
                "guild_id": Int64(guild_id),
                "user_id": Int64(user_id),
                "cards": [],
                "unopened_packs": [],
                "created_at": now,
                "updated_at": now,
            }
            await self.collections_col.insert_one(doc)
        return doc

    async def get_collection(self, guild_id: int, user_id: int) -> dict:
        doc = await self._get_or_create(guild_id, user_id)
        return {
            "cards": doc.get("cards", []),
            "unopened_packs": doc.get("unopened_packs", []),
        }

    def _find_card(self, cards: list[dict], card_id: str) -> dict | None:
        for c in cards:
            if c["card_id"] == card_id:
                return c
        return None

    async def add_cards(self, guild_id: int, user_id: int, card_ids: list[str]):
        now = datetime.now(UTC)
        doc = await self._get_or_create(guild_id, user_id)
        cards = doc.get("cards", [])

        for card_id in card_ids:
            existing = self._find_card(cards, card_id)
            if existing:
                existing["quantity"] += 1
                existing["last_acquired_at"] = now
            else:
                cards.append(
                    {
                        "card_id": card_id,
                        "quantity": 1,
                        "first_acquired_at": now,
                        "last_acquired_at": now,
                    }
                )

        await self.collections_col.update_one(
            {"guild_id": Int64(guild_id), "user_id": Int64(user_id)},
            {"$set": {"cards": cards, "updated_at": now}},
        )

    async def remove_cards(self, guild_id: int, user_id: int, card_id: str, quantity: int = 1) -> bool:
        doc = await self._get_or_create(guild_id, user_id)
        cards = doc.get("cards", [])
        existing = self._find_card(cards, card_id)
        if not existing or existing["quantity"] < quantity:
            return False
        existing["quantity"] -= quantity
        if existing["quantity"] <= 0:
            cards = [c for c in cards if c["card_id"] != card_id]
        now = datetime.now(UTC)
        await self.collections_col.update_one(
            {"guild_id": Int64(guild_id), "user_id": Int64(user_id)},
            {"$set": {"cards": cards, "updated_at": now}},
        )
        return True

    async def get_card_quantity(self, guild_id: int, user_id: int, card_id: str) -> int:
        doc = await self._get_or_create(guild_id, user_id)
        existing = self._find_card(doc.get("cards", []), card_id)
        return existing["quantity"] if existing else 0

    async def add_packs(self, guild_id: int, user_id: int, pack_id: str, quantity: int = 1):
        now = datetime.now(UTC)
        doc = await self._get_or_create(guild_id, user_id)
        packs = doc.get("unopened_packs", [])

        for p in packs:
            if p["pack_id"] == pack_id:
                await self.collections_col.update_one(
                    {"guild_id": Int64(guild_id), "user_id": Int64(user_id), "unopened_packs.pack_id": pack_id},
                    {"$inc": {"unopened_packs.$.quantity": quantity}, "$set": {"updated_at": now}},
                )
                return

        await self.collections_col.update_one(
            {"guild_id": Int64(guild_id), "user_id": Int64(user_id)},
            {"$push": {"unopened_packs": {"pack_id": pack_id, "quantity": quantity, "acquired_at": now}}, "$set": {"updated_at": now}},
        )

    def _roll_rarity(self) -> TradingCardRarity:
        roll = random.random()
        cumulative = 0.0
        for rarity, prob in DEFAULT_DROP_TABLE:
            cumulative += prob
            if roll < cumulative:
                return rarity
        return TradingCardRarity.COMMON

    def _pick_card_from_rarity(self, rarity: TradingCardRarity, set_id: str | None = None) -> str | None:
        catalog = self.bot.trading_card_catalog_service
        if set_id:
            candidates = [c for c in catalog.get_cards_by_series(set_id) if c.rarity == rarity]
        else:
            candidates = catalog.get_cards_by_rarity(rarity)
            if not candidates:
                candidates = catalog.get_all_released_cards()
        if not candidates:
            return None
        return random.choice(candidates).card_id

    def _roll_pack(self, pack_def, cards_per: int, set_id: str | None = None) -> list[str] | None:
        guaranteed = pack_def.guaranteed_rarity if pack_def else None
        card_ids = []
        guaranteed_slot = random.randint(0, cards_per - 1) if guaranteed else -1
        for i in range(cards_per):
            if i == guaranteed_slot:
                picked = self._pick_card_from_rarity(guaranteed, set_id)
            else:
                picked = self._pick_card_from_rarity(self._roll_rarity(), set_id)
            if picked is None:
                return None
            card_ids.append(picked)
        return card_ids

    async def buy_pack(self, guild_id: int, user_id: int, pack_id: str) -> dict:
        pack_def = self.bot.trading_card_catalog_service.get_pack(pack_id)
        if not pack_def:
            return {"success": False, "error": f"Unknown pack type: {pack_id}"}

        config = await self.bot.config_service.get_config(str(guild_id))
        if not config.economyConfig.bruhCardsEnabled or not config.economyConfig.tradingCardPacksEnabled:
            return {"success": False, "error": "Trading card packs are currently disabled."}

        success, _ = await self.bot.economy_service.deduct_coins(guild_id, user_id, pack_def.price)
        if not success:
            return {"success": False, "error": f"You need **🪙 {pack_def.price:,}** for a {pack_def.name}."}

        await self.bot.economy_service.record_transaction(
            guild_id,
            user_id,
            "trading_card_pack_purchase",
            -pack_def.price,
            0.0,
            reference_type="trading_card_pack",
            reference_id=pack_id,
        )
        await self.add_packs(guild_id, user_id, pack_id)
        return {"success": True, "pack_name": pack_def.name, "price": pack_def.price}

    async def open_pack(self, guild_id: int, user_id: int, pack_id: str) -> dict:
        pack_def = self.bot.trading_card_catalog_service.get_pack(pack_id)
        if not pack_def:
            return {"success": False, "error": f"Unknown pack type: {pack_id}"}

        doc = await self._get_or_create(guild_id, user_id)
        packs = doc.get("unopened_packs", [])
        found = False
        for p in packs:
            if p["pack_id"] == pack_id and p.get("quantity", 0) > 0:
                found = True
                break
        if not found:
            return {"success": False, "error": f"You don't have any unopened **{pack_def.name}** packs."}

        card_ids = self._roll_pack(pack_def, pack_def.cards_per_pack, pack_def.series_id)
        if card_ids is None:
            set_name = pack_def.series_id.replace("_", " ").title()

            # Remove one pack quantity
            now = datetime.now(UTC)
            for i, p in enumerate(packs):
                if p["pack_id"] == pack_id:
                    p["quantity"] -= 1
                    if p["quantity"] <= 0:
                        packs.pop(i)
                    break
            await self.collections_col.update_one(
                {"guild_id": Int64(guild_id), "user_id": Int64(user_id)},
                {"$set": {"unopened_packs": packs, "updated_at": now}},
            )

            # Refund coins
            new_balance = await self.bot.economy_service.add_coins(guild_id, user_id, pack_def.price)
            await self.bot.economy_service.record_transaction(
                guild_id,
                user_id,
                "trading_card_pack_refund",
                pack_def.price,
                new_balance,
                reference_type="trading_card_pack",
                reference_id=pack_id,
            )

            return {
                "success": False,
                "error": f"The **{set_name}** collection has no released cards yet — your pack was refunded 🪙 {pack_def.price:,.2f}.",
                "refunded": True,
            }
        rarities = []
        for cid in card_ids:
            card = self.bot.trading_card_catalog_service.get_card(cid)
            rarities.append(card.rarity.value if card else "common")

        await self.add_cards(guild_id, user_id, card_ids)

        # Remove one pack quantity
        now = datetime.now(UTC)
        for i, p in enumerate(packs):
            if p["pack_id"] == pack_id:
                p["quantity"] -= 1
                if p["quantity"] <= 0:
                    packs.pop(i)
                break
        await self.collections_col.update_one(
            {"guild_id": Int64(guild_id), "user_id": Int64(user_id)},
            {"$set": {"unopened_packs": packs, "updated_at": now}},
        )

        return {
            "success": True,
            "pack_name": pack_def.name,
            "card_ids": card_ids,
            "rarities": rarities,
        }

    async def sell_cards(self, guild_id: int, user_id: int, card_id: str, quantity: int) -> dict:
        card = self.bot.trading_card_catalog_service.get_card(card_id)
        if not card:
            return {"success": False, "error": "Card not found in catalog."}

        success = await self.remove_cards(guild_id, user_id, card_id, quantity)
        if not success:
            return {"success": False, "error": f"You don't have {quantity} of this card."}

        value = round(card.sellback_value * quantity, 2)
        new_balance = await self.bot.economy_service.add_coins(guild_id, user_id, value)
        await self.bot.economy_service.record_transaction(
            guild_id,
            user_id,
            "trading_card_sellback",
            value,
            new_balance,
            reference_type="trading_card",
            reference_id=card_id,
            metadata={"quantity": quantity},
        )
        return {"success": True, "value": value, "balance": new_balance, "card_name": card.name}

    async def get_collection_stats(self, guild_id: int, user_id: int, set_id: str | None = None) -> dict:
        doc = await self._get_or_create(guild_id, user_id)
        cards = doc.get("cards", [])
        packs = doc.get("unopened_packs", [])

        catalog = self.bot.trading_card_catalog_service
        total_cards = sum(c.get("quantity", 1) for c in cards)
        unique_cards = 0
        series_total = 0
        rarity_counts = dict.fromkeys(TradingCardRarity, 0)
        set_counts: dict[str, int] = {}

        for entry in cards:
            card = catalog.get_card(entry["card_id"])
            if card:
                qty = entry.get("quantity", 1)
                rarity_counts[card.rarity] += qty
                if set_id and card.series_id != set_id:
                    continue
                unique_cards += 1
                set_counts[card.series_id] = set_counts.get(card.series_id, 0) + 1

        if set_id:
            series_total = catalog.get_series_total(set_id)
            filtered_cards = [c for c in cards if catalog.get_card(c["card_id"]) and catalog.get_card(c["card_id"]).series_id == set_id]
        else:
            series_total = len(catalog.get_all_released_cards())
            filtered_cards = cards

        completion_pct = round(unique_cards / series_total * 100, 1) if series_total else 0

        return {
            "total_cards": total_cards,
            "unique_cards": unique_cards,
            "series_total": series_total,
            "completion_pct": completion_pct,
            "rarity_counts": rarity_counts,
            "cards": filtered_cards,
            "unopened_packs": packs,
            "set_counts": set_counts,
        }

    async def reset_collection(self, guild_id: int, user_id: int):
        now = datetime.now(UTC)
        await self.collections_col.update_one(
            {"guild_id": Int64(guild_id), "user_id": Int64(user_id)},
            {"$set": {"cards": [], "unopened_packs": [], "updated_at": now}},
        )

    async def get_collection_leaderboard(self, guild_id: int, limit: int = 25) -> list[dict]:
        catalog = self.bot.trading_card_catalog_service
        cursor = self.collections_col.find({"guild_id": Int64(guild_id), "cards.0": {"$exists": True}})
        entries = []
        async for doc in cursor:
            total_cards = 0
            weighted_score = 0.0
            for entry in doc.get("cards", []):
                card = catalog.get_card(entry["card_id"])
                if not card:
                    continue
                qty = entry.get("quantity", 1)
                total_cards += qty
                weighted_score += card.sellback_value * qty
            if total_cards > 0:
                entries.append(
                    {
                        "user_id": str(doc["user_id"]),
                        "total_cards": total_cards,
                        "weighted_score": round(weighted_score, 2),
                    }
                )
        entries.sort(key=lambda e: e["weighted_score"], reverse=True)
        return entries[:limit]
