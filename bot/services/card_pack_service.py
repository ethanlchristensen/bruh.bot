import logging
import random
from typing import TYPE_CHECKING

from bot.data.models import CosmeticRarity

if TYPE_CHECKING:
    from bot.bruh_bot import BruhBot


STANDARD_PACK = {
    "id": "card_pack_standard",
    "name": "Standard Card Pack",
    "price": 200,
    "description": "Mostly basic and common cards. A chance at rare!",
    "cards_per_pack": 3,
    "guaranteed_rarity": None,
}

PREMIUM_PACK = {
    "id": "card_pack_premium",
    "name": "Premium Card Pack",
    "price": 750,
    "description": "At least one rare or better guaranteed!",
    "cards_per_pack": 3,
    "guaranteed_rarity": CosmeticRarity.RARE,
}

CARD_PACKS = {
    "standard": STANDARD_PACK,
    "premium": PREMIUM_PACK,
}

CARD_DROP_TABLE = [
    (CosmeticRarity.BASIC, 0.40),
    (CosmeticRarity.COMMON, 0.30),
    (CosmeticRarity.RARE, 0.18),
    (CosmeticRarity.EPIC, 0.08),
    (CosmeticRarity.LEGENDARY, 0.03),
    (CosmeticRarity.DIAMOND, 0.008),
    (CosmeticRarity.PLATINUM, 0.002),
]


class CardPackService:
    def __init__(self, bot: "BruhBot"):
        self.bot = bot
        self.logger = logging.getLogger(__name__)

    def _roll_rarity(self) -> CosmeticRarity:
        roll = random.random()
        cumulative = 0.0
        for rarity, prob in CARD_DROP_TABLE:
            cumulative += prob
            if roll < cumulative:
                return rarity
        return CosmeticRarity.COMMON

    def _roll_pack(self, pack_def: dict) -> list[CosmeticRarity]:
        results = []
        guaranteed_slot = -1
        guaranteed_rarity = pack_def.get("guaranteed_rarity")

        if guaranteed_rarity:
            guaranteed_slot = random.randint(0, pack_def["cards_per_pack"] - 1)

        for i in range(pack_def["cards_per_pack"]):
            if i == guaranteed_slot:
                results.append(guaranteed_rarity)
            else:
                results.append(self._roll_rarity())

        return results

    def _pick_card_from_rarity(self, rarity: CosmeticRarity) -> str:
        from bot.data.cosmetic_catalog import COSMETIC_CATALOG

        candidates = [c for c in COSMETIC_CATALOG.values() if c.rarity == rarity and c.released]
        if not candidates:
            candidates = [c for c in COSMETIC_CATALOG.values() if c.released]
        if not candidates:
            return "card_mystery"

        chosen = random.choice(candidates)
        return f"card_{chosen.id}"

    async def open_pack(self, guild_id: int, user_id: int, pack_type: str) -> dict:
        pack_def = CARD_PACKS.get(pack_type)
        if not pack_def:
            return {"success": False, "error": f"Unknown pack type: {pack_type}"}

        config = await self.bot.config_service.get_config(str(guild_id))
        if not config.economyConfig.cardPacksEnabled:
            return {"success": False, "error": "Card packs are currently disabled."}

        inventory = await self.bot.inventory_service.get_inventory(guild_id, user_id)
        packs = inventory.get("cosmetic_packs_unopened", [])
        has_pack = False
        for p in packs:
            if p["pack_id"] == pack_type and p.get("quantity", 0) > 0:
                has_pack = True
                break

        if not has_pack:
            return {"success": False, "error": f"You don't have any unopened **{pack_def['name']}** packs."}

        rarities = self._roll_pack(pack_def)
        card_ids = [self._pick_card_from_rarity(r) for r in rarities]
        cosmetic_ids = [cid.replace("card_", "") for cid in card_ids]
        new_unlocks = []

        for cid in cosmetic_ids:
            if not await self.bot.inventory_service.has_item(guild_id, user_id, cid):
                await self.bot.inventory_service.add_item(guild_id, user_id, cid, "card_pack")
                new_unlocks.append(cid)

        await self.bot.inventory_service.remove_cards(guild_id, user_id, pack_type, 1)
        await self.bot.inventory_service.add_cards(guild_id, user_id, card_ids)

        return {
            "success": True,
            "pack_name": pack_def["name"],
            "rarities": [r.value for r in rarities],
            "card_ids": card_ids,
            "cosmetic_ids": cosmetic_ids,
            "new_unlocks": new_unlocks,
        }

    async def buy_pack(self, guild_id: int, user_id: int, pack_type: str) -> dict:
        pack_def = CARD_PACKS.get(pack_type)
        if not pack_def:
            return {"success": False, "error": f"Unknown pack type: {pack_type}"}

        config = await self.bot.config_service.get_config(str(guild_id))
        if not config.economyConfig.cardPacksEnabled:
            return {"success": False, "error": "Card packs are currently disabled."}

        price = pack_def["price"]
        settlement = await self.bot.economy_service.settle_purchase(guild_id, user_id, price, "cosmetic_pack_purchase", reference_type="card_pack", reference_id=pack_type)
        if not settlement["success"]:
            return {"success": False, "error": f"You need **🪙 {price:,}** for a {pack_def['name']}."}

        await self.bot.inventory_service.add_card_pack(guild_id, user_id, pack_type)

        return {
            "success": True,
            "pack_name": pack_def["name"],
            "price": price,
            "tax_amount": settlement["tax_amount"],
        }

    def get_pack_info(self, pack_type: str) -> dict | None:
        return CARD_PACKS.get(pack_type)

    def get_all_packs(self) -> dict:
        return CARD_PACKS
