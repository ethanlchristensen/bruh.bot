import asyncio
import logging
import os
from typing import Any
from urllib.parse import urlparse

import discord
import yt_dlp

from .types import AudioMetaData, AudioSource, FilterPreset


class AudioService:
    YDL_OPTS = {
        "format": "bestaudio[acodec=mp3][protocol!=m3u8]/bestaudio[acodec^=mp4a][protocol!=m3u8]/bestaudio[protocol!=m3u8]/bestaudio/best",
        "quiet": True,
        "noplaylist": True,
        "extract_flat": False,
        "extractor_args": {
            "youtube": {
                "player_client": ["android", "ios"],
                "skip": ["web_safari", "web"],
            }
        },
    }

    FFMPEG_BEFORE_OPTIONS = (
        "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 "
        '-user_agent "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"'
    )

    MEDIA_EXTENSIONS = {
        ".mov",
        ".mp4",
        ".mp3",
        ".wav",
        ".ogg",
        ".m4a",
        ".webm",
        ".opus",
    }

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def is_direct_media_url(self, url: str) -> bool:
        """Check if the URL is a direct link to a media file."""
        parsed_url = urlparse(url)
        path = parsed_url.path.lower()
        return any(path.endswith(ext) for ext in self.MEDIA_EXTENSIONS)

    async def _get_duration_with_ffprobe(self, url: str) -> int:
        """Use ffprobe to get the duration of a media file from a URL."""
        cmd = [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            url,
        ]

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await process.communicate()

            if process.returncode == 0 and stdout:
                return int(float(stdout.decode().strip()))
        except Exception as e:
            self.logger.error("Failed to get duration with ffprobe for %s: %s", url, e)

        return 0

    async def extract_info(self, query: str) -> dict[str, Any]:
        if query.startswith("http") and self.is_direct_media_url(query):
            parsed_url = urlparse(query)
            filename = os.path.basename(parsed_url.path)
            duration = await self._get_duration_with_ffprobe(query)
            return {
                "title": filename,
                "uploader": "Direct URL",
                "duration": duration,
                "webpage_url": query,
                "url": query,
                "thumbnail": None,
                "_direct_url": True,
            }

        # Run yt-dlp in a thread to avoid blocking the event loop
        loop = asyncio.get_event_loop()

        def _extract():
            with yt_dlp.YoutubeDL(self.YDL_OPTS) as ydl:
                self.logger.info("Extracting info for: %s", query)

                if query.startswith("http"):
                    return ydl.extract_info(query, download=False)

                # Search sequence: YouTube -> SoundCloud
                for prefix in ["ytsearch", "scsearch"]:
                    try:
                        info = ydl.extract_info(f"{prefix}:{query}", download=False)
                        if info and info.get("entries"):
                            return info["entries"][0]
                    except yt_dlp.utils.DownloadError:
                        continue

                raise yt_dlp.utils.DownloadError(f"No results found for: {query}")

        try:
            return await loop.run_in_executor(None, _extract)
        except Exception as e:
            self.logger.error("Error extracting info for %s: %s", query, e)
            raise

    def get_audio_source(
        self,
        url: str,
        filter_preset: FilterPreset | None = None,
        position: float = 0,
    ) -> discord.FFmpegPCMAudio:
        self.logger.info("Creating FFmpeg audio source (position=%s, filter=%s)", position, filter_preset.name if filter_preset else "None")

        # Adjust position if a filter speed multiplier exists
        seek_position = position
        if filter_preset and filter_preset.speed_multiplier != 1.0:
            seek_position = position * filter_preset.speed_multiplier

        options_parts = ["-vn"]
        if seek_position > 0:
            options_parts.append(f"-ss {seek_position}")

        if filter_preset and filter_preset != FilterPreset.NONE:
            if ffmpeg_filter := filter_preset.ffmpeg_filter:
                options_parts.append(f"-af {ffmpeg_filter}")

        options = " ".join(options_parts)
        return discord.FFmpegPCMAudio(url, before_options=self.FFMPEG_BEFORE_OPTIONS, options=options)

    async def get_metadata(self, info: dict[str, Any]) -> AudioMetaData:
        source_type = AudioSource.YOUTUBE

        if info.get("_direct_url"):
            source_type = AudioSource.DIRECT_URL
        elif info.get("extractor") and "soundcloud" in info.get("extractor").lower():
            source_type = AudioSource.SOUNDCLOUD

        if info.get("_type") == "playlist" and info.get("entries"):
            info = info["entries"][0]

        author_url = None
        if source_type == AudioSource.YOUTUBE and info.get("channel_url"):
            author_url = info.get("channel_url")
        elif source_type == AudioSource.SOUNDCLOUD and info.get("uploader_url"):
            author_url = info.get("uploader_url")

        return AudioMetaData(
            title=info.get("title", "Unknown Title"),
            author=info.get("uploader", info.get("artist", "Unknown Artist")),
            author_url=author_url,
            duration=info.get("duration", 0),
            likes=info.get("like_count"),
            url=info.get("url", info.get("webpage_url", "")),
            webpage_url=info.get("webpage_url", ""),
            thumbnail_url=info.get("thumbnail"),
            source=source_type,
        )
