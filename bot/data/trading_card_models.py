from dataclasses import dataclass
from enum import StrEnum


class TradingCardRarity(StrEnum):
    BASIC = "basic"
    COMMON = "common"
    RARE = "rare"
    EPIC = "epic"
    LEGENDARY = "legendary"
    DIAMOND = "diamond"
    PLATINUM = "platinum"


RARITY_SORT_ORDER = {rarity: index for index, rarity in enumerate(reversed(tuple(TradingCardRarity)))}


RARITY_FRAME_COLORS = {
    TradingCardRarity.BASIC: (160, 160, 160),
    TradingCardRarity.COMMON: (50, 200, 50),
    TradingCardRarity.RARE: (30, 120, 220),
    TradingCardRarity.EPIC: (160, 50, 220),
    TradingCardRarity.LEGENDARY: (240, 140, 30),
    TradingCardRarity.DIAMOND: (30, 220, 240),
    TradingCardRarity.PLATINUM: (220, 210, 180),
}

RARITY_DISPLAY_EMOJI = {
    TradingCardRarity.BASIC: "⬜",
    TradingCardRarity.COMMON: "🟢",
    TradingCardRarity.RARE: "🔵",
    TradingCardRarity.EPIC: "🟣",
    TradingCardRarity.LEGENDARY: "🟠",
    TradingCardRarity.DIAMOND: "💠",
    TradingCardRarity.PLATINUM: "💫",
}

RARITY_DISCORD_COLORS = {
    TradingCardRarity.BASIC: 0x9B9B9B,
    TradingCardRarity.COMMON: 0x1EFF00,
    TradingCardRarity.RARE: 0x0070DD,
    TradingCardRarity.EPIC: 0xA335EE,
    TradingCardRarity.LEGENDARY: 0xFF8000,
    TradingCardRarity.DIAMOND: 0x00F0FF,
    TradingCardRarity.PLATINUM: 0xE5CC80,
}

RARITY_SELLBACK_MULTIPLIER = {
    TradingCardRarity.BASIC: 0.03,
    TradingCardRarity.COMMON: 0.06,
    TradingCardRarity.RARE: 0.12,
    TradingCardRarity.EPIC: 0.25,
    TradingCardRarity.LEGENDARY: 0.40,
    TradingCardRarity.DIAMOND: 0.55,
    TradingCardRarity.PLATINUM: 0.70,
}

RARITY_BASE_VALUE = {
    TradingCardRarity.BASIC: 80,
    TradingCardRarity.COMMON: 200,
    TradingCardRarity.RARE: 500,
    TradingCardRarity.EPIC: 1500,
    TradingCardRarity.LEGENDARY: 4500,
    TradingCardRarity.DIAMOND: 12000,
    TradingCardRarity.PLATINUM: 35000,
}


@dataclass
class TradingCardDefinition:
    card_id: str
    series_id: str
    number: int
    name: str
    rarity: TradingCardRarity
    description: str
    art_path: str
    tradable: bool = True
    released: bool = True
    asset_sha256: str = ""
    generation_description: str = ""

    @property
    def sellback_value(self) -> float:
        return round(RARITY_BASE_VALUE[self.rarity] * RARITY_SELLBACK_MULTIPLIER[self.rarity], 2)


@dataclass
class CardPackDefinition:
    pack_id: str
    series_id: str
    name: str
    price: float
    cards_per_pack: int
    guaranteed_rarity: TradingCardRarity | None = None
    description: str = ""
    released: bool = True


DEFAULT_DROP_TABLE: list[tuple[TradingCardRarity, float]] = [
    (TradingCardRarity.BASIC, 0.40),
    (TradingCardRarity.COMMON, 0.30),
    (TradingCardRarity.RARE, 0.18),
    (TradingCardRarity.EPIC, 0.08),
    (TradingCardRarity.LEGENDARY, 0.03),
    (TradingCardRarity.DIAMOND, 0.008),
    (TradingCardRarity.PLATINUM, 0.002),
]

CARD_RENDER_VERSION = "6"
