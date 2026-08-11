import logging
import os
from io import BytesIO
from typing import TYPE_CHECKING

from PIL import Image

from bot.data.cosmetic_catalog import get_cosmetic
from bot.data.models import SLOT_LAYER_ORDER, CosmeticSlot

if TYPE_CHECKING:
    from bot.bruh_bot import BruhBot

CHARACTER_SIZE = (512, 512)
DEFAULT_BASE_IMAGE = "character_base.png"


class CharacterRenderService:
    def __init__(self, bot: "BruhBot"):
        self.bot = bot
        self.logger = logging.getLogger(__name__)
        self.assets_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets", "characters")
        self._rendered_cache: dict[str, bytes] = {}

    def _get_asset_path(self, filename: str) -> str:
        return os.path.join(self.assets_dir, filename)

    def _get_base_image(self) -> Image.Image:
        base_path = self._get_asset_path(DEFAULT_BASE_IMAGE)
        if os.path.exists(base_path):
            return Image.open(base_path).convert("RGBA")
        return Image.new("RGBA", CHARACTER_SIZE, (54, 57, 63, 255))

    def _load_layer(self, filename: str) -> Image.Image | None:
        if not filename:
            return None
        path = self._get_asset_path(filename)
        if os.path.exists(path):
            return Image.open(path).convert("RGBA").resize(CHARACTER_SIZE, Image.LANCZOS)
        self.logger.debug(f"Asset not found: {path}")
        return None

    def _cache_key(self, guild_id: int, user_id: int, equipped: dict[str, str | None]) -> str:
        parts = [f"{guild_id}", f"{user_id}"]
        for slot in SLOT_LAYER_ORDER:
            parts.append(equipped.get(slot.value, "none") or "none")
        return "|".join(parts)

    def _compose_character(self, equipped: dict[str, str | None]) -> Image.Image:
        base = self._get_base_image()
        for slot in SLOT_LAYER_ORDER:
            item_id = equipped.get(slot.value, "default" if slot == CosmeticSlot.BACKGROUND else None)
            if not item_id and slot == CosmeticSlot.BACKGROUND:
                continue
            if item_id and item_id != "default":
                cosmetic = get_cosmetic(item_id)
                if cosmetic:
                    layer = self._load_layer(cosmetic.asset_filename)
                    if layer:
                        base.paste(layer, (0, 0), layer)
        return base

    async def render_character(self, guild_id: int, user_id: int, equipped: dict[str, str | None] | None = None) -> BytesIO:
        if equipped is None:
            equipped = await self.bot.inventory_service.get_equipped(guild_id, user_id)

        cache_key = self._cache_key(guild_id, user_id, equipped)
        if cache_key in self._rendered_cache:
            return BytesIO(self._rendered_cache[cache_key])

        image = self._compose_character(equipped)
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        buffer.seek(0)
        self._rendered_cache[cache_key] = buffer.getvalue()
        return BytesIO(buffer.getvalue())

    async def render_preview(self, guild_id: int, user_id: int, preview_item_id: str) -> BytesIO | None:
        preview_cosmetic = get_cosmetic(preview_item_id)
        if not preview_cosmetic:
            return None

        equipped = await self.bot.inventory_service.get_equipped(guild_id, user_id)
        preview_equipped = dict(equipped)
        preview_equipped[preview_cosmetic.slot.value] = preview_item_id

        image = self._compose_character(preview_equipped)
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        buffer.seek(0)
        return buffer

    def invalidate_cache(self, guild_id: int = 0, user_id: int = 0):
        if guild_id == 0 and user_id == 0:
            self._rendered_cache.clear()
            return
        prefix = f"{guild_id}|{user_id}|"
        for key in list(self._rendered_cache.keys()):
            if key.startswith(prefix):
                del self._rendered_cache[key]
