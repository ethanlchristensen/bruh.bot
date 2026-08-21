import unittest

from PIL import Image

from tools.card_gen import CardSetGenerator, apply_theme_story


class CardGenerationPromptTests(unittest.TestCase):
    def test_base_prompt_includes_themed_mechanics(self):
        generator = CardSetGenerator()

        prompt = generator._build_base_prompt("Canopy Circuit", "A reclaimed server vault.", "Molded handheld plastic frame with d-pad grips.")

        self.assertIn("Molded handheld plastic frame", prompt)
        self.assertIn("No text", prompt)

    def test_character_card_uses_canonical_reference_instruction(self):
        generator = CardSetGenerator()

        prompt = generator._build_card_prompt({"description": "A moss-covered handheld scout crosses roots.", "featured_character_ids": ["cartridge_wisp"]})

        self.assertIn("cartridge_wisp", prompt)
        self.assertIn("canonical", prompt)
        self.assertIn("exactly ONE visible instance", prompt)
        self.assertIn("Never duplicate", prompt)
        self.assertIn("zero text", prompt)

    def test_scene_card_does_not_claim_character_references(self):
        generator = CardSetGenerator()

        prompt = generator._build_card_prompt({"description": "Fiber optic vines fill a dark corridor."})

        self.assertNotIn("canonical", prompt)

    def test_theme_story_assigns_characters_and_escalates_by_rarity(self):
        cards = [
            {"number": 1, "rarity": "basic"},
            {"number": 27, "rarity": "rare"},
            {"number": 42, "rarity": "legendary"},
        ]
        theme_bible = {
            "characters": [
                {"id": "rootwake", "faction": "plugs"},
                {"id": "wisp", "faction": "slots"},
                {"id": "relay", "faction": "nodes"},
            ]
        }

        apply_theme_story(cards, theme_bible)

        self.assertEqual(cards[0]["featured_character_ids"], ["rootwake"])
        self.assertEqual(len(cards[1]["featured_character_ids"]), 2)
        self.assertEqual(cards[2]["featured_character_ids"], ["rootwake", "wisp", "relay"])
        self.assertIn("convergence", cards[2]["story_beat"])

    def test_character_card_uses_base_and_character_image_references(self):
        generator = CardSetGenerator()
        generator.base_image = Image.new("RGBA", (1, 1))
        character_image = Image.new("RGBA", (1, 1))
        generator.character_images = {"cartridge_wisp": character_image}

        references = generator._reference_images_for_card({"featured_character_ids": ["cartridge_wisp"]})

        self.assertEqual(references, [generator.base_image, character_image])
