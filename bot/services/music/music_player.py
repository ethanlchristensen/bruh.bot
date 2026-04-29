import asyncio
import logging
import os
import time
from typing import TYPE_CHECKING, Optional

import discord
from discord import FFmpegPCMAudio, Interaction

from .priority_music_queue import PriorityMusicQueue
from .types import AudioMetaData, FilterPreset, MusicPlayerActionResponse

if TYPE_CHECKING:
    from bot.juno import Juno


class MusicPlayer:
    def __init__(self, bot: "Juno", guild: discord.Guild):
        self.bot = bot
        self.guild = guild
        self.queue = PriorityMusicQueue()
        self.voice_client: Optional[discord.VoiceClient] = None
        self.played_at: Optional[float] = None
        self.paused_at: Optional[float] = None
        self.current: Optional[AudioMetaData] = None
        self.last_text_channel: Optional[discord.TextChannel] = None
        self.logger = logging.getLogger(__name__)

    def is_playing(self) -> bool:
        """Check if the voice client is playing"""
        return self.voice_client is not None and self.voice_client.is_playing()

    def is_paused(self) -> bool:
        """Check if the voice client is paused"""
        return self.voice_client is not None and self.voice_client.is_paused()

    def is_blocked(self) -> bool:
        """Check is the player is blocked from playing a new song"""
        return self.is_playing() or self.is_paused() or not self.queue.empty()

    def is_in_vc(self) -> bool:
        """Check if the bot is in a vc"""
        return bool(self.voice_client)

    async def join(self, interaction: Interaction) -> MusicPlayerActionResponse:
        if self.is_in_vc():
            return MusicPlayerActionResponse(is_success=True, message="Already in a VC.")

        try:
            user_channel = interaction.user.voice.channel
            self.voice_client = await user_channel.connect(self_deaf=True)
            self.last_text_channel = interaction.channel
            return MusicPlayerActionResponse(is_success=True, message=f"Joined VC: {user_channel.name}")
        except Exception as e:
            self.logger.error("Failed to join voice channel: %s", e)
            return MusicPlayerActionResponse(is_success=False, message=f"Failed to join VC: {e}")

    async def leave(self) -> MusicPlayerActionResponse:
        if not self.is_in_vc():
            return MusicPlayerActionResponse(is_success=False, message="Not in a VC.")

        await self.voice_client.disconnect()
        self.queue = PriorityMusicQueue()
        self.voice_client = None
        self.current = None
        self.played_at = None
        self.paused_at = None
        self.last_text_channel = None
        await self._broadcast_state()
        return MusicPlayerActionResponse(is_success=True, message="Disconnected from VC.")

    async def _broadcast_state(self):
        """Broadcast the current state to all websocket clients for this guild."""
        if hasattr(self.bot, "music_websocket_service"):
            state = await self.bot.music_websocket_service.get_guild_state(self.guild.id)
            await self.bot.music_websocket_service.broadcast(self.guild.id, {"type": "state_update", "data": state})

    async def add(self, song: AudioMetaData) -> MusicPlayerActionResponse:
        """Add a song to queue"""
        if song.text_channel:
            self.last_text_channel = song.text_channel
        elif self.last_text_channel:
            song.text_channel = self.last_text_channel

        if self.is_blocked():
            self.logger.info("Adding song to queue: %s", song.title)
            if song.to_front:
                await self.queue.put_front(song)
            else:
                await self.queue.put(song)

            await self._broadcast_state()
            return MusicPlayerActionResponse(is_success=True, message=f"Added to queue: {song.title}")

        if not self.is_in_vc():
            self.logger.warning("Cannot play '%s': Bot not in VC.", song.title)
            return MusicPlayerActionResponse(is_success=False, message="Bot not in VC. Use /join first.")

        self.logger.info("Playing song: %s", song.title)
        self.current = song
        self.played_at = time.time()
        self._play(self.bot.audio_service.get_audio_source(url=song.url, filter_preset=song.filter_preset, position=song.position))

        if song.should_pause:
            self._pause()

        if not song.skip_now_playing_embed:
            await self._send_now_playing_embed(self.current)

        await self._broadcast_state()
        return MusicPlayerActionResponse(is_success=True, message=f"Playing: {song.title}")

    async def skip(self) -> MusicPlayerActionResponse:
        """Skip the currently playing song"""
        if self.is_playing() or self.is_paused():
            self.logger.info("Skipping: %s", self.current.title if self.current else "Unknown")
            self._stop()
            return MusicPlayerActionResponse(is_success=True, message="Skipped.")
        return MusicPlayerActionResponse(is_success=False, message="Nothing playing.")

    async def pause(self) -> MusicPlayerActionResponse:
        if self.is_paused():
            return MusicPlayerActionResponse(is_success=False, message="Already paused.")

        if self.is_playing():
            self._pause()
            self.paused_at = time.time()
            await self._broadcast_state()
            return MusicPlayerActionResponse(is_success=True, message="Paused.")

        return MusicPlayerActionResponse(is_success=False, message="Nothing playing.")

    async def resume(self) -> MusicPlayerActionResponse:
        if self.is_playing():
            return MusicPlayerActionResponse(is_success=False, message="Already playing.")

        if self.is_paused():
            self._resume()
            if self.paused_at and self.played_at:
                self.played_at += time.time() - self.paused_at
            self.paused_at = None

            await self._broadcast_state()
            return MusicPlayerActionResponse(is_success=True, message="Resumed.")

        return MusicPlayerActionResponse(is_success=False, message="Nothing to resume.")

    async def _requeue_with_modifications(self, **kwargs) -> None:
        """Helper to requeue the current song with modifications (for seek/filter)"""
        if not self.current:
            return

        modified_song = AudioMetaData.from_dict(self.current.to_dict())
        modified_song.text_channel = self.current.text_channel

        for key, value in kwargs.items():
            setattr(modified_song, key, value)

        modified_song.should_pause = self.is_paused()
        modified_song.to_front = True
        modified_song.skip_now_playing_embed = True

        await self.add(song=modified_song)
        self._stop()

    async def filter(self, filter_preset: FilterPreset) -> MusicPlayerActionResponse:
        if not (self.is_playing() or self.is_paused()):
            return MusicPlayerActionResponse(is_success=False, message="Nothing playing.")

        current_position = 0
        if self.played_at:
            ref_time = self.paused_at if self.is_paused() and self.paused_at else time.time()
            current_position = int(ref_time - self.played_at)

        # Calculate equivalent position for new speed multiplier
        old_speed = self.current.filter_preset.speed_multiplier if self.current.filter_preset else 1.0
        new_speed = filter_preset.speed_multiplier
        new_position = int((current_position * old_speed) / new_speed)

        self.logger.info("Applying filter '%s' at position %s", filter_preset.value, new_position)
        await self._requeue_with_modifications(filter_preset=filter_preset, position=new_position)

        return MusicPlayerActionResponse(is_success=True, message=f"Applied filter: {filter_preset.display_name}")

    async def seek(self, hours: int = 0, minutes: int = 0, seconds: int = 0) -> MusicPlayerActionResponse:
        if not (self.is_playing() or self.is_paused()):
            return MusicPlayerActionResponse(is_success=False, message="Nothing playing.")

        position = seconds + (minutes * 60) + (hours * 3600)
        effective_duration = self.current.effective_duration

        if effective_duration and position > effective_duration:
            return MusicPlayerActionResponse(is_success=False, message=f"Seek position {position}s exceeds duration.")

        self.logger.info("Seeking to %ss for: %s", position, self.current.title)
        await self._requeue_with_modifications(position=position)

        return MusicPlayerActionResponse(is_success=True, message=f"Seeked to {position}s")

    def _pause(self):
        self.voice_client.pause()

    def _resume(self):
        self.voice_client.resume()

    def _stop(self):
        self.voice_client.stop()

    def _play(self, audio_source: FFmpegPCMAudio):
        current_time = time.time()
        self.played_at = current_time - (self.current.position if self.current and self.current.position else 0)
        self.voice_client.play(audio_source, after=self._after_wrapper())

    def _after_wrapper(self):
        def after_callback(error):
            loop = self.bot.loop
            if loop.is_closed():
                self.logger.error("Event loop closed, cannot schedule next song.")
                return
            loop.call_soon_threadsafe(asyncio.create_task, self._on_track_end(error))

        return after_callback

    async def _on_track_end(self, error: Optional[Exception] = None) -> None:
        if error:
            self.logger.error("Track ended with error: %s - %s", self.current.title if self.current else "Unknown", error)
        else:
            self.logger.info("Track ended: %s", self.current.title if self.current else "Unknown")

        if not self.queue.empty():
            self.current = await self.queue.get()
            self.logger.info("Playing next from queue: %s", self.current.title)
            self._play(self.bot.audio_service.get_audio_source(self.current.url, self.current.filter_preset, self.current.position))

            if self.current.should_pause:
                self._pause()
            elif not self.current.skip_now_playing_embed:
                await self._send_now_playing_embed(self.current)
        else:
            self.current = None
            self.played_at = None

        await self._broadcast_state()

    async def _send_now_playing_embed(self, song: AudioMetaData):
        if not song.text_channel:
            return
        now_playing_embed, emoji_file = self.bot.embed_service.create_now_playing_embed(song)
        discord_file = None
        if emoji_file:
            discord_file = discord.File(os.path.join(os.getcwd(), "emojis", emoji_file), emoji_file)
        await song.text_channel.send(embed=now_playing_embed, file=discord_file)
