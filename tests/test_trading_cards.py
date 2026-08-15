import unittest

from bot.data.trading_card_models import CARD_RENDER_VERSION, RARITY_SORT_ORDER, TradingCardRarity


class TradingCardPresentationTests(unittest.TestCase):
    def test_collection_rarity_order_prioritizes_rarest_cards(self):
        ordered = sorted(TradingCardRarity, key=RARITY_SORT_ORDER.__getitem__)

        self.assertEqual(
            ordered,
            [
                TradingCardRarity.PLATINUM,
                TradingCardRarity.DIAMOND,
                TradingCardRarity.LEGENDARY,
                TradingCardRarity.EPIC,
                TradingCardRarity.RARE,
                TradingCardRarity.COMMON,
                TradingCardRarity.BASIC,
            ],
        )

    def test_card_render_version_is_bumped_for_overlay_changes(self):
        self.assertEqual(CARD_RENDER_VERSION, "5")
