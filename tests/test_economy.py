import unittest
from types import SimpleNamespace

from bot.cogs.economy_cog import EconomyCog, pack_id_autocomplete


class EconomyRankProgressTests(unittest.TestCase):
    def setUp(self):
        self.cog = EconomyCog.__new__(EconomyCog)

    def test_level_21_progress_uses_cumulative_xp_thresholds(self):
        result = self.cog._format_xp_progress(29313, 21)

        self.assertEqual(result, "`███████░░░` 2363/3355 XP")

    def test_progress_bar_is_limited_to_ten_characters(self):
        result = self.cog._format_xp_progress(100000, 21)

        bar = result.split("`")[1]
        self.assertEqual(len(bar), 10)
        self.assertEqual(bar, "██████████")


class TradingCardPackAutocompleteTests(unittest.IsolatedAsyncioTestCase):
    async def test_pack_autocomplete_returns_catalog_matches(self):
        packs = [
            SimpleNamespace(pack_id="alpha_standard", name="Alpha Standard", price=350),
            SimpleNamespace(pack_id="beta_premium", name="Beta Premium", price=1100),
        ]
        interaction = SimpleNamespace(
            client=SimpleNamespace(
                trading_card_catalog_service=SimpleNamespace(get_all_packs=lambda: {pack.pack_id: pack for pack in packs})
            )
        )

        choices = await pack_id_autocomplete(interaction, "premium")

        self.assertEqual([(choice.name, choice.value) for choice in choices], [("Beta Premium — 🪙 1,100", "beta_premium")])

    async def test_pack_autocomplete_limits_results_to_discord_choice_limit(self):
        packs = [SimpleNamespace(pack_id=f"pack_{index}", name=f"Pack {index}", price=index) for index in range(30)]
        interaction = SimpleNamespace(
            client=SimpleNamespace(
                trading_card_catalog_service=SimpleNamespace(get_all_packs=lambda: {pack.pack_id: pack for pack in packs})
            )
        )

        choices = await pack_id_autocomplete(interaction, "")

        self.assertEqual(len(choices), 25)
