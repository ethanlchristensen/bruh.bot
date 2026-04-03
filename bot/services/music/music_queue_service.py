from typing import TYPE_CHECKING

import discord

from .music_player import MusicPlayer

if TYPE_CHECKING:
    from bot.juno import Juno


class MusicQueueService:
    def __init__(self, bot: "Juno"):
        self.bot = bot
        self.players: dict[int, MusicPlayer] = {}

    def get_player(self, guild: discord.Guild) -> MusicPlayer:
        if guild.id not in self.players:
            player = MusicPlayer(self.bot, guild)
            self.players[guild.id] = player
        return self.players[guild.id]

    def remove_player(self, guild: discord.Guild):
        if guild.id in self.players:
            del self.players[guild.id]

    def should_remove_player(self, guild: discord.Guild, channel: discord.VoiceChannel) -> bool:
        """Check if the player should be removed because no users are left in the channel."""
        if guild.id not in self.players:
            return False

        player = self.players[guild.id]
        if not player.voice_client or player.voice_client.channel != channel:
            return False

        # Check if there are any non-bot users in the channel
        remaining_users = [m for m in channel.members if not m.bot]
        return len(remaining_users) == 0
