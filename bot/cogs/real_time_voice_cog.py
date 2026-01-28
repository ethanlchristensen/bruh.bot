import asyncio
import logging
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands, voice_recv

from bot.services import AudioProcessor, RealTimeAudioService, VoiceReceiveSink
from bot.utils.decarators.admin_check import is_admin
from bot.utils.decarators.command_logging import log_command_usage
from bot.utils.decarators.global_block_check import is_globally_blocked
from bot.utils.decarators.voice_check import require_voice_channel

if TYPE_CHECKING:
    from bot.juno import Juno


class QueuedAudioSource(discord.AudioSource):
    """Custom audio source that reads from a queue for real-time streaming."""

    def __init__(self, audio_queue: asyncio.Queue, audio_processor: AudioProcessor):
        self.audio_queue = audio_queue
        self.audio_processor = audio_processor
        self.buffer = bytearray()
        self.frame_size = 3840  # 20ms at 48kHz stereo (960 samples * 2 channels * 2 bytes)
        self.logger = logging.getLogger(__name__)
        self.is_done = False

    def read(self) -> bytes:
        """Read 20ms of audio (3840 bytes for 48kHz stereo)."""
        # Try to get data from queue (non-blocking)
        while len(self.buffer) < self.frame_size and not self.is_done:
            try:
                chunk = self.audio_queue.get_nowait()

                if chunk is None:
                    # End of response marker
                    self.is_done = True
                    break

                # Upsample from 24kHz mono to 48kHz stereo
                converted = self.audio_processor.upsample_audio(chunk, 24000, 48000)
                if converted:
                    self.buffer.extend(converted)

            except asyncio.QueueEmpty:
                break

        # Return a frame if we have enough data
        if len(self.buffer) >= self.frame_size:
            frame = bytes(self.buffer[: self.frame_size])
            self.buffer = self.buffer[self.frame_size :]
            return frame
        elif self.is_done and len(self.buffer) > 0:
            # Return remaining data padded to frame size
            frame = bytes(self.buffer) + b"\x00" * (self.frame_size - len(self.buffer))
            self.buffer.clear()
            return frame
        else:
            # Return silence if no data available
            return b"\x00" * self.frame_size

    def is_opus(self) -> bool:
        return False

    def cleanup(self):
        self.buffer.clear()


class BufferedAudioSource(discord.AudioSource):
    """Audio source that plays from a pre-buffered audio chunk."""

    def __init__(self, audio_data: bytes):
        self.audio_data = audio_data
        self.position = 0
        self.frame_size = 3840  # 20ms at 48kHz stereo

    def read(self) -> bytes:
        """Read 20ms of audio (3840 bytes for 48kHz stereo)."""
        if self.position >= len(self.audio_data):
            return b""

        # Read a frame
        frame = self.audio_data[self.position : self.position + self.frame_size]
        self.position += self.frame_size

        # Pad with silence if needed
        if len(frame) < self.frame_size:
            frame += b"\x00" * (self.frame_size - len(frame))

        return frame

    def is_opus(self) -> bool:
        return False

    def cleanup(self):
        pass


class StreamingAudioSource(discord.AudioSource):
    """Audio source that streams from a queue in real-time."""

    def __init__(self, audio_processor: AudioProcessor):
        self.audio_processor = audio_processor
        self.buffer = bytearray()
        self.frame_size = 3840  # 20ms at 48kHz stereo
        self.logger = logging.getLogger(__name__)
        self.pending_chunks = []
        self.is_active = True

    def add_chunk(self, chunk: bytes):
        """Add a chunk of 24kHz mono audio to be played."""
        if chunk:
            # Convert immediately and add to pending
            converted = self.audio_processor.upsample_audio(chunk, 24000, 48000)
            if converted:
                self.pending_chunks.append(converted)

    def read(self) -> bytes:
        """Read 20ms of audio (3840 bytes for 48kHz stereo)."""
        # Process any pending chunks
        while self.pending_chunks and len(self.buffer) < self.frame_size * 2:
            self.buffer.extend(self.pending_chunks.pop(0))

        # Return a frame if we have enough data
        if len(self.buffer) >= self.frame_size:
            frame = bytes(self.buffer[: self.frame_size])
            self.buffer = self.buffer[self.frame_size :]
            return frame
        else:
            # Return silence if no data available yet
            return b"\x00" * self.frame_size

    def is_opus(self) -> bool:
        return False

    def cleanup(self):
        self.buffer.clear()
        self.pending_chunks.clear()
        self.is_active = False


class RealTimeVoiceCog(commands.Cog):
    """Cog for real-time voice conversations with OpenAI."""

    def __init__(self, bot: "Juno"):
        self.bot = bot
        self.logger = logging.getLogger(__name__)

        # Track active sessions per guild
        self.active_sessions: dict[int, dict] = {}
        # guild_id -> {
        #     'service': RealTimeAudioService,
        #     'voice_client': VoiceRecvClient,
        #     'sink': VoiceReceiveSink,
        #     'audio_queue': asyncio.Queue,
        #     'playback_task': asyncio.Task,
        #     'listen_task': asyncio.Task
        # }

        self.audio_processor = AudioProcessor()

    def _get_session(self, guild_id: int) -> dict | None:
        """Get the active session for a guild."""
        return self.active_sessions.get(guild_id)

    def _has_active_session(self, guild_id: int) -> bool:
        """Check if a guild has an active session."""
        return guild_id in self.active_sessions

    async def _audio_playback_task(self, guild_id: int):
        """Monitor queue and start playing when audio arrives."""
        session = self._get_session(guild_id)
        if not session:
            return

        self.logger.info(f"Started audio playback task for guild {guild_id}")

        try:
            while session["service"].is_running:
                try:
                    voice_client = session["voice_client"]

                    # Wait for audio to arrive in queue
                    chunk = await asyncio.wait_for(session["audio_queue"].get(), timeout=0.5)

                    if chunk is None:
                        # End marker, continue waiting for next response
                        continue

                    # We have audio data - convert it first
                    self.logger.info(f"Received audio chunk of {len(chunk)} bytes")

                    # Upsample from 24kHz mono to 48kHz stereo
                    converted = self.audio_processor.upsample_audio(chunk, 24000, 48000)

                    if not converted:
                        self.logger.warning("Failed to convert audio")
                        continue

                    self.logger.info(f"Converted to {len(converted)} bytes for Discord")

                    # Create audio source with the buffered data
                    audio_source = BufferedAudioSource(converted)

                    # Stop current playback if any
                    if voice_client.is_playing():
                        voice_client.stop()
                        await asyncio.sleep(0.05)

                    # Start playing
                    if voice_client.is_connected():

                        def after_playback(error):
                            if error:
                                self.logger.error(f"Playback error: {error}")
                            else:
                                self.logger.info("Playback completed successfully")

                        voice_client.play(audio_source, after=after_playback)
                        self.logger.info("Started playback")

                        # Wait for playback to finish
                        while voice_client.is_playing():
                            await asyncio.sleep(0.1)

                except TimeoutError:
                    continue
                except Exception as e:
                    self.logger.error(f"Error in playback task for guild {guild_id}: {e}", exc_info=True)
                    await asyncio.sleep(0.1)
        finally:
            self.logger.info(f"Stopped audio playback task for guild {guild_id}")

    @app_commands.command(name="voice_join", description="Have Juno join your voice channel for conversation.")
    @log_command_usage()
    @require_voice_channel(ephemeral=True, allow_admin_bypass=True)
    @is_admin()
    @is_globally_blocked()
    async def voice_join(self, interaction: discord.Interaction):
        """Join the user's voice channel."""
        if self._has_active_session(interaction.guild.id):
            await interaction.followup.send("Already in a voice channel! Use `/voice_leave` first.", ephemeral=True)
            return

        if not interaction.user.voice:
            await interaction.followup.send("You need to be in a voice channel!", ephemeral=True)
            return

        try:
            channel = interaction.user.voice.channel

            # Connect using voice_recv.VoiceRecvClient
            voice_client = await channel.connect(cls=voice_recv.VoiceRecvClient)

            # Initialize session storage
            self.active_sessions[interaction.guild.id] = {"voice_client": voice_client, "service": None, "sink": None, "audio_queue": None, "playback_task": None, "listen_task": None}

            await interaction.followup.send(f"Joined {channel.name}! Use `/voice_start` to begin conversation.", ephemeral=True)

        except Exception as e:
            self.logger.error(f"Error joining voice channel: {e}")
            await interaction.followup.send(f"Failed to join voice channel: {e}", ephemeral=True)

    @app_commands.command(name="voice_start", description="Start a real-time conversation with Juno.")
    @app_commands.describe(listen_to="Optional: Specific user to listen to (leave empty to listen to everyone)")
    @log_command_usage()
    @is_admin()
    @require_voice_channel(ephemeral=True, allow_admin_bypass=True)
    @is_globally_blocked()
    async def voice_start(self, interaction: discord.Interaction, listen_to: discord.Member | None = None):
        """Start a real-time conversation."""
        session = self._get_session(interaction.guild.id)

        if not session:
            await interaction.followup.send("Not in a voice channel! Use `/voice_join` first.", ephemeral=True)
            return

        if session.get("service") and session["service"].is_running:
            await interaction.followup.send("Conversation already active! Use `/voice_stop` first.", ephemeral=True)
            return

        try:
            # Create RealTimeAudioService
            service = RealTimeAudioService(self.bot)

            # Connect to OpenAI
            await service.connect()

            # Configure session
            instructions = "You are Juno, a friendly Discord bot assistant. "
            instructions += "Keep responses brief and conversational. "
            instructions += "You're talking to people in a Discord voice channel."

            if listen_to:
                instructions += f" You're currently listening to {listen_to.display_name}."

            await service.configure_session(instructions=instructions)

            # Create audio queue
            audio_queue = asyncio.Queue()

            # Update session
            session["service"] = service
            session["audio_queue"] = audio_queue
            service.is_running = True

            # Start background tasks
            listen_task = asyncio.create_task(service.listen_for_response(audio_queue))
            playback_task = asyncio.create_task(self._audio_playback_task(interaction.guild.id))

            session["listen_task"] = listen_task
            session["playback_task"] = playback_task

            # Create and start the voice receive sink
            target_user_id = listen_to.id if listen_to else None
            sink = VoiceReceiveSink(service, target_user_id)
            session["voice_client"].listen(sink)
            session["sink"] = sink

            listen_msg = f"listening to {listen_to.mention}" if listen_to else "listening to everyone"
            await interaction.followup.send(f"**Conversation started!** Now {listen_msg}. Start speaking!", ephemeral=True)

        except Exception as e:
            self.logger.error(f"Error starting conversation: {e}")
            await interaction.followup.send(f"Error starting conversation: {e}", ephemeral=True)

            # Cleanup on error
            if session.get("service"):
                await session["service"].disconnect()
            self.active_sessions[interaction.guild.id] = {"voice_client": session["voice_client"], "service": None, "sink": None, "audio_queue": None, "playback_task": None, "listen_task": None}

    @app_commands.command(name="voice_stop", description="Stop the current conversation.")
    @log_command_usage()
    @is_admin()
    @require_voice_channel(ephemeral=True, allow_admin_bypass=True)
    @is_globally_blocked()
    async def voice_stop(self, interaction: discord.Interaction):
        """Stop the conversation."""
        session = self._get_session(interaction.guild.id)

        if not session or not session.get("service"):
            await interaction.followup.send("No active conversation!", ephemeral=True)
            return

        try:
            # Stop listening
            if session["voice_client"]:
                session["voice_client"].stop_listening()

            # Cancel tasks
            if session.get("playback_task") and not session["playback_task"].done():
                session["playback_task"].cancel()
                try:
                    await session["playback_task"]
                except asyncio.CancelledError:
                    pass

            if session.get("listen_task") and not session["listen_task"].done():
                session["listen_task"].cancel()
                try:
                    await session["listen_task"]
                except asyncio.CancelledError:
                    pass

            # Disconnect from OpenAI
            if session["service"]:
                await session["service"].disconnect()

            # Clear session data but keep voice_client
            session["service"] = None
            session["sink"] = None
            session["audio_queue"] = None
            session["playback_task"] = None
            session["listen_task"] = None

            await interaction.followup.send("Conversation stopped.", ephemeral=True)

        except Exception as e:
            self.logger.error(f"Error stopping conversation: {e}")
            await interaction.followup.send(f"Error stopping conversation: {e}", ephemeral=True)

    @app_commands.command(name="voice_leave", description="Have Juno leave the voice channel.")
    @log_command_usage()
    @is_admin()
    @require_voice_channel(ephemeral=True, allow_admin_bypass=True)
    @is_globally_blocked()
    async def voice_leave(self, interaction: discord.Interaction):
        """Leave the voice channel."""
        session = self._get_session(interaction.guild.id)

        if not session:
            await interaction.followup.send("Not in a voice channel!", ephemeral=True)
            return

        try:
            if session.get("service") and session["service"].is_running:
                await self.voice_stop(interaction)

            if session["voice_client"]:
                await session["voice_client"].disconnect()

            del self.active_sessions[interaction.guild.id]

            await interaction.followup.send("Left the voice channel.", ephemeral=True)

        except Exception as e:
            self.logger.error(f"Error leaving voice channel: {e}")
            await interaction.followup.send(f"Error leaving voice channel: {e}", ephemeral=True)

    async def cog_unload(self):
        """Cleanup when cog is unloaded."""
        self.logger.info("Cleaning up RealTimeVoiceCog...")

        # Stop all active sessions
        for guild_id in list(self.active_sessions.keys()):
            session = self.active_sessions[guild_id]

            try:
                # Stop voice client
                if session.get("voice_client"):
                    session["voice_client"].stop_listening()
                    await session["voice_client"].disconnect()

                # Cancel tasks
                if session.get("playback_task"):
                    session["playback_task"].cancel()
                if session.get("listen_task"):
                    session["listen_task"].cancel()

                # Disconnect service
                if session.get("service"):
                    await session["service"].disconnect()

            except Exception as e:
                self.logger.error(f"Error cleaning up session for guild {guild_id}: {e}")

        self.active_sessions.clear()


async def setup(bot: "Juno"):
    await bot.add_cog(RealTimeVoiceCog(bot))
