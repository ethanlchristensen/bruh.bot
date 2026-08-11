import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from bson import Int64

from bot.data.cosmetic_catalog import get_cosmetic
from bot.data.models import CosmeticSlot

if TYPE_CHECKING:
    from bot.bruh_bot import BruhBot


class MongoInventoryService:
    def __init__(self, bot: "BruhBot"):
        self.bot = bot
        self.collection = self.bot.config_service.col(self.bot.config_service.base.mongoUserInventoryCollectionName)
        self.logger = logging.getLogger(__name__)

    async def initialize(self):
        await self._ensure_indexes()
        await self._migrate_cosmetic_fields()

    async def _ensure_indexes(self):
        try:
            await self.collection.create_index([("guild_id", 1), ("user_id", 1)], unique=True)
            await self.collection.create_index("items.item_id")
            self.logger.info("Created indexes on UserInventory collection")
        except Exception as e:
            self.logger.warning(f"Could not create inventory indexes: {e}")

    async def _migrate_cosmetic_fields(self):
        try:
            result = await self.collection.update_many(
                {"cards": {"$exists": True}, "cosmetic_cards": {"$exists": False}},
                {"$rename": {"cards": "cosmetic_cards"}},
            )
            if result.modified_count > 0:
                self.logger.info(f"Migrated {result.modified_count} documents: cards -> cosmetic_cards")
            result2 = await self.collection.update_many(
                {"card_packs_unopened": {"$exists": True}, "cosmetic_packs_unopened": {"$exists": False}},
                {"$rename": {"card_packs_unopened": "cosmetic_packs_unopened"}},
            )
            if result2.modified_count > 0:
                self.logger.info(f"Migrated {result2.modified_count} documents: cosmetic_packs_unopened -> cosmetic_packs_unopened")
        except Exception as e:
            self.logger.warning(f"Could not run cosmetic field migration: {e}")

    async def _get_or_create_inventory(self, guild_id: int, user_id: int) -> dict:
        now = datetime.now(UTC)
        doc = await self.collection.find_one({"guild_id": Int64(guild_id), "user_id": Int64(user_id)})
        if not doc:
            doc = {
                "guild_id": Int64(guild_id),
                "user_id": Int64(user_id),
                "items": [],
                "equipped": {slot.value: None for slot in CosmeticSlot},
                "cosmetic_cards": [],
                "cosmetic_packs_unopened": [],
                "created_at": now,
                "updated_at": now,
            }
            await self.collection.insert_one(doc)
        else:
            defaults = {
                "cosmetic_cards": [],
                "cosmetic_packs_unopened": [],
            }
            equipped = doc.get("equipped", {})
            for slot in CosmeticSlot:
                equipped.setdefault(slot.value, None)
            missing = {k: v for k, v in defaults.items() if k not in doc}
            updates = {}
            if equipped != doc.get("equipped"):
                updates["equipped"] = equipped
            if missing:
                updates.update(missing)
            if updates:
                await self.collection.update_one({"_id": doc["_id"]}, {"$set": updates})
                doc.update(updates)
        return doc

    def _find_item(self, items: list[dict], item_id: str) -> dict | None:
        for item in items:
            if item["item_id"] == item_id:
                return item
        return None

    async def has_item(self, guild_id: int, user_id: int, item_id: str) -> bool:
        doc = await self._get_or_create_inventory(guild_id, user_id)
        return self._find_item(doc["items"], item_id) is not None

    async def get_inventory(self, guild_id: int, user_id: int) -> dict:
        doc = await self._get_or_create_inventory(guild_id, user_id)
        return {
            "items": doc["items"],
            "equipped": doc["equipped"],
            "cosmetic_cards": doc.get("cosmetic_cards", []),
            "cosmetic_packs_unopened": doc.get("cosmetic_packs_unopened", []),
        }

    async def add_item(self, guild_id: int, user_id: int, item_id: str, acquisition: str = "purchase") -> bool:
        cosmetic = get_cosmetic(item_id)
        if not cosmetic:
            return False

        doc = await self._get_or_create_inventory(guild_id, user_id)
        existing = self._find_item(doc["items"], item_id)
        now = datetime.now(UTC)

        if existing:
            await self.collection.update_one(
                {"guild_id": Int64(guild_id), "user_id": Int64(user_id), "items.item_id": item_id},
                {"$inc": {"items.$.quantity": 1}, "$set": {"updated_at": now}},
            )
        else:
            await self.collection.update_one(
                {"guild_id": Int64(guild_id), "user_id": Int64(user_id)},
                {
                    "$push": {
                        "items": {
                            "item_id": item_id,
                            "quantity": 1,
                            "acquired_at": now,
                            "acquisition": acquisition,
                        }
                    },
                    "$set": {"updated_at": now},
                },
            )
        return True

    async def remove_item(self, guild_id: int, user_id: int, item_id: str, quantity: int = 1) -> bool:
        doc = await self._get_or_create_inventory(guild_id, user_id)
        existing = self._find_item(doc["items"], item_id)
        if not existing or existing["quantity"] < quantity:
            return False

        now = datetime.now(UTC)
        new_qty = existing["quantity"] - quantity
        if new_qty <= 0:
            await self.collection.update_one(
                {"guild_id": Int64(guild_id), "user_id": Int64(user_id)},
                {"$pull": {"items": {"item_id": item_id}}, "$set": {"updated_at": now}},
            )
        else:
            await self.collection.update_one(
                {"guild_id": Int64(guild_id), "user_id": Int64(user_id), "items.item_id": item_id},
                {"$set": {"items.$.quantity": new_qty, "updated_at": now}},
            )
        return True

    async def equip_item(self, guild_id: int, user_id: int, item_id: str) -> tuple[bool, str]:
        cosmetic = get_cosmetic(item_id)
        if not cosmetic:
            return False, "Item not found in catalog."

        doc = await self._get_or_create_inventory(guild_id, user_id)
        existing = self._find_item(doc["items"], item_id)
        if not existing or existing["quantity"] < 1:
            return False, "You don't own this item."

        slot_key = cosmetic.slot.value
        now = datetime.now(UTC)
        await self.collection.update_one(
            {"guild_id": Int64(guild_id), "user_id": Int64(user_id)},
            {"$set": {f"equipped.{slot_key}": item_id, "updated_at": now}},
        )
        return True, f"Equipped **{cosmetic.name}**!"

    async def unequip_slot(self, guild_id: int, user_id: int, slot: CosmeticSlot) -> bool:
        now = datetime.now(UTC)
        await self.collection.update_one(
            {"guild_id": Int64(guild_id), "user_id": Int64(user_id)},
            {"$set": {f"equipped.{slot.value}": None, "updated_at": now}},
        )
        return True

    async def get_equipped(self, guild_id: int, user_id: int) -> dict[str, str | None]:
        doc = await self._get_or_create_inventory(guild_id, user_id)
        return doc.get("equipped", {})

    async def get_item_quantity(self, guild_id: int, user_id: int, item_id: str) -> int:
        doc = await self._get_or_create_inventory(guild_id, user_id)
        existing = self._find_item(doc["items"], item_id)
        return existing["quantity"] if existing else 0

    async def add_card_pack(self, guild_id: int, user_id: int, pack_id: str, quantity: int = 1):
        now = datetime.now(UTC)
        doc = await self._get_or_create_inventory(guild_id, user_id)
        packs = doc.get("cosmetic_packs_unopened", [])
        for p in packs:
            if p["pack_id"] == pack_id:
                await self.collection.update_one(
                    {"guild_id": Int64(guild_id), "user_id": Int64(user_id), "cosmetic_packs_unopened.pack_id": pack_id},
                    {"$inc": {"cosmetic_packs_unopened.$.quantity": quantity}, "$set": {"updated_at": now}},
                )
                return
        await self.collection.update_one(
            {"guild_id": Int64(guild_id), "user_id": Int64(user_id)},
            {
                "$push": {
                    "cosmetic_packs_unopened": {
                        "pack_id": pack_id,
                        "quantity": quantity,
                        "acquired_at": now,
                    }
                },
                "$set": {"updated_at": now},
            },
        )

    async def add_cards(self, guild_id: int, user_id: int, card_ids: list[str]):
        now = datetime.now(UTC)
        doc = await self._get_or_create_inventory(guild_id, user_id)
        cosmetic_cards = doc.get("cosmetic_cards", [])

        for card_id in card_ids:
            found = False
            for c in cosmetic_cards:
                if c["card_id"] == card_id:
                    c["quantity"] += 1
                    found = True
                    break
            if not found:
                cosmetic_cards.append(
                    {
                        "card_id": card_id,
                        "quantity": 1,
                        "acquired_at": now,
                    }
                )

        await self.collection.update_one(
            {"guild_id": Int64(guild_id), "user_id": Int64(user_id)},
            {"$set": {"cosmetic_cards": cosmetic_cards, "updated_at": now}},
        )

    async def remove_cards(self, guild_id: int, user_id: int, card_id: str, quantity: int = 1) -> bool:
        doc = await self._get_or_create_inventory(guild_id, user_id)
        cosmetic_cards = doc.get("cosmetic_cards", [])
        for c in cosmetic_cards:
            if c["card_id"] == card_id:
                if c["quantity"] < quantity:
                    return False
                c["quantity"] -= quantity
                if c["quantity"] <= 0:
                    cosmetic_cards = [c2 for c2 in cosmetic_cards if c2["card_id"] != card_id]
                now = datetime.now(UTC)
                await self.collection.update_one(
                    {"guild_id": Int64(guild_id), "user_id": Int64(user_id)},
                    {"$set": {"cosmetic_cards": cosmetic_cards, "updated_at": now}},
                )
                return True
        return False

    async def reset_inventory(self, guild_id: int, user_id: int):
        now = datetime.now(UTC)
        await self.collection.update_one(
            {"guild_id": Int64(guild_id), "user_id": Int64(user_id)},
            {
                "$set": {
                    "items": [],
                    "equipped": {slot.value: None for slot in CosmeticSlot},
                    "cosmetic_cards": [],
                    "cosmetic_packs_unopened": [],
                    "updated_at": now,
                }
            },
        )

    async def transfer_items_between(
        self,
        from_guild: int,
        from_user: int,
        to_guild: int,
        to_user: int,
        item_ids: list[tuple[str, int]],
        card_ids: list[tuple[str, int]],
    ) -> tuple[bool, str]:
        from_doc = await self._get_or_create_inventory(from_guild, from_user)

        for item_id, qty in item_ids:
            existing = self._find_item(from_doc["items"], item_id)
            if not existing or existing["quantity"] < qty:
                return False, f"You don't have enough **{item_id}**."
        for card_id, qty in card_ids:
            card = None
            for c in from_doc.get("cosmetic_cards", []):
                if c["card_id"] == card_id:
                    card = c
                    break
            if not card or card["quantity"] < qty:
                return False, f"You don't have enough **{card_id}** cards."

        for item_id, qty in item_ids:
            await self.remove_item(from_guild, from_user, item_id, qty)
            await self.add_item(to_guild, to_user, item_id, "trade")
        for card_id, qty in card_ids:
            await self.remove_cards(from_guild, from_user, card_id, qty)
            await self.add_cards(to_guild, to_user, [card_id] * qty)

        return True, "Trade completed!"
