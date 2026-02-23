import asyncio
import base64
import json
import logging
from typing import TYPE_CHECKING

import discord
import numpy as np
import websockets
from discord.ext import voice_recv

from ..config_service import DynamicConfig

if TYPE_CHECKING:
    from bot.juno import Juno


class RealTimeAudioService:
    def __init__(self, bot: "Juno", config: DynamicConfig):
        self.bot = bot
        self.config = config
        self.model = config.aiConfig.realTimeConfig.realTimeModel
        self.voice = config.aiConfig.realTimeConfig.voice
        self.apiKey = config.aiConfig.realTimeConfig.apiKey
        self.ws: websockets.ClientConnection | None = None
        self.is_running = False
        self.ws_url = f"wss://api.openai.com/v1/realtime?model={self.model}"
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"Initialized RealTimeAudioService with model {self.model} for guild {config.guildId}")

    async def connect(self):
        """Establish WebSocket connection to OpenAI Realtime API."""
        if not self.apiKey:
            self.logger.error(f"No API key configured for RealTimeAudioService in guild {self.config.guildId}")
            return False

        headers = {"Authorization": f"Bearer {self.apiKey}"}

        self.ws = await websockets.connect(self.ws_url, additional_headers=headers)

        response = await self.ws.recv()

        event = json.loads(response)
        if event["type"] == "session.created":
            self.logger.info("OpenAI WS session created")
            return True
        return False

    async def configure_session(
        self,
        instructions: str = "Speak clearly and briefly. Confirm understanding before taking actions.",
    ):
        """Configure the session parameters."""
        # Get prompts for this specific guild
        prompts = self.bot.get_prompts(self.config.promptsPath)
        if erm := prompts.get("realtime"):
            instructions = erm

        self.logger.info(f"Using model: {self.model} and voice: {self.voice}")
        self.logger.info(f"Configuring with instructions of: {instructions}")
        event = {
            "type": "session.update",
            "session": {
                "type": "realtime",
                "model": self.model,
                "output_modalities": ["audio"],
                "audio": {
                    "input": {
                        "format": {
                            "type": "audio/pcm",
                            "rate": 24000,
                        },
                        "turn_detection": {"type": "server_vad"},
                    },
                    "output": {
                        "format": {"type": "audio/pcm", "rate": 24000},
                        "voice": self.voice,
                    },
                },
                "instructions": instructions,
            },
        }
        await self.ws.send(json.dumps(event))

        response = await self.ws.recv()
        event = json.loads(response)

        if event.get("type") == "session.updated":
            self.logger.info("✅ Session configured successfully")
            return True
        else:
            self.logger.warning(f"Unexpected response: {event}")
            return False

    async def send_audio_chunk(self, audio_data: bytes):
        """Send audio chunk to OpenAI."""
        if not audio_data or not self.ws:
            return

        base64_audio = base64.b64encode(audio_data).decode("ascii")
        event = {"type": "input_audio_buffer.append", "audio": base64_audio}

        await self.ws.send(json.dumps(event))

    async def listen_for_response(self, audio_queue: asyncio.Queue):
        """Listen for server responses and queue audio for playback."""
        audio_buffer = []

        while self.is_running:
            try:
                response = await asyncio.wait_for(self.ws.recv(), timeout=0.1)
                event = json.loads(response)
                event_type = event.get("type")

                if event_type == "response.output_audio.delta":
                    audio_b64 = event.get("delta", "")
                    if audio_b64:
                        audio_bytes = base64.b64decode(audio_b64)
                        # Accumulate chunks instead of sending immediately
                        audio_buffer.append(audio_bytes)

                elif event_type == "response.output_audio.done":
                    self.logger.info("🎵 Audio response complete - processing buffer")

                    # Combine all buffered audio
                    if audio_buffer:
                        combined = b"".join(audio_buffer)
                        # Put the complete audio in the queue for processing
                        await audio_queue.put(combined)
                        audio_buffer.clear()

                    # Signal end of this response
                    await audio_queue.put(None)

                elif event_type == "response.output_audio_transcript.delta":
                    transcript = event.get("delta", "")
                    self.logger.info(f"{transcript}")

                elif event_type == "response.output_audio_transcript.done":
                    self.logger.info("Transcript complete")

                elif event_type == "input_audio_buffer.speech_started":
                    self.logger.info("User started speaking")

                elif event_type == "input_audio_buffer.speech_stopped":
                    self.logger.info("User stopped speaking")

                elif event_type == "error":
                    self.logger.error(f"Error: {event.get('error', {})}")

                elif event_type == "session.updated":
                    self.logger.info("Session updated")

            except TimeoutError:
                continue
            except Exception as e:
                self.logger.error(f"Exception encountered while listening for websocket response: {e}")
                break

    async def send_text_message(self, text: str):
        """Send a text message to the conversation and trigger a response."""
        if not self.ws:
            return

        # Add the message to the conversation
        item_event = {
            "type": "conversation.item.create",
            "item": {
                "type": "message",
                "role": "user",
                "content": [{"type": "input_text", "text": text}],
            },
        }
        await self.ws.send(json.dumps(item_event))
        self.logger.info(f"Sent text message: {text}")

        # Trigger a response
        response_event = {"type": "response.create"}
        await self.ws.send(json.dumps(response_event))
        self.logger.info("Triggered response from assistant")

    async def disconnect(self):
        """Close the WebSocket connection."""
        self.is_running = False
        if self.ws:
            await self.ws.close()


class AudioProcessor:
    """Handles audio format conversions between Discord and OpenAI."""

    DISCORD_FRAME_SIZE = 960
    DISCORD_FRAME_DURATION = 0.02

    @staticmethod
    def resample_audio(
        audio_data: bytes,
        from_rate: int,
        to_rate: int,
        from_channels: int = 2,
        to_channels: int = 1,
    ) -> bytes:
        """
        Resample audio from Discord format to OpenAI format.
        Discord: 48kHz stereo -> OpenAI: 24kHz mono
        """
        if not audio_data:
            return b""

        audio_np = np.frombuffer(audio_data, dtype=np.int16)

        # Convert stereo to mono
        if from_channels == 2 and to_channels == 1 and len(audio_np) > 0:
            audio_np = audio_np.reshape(-1, 2).mean(axis=1).astype(np.int16)

        # Resample
        if len(audio_np) > 0:
            ratio = to_rate / from_rate
            new_length = int(len(audio_np) * ratio)
            if new_length > 0:
                indices = np.linspace(0, len(audio_np) - 1, new_length)
                resampled = np.interp(indices, np.arange(len(audio_np)), audio_np)
                return resampled.astype(np.int16).tobytes()

        return b""

    @staticmethod
    def upsample_audio(audio_data: bytes, from_rate: int = 24000, to_rate: int = 48000) -> bytes:
        """
        Upsample audio from OpenAI format to Discord format.
        OpenAI: 24kHz mono -> Discord: 48kHz stereo
        """
        if not audio_data:
            return b""

        audio_np = np.frombuffer(audio_data, dtype=np.int16)

        if len(audio_np) == 0:
            return b""

        # Upsample
        ratio = int(to_rate / from_rate)
        upsampled = np.repeat(audio_np, ratio)

        # Convert mono to stereo
        stereo = np.column_stack((upsampled, upsampled)).flatten()

        return stereo.astype(np.int16).tobytes()

    @staticmethod
    def buffer_audio_chunks(audio_buffer: list[bytes], target_size: int = 3840) -> list[bytes]:
        """
        Buffer small audio chunks into consistent sizes for smooth playback.
        target_size = 3840 bytes = 960 samples * 2 channels * 2 bytes per sample (20ms at 48kHz stereo)
        """
        buffered_chunks = []
        accumulated = b""

        for chunk in audio_buffer:
            accumulated += chunk

            # When we have enough data, extract consistent chunks
            while len(accumulated) >= target_size:
                buffered_chunks.append(accumulated[:target_size])
                accumulated = accumulated[target_size:]

        # Return any remaining data as well if it's substantial
        if len(accumulated) > target_size // 2:
            buffered_chunks.append(accumulated)

        return buffered_chunks, accumulated


class VoiceReceiveSink(voice_recv.AudioSink):
    """Custom audio sink for receiving voice from Discord and sending to OpenAI."""

    def __init__(
        self,
        real_time_audio_service: RealTimeAudioService,
        target_user_id: int | None = None,
    ):
        super().__init__()
        self.real_time_audio_service = real_time_audio_service
        self.target_user_id = target_user_id
        self.audio_processor = AudioProcessor()
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"VoiceReceiveSink initialized. Target user ID: {target_user_id}")
        self.loop = asyncio.get_event_loop()

    @voice_recv.AudioSink.listener()
    def on_voice_member_speaking_state(self, member: discord.Member, speaking: bool):
        """Called when a member starts or stops speaking."""
        if self.target_user_id and member.id != self.target_user_id:
            return

        if speaking:
            self.logger.info(f"🎤 {member.display_name} started speaking")
        else:
            self.logger.info(f"🔇 {member.display_name} stopped speaking")

    def write(self, user: discord.User, data: voice_recv.VoiceData):
        """
        Called when audio data is received from a user.
        Discord provides: 48kHz, 16-bit, stereo PCM
        """
        if self.target_user_id and user.id != self.target_user_id:
            return

        pcm_data = data.pcm

        if pcm_data:
            # Convert Discord audio (48kHz stereo) to OpenAI format (24kHz mono)
            converted = self.audio_processor.resample_audio(pcm_data, from_rate=48000, to_rate=24000, from_channels=2, to_channels=1)

            if converted:
                asyncio.run_coroutine_threadsafe(self.real_time_audio_service.send_audio_chunk(converted), self.loop)

    def cleanup(self):
        self.logger.info("Speech recognition sink cleaned up")

    def wants_opus(self):
        return False
