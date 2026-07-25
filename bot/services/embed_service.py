import logging
import os
from datetime import datetime
from enum import Enum

import discord

from .music.types import AudioMetaData, AudioSource

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "static")


class BrandColor(Enum):
    PRIMARY = 0x5865F2
    ACCENT = 0x00B0F4
    SUCCESS = 0x57F287
    ERROR = 0xED4245
    WARNING = 0xFEE75C


def _asset_url(filename: str) -> str | None:
    path = os.path.join(STATIC_DIR, filename)
    return f"attachment://{filename}" if os.path.exists(path) else None


class EmbedService:
    logger = logging.getLogger(__name__)
    source_labels = {AudioSource.SOUNDCLOUD: "Artist", AudioSource.YOUTUBE: "Channel"}

    def _create_base_embed(
        self,
        title: str | None = None,
        description: str | None = None,
        color: BrandColor = BrandColor.PRIMARY,
    ) -> discord.Embed:
        embed = discord.Embed(
            title=title,
            description=description,
            color=color.value,
            timestamp=datetime.now(),
        )
        embed.set_footer(text="bruh.bot")
        avatar_url = _asset_url("avatar.png")
        if avatar_url:
            embed.set_author(name="bruh.bot", icon_url=avatar_url)
        return embed

    @staticmethod
    def get_brand_files(embed: discord.Embed | None = None) -> list[discord.File]:
        if not os.path.isdir(STATIC_DIR):
            return []

        if embed is not None:
            needed = set()
            raw = embed.to_dict()
            for url in [
                raw.get("author", {}).get("icon_url", ""),
                raw.get("thumbnail", {}).get("url", ""),
                raw.get("image", {}).get("url", ""),
                raw.get("footer", {}).get("icon_url", ""),
            ]:
                if url.startswith("attachment://"):
                    needed.add(url.replace("attachment://", ""))
            if not needed:
                return []
            return [discord.File(os.path.join(STATIC_DIR, f), filename=f) for f in os.listdir(STATIC_DIR) if f in needed and os.path.isfile(os.path.join(STATIC_DIR, f))]

        return [discord.File(os.path.join(STATIC_DIR, f), filename=f) for f in os.listdir(STATIC_DIR) if os.path.isfile(os.path.join(STATIC_DIR, f)) and f.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".webp"))]

    def create_action_embed(
        self,
        title: str,
        message: str,
        is_success: bool = True,
        thumbnail_url: str | None = None,
    ) -> discord.Embed:
        color = BrandColor.SUCCESS if is_success else BrandColor.ERROR
        embed = self._create_base_embed(title=title, description=message, color=color)

        if thumbnail_url:
            embed.set_thumbnail(url=thumbnail_url)
        elif is_success:
            icon = _asset_url("success.png")
            if icon:
                embed.set_thumbnail(url=icon)
        else:
            icon = _asset_url("error.png")
            if icon:
                embed.set_thumbnail(url=icon)

        return embed

    def create_added_to_queue_embed(self, metadata: AudioMetaData, position: int) -> discord.Embed:
        embed = self._create_base_embed(
            title="Added to Queue",
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
            embed.set_footer(text=f"Requested by {metadata.requested_by}")

        if metadata.thumbnail_url:
            embed.set_thumbnail(url=metadata.thumbnail_url)

        if metadata.filter_preset:
            embed.add_field(
                name="Active Filter",
                value=metadata.filter_preset.display_name,
                inline=False,
            )

        return embed

    def create_now_playing_embed(self, metadata: AudioMetaData) -> discord.Embed:
        embed = self._create_base_embed(
            title="Now Playing",
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
            embed.add_field(name="Likes", value=f"{metadata.likes:,}", inline=True)

        if metadata.thumbnail_url:
            embed.set_thumbnail(url=metadata.thumbnail_url)

        if metadata.filter_preset:
            embed.add_field(
                name="Active Filter",
                value=metadata.filter_preset.display_name,
                inline=False,
            )

        banner = _asset_url("nowplaying.png")
        if banner:
            embed.set_image(url=banner)

        return embed

    def create_queue_embed(
        self,
        queue_items: list[AudioMetaData],
        current_track: AudioMetaData | None = None,
        page: int = 1,
        items_per_page: int = 5,
    ) -> discord.Embed:
        embed = self._create_base_embed(title="Music Queue", color=BrandColor.ACCENT)
        icon = _asset_url("info.png")
        if icon:
            embed.set_thumbnail(url=icon)

        if current_track:
            author_text = current_track.author if not current_track.author_url else f"[{current_track.author}]({current_track.author_url})"
            embed.add_field(
                name="Now Playing",
                value=f"▶️ **[{current_track.title}]({current_track.webpage_url})**\n└ {author_text}",
                inline=False,
            )

        start_idx = (page - 1) * items_per_page
        end_idx = start_idx + items_per_page

        if not queue_items:
            embed.description = "The queue is empty. Use /play to add tracks."
        else:
            queue_display = []
            for i, item in enumerate(queue_items[start_idx:end_idx], start=start_idx + 1):
                author_text = item.author if not item.author_url else f"[{item.author}]({item.author_url})"
                queue_display.append(f"`{i}.` **[{item.title}]({item.webpage_url})**\n└ {author_text} - {self.format_duration(item.duration)}")

            embed.description = "\n\n".join(queue_display)

            total_pages = (len(queue_items) + items_per_page - 1) // items_per_page
            embed.set_footer(text=f"Page {page} of {total_pages} - {len(queue_items)} tracks")

        return embed

    def create_error_embed(self, error_message: str) -> discord.Embed:
        return self.create_action_embed(title="Error", message=error_message, is_success=False)

    def create_success_embed(self, message: str, title: str = "Done") -> discord.Embed:
        return self.create_action_embed(title=title, message=message, is_success=True)

    def create_info_embed(self, title: str, description: str, fields: list[tuple[str, str, bool]] | None = None) -> discord.Embed:
        embed = self._create_base_embed(title=title, description=description, color=BrandColor.ACCENT)
        icon = _asset_url("info.png")
        if icon:
            embed.set_thumbnail(url=icon)
        if fields:
            for name, value, inline in fields:
                embed.add_field(name=name, value=value, inline=inline)
        return embed

    def create_warning_embed(self, title: str, description: str) -> discord.Embed:
        return self._create_base_embed(title=title, description=description, color=BrandColor.WARNING)

    def create_morning_embed(self, message: str, title: str = "Good Morning!") -> discord.Embed:
        embed = self._create_base_embed(title=title, description=message, color=BrandColor.WARNING)
        banner = _asset_url("morning.png")
        if banner:
            embed.set_image(url=banner)
        return embed

    @staticmethod
    def format_duration(seconds: int) -> str:
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
        super().__init__(timeout=180)
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

    @discord.ui.button(label="Previous", style=discord.ButtonStyle.primary, emoji="⬅️")
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

    @discord.ui.button(label="Next", style=discord.ButtonStyle.primary, emoji="➡️")
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


class NowPlayingView(discord.ui.View):
    def __init__(self, player):
        super().__init__(timeout=180)
        self.player = player

    @discord.ui.button(label="Pause", style=discord.ButtonStyle.secondary, emoji="⏸")
    async def pause_resume(self, interaction: discord.Interaction, button: discord.ui.Button):
        action = await self.player.pause()
        if action.is_success:
            button.label = "Resume"
            button.emoji = "▶️"
        else:
            button.label = "Pause"
            button.emoji = "⏸"
        await interaction.response.edit_message(view=self)

    @discord.ui.button(label="Skip", style=discord.ButtonStyle.primary, emoji="⏭")
    async def skip(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.player.skip()
        await interaction.response.defer()

    @discord.ui.button(label="Stop", style=discord.ButtonStyle.danger, emoji="⏹")
    async def stop(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.player.queue._queue.clear()
        await self.player.skip()
        self.stop()
        await interaction.response.defer()


class ConfirmView(discord.ui.View):
    def __init__(self, confirm_message: str = "Are you sure?"):
        super().__init__(timeout=60)
        self.confirmed = False
        self.confirm_message = confirm_message

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.danger, emoji="✔️")
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.confirmed = True
        self.stop()
        await interaction.response.defer()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, emoji="✖️")
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.confirmed = False
        self.stop()
        await interaction.response.defer()
