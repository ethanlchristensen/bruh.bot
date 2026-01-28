import logging
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from bot.services.embed_service import QueuePaginationView
from bot.services.music.types import FilterPreset
from bot.utils.decarators.command_logging import log_command_usage
from bot.utils.decarators.global_block_check import is_globally_blocked
from bot.utils.decarators.voice_check import require_voice_channel

if TYPE_CHECKING:
    from bot.juno import Juno


class MusicCog(commands.Cog):
    def __init__(self, bot: "Juno"):
        self.bot = bot
        self.logger = logging.getLogger(__name__)

    async def filter_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        """Autocomplete for filter presets"""
        choices = []
        current_lower = current.lower()

        for preset in FilterPreset:
            # Filter based on user input
            if current_lower in preset.display_name.lower() or current_lower in preset.value.lower():
                choices.append(app_commands.Choice(name=preset.display_name, value=preset.value))

                # Discord limits autocomplete to 25 choices
                if len(choices) >= 25:
                    break

        return choices

    @app_commands.command(name="join", description="Have Juno join the VC you are currently in.")
    @log_command_usage()
    @require_voice_channel(ephemeral=True, allow_admin_bypass=True)
    @is_globally_blocked()
    async def join(self, interaction: discord.Interaction):
        action_response = await self.bot.music_queue_service.get_player(interaction.guild).join(interaction)
        await interaction.response.send_message(action_response.message, ephemeral=not action_response.is_success)

    @app_commands.command(name="play", description="Play a song with a link or query.")
    @app_commands.describe(query="Song name or YouTube link", filter="Audio filter to apply")
    @app_commands.autocomplete(filter=filter_autocomplete)
    @log_command_usage()
    @require_voice_channel(ephemeral=True, allow_admin_bypass=True)
    @is_globally_blocked()
    async def play(self, interaction: discord.Interaction, query: str, filter: str | None):
        await interaction.response.defer(ephemeral=True)

        # Get the music player for this guild
        player = self.bot.music_queue_service.get_player(interaction.guild)

        # Check / Join a voice channel
        if not player.voice_client:
            join_action_response = await player.join(interaction)

            if not join_action_response.is_success:
                await interaction.followup.send(join_action_response.message)
                return

        # Generate the song metadata
        metadata = self.bot.audio_service.get_metadata(self.bot.audio_service.extract_info(query))
        metadata.text_channel = interaction.channel
        metadata.requested_by = interaction.user.name
        metadata.filter_preset = FilterPreset.from_value(filter)

        if not player.is_playing() and player.queue.empty():
            await interaction.followup.send("Starting playback...", ephemeral=True)
        else:
            queue_position = player.queue.qsize()
            embed = self.bot.embed_service.create_added_to_queue_embed(metadata, queue_position)
            await interaction.followup.send(embed=embed, ephemeral=True)

        await player.add(metadata)

    @app_commands.command(name="skip", description="Skip actively playing audio.")
    @log_command_usage()
    @require_voice_channel(ephemeral=True, allow_admin_bypass=True)
    @is_globally_blocked()
    async def skip(self, interaction: discord.Interaction):
        skip_action_response = await self.bot.music_queue_service.get_player(interaction.guild).skip()
        await interaction.response.send_message(skip_action_response.message, ephemeral=not skip_action_response.is_success)

    @app_commands.command(name="pause", description="Pause the currently playing audio.")
    @log_command_usage()
    @require_voice_channel(ephemeral=True, allow_admin_bypass=True)
    @is_globally_blocked()
    async def pause(self, interaction: discord.Interaction):
        pause_action_response = await self.bot.music_queue_service.get_player(interaction.guild).pause()
        await interaction.response.send_message(pause_action_response.message, ephemeral=not pause_action_response.is_success)

    @app_commands.command(name="resume", description="Resume audio that was previously paused.")
    @log_command_usage()
    @require_voice_channel(ephemeral=True, allow_admin_bypass=True)
    @is_globally_blocked()
    async def resume(self, interaction: discord.Interaction):
        resume_action_response = await self.bot.music_queue_service.get_player(interaction.guild).resume()
        await interaction.response.send_message(resume_action_response.message, ephemeral=not resume_action_response.is_success)

    @app_commands.command(name="leave", description="Have Juno leave the voice channel.")
    @log_command_usage()
    @require_voice_channel(ephemeral=True, allow_admin_bypass=True)
    @is_globally_blocked()
    async def leave(self, interaction: discord.Interaction):
        leave_action_response = await self.bot.music_queue_service.get_player(interaction.guild).leave()
        await interaction.response.send_message(leave_action_response.message, ephemeral=not leave_action_response.is_success)

    @app_commands.command(name="queue", description="View the current music queue.")
    @log_command_usage()
    @require_voice_channel(ephemeral=True, allow_admin_bypass=True)
    @is_globally_blocked()
    async def queue(self, interaction: discord.Interaction):
        player = self.bot.music_queue_service.get_player(interaction.guild)

        # Get a copy of the queue items
        queue_items = list(player.queue._queue)

        embed = self.bot.embed_service.create_queue_embed(
            queue_items=queue_items,
            current_track=player.current,
            page=1,
            items_per_page=5,
        )

        view = QueuePaginationView(queue_items, player.current, self.bot.embed_service)

        await interaction.response.send_message(embed=embed, view=view)

    @app_commands.command(name="filter", description="Apply a new audio filter to the current track.")
    @app_commands.autocomplete(new_filter=filter_autocomplete)
    @log_command_usage()
    @require_voice_channel(ephemeral=True, allow_admin_bypass=True)
    @is_globally_blocked()
    async def filter(
        self,
        interaction: discord.Interaction,
        new_filter: str,
    ):
        player = self.bot.music_queue_service.get_player(interaction.guild)
        filter_preset = FilterPreset.from_value(new_filter)

        self.logger.info(f"Filter called with {new_filter} to {player.current.title}")

        filtered = await player.filter(filter_preset)

        if filtered:
            await interaction.response.send_message(f"Applied filter: `{filter_preset.display_name}`")
        else:
            await interaction.response.send_message("No song is currently playing to apply a filter to.", ephemeral=True)

    @app_commands.command(name="seek", description="Seek to a specific position in the current song.")
    @app_commands.describe(
        hours="Hours (optional)",
        minutes="Minutes (optional)",
        seconds="Seconds (optional)",
    )
    @log_command_usage()
    @require_voice_channel(ephemeral=True, allow_admin_bypass=True)
    @is_globally_blocked()
    async def seek(
        self,
        interaction: discord.Interaction,
        hours: int | None = 0,
        minutes: int | None = 0,
        seconds: int | None = 0,
    ):
        player = self.bot.music_queue_service.get_player(interaction.guild)

        if not player.current:
            await interaction.response.send_message("No song is currently playing.", ephemeral=True)
            return

        # Validate inputs
        if hours < 0 or minutes < 0 or seconds < 0:
            await interaction.response.send_message(
                "Please provide non-negative values for hours, minutes, and seconds.",
                ephemeral=True,
            )
            return

        # If no values were provided, default to beginning of the song
        if hours == 0 and minutes == 0 and seconds == 0:
            await interaction.response.send_message(
                "Please specify at least one time value (hours, minutes, or seconds).",
                ephemeral=True,
            )
            return

        action_response = await player.seek(hours, minutes, seconds)

        await interaction.response.send_message(action_response.message, ephemeral=not action_response.is_success)


async def setup(bot: "Juno"):
    await bot.add_cog(MusicCog(bot))
