import logging
from typing import TYPE_CHECKING

from bot.data.trading_card_models import CardPackDefinition, TradingCardDefinition, TradingCardRarity

if TYPE_CHECKING:
    from bot.bruh_bot import BruhBot


class MongoTradingCardCatalogService:
    def __init__(self, bot: "BruhBot"):
        self.bot = bot
        self.sets_col = self.bot.config_service.col(self.bot.config_service.base.mongoTradingCardSetsCollectionName)
        self.catalog_col = self.bot.config_service.col(self.bot.config_service.base.mongoTradingCardCatalogCollectionName)
        self.packs_col = self.bot.config_service.col(self.bot.config_service.base.mongoTradingCardPacksCollectionName)
        self.logger = logging.getLogger(__name__)
        self._cards_cache: dict[str, TradingCardDefinition] = {}
        self._packs_cache: dict[str, CardPackDefinition] = {}

    async def initialize(self):
        await self._ensure_indexes()
        await self.reload_catalog()

    async def _ensure_indexes(self):
        try:
            await self.sets_col.create_index([("set_id", 1)], unique=True)
            await self.catalog_col.create_index([("card_id", 1)], unique=True)
            await self.catalog_col.create_index("set_id")
            await self.catalog_col.create_index("rarity")
            await self.packs_col.create_index([("pack_id", 1)], unique=True)
            self.logger.info("Created indexes on TradingCard catalog collections")
        except Exception as e:
            self.logger.warning(f"Could not create trading card catalog indexes: {e}")

    async def reload_catalog(self):
        self._cards_cache.clear()
        self._packs_cache.clear()

        async for doc in self.catalog_col.find({"released": True}):
            friendly = doc.get("friendly_description") or doc.get("description", "")
            card = TradingCardDefinition(
                card_id=doc["card_id"],
                series_id=doc["set_id"],
                number=doc["number"],
                rarity=TradingCardRarity(doc["rarity"]),
                name=doc["name"],
                description=friendly,
                art_path="",  # GridFS — resolved at render time
                tradable=doc.get("tradable", True),
                released=True,
                asset_sha256=doc.get("asset_sha256", ""),
                generation_description=doc.get("description", ""),
            )
            self._cards_cache[card.card_id] = card

        async for doc in self.packs_col.find({"released": True}):
            guaranteed = doc.get("guaranteed_rarity")
            pk = CardPackDefinition(
                pack_id=doc["pack_id"],
                series_id=doc["set_id"],
                name=doc["name"],
                price=doc["price"],
                cards_per_pack=doc["cards_per_pack"],
                guaranteed_rarity=TradingCardRarity(guaranteed) if guaranteed else None,
                description=doc.get("description", ""),
                released=True,
            )
            self._packs_cache[pk.pack_id] = pk

        self.logger.info(f"Loaded trading card catalog: {len(self._cards_cache)} cards, {len(self._packs_cache)} packs")

    # ── Card queries ──
    def get_card(self, card_id: str) -> TradingCardDefinition | None:
        return self._cards_cache.get(card_id)

    def get_all_released_cards(self) -> list[TradingCardDefinition]:
        return list(self._cards_cache.values())

    def get_cards_by_rarity(self, rarity: TradingCardRarity) -> list[TradingCardDefinition]:
        return [c for c in self._cards_cache.values() if c.rarity == rarity]

    def get_cards_by_series(self, series_id: str) -> list[TradingCardDefinition]:
        return [c for c in self._cards_cache.values() if c.series_id == series_id]

    def get_series_total(self, series_id: str) -> int:
        return len(self.get_cards_by_series(series_id))

    def get_series_list(self) -> list[str]:
        return list({c.series_id for c in self._cards_cache.values()})

    # ── Pack queries ──
    def get_pack(self, pack_id: str) -> CardPackDefinition | None:
        return self._packs_cache.get(pack_id)

    def get_all_packs(self) -> dict[str, CardPackDefinition]:
        return self._packs_cache

    def get_packs_by_series(self, series_id: str) -> dict[str, CardPackDefinition]:
        return {k: v for k, v in self._packs_cache.items() if v.series_id == series_id}

    def get_eligible_cards_for_pack(self, pack_id: str) -> dict[str, list[dict]]:
        """Returns eligible cards for a pack, grouped by rarity.

        Only shows cards that actually belong to this pack's series — the per-rarity
        fallback to all-series cards (used during gameplay) is intentionally omitted
        so the admin view accurately reflects the collection's contents.
        """
        pack = self.get_pack(pack_id)
        if not pack:
            return {}

        series_cards = self.get_cards_by_series(pack.series_id)

        grouped: dict[str, list[dict]] = {}
        rarity_order = [TradingCardRarity.BASIC, TradingCardRarity.COMMON, TradingCardRarity.RARE, TradingCardRarity.EPIC, TradingCardRarity.LEGENDARY, TradingCardRarity.DIAMOND, TradingCardRarity.PLATINUM]

        for rarity in rarity_order:
            candidates = [c for c in series_cards if c.rarity == rarity]
            grouped[rarity.value] = [
                {
                    "card_id": c.card_id,
                    "number": c.number,
                    "name": c.name,
                    "rarity": c.rarity.value,
                    "description": c.description,
                    "asset_sha256": c.asset_sha256,
                }
                for c in sorted(candidates, key=lambda x: x.number)
            ]

        return grouped
