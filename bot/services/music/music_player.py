import asyncio
import logging
import os
import time
from typing import TYPE_CHECKING

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
        self.voice_client: discord.VoiceClient = None
        self.played_at = None
        self.paused_at = None
        self.current: AudioMetaData = None
        self.last_text_channel: discord.TextChannel = None
        self.logger = logging.getLogger(__name__)

    def is_playing(self):
        """Check if the voice client is playing"""
        return self.voice_client is not None and self.voice_client.is_playing()

    def is_paused(self):
        """Check if the voice client is paused"""
        return self.voice_client is not None and self.voice_client.is_paused()

    def is_blocked(self):
        """Check is the player is blocked from playing a new song"""
        return self.is_playing() or self.is_paused() or not self.queue.empty()

    def is_in_vc(self):
        """Check if the bot is in a vc"""
        return bool(self.voice_client)

    async def join(self, interaction: Interaction) -> MusicPlayerActionResponse:
        if self.is_in_vc():
            return MusicPlayerActionResponse(is_success=True, message="Already in a VC, no need to join.")

        try:
            user_channel = interaction.user.voice.channel
            self.voice_client = await user_channel.connect(self_deaf=True)
            self.last_text_channel = interaction.channel
            return MusicPlayerActionResponse(is_success=True, message=f"Successfully joined the VC '{user_channel.name}'.")
        except Exception as e:
            self.logger.error(f"[JOIN] - Failed to join voice channel: {e}")
            return MusicPlayerActionResponse(is_success=False, message=f"Failed to join the VC due to: {e}")

    async def leave(self) -> MusicPlayerActionResponse:
        if not self.is_in_vc():
            return MusicPlayerActionResponse(is_success=False, message="Not currently in a VC.")

        await self.voice_client.disconnect()
        self.queue = PriorityMusicQueue()
        self.voice_client = None
        self.current = None
        self.played_at = None
        self.paused_at = None
        self.last_text_channel = None
        await self._broadcast_state()
        return MusicPlayerActionResponse(is_success=True, message="Successfully disconnected from the VC.")

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
            self.logger.info(f"[ADD] - Bot is currently playing audio or the queue has items, adding song '{song.title}' to the queue")
            if song.to_front:
                await self.queue.put_front(song)
            else:
                await self.queue.put(song)

            await self._broadcast_state()
            return MusicPlayerActionResponse(is_success=True, message=f"Successfully added the song '{song.title}' to the queue.")
        else:
            if not self.is_in_vc():
                self.logger.warning(f"[ADD] - Cannot play '{song.title}' because bot is not in a voice channel.")
                return MusicPlayerActionResponse(is_success=False, message="Bot is not in a voice channel. Use /join in Discord first.")

            self.logger.info(f"[ADD] - Bot is not playing audio and the queue is empty, playing song '{song.title}'")
            self.current = song
            self.played_at = time.time()
            self._play(self.bot.audio_service.get_audio_source(url=song.url, filter_preset=song.filter_preset, position=song.position))
            if song.should_pause:
                self._pause()

            if not song.skip_now_playing_embed:
                await self._send_now_playing_embed(self.current)

            await self._broadcast_state()
            return MusicPlayerActionResponse(is_success=True, message=f"Successfully started playing the song '{song.title}'.")

    async def skip(self) -> MusicPlayerActionResponse:
        """Skip the currently playing song"""
        if self.is_playing() or self.is_paused():
            self.logger.info(f"[SKIP] - Skipping current audio '{self.current.title}'")
            self._stop()
            # Broadcast will happen in _on_track_end
            return MusicPlayerActionResponse(is_success=True, message="Successfully skipped the audio.")
        return MusicPlayerActionResponse(is_success=False, message="No audio is currently playing.")

    async def pause(self) -> MusicPlayerActionResponse:
        if self.is_paused():
            return MusicPlayerActionResponse(is_success=False, message="Player is not currently paused, nothing to resume.")

        if self.is_playing():
            self._pause()
            self.paused_at = time.time()
            await self._broadcast_state()
            return MusicPlayerActionResponse(is_success=True, message="Successfully paused the audio.")

        return MusicPlayerActionResponse(is_success=False, message="Failed to pause audio for unknown reason.")

    async def resume(self) -> MusicPlayerActionResponse:
        if self.is_playing():
            return MusicPlayerActionResponse(is_success=False, message="No audio is currently paused.")

        if self.is_paused():
            self._resume()
            # If we resumed, we need to adjust played_at if we are tracking position
            if self.paused_at and self.played_at:
                pause_duration = time.time() - self.paused_at
                self.played_at += pause_duration
            self.paused_at = None

            await self._broadcast_state()
            return MusicPlayerActionResponse(is_success=True, message="Successfully resumed the audio.")

        return MusicPlayerActionResponse(is_success=False, message="Failed to resume audio for unknown reason.")

    async def filter(self, filter_preset: FilterPreset) -> MusicPlayerActionResponse:
        if not (self.is_playing() or self.is_paused()):
            return MusicPlayerActionResponse(is_success=False, message="No audio is currently playing / paused, cannot apply a filter.")

        current_position = 0
        if self.played_at:
            if self.is_paused() and self.paused_at:
                current_position = int(self.paused_at - self.played_at)
            else:
                current_position = int(time.time() - self.played_at)

        filtered_song = AudioMetaData.from_dict(self.current.to_dict())
        filtered_song.text_channel = self.current.text_channel
        filtered_song.filter_preset = filter_preset
        filtered_song.position = current_position
        filtered_song.should_pause = self.is_paused()
        filtered_song.to_front = True
        filtered_song.skip_now_playing_embed = True

        await self.add(song=filtered_song)

        self._stop()

        self.logger.info(f"[FILTER] - Applied filter '{filtered_song.filter_preset.value}' at position {current_position}")

        return MusicPlayerActionResponse(is_success=False, message="Successfully applied the new filter to the audio.")

    async def seek(self, hours: int = 0, minutes: int = 0, seconds: int = 0) -> MusicPlayerActionResponse:
        if not (self.is_playing() or self.is_paused()):
            return MusicPlayerActionResponse(is_success=False, message="Bot is not in a VC or is not playing any audio.")

        position = 0
        if seconds >= 0:
            position += seconds
        if minutes >= 0:
            position += minutes * 60
        if hours >= 0:
            position += hours * 60 * 60

        # Calculate effective duration for the duration check
        effective_duration = int(self.current.duration / self.current.filter_preset.speed_multiplier) if self.current.filter_preset else self.current.duration

        if effective_duration and position > effective_duration:
            minutes, seconds = divmod(effective_duration, 60)
            hours, minutes = divmod(minutes, 60)
            hours, minutes, seconds = int(hours), int(minutes), int(seconds)
            time_format = f"{hours}h {minutes}m {seconds}s" if hours else f"{minutes}m {seconds}s" if minutes else f"{seconds}s"
            return MusicPlayerActionResponse(is_success=False, message=f"Cannot seek to {position} seconds. Song is only {time_format} long.")

        seeked_song = AudioMetaData.from_dict(self.current.to_dict())
        seeked_song.text_channel = self.current.text_channel
        seeked_song.filter_preset = self.current.filter_preset

        seeked_song.position = position
        seeked_song.should_pause = self.is_paused()
        seeked_song.to_front = True
        seeked_song.skip_now_playing_embed = True

        await self.add(song=seeked_song)

        self._stop()

        self.logger.info(f"[SEEK] - Seeked to {position} for song {seeked_song.title}")

        return MusicPlayerActionResponse(is_success=True, message=f"Seeked to {position} seconds!")

    def _pause(self):
        self.voice_client.pause()

    def _resume(self):
        self.voice_client.resume()

    def _stop(self):
        self.voice_client.stop()

    def _play(self, audio_source: FFmpegPCMAudio):
        current_time = time.time()

        if self.current and self.current.position:
            self.played_at = int(current_time - self.current.position)
        else:
            self.played_at = current_time

        self.voice_client.play(audio_source, after=self._after_wrapper())

    def _after_wrapper(self):
        def after_callback(error):
            loop = self.bot.loop
            if loop.is_closed():
                self.logger.error("[AFTERWRAPPER] - bots event loop is closed, cannot schedule the song to play")
                return
            loop.call_soon_threadsafe(asyncio.create_task, self._on_track_end(error))

        return after_callback

    async def _on_track_end(self, error: str | None = None) -> None:
        """Ran after each audio source completes playing to the discord voice client"""
        if error:
            self.logger.error(f"[ONTRACKEND] - Song Completed Playback due to ERROR: {self.current.title if self.current else 'UNKNOWN'} - error")
        else:
            self.logger.info(f"[ONTRACKEND] - Song Completed Playback: {self.current.title if self.current else 'UNKNOWN'}")

        if not self.queue.empty():
            self.logger.info("[ONTRACKEND] - Queue is not empty, moving on to next song")
            self.current = await self.queue.get()
            self._play(self.bot.audio_service.get_audio_source(self.current.url, self.current.filter_preset, self.current.position))
            if self.current.should_pause:
                self._pause()
            else:
                await self._send_now_playing_embed(self.current)
        else:
            self.current = None
            self.played_at = None

        await self._broadcast_state()

    async def _send_now_playing_embed(self, song: AudioMetaData):
        if not song.text_channel:
            self.logger.warning(f"No text channel associated with song '{song.title}', skipping embed.")
            return
        now_playing_embed, emoji_file = self.bot.embed_service.create_now_playing_embed(song)
        discord_file = None if not emoji_file else discord.File(os.path.join(os.getcwd(), "emojis", emoji_file), emoji_file)
        await song.text_channel.send(embed=now_playing_embed, file=discord_file)
