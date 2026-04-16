from dataclasses import dataclass
from enum import Enum
from typing import Any

import discord
from discord import app_commands


class AudioSource(Enum):
    YOUTUBE = "youtube"
    SOUNDCLOUD = "soundcloud"
    DIRECT_URL = "direct_url"


class FilterPreset(Enum):
    NONE = ("none", "None", None, 1.0)
    BASSBOOST = ("bassboost", "Bass Boost", "bass=g=10", 1.0)
    NIGHTCORE = (
        "nightcore",
        "Nightcore",
        "asetrate=48000*1.25,aresample=48000",
        1.25,
    )
    VAPORWAVE = (
        "vaporwave",
        "Vaporwave",
        "asetrate=48000*0.8,aresample=48000",
        0.8,
    )
    TREBLE = ("treble", "Treble Boost", "treble=g=5", 1.0)
    ECHO = ("echo", "Echo", "aecho=0.8:0.88:60:0.4", 1.0)
    VIBRATO = ("vibrato", "Vibrato", "vibrato=f=6.5:d=0.5", 1.0)
    TREMOLO = ("tremolo", "Tremolo", "tremolo=f=6.5:d=0.5", 1.0)
    DISTORTION = ("distortion", "Distortion", "areverse,areverse", 1.0)
    MONO = ("mono", "Mono", "pan=mono|c0=0.5*c0+0.5*c1", 1.0)
    VOLUME_BOOST = ("volume_boost", "Volume Boost", "volume=2.0", 1.0)
    LOFI = ("lofi", "Lo-Fi", "aresample=8000,aresample=44100", 1.0)
    CHORUS = (
        "chorus",
        "Chorus",
        "chorus=0.5:0.9:50|60|40:0.4|0.32|0.3:0.25|0.4|0.3:2|2.3|1.3",
        1.0,
    )
    REVERSE = ("reverse", "Reverse", "areverse", 1.0)
    PHASER = (
        "phaser",
        "Phaser",
        "aphaser=in_gain=0.4:out_gain=0.74:delay=3:decay=0.4:speed=0.5:type=triangular",
        1.0,
    )
    CHIPMUNK = ("chipmunk", "Chipmunk", "asetrate=48000*1.5,aresample=48000", 1.5)
    SLOWMO = ("slowmo", "Slow Motion", "asetrate=48000*0.5,aresample=48000", 0.5)
    ROBOT = (
        "robot",
        "Robot Voice",
        "afftfilt=real='hypot(re,im)*sin(0)':imag='hypot(re,im)*cos(0)':win_size=512:overlap=0.75",
        1.0,
    )
    UNDERWATER = (
        "underwater",
        "Underwater",
        "lowpass=f=800,highpass=f=200,chorus=0.7:0.9:55:0.4:0.25:2",
        1.0,
    )
    TELEPHONE = ("telephone", "Telephone", "highpass=f=900,lowpass=f=3000", 1.0)
    CRYSTALIZE = (
        "crystalize",
        "Crystalize",
        "crystalizer=intensity=0.7:resonance=0.5",
        1.0,
    )
    COMPRESSOR = (
        "compressor",
        "Compressor",
        "acompressor=threshold=0.089:ratio=9:attack=200:release=1000",
        1.0,
    )
    EARWAX = ("earwax", "Earwax", "earwax", 1.0)
    REVERB = (
        "reverb",
        "Shimmering Reverb",
        "aecho=0.8:0.88:1000:0.6,aecho=0.8:0.9:1500:0.4,aecho=0.8:0.92:2000:0.3,volume=0.8",
        1.0,
    )
    # HAAS = ("haas", "Haas Effect", "haas=level_in=1:level_out=1:side_gain=0.5:middle_source=mid:middle_phase=0")
    STEREOWIDE = (
        "stereowide",
        "Stereo Wide",
        "stereowiden=delay=20:feedback=0.3:crossfeed=0.3:drymix=0.8",
        1.0,
    )
    PITCH_UP = (
        "pitch_up",
        "Pitch Up",
        "asetrate=48000*1.2,aresample=48000",
        1.2,
    )
    PITCH_DOWN = (
        "pitch_down",
        "Pitch Down",
        "asetrate=48000*0.8,aresample=48000",
        0.8,
    )
    EIGHT_BIT = (
        "8bit",
        "8-Bit",
        "aresample=8000:resampler=soxr,aresample=48000:resampler=soxr",
        1.0,
    )

    def __init__(
        self,
        value: str,
        display_name: str,
        ffmpeg_filter: str | None,
        speed_multiplier: float = 1.0,
    ):
        self._value_ = value
        self.display_name = display_name
        self.ffmpeg_filter = ffmpeg_filter
        self.speed_multiplier = speed_multiplier

    @classmethod
    def get_choices(cls) -> list[app_commands.Choice[str]]:
        """Convert the enum members to app_commands.Choice objects for use with slash commands"""
        return [app_commands.Choice(name=preset.display_name, value=preset.value) for preset in cls]

    @classmethod
    def from_value(cls, value: str) -> "FilterPreset":
        """Get a FilterPreset from its string value"""
        for preset in cls:
            if preset.value == value:
                return preset
        return cls.NONE


@dataclass
class AudioMetaData:
    title: str
    author: str
    author_url: str
    duration: int
    url: str
    webpage_url: str
    thumbnail_url: str | None = None
    source: AudioSource = AudioSource.YOUTUBE
    likes: int | None = None
    filter_preset: FilterPreset | None = FilterPreset.NONE
    requested_by: str | None = None
    text_channel: discord.TextChannel | None = None
    position: int = 0
    to_front: bool = False
    should_pause: bool = False
    skip_now_playing_embed: bool = False

    @property
    def effective_duration(self) -> int:
        """Calculate the duration adjusted for the filter speed multiplier."""
        if self.filter_preset and self.filter_preset.speed_multiplier != 1.0:
            return int(self.duration / self.filter_preset.speed_multiplier)
        return self.duration

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AudioMetaData":
        filter_preset = FilterPreset.from_value(data.get("filter_preset"))

        return cls(
            title=data["title"],
            author=data["author"],
            author_url=data["author_url"],
            duration=data["duration"],
            url=data["url"],
            webpage_url=data["webpage_url"],
            thumbnail_url=data.get("thumbnail_url"),
            source=AudioSource(data.get("source", "youtube")),
            likes=data.get("likes"),
            filter_preset=filter_preset,
            requested_by=data["requested_by"],
            position=data.get("position"),
            to_front=data.get("to_front"),
            should_pause=data.get("should_pause"),
            skip_now_playing_embed=data.get("skip_now_playing_embed", False),
        )

    def to_dict(self) -> dict[str, Any]:
        """Return a dictionary representation of the metadata with the RAW duration."""
        return {
            "title": self.title,
            "author": self.author,
            "author_url": self.author_url,
            "duration": self.duration,
            "url": self.url,
            "webpage_url": self.webpage_url,
            "thumbnail_url": self.thumbnail_url,
            "source": self.source.value,
            "likes": self.likes,
            "filter_preset": self.filter_preset.value if self.filter_preset else None,
            "requested_by": self.requested_by,
            "position": self.position or 0,
            "to_front": self.to_front or False,
            "should_pause": self.should_pause or False,
            "skip_now_playing_embed": self.skip_now_playing_embed or False,
        }

    def to_ui_dict(self) -> dict[str, Any]:
        """Return a dictionary representation of the metadata with the EFFECTIVE duration for UI display."""
        d = self.to_dict()
        d["duration"] = self.effective_duration
        return d


@dataclass
class MusicPlayerActionResponse:
    is_success: bool
    message: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MusicPlayerActionResponse":
        return cls(
            is_success=data["is_success"],
            message=data.get("message"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "is_success": self.is_success,
            "message": self.message,
        }
