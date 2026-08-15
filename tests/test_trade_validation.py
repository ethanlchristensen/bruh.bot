import unittest
from types import SimpleNamespace

from bot.cogs.economy_cog import EconomyCog


class FakeEconomyService:
    async def get_profile(self, _guild_id, _user_id):
        return {"bruh_coins": 100.0}


class FakeInventoryService:
    def __init__(self, inventories):
        self.inventories = inventories

    async def get_inventory(self, _guild_id, user_id):
        return self.inventories[user_id]


class FakeTradingCardService:
    def __init__(self, cards):
        self.cards = cards

    async def get_card_quantity(self, _guild_id, user_id, card_id):
        return self.cards.get((user_id, card_id), 0)


class TradeValidationTests(unittest.IsolatedAsyncioTestCase):
    def test_trade_quantities_aggregate_duplicate_ids(self):
        self.assertEqual(EconomyCog._trade_quantities(["card_a", "card_a", "card_b"]), {"card_a": 2, "card_b": 1})

    async def test_cosmetic_trade_rejects_duplicate_request_without_enough_copies(self):
        cog = EconomyCog.__new__(EconomyCog)
        cog.bot = SimpleNamespace(
            inventory_service=FakeInventoryService(
                {
                    1: {"items": [], "equipped": {}, "cosmetic_cards": []},
                    2: {"items": [], "equipped": {}, "cosmetic_cards": [{"card_id": "card_a", "quantity": 1}]},
                }
            ),
            economy_service=FakeEconomyService(),
        )

        error = await cog._validate_cosmetic_trade(10, 1, 2, [], [], [], ["card_a", "card_a"], 0, 0)

        self.assertIn("enough", error)

    async def test_card_trade_rejects_recipient_who_spent_requested_card(self):
        cog = EconomyCog.__new__(EconomyCog)
        cog.bot = SimpleNamespace(
            trading_card_service=FakeTradingCardService({(1, "card_a"): 1, (2, "card_b"): 0}),
            trading_card_catalog_service=SimpleNamespace(get_card=lambda _card_id: None),
            economy_service=FakeEconomyService(),
        )

        error = await cog._validate_card_trade(10, 1, 2, ["card_a"], ["card_b"], 0, 0)

        self.assertIn("no longer has enough", error)
