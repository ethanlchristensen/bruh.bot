import logging
import os
import random
from datetime import datetime
from enum import Enum

import discord

from .music.types import AudioMetaData, AudioSource


class BrandColor(Enum):
    PRIMARY = 0x9B59B6  # Amethyst Purple
    ACCENT = 0x00D1FF  # Neon Cyan
    SUCCESS = 0x4BFFAB  # Emerald Mint
    ERROR = 0xFF4B4B  # Crimson Burst
    GOLD = 0xF1C40F  # Celestial Gold


class EmbedService:
    """Service for creating various branded Discord embeds"""

    logger = logging.getLogger(__name__)
    source_labels = {AudioSource.SOUNDCLOUD: "Artist", AudioSource.YOUTUBE: "Channel"}

    # Placeholder for AI-generated brand images (URLs or local paths)
    BRAND_IMAGES = {
        "NOW_PLAYING": None,
        "QUEUE": None,
        "SUCCESS": None,
        "ERROR": None,
        "MORNING": None,
    }

    def _create_base_embed(
        self,
        title: str | None = None,
        description: str | None = None,
        color: BrandColor = BrandColor.PRIMARY,
    ) -> discord.Embed:
        """Internal helper to create a consistent base embed"""
        embed = discord.Embed(
            title=title,
            description=description,
            color=color.value,
            timestamp=datetime.now(),
        )
        embed.set_footer(text="Celestial Juno • AI Powered")
        return embed

    def create_action_embed(
        self,
        title: str,
        message: str,
        is_success: bool = True,
        thumbnail_url: str | None = None,
    ) -> discord.Embed:
        """Create a standard embed for command results"""
        color = BrandColor.SUCCESS if is_success else BrandColor.ERROR
        embed = self._create_base_embed(title=title, description=message, color=color)

        if thumbnail_url:
            embed.set_thumbnail(url=thumbnail_url)
        elif self.BRAND_IMAGES.get("SUCCESS" if is_success else "ERROR"):
            embed.set_thumbnail(url=self.BRAND_IMAGES["SUCCESS" if is_success else "ERROR"])

        return embed

    def create_added_to_queue_embed(self, metadata: AudioMetaData, position: int) -> discord.Embed:
        """Create an embed for when a track is added to the queue"""
        embed = self._create_base_embed(
            title="✨ Added to Queue",
            description=f"**[{metadata.title}]({metadata.webpage_url})**",
            color=BrandColor.ACCENT,
        )

        embed.add_field(
            name=self.source_labels.get(metadata.source, "Source"),
            value=(metadata.author if not metadata.author_url else f"[{metadata.author}]({metadata.author_url})"),
            inline=True,
        )
        embed.add_field(
            name="Duration",
            value=self.format_duration(metadata.effective_duration),
            inline=True,
        )
        embed.add_field(name="Queue Position", value=f"`#{position}`", inline=True)

        if metadata.requested_by:
            embed.set_footer(text=f"Requested by: {metadata.requested_by} • Celestial Juno")

        if metadata.thumbnail_url:
            embed.set_thumbnail(url=metadata.thumbnail_url)

        if metadata.filter_preset:
            embed.add_field(
                name="Active Filter",
                value=f"🧪 {metadata.filter_preset.display_name}",
                inline=False,
            )

        return embed

    def create_now_playing_embed(self, metadata: AudioMetaData) -> discord.Embed:
        """Create an embed for currently playing track"""
        embed = self._create_base_embed(
            title="🎵 Now Playing",
            description=f"**[{metadata.title}]({metadata.webpage_url})**",
            color=BrandColor.PRIMARY,
        )

        author_val = metadata.author if not metadata.author_url else f"[{metadata.author}]({metadata.author_url})"
        embed.add_field(
            name=self.source_labels.get(metadata.source, "Source"),
            value=author_val,
            inline=True,
        )
        embed.add_field(
            name="Duration",
            value=self.format_duration(metadata.effective_duration),
            inline=True,
        )

        if metadata.likes is not None:
            embed.add_field(name="Likes", value=f"👍 {metadata.likes:,}", inline=True)

        emoji_filename = None
        if metadata.thumbnail_url:
            embed.set_thumbnail(url=metadata.thumbnail_url)
        elif self.BRAND_IMAGES.get("NOW_PLAYING"):
            embed.set_thumbnail(url=self.BRAND_IMAGES["NOW_PLAYING"])
        else:
            # Fallback to legacy random emoji if no brand image set
            try:
                emoji_path = os.path.join(os.getcwd(), "emojis")
                if os.path.exists(emoji_path) and os.listdir(emoji_path):
                    emoji_filename = random.choice(os.listdir(emoji_path))
                    embed.set_thumbnail(url=f"attachment://{emoji_filename}")
            except Exception:
                pass

        if metadata.filter_preset:
            embed.add_field(
                name="Active Filter",
                value=f"🧪 {metadata.filter_preset.display_name}",
                inline=False,
            )

        return embed, emoji_filename

    def create_queue_embed(
        self,
        queue_items: list[AudioMetaData],
        current_track: AudioMetaData | None = None,
        page: int = 1,
        items_per_page: int = 5,
    ) -> discord.Embed:
        """Create an embed displaying the music queue"""
        embed = self._create_base_embed(title="🌌 Starlight Queue", color=BrandColor.ACCENT)

        if current_track:
            author_text = current_track.author if not current_track.author_url else f"[{current_track.author}]({current_track.author_url})"
            embed.add_field(
                name="Currently Pulsing",
                value=f"▶️ **[{current_track.title}]({current_track.webpage_url})**\n└ {author_text}",
                inline=False,
            )

        start_idx = (page - 1) * items_per_page
        end_idx = start_idx + items_per_page

        if not queue_items:
            embed.description = "*The queue is currently a silent void. Use /play to bring it to life.*"
        else:
            queue_display = []
            for i, item in enumerate(queue_items[start_idx:end_idx], start=start_idx + 1):
                author_text = item.author if not item.author_url else f"[{item.author}]({item.author_url})"
                queue_display.append(f"`{i}.` **[{item.title}]({item.webpage_url})**\n└ {author_text} • {self.format_duration(item.duration)}")

            embed.description = "\n\n".join(queue_display)

            total_pages = (len(queue_items) + items_per_page - 1) // items_per_page
            embed.set_footer(text=f"Page {page} of {total_pages} • {len(queue_items)} tracks in orbit")

        return embed

    def create_error_embed(self, error_message: str) -> discord.Embed:
        """Create an embed for displaying errors"""
        return self.create_action_embed(title="⚠️ System Error", message=error_message, is_success=False)

    def create_success_embed(self, message: str, title: str = "✅ Success") -> discord.Embed:
        """Create an embed for displaying success messages"""
        return self.create_action_embed(title=title, message=message, is_success=True)

    def create_morning_embed(self, message: str, title: str = "🌅 Celestial Sunrise") -> tuple[discord.Embed, str]:
        """Create an embed for morning messages"""
        embed = self._create_base_embed(title=title, description=message, color=BrandColor.GOLD)

        emoji_filename = None
        if self.BRAND_IMAGES.get("MORNING"):
            embed.set_thumbnail(url=self.BRAND_IMAGES["MORNING"])
        else:
            try:
                emoji_path = os.path.join(os.getcwd(), "emojis")
                if os.path.exists(emoji_path) and os.listdir(emoji_path):
                    emoji_filename = random.choice(os.listdir(emoji_path))
                    embed.set_thumbnail(url=f"attachment://{emoji_filename}")
            except Exception:
                pass

        return embed, emoji_filename

    @staticmethod
    def format_duration(seconds: int) -> str:
        """Convert seconds to a friendly readable format"""
        if not seconds or seconds <= 0:
            return "Live"

        days, remainder = divmod(seconds, 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes, remainder = divmod(remainder, 60)

        parts = []
        if days > 0:
            parts.append(f"{int(days)}d")
        if hours > 0:
            parts.append(f"{int(hours)}h")
        if minutes > 0:
            parts.append(f"{int(minutes)}m")
        if remainder > 0 or not parts:
            parts.append(f"{int(remainder)}s")

        return " ".join(parts)


class QueuePaginationView(discord.ui.View):
    def __init__(self, queue_items, current_track, embed_service):
        super().__init__(timeout=60)
        self.queue_items = queue_items
        self.current_track = current_track
        self.embed_service = embed_service
        self.current_page = 1
        self.items_per_page = 5
        self.total_pages = max(1, (len(queue_items) + self.items_per_page - 1) // self.items_per_page)

        self.update_button_states()

    def update_button_states(self):
        self.previous_button.disabled = self.current_page == 1
        self.next_button.disabled = self.current_page == self.total_pages

    @discord.ui.button(label="Previous", style=discord.ButtonStyle.secondary, emoji="⬅️")
    async def previous_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page = max(1, self.current_page - 1)
        self.update_button_states()

        embed = self.embed_service.create_queue_embed(
            queue_items=self.queue_items,
            current_track=self.current_track,
            page=self.current_page,
            items_per_page=self.items_per_page,
        )

        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Next", style=discord.ButtonStyle.secondary, emoji="➡️")
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page = min(self.total_pages, self.current_page + 1)
        self.update_button_states()

        embed = self.embed_service.create_queue_embed(
            queue_items=self.queue_items,
            current_track=self.current_track,
            page=self.current_page,
            items_per_page=self.items_per_page,
        )

        await interaction.response.edit_message(embed=embed, view=self)
