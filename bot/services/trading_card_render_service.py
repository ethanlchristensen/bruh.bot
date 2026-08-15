import logging
import os
from io import BytesIO
from typing import TYPE_CHECKING

from motor.motor_asyncio import AsyncIOMotorGridFSBucket
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from bot.data.trading_card_models import CARD_RENDER_VERSION, RARITY_FRAME_COLORS, TradingCardRarity

if TYPE_CHECKING:
    from bot.bruh_bot import BruhBot

CARD_CANVAS = (768, 1024)
ART_AREA = (20, 20, 748, 900)
FRAME_WIDTH = 12


class TradingCardRenderService:
    def __init__(self, bot: "BruhBot"):
        self.bot = bot
        self.logger = logging.getLogger(__name__)
        assets_bucket = self.bot.config_service.base.mongoTradingCardAssetsBucketName
        env = self.bot.config_service.environment or "dev"
        bucket_name = f"{assets_bucket}_{env}"
        db = self.bot.config_service.db
        self.gridfs = AsyncIOMotorGridFSBucket(db, bucket_name=bucket_name)
        self._rendered_cache: dict[str, bytes] = {}
        self._art_cache: dict[str, bytes] = {}
        self._assets_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets", "trading_cards")

    def _get_asset_path(self, filename: str) -> str:
        return os.path.join(self._assets_dir, filename)

    def _get_font(self, size: int) -> ImageFont.FreeTypeFont:
        font_paths = [
            os.path.join(os.path.dirname(__file__), "..", "static", "font.ttf"),
            "C:\\Windows\\Fonts\\segoeui.ttf",
            "C:\\Windows\\Fonts\\arial.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ]
        for fp in font_paths:
            if os.path.exists(fp):
                return ImageFont.truetype(fp, size)
        return ImageFont.load_default()

    async def _load_art(self, card_id: str) -> Image.Image | None:
        if card_id in self._art_cache:
            return Image.open(BytesIO(self._art_cache[card_id])).convert("RGBA")

        # Try GridFS first
        try:
            gridfs_out = await self.gridfs.open_download_stream_by_name(card_id)
            data = await gridfs_out.read()
            self._art_cache[card_id] = data
            return Image.open(BytesIO(data)).convert("RGBA")
        except Exception:
            pass

        # Fallback: try local filesystem (for migration/development)
        card = self.bot.trading_card_catalog_service.get_card(card_id)
        if card and card.art_path:
            path = self._get_asset_path(card.art_path)
            if os.path.exists(path):
                img = Image.open(path).convert("RGBA")
                data = BytesIO()
                img.save(data, format="PNG")
                self._art_cache[card_id] = data.getvalue()
                return img

        self.logger.debug(f"Card art not found for: {card_id}")
        return None

    def _create_frame(self, canvas: Image.Image, rarity: TradingCardRarity):
        color = RARITY_FRAME_COLORS.get(rarity, (160, 160, 160))
        bounds = [4, 4, CARD_CANVAS[0] - 5, CARD_CANVAS[1] - 5]

        glow = Image.new("RGBA", CARD_CANVAS, (0, 0, 0, 0))
        glow_draw = ImageDraw.Draw(glow)
        glow_draw.rounded_rectangle(bounds, radius=20, outline=(*color, 180), width=24)
        glow = glow.filter(ImageFilter.GaussianBlur(18))
        canvas.alpha_composite(glow)

        frame = Image.new("RGBA", CARD_CANVAS, (0, 0, 0, 0))
        draw = ImageDraw.Draw(frame)
        draw.rounded_rectangle(
            bounds,
            radius=20,
            outline=(*color, 100),
            width=FRAME_WIDTH + 8,
        )
        draw.rounded_rectangle(
            [8, 8, CARD_CANVAS[0] - 9, CARD_CANVAS[1] - 9],
            radius=17,
            outline=(*color, 255),
            width=FRAME_WIDTH,
        )
        draw.rounded_rectangle(
            [20, 20, CARD_CANVAS[0] - 21, CARD_CANVAS[1] - 21],
            radius=12,
            outline=(255, 255, 255, 70),
            width=2,
        )
        canvas.alpha_composite(frame)

    def _draw_text_box(self, canvas: Image.Image, rarity: TradingCardRarity, name: str, card_number: int, series_name: str):
        draw = ImageDraw.Draw(canvas)
        color = RARITY_FRAME_COLORS.get(rarity, (160, 160, 160))
        panel = [24, CARD_CANVAS[1] - 142, CARD_CANVAS[0] - 24, CARD_CANVAS[1] - 24]

        overlay = Image.new("RGBA", CARD_CANVAS, (0, 0, 0, 0))
        overlay_draw = ImageDraw.Draw(overlay)
        fade_start = CARD_CANVAS[1] - 220
        for y in range(fade_start, CARD_CANVAS[1]):
            progress = (y - fade_start) / (CARD_CANVAS[1] - fade_start)
            alpha = int(16 + progress * 174)
            overlay_draw.line([(0, y), (CARD_CANVAS[0], y)], fill=(10, 13, 20, alpha))
        overlay_draw.rounded_rectangle(panel, radius=18, fill=(10, 13, 20, 194), outline=(*color, 150), width=2)
        canvas.paste(overlay, (0, 0), overlay)

        try:
            name_font = self._get_font(38)
            rarity_font = self._get_font(26)
            series_font = self._get_font(20)
        except Exception:
            name_font = ImageFont.load_default()
            rarity_font = ImageFont.load_default()
            series_font = ImageFont.load_default()

        badge_text = rarity.value.upper()
        badge_width = draw.textbbox((0, 0), badge_text, font=rarity_font)[2] + 24
        badge = [36, CARD_CANVAS[1] - 128, 36 + badge_width, CARD_CANVAS[1] - 96]
        draw.rounded_rectangle(badge, radius=12, fill=(8, 12, 18, 220), outline=(*color, 210), width=1)
        draw.text(((badge[0] + badge[2]) // 2, (badge[1] + badge[3]) // 2), badge_text, fill=(242, 245, 250), font=rarity_font, anchor="mm")
        number_badge = [CARD_CANVAS[0] - 100, CARD_CANVAS[1] - 128, CARD_CANVAS[0] - 36, CARD_CANVAS[1] - 96]
        draw.rounded_rectangle(number_badge, radius=12, fill=(8, 12, 18, 220), outline=(*color, 150), width=1)
        draw.text(((number_badge[0] + number_badge[2]) // 2, (number_badge[1] + number_badge[3]) // 2), f"#{card_number}", fill=(242, 245, 250), font=series_font, anchor="mm")
        draw.text((CARD_CANVAS[0] // 2, CARD_CANVAS[1] - 92), name, fill=(248, 249, 252), font=name_font, anchor="mt")
        draw.text((CARD_CANVAS[0] // 2, CARD_CANVAS[1] - 48), series_name, fill=(178, 186, 198), font=series_font, anchor="mt")

    def _cache_key(self, card_id: str) -> str:
        card = self.bot.trading_card_catalog_service.get_card(card_id)
        sha = card.asset_sha256 if card else "nocatalog"
        return f"{card_id}:{sha}:{CARD_RENDER_VERSION}"

    async def render_card(self, card_id: str) -> BytesIO | None:
        cache_key = self._cache_key(card_id)
        if cache_key in self._rendered_cache:
            return BytesIO(self._rendered_cache[cache_key])

        card = self.bot.trading_card_catalog_service.get_card(card_id)
        if not card:
            return None

        art = await self._load_art(card_id)
        canvas = Image.new("RGBA", CARD_CANVAS, (20, 20, 24, 255))

        if art:
            art_resized = art.resize((ART_AREA[2] - ART_AREA[0], ART_AREA[3] - ART_AREA[1]), Image.LANCZOS)
            canvas.paste(art_resized, (ART_AREA[0], ART_AREA[1]), art_resized)
        else:
            draw = ImageDraw.Draw(canvas)
            for y in range(ART_AREA[3] - ART_AREA[1]):
                r = int(40 + (y / (ART_AREA[3] - ART_AREA[1])) * 30)
                g = int(20 + (y / (ART_AREA[3] - ART_AREA[1])) * 20)
                b = int(30 + (y / (ART_AREA[3] - ART_AREA[1])) * 50)
                draw.line([(ART_AREA[0], ART_AREA[1] + y), (ART_AREA[2], ART_AREA[1] + y)], fill=(r, g, b))

        display_name = card.series_id.replace("_", " ").title()
        self._create_frame(canvas, card.rarity)
        self._draw_text_box(canvas, card.rarity, card.name, card.number, display_name)

        buffer = BytesIO()
        canvas.save(buffer, format="PNG")
        buffer.seek(0)
        # Do not cache fallback renders; an asset may be uploaded after the first request.
        if art is not None:
            self._rendered_cache[cache_key] = buffer.getvalue()
        return BytesIO(buffer.getvalue())

    def invalidate_cache(self):
        self._rendered_cache.clear()
        self._art_cache.clear()

    def invalidate_card_cache(self, card_id: str):
        self._art_cache.pop(card_id, None)
        for key in list(self._rendered_cache.keys()):
            if key.startswith(f"{card_id}:"):
                del self._rendered_cache[key]

    async def render_collection_grid(self, card_ids: list[str], cards_per_row: int = 5, thumb_width: int = 192) -> BytesIO | None:
        if not card_ids:
            return None

        THUMB_HEIGHT = int(thumb_width * 4 / 3)
        GAP = 8
        MAX_CARDS = 50

        card_ids = card_ids[:MAX_CARDS]
        images: list[Image.Image] = []

        for cid in card_ids:
            rendered = await self.render_card(cid)
            if rendered:
                img = Image.open(rendered).convert("RGBA")
                img = img.resize((thumb_width, THUMB_HEIGHT), Image.LANCZOS)
                images.append(img)

        if not images:
            return None

        cols = min(cards_per_row, len(images))
        rows = (len(images) + cols - 1) // cols

        grid_w = cols * thumb_width + (cols - 1) * GAP
        grid_h = rows * THUMB_HEIGHT + (rows - 1) * GAP

        canvas = Image.new("RGBA", (grid_w, grid_h), (30, 30, 30, 255))

        for idx, img in enumerate(images):
            row = idx // cols
            col = idx % cols
            x = col * (thumb_width + GAP)
            y = row * (THUMB_HEIGHT + GAP)
            canvas.paste(img, (x, y), img)

        buf = BytesIO()
        canvas.save(buf, format="PNG")
        buf.seek(0)
        return buf
