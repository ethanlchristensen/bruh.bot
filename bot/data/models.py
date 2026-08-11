from dataclasses import dataclass, field
from enum import Enum


class CosmeticRarity(str, Enum):
    BASIC = "basic"
    COMMON = "common"
    RARE = "rare"
    EPIC = "epic"
    LEGENDARY = "legendary"
    DIAMOND = "diamond"
    PLATINUM = "platinum"


class CosmeticSlot(str, Enum):
    BACKGROUND = "background"
    BACK_ACCESSORY = "back_accessory"
    OUTFIT = "outfit"
    HEADWEAR = "headwear"
    FACE_ACCESSORY = "face_accessory"
    HAND_ITEM = "hand_item"
    FOREGROUND = "foreground"


class PackType(str, Enum):
    STANDARD = "standard"
    PREMIUM = "premium"
    EVENT = "event"


RARITY_COLORS = {
    CosmeticRarity.BASIC: 0x9B9B9B,
    CosmeticRarity.COMMON: 0x1EFF00,
    CosmeticRarity.RARE: 0x0070DD,
    CosmeticRarity.EPIC: 0xA335EE,
    CosmeticRarity.LEGENDARY: 0xFF8000,
    CosmeticRarity.DIAMOND: 0x00F0FF,
    CosmeticRarity.PLATINUM: 0xE5CC80,
}

RARITY_DISPLAY_EMOJI = {
    CosmeticRarity.BASIC: "⬜",
    CosmeticRarity.COMMON: "🟢",
    CosmeticRarity.RARE: "🔵",
    CosmeticRarity.EPIC: "🟣",
    CosmeticRarity.LEGENDARY: "🟠",
    CosmeticRarity.DIAMOND: "💠",
    CosmeticRarity.PLATINUM: "💫",
}

RARITY_SELLBACK_MULTIPLIER = {
    CosmeticRarity.BASIC: 0.05,
    CosmeticRarity.COMMON: 0.1,
    CosmeticRarity.RARE: 0.2,
    CosmeticRarity.EPIC: 0.35,
    CosmeticRarity.LEGENDARY: 0.5,
    CosmeticRarity.DIAMOND: 0.65,
    CosmeticRarity.PLATINUM: 0.8,
}


@dataclass
class CosmeticItem:
    id: str
    name: str
    slot: CosmeticSlot
    rarity: CosmeticRarity
    price: float
    description: str = ""
    asset_filename: str = ""
    collection: str | None = None
    released: bool = True


@dataclass
class CardPackDefinition:
    id: str
    name: str
    type: PackType
    price: float
    description: str = ""
    drop_table: list[tuple[str, float]] = field(default_factory=list)
    card_image_prefix: str = "card"


SLOT_LAYER_ORDER = [
    CosmeticSlot.BACKGROUND,
    CosmeticSlot.BACK_ACCESSORY,
    CosmeticSlot.OUTFIT,
    CosmeticSlot.HEADWEAR,
    CosmeticSlot.FACE_ACCESSORY,
    CosmeticSlot.HAND_ITEM,
    CosmeticSlot.FOREGROUND,
]
