from .models import CosmeticItem, CosmeticRarity, CosmeticSlot

COSMETIC_CATALOG: dict[str, CosmeticItem] = {}


def _add(item: CosmeticItem):
    COSMETIC_CATALOG[item.id] = item
    return item


# ── HEADWEAR ──
_add(CosmeticItem("hat_baseball_basic", "Basic Baseball Cap", CosmeticSlot.HEADWEAR, CosmeticRarity.BASIC, 50, "A simple baseball cap.", "headwear/hat_baseball_basic.png"))
_add(CosmeticItem("hat_beanie_common", "Common Beanie", CosmeticSlot.HEADWEAR, CosmeticRarity.COMMON, 150, "A cozy beanie.", "headwear/hat_beanie_common.png"))
_add(CosmeticItem("hat_wizard_rare", "Rare Wizard Hat", CosmeticSlot.HEADWEAR, CosmeticRarity.RARE, 500, "A mystical wizard hat.", "headwear/hat_wizard_rare.png"))
_add(CosmeticItem("hat_crown_epic", "Epic Crown", CosmeticSlot.HEADWEAR, CosmeticRarity.EPIC, 2000, "A royal crown fit for a king.", "headwear/hat_crown_epic.png"))
_add(CosmeticItem("hat_halo_legendary", "Legendary Halo", CosmeticSlot.HEADWEAR, CosmeticRarity.LEGENDARY, 8000, "A divine halo of light.", "headwear/hat_halo_legendary.png"))

# ── OUTFIT ──
_add(CosmeticItem("outfit_hoodie_basic", "Basic Hoodie", CosmeticSlot.OUTFIT, CosmeticRarity.BASIC, 75, "A plain hoodie.", "outfit/outfit_hoodie_basic.png"))
_add(CosmeticItem("outfit_jacket_common", "Common Jacket", CosmeticSlot.OUTFIT, CosmeticRarity.COMMON, 200, "A stylish jacket.", "outfit/outfit_jacket_common.png"))
_add(CosmeticItem("outfit_armor_rare", "Rare Armor", CosmeticSlot.OUTFIT, CosmeticRarity.RARE, 600, "Sturdy plate armor.", "outfit/outfit_armor_rare.png"))
_add(CosmeticItem("outfit_robe_epic", "Epic Mage Robe", CosmeticSlot.OUTFIT, CosmeticRarity.EPIC, 2500, "Robes crackling with arcane energy.", "outfit/outfit_robe_epic.png"))

# ── BACKGROUND ──
_add(CosmeticItem("bg_solid_common", "Common Solid Background", CosmeticSlot.BACKGROUND, CosmeticRarity.COMMON, 100, "A simple solid color background.", "background/bg_solid_common.png"))
_add(CosmeticItem("bg_forest_rare", "Rare Forest Background", CosmeticSlot.BACKGROUND, CosmeticRarity.RARE, 400, "A lush forest backdrop.", "background/bg_forest_rare.png"))
_add(CosmeticItem("bg_nebula_epic", "Epic Nebula", CosmeticSlot.BACKGROUND, CosmeticRarity.EPIC, 1500, "A stunning cosmic nebula.", "background/bg_nebula_epic.png"))

# ── FACE ACCESSORY ──
_add(CosmeticItem("face_glasses_basic", "Basic Glasses", CosmeticSlot.FACE_ACCESSORY, CosmeticRarity.BASIC, 40, "A pair of reading glasses.", "face/face_glasses_basic.png"))
_add(CosmeticItem("face_sunglasses_common", "Common Sunglasses", CosmeticSlot.FACE_ACCESSORY, CosmeticRarity.COMMON, 120, "Cool shades.", "face/face_sunglasses_common.png"))
_add(CosmeticItem("face_mask_rare", "Rare Mask", CosmeticSlot.FACE_ACCESSORY, CosmeticRarity.RARE, 450, "A mysterious mask.", "face/face_mask_rare.png"))
_add(CosmeticItem("face_monocle_epic", "Epic Monocle", CosmeticSlot.FACE_ACCESSORY, CosmeticRarity.EPIC, 1800, "A gentleman's monocle with a golden chain.", "face/face_monocle_epic.png"))

# ── HAND ITEM ──
_add(CosmeticItem("hand_sword_rare", "Rare Sword", CosmeticSlot.HAND_ITEM, CosmeticRarity.RARE, 550, "A gleaming blade.", "hand/hand_sword_rare.png"))
_add(CosmeticItem("hand_staff_epic", "Epic Staff", CosmeticSlot.HAND_ITEM, CosmeticRarity.EPIC, 2200, "A staff humming with power.", "hand/hand_staff_epic.png"))
_add(CosmeticItem("hand_rose_legendary", "Legendary Rose", CosmeticSlot.HAND_ITEM, CosmeticRarity.LEGENDARY, 7500, "An enchanted rose that never wilts.", "hand/hand_rose_legendary.png"))

# ── BACK ACCESSORY ──
_add(CosmeticItem("back_cape_rare", "Rare Cape", CosmeticSlot.BACK_ACCESSORY, CosmeticRarity.RARE, 480, "A flowing cape.", "back/back_cape_rare.png"))
_add(CosmeticItem("back_wings_epic", "Epic Wings", CosmeticSlot.BACK_ACCESSORY, CosmeticRarity.EPIC, 3000, "Majestic wings.", "back/back_wings_epic.png"))
_add(CosmeticItem("back_aura_legendary", "Legendary Aura", CosmeticSlot.BACK_ACCESSORY, CosmeticRarity.LEGENDARY, 9000, "A shimmering aura of light.", "back/back_aura_legendary.png"))

# ── FOREGROUND ──
_add(CosmeticItem("fg_particles_common", "Common Particles", CosmeticSlot.FOREGROUND, CosmeticRarity.COMMON, 130, "Floating sparkles.", "foreground/fg_particles_common.png"))
_add(CosmeticItem("fg_rain_rare", "Rare Rain Effect", CosmeticSlot.FOREGROUND, CosmeticRarity.RARE, 420, "A gentle rain overlay.", "foreground/fg_rain_rare.png"))
_add(CosmeticItem("fg_butterflies_epic", "Epic Butterflies", CosmeticSlot.FOREGROUND, CosmeticRarity.EPIC, 2000, "Magical butterflies floating around you.", "foreground/fg_butterflies_epic.png"))


def get_cosmetic(item_id: str) -> CosmeticItem | None:
    return COSMETIC_CATALOG.get(item_id)


def get_cosmetics_by_slot(slot: CosmeticSlot) -> list[CosmeticItem]:
    return [item for item in COSMETIC_CATALOG.values() if item.slot == slot and item.released]


def get_cosmetics_by_rarity(rarity: CosmeticRarity) -> list[CosmeticItem]:
    return [item for item in COSMETIC_CATALOG.values() if item.rarity == rarity and item.released]


def get_all_released() -> list[CosmeticItem]:
    return [item for item in COSMETIC_CATALOG.values() if item.released]
