import unittest
from types import SimpleNamespace

from bot.services.mongo_reputation_service import MongoReputationService


class ReputationEscalationTests(unittest.TestCase):
    def setUp(self):
        self.config = SimpleNamespace(
            blockDurationHours=168,
            repeatBlockMultiplier=2,
            maxBlockDurationHours=1344,
        )

    def test_repeat_blocks_double_until_the_cap(self):
        durations = [MongoReputationService._automatic_block_duration_hours(self.config, count) for count in range(1, 6)]

        self.assertEqual(durations, [168, 336, 672, 1344, 1344])

    def test_invalid_escalation_values_cannot_reduce_base_duration(self):
        config = SimpleNamespace(blockDurationHours=168, repeatBlockMultiplier=0, maxBlockDurationHours=24)

        self.assertEqual(MongoReputationService._automatic_block_duration_hours(config, 3), 168)
