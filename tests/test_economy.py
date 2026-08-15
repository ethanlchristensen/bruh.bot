import unittest

from bot.cogs.economy_cog import EconomyCog


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
