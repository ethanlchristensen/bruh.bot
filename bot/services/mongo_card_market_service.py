import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from bson import Int64

from bot.data.trading_card_catalog import get_card

if TYPE_CHECKING:
    from bot.bruh_bot import BruhBot

LISTING_EXPIRY_HOURS = 72
MAX_ACTIVE_LISTINGS = 20


class MongoCardMarketService:
    def __init__(self, bot: "BruhBot"):
        self.bot = bot
        self.listings_col = self.bot.config_service.col("TradingCardMarketListings")
        self.logger = logging.getLogger(__name__)

    async def initialize(self):
        await self._ensure_indexes()

    async def _ensure_indexes(self):
        try:
            await self.listings_col.create_index([("guild_id", 1), ("status", 1), ("created_at", -1)])
            await self.listings_col.create_index([("guild_id", 1), ("seller_id", 1), ("status", 1)])
            await self.listings_col.create_index([("guild_id", 1), ("card_id", 1), ("status", 1)])
            await self.listings_col.create_index("expires_at")
            self.logger.info("Created indexes on TradingCardMarketListings")
        except Exception as e:
            self.logger.warning(f"Could not create market indexes: {e}")

    async def list_card(self, guild_id: int, user_id: int, card_id: str, quantity: int, price_each: float) -> dict:
        config = await self.bot.config_service.get_config(str(guild_id))
        if not config.economyConfig.bruhCardsEnabled or not config.economyConfig.tradingCardMarketEnabled:
            return {"success": False, "error": "The card marketplace is currently disabled."}

        if quantity < 1 or price_each < 1:
            return {"success": False, "error": "Quantity and price must be positive."}

        card = get_card(card_id)
        if not card:
            return {"success": False, "error": "Card not found."}
        if not card.tradable:
            return {"success": False, "error": "This card is not tradable."}

        owned = await self.bot.trading_card_service.get_card_quantity(guild_id, user_id, card_id)
        if owned < quantity:
            return {"success": False, "error": f"You only have **{owned}x** {card.name}."}

        active_count = await self.listings_col.count_documents(
            {
                "guild_id": Int64(guild_id),
                "seller_id": Int64(user_id),
                "status": "active",
            }
        )
        if active_count >= MAX_ACTIVE_LISTINGS:
            return {"success": False, "error": f"You have reached the maximum of {MAX_ACTIVE_LISTINGS} active listings."}

        success = await self.bot.trading_card_service.remove_cards(guild_id, user_id, card_id, quantity)
        if not success:
            return {"success": False, "error": "Failed to remove cards from your collection."}

        now = datetime.now(UTC)
        listing = {
            "listing_id": uuid.uuid4().hex[:12],
            "guild_id": Int64(guild_id),
            "seller_id": Int64(user_id),
            "card_id": card_id,
            "quantity_total": quantity,
            "quantity_remaining": quantity,
            "price_each": price_each,
            "status": "active",
            "created_at": now,
            "expires_at": now + timedelta(hours=LISTING_EXPIRY_HOURS),
        }
        await self.listings_col.insert_one(listing)
        return {"success": True, "listing_id": listing["listing_id"], "card_name": card.name}

    async def browse(
        self,
        guild_id: int,
        rarity: str | None = None,
        seller_id: int | None = None,
        page: int = 0,
        per_page: int = 10,
    ) -> dict:
        query = {"guild_id": Int64(guild_id), "status": "active", "expires_at": {"$gt": datetime.now(UTC)}}
        if seller_id:
            query["seller_id"] = Int64(seller_id)
        if rarity:
            all_cards = self._get_card_ids_by_rarity(rarity)
            if all_cards:
                query["card_id"] = {"$in": all_cards}

        total = await self.listings_col.count_documents(query)
        cursor = self.listings_col.find(query).sort("price_each", 1).skip(page * per_page).limit(per_page)
        listings = []
        async for doc in cursor:
            card = get_card(doc["card_id"])
            listings.append(
                {
                    "listing_id": doc["listing_id"],
                    "seller_id": doc["seller_id"],
                    "card_id": doc["card_id"],
                    "card_name": card.name if card else doc["card_id"],
                    "rarity": card.rarity.value if card else "common",
                    "quantity_remaining": doc["quantity_remaining"],
                    "price_each": doc["price_each"],
                    "expires_at": doc["expires_at"].isoformat(),
                }
            )
        return {"listings": listings, "total": total, "page": page, "pages": max(1, (total - 1) // per_page + 1)}

    def _get_card_ids_by_rarity(self, rarity: str) -> list[str]:
        from bot.data.trading_card_models import TradingCardRarity

        try:
            r = TradingCardRarity(rarity)
            from bot.data.trading_card_catalog import get_cards_by_rarity

            return [c.card_id for c in get_cards_by_rarity(r)]
        except ValueError:
            return []

    async def buy(self, guild_id: int, buyer_id: int, listing_id: str, quantity: int = 0) -> dict:
        config = await self.bot.config_service.get_config(str(guild_id))
        fee_rate = config.economyConfig.tradingCardMarketFeeRate

        listing = await self.listings_col.find_one(
            {
                "listing_id": listing_id,
                "guild_id": Int64(guild_id),
                "status": "active",
            }
        )
        if not listing:
            return {"success": False, "error": "Listing not found or no longer available."}

        if listing["seller_id"] == buyer_id:
            return {"success": False, "error": "You cannot buy your own listing."}

        buy_qty = quantity if quantity > 0 else listing["quantity_remaining"]
        if buy_qty > listing["quantity_remaining"]:
            return {"success": False, "error": f"Only {listing['quantity_remaining']} available."}

        total_cost = round(listing["price_each"] * buy_qty, 2)
        success, _ = await self.bot.economy_service.deduct_coins(guild_id, buyer_id, total_cost)
        if not success:
            return {"success": False, "error": f"You need **🪙 {total_cost:,.2f}** for this purchase."}

        seller_payout = round(total_cost * (1.0 - fee_rate), 2)
        await self.bot.economy_service.add_coins(guild_id, listing["seller_id"], seller_payout)
        await self.bot.trading_card_service.add_cards(guild_id, buyer_id, [listing["card_id"]] * buy_qty)

        new_remaining = listing["quantity_remaining"] - buy_qty
        new_status = "sold" if new_remaining <= 0 else "active"

        await self.listings_col.update_one(
            {"listing_id": listing_id},
            {"$set": {"quantity_remaining": new_remaining, "status": new_status}},
        )

        card = get_card(listing["card_id"])
        card_name = card.name if card else listing["card_id"]

        await self.bot.economy_service.record_transaction(
            guild_id,
            buyer_id,
            "market_buy_debit",
            -total_cost,
            0.0,
            reference_type="market",
            reference_id=listing_id,
        )
        await self.bot.economy_service.record_transaction(
            guild_id,
            listing["seller_id"],
            "market_sale_credit",
            seller_payout,
            0.0,
            reference_type="market",
            reference_id=listing_id,
        )

        return {
            "success": True,
            "card_name": card_name,
            "quantity": buy_qty,
            "price_each": listing["price_each"],
            "total_cost": total_cost,
        }

    async def cancel_listing(self, guild_id: int, user_id: int, listing_id: str) -> dict:
        listing = await self.listings_col.find_one(
            {
                "listing_id": listing_id,
                "guild_id": Int64(guild_id),
                "status": "active",
            }
        )
        if not listing:
            return {"success": False, "error": "Listing not found."}

        config = await self.bot.config_service.get_config(str(guild_id))
        is_admin = str(user_id) in config.adminIds
        if listing["seller_id"] != user_id and not is_admin:
            return {"success": False, "error": "You can only cancel your own listings."}

        await self.listings_col.update_one(
            {"listing_id": listing_id},
            {"$set": {"status": "cancelled"}},
        )
        await self.bot.trading_card_service.add_cards(
            guild_id,
            listing["seller_id"],
            [listing["card_id"]] * listing["quantity_remaining"],
        )
        card = get_card(listing["card_id"])
        return {"success": True, "card_name": card.name if card else listing["card_id"], "quantity_returned": listing["quantity_remaining"]}

    async def get_seller_listings(self, guild_id: int, user_id: int) -> list[dict]:
        cursor = self.listings_col.find(
            {
                "guild_id": Int64(guild_id),
                "seller_id": Int64(user_id),
                "status": "active",
            }
        ).sort("created_at", -1)
        results = []
        async for doc in cursor:
            card = get_card(doc["card_id"])
            results.append(
                {
                    "listing_id": doc["listing_id"],
                    "card_name": card.name if card else doc["card_id"],
                    "quantity_remaining": doc["quantity_remaining"],
                    "price_each": doc["price_each"],
                    "expires_at": doc["expires_at"].isoformat(),
                }
            )
        return results

    async def expire_stale_listings(self, guild_id: int):
        cursor = self.listings_col.find(
            {
                "guild_id": Int64(guild_id),
                "status": "active",
                "expires_at": {"$lt": datetime.now(UTC)},
            }
        )
        async for doc in cursor:
            await self.listings_col.update_one(
                {"listing_id": doc["listing_id"]},
                {"$set": {"status": "expired"}},
            )
            if doc["quantity_remaining"] > 0:
                await self.bot.trading_card_service.add_cards(
                    guild_id,
                    doc["seller_id"],
                    [doc["card_id"]] * doc["quantity_remaining"],
                )
