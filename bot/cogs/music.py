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
        embed = self.bot.embed_service.create_action_embed(title="Channel Connection", message=action_response.message, is_success=action_response.is_success)
        await interaction.response.send_message(embed=embed, ephemeral=not action_response.is_success)

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
                embed = self.bot.embed_service.create_error_embed(join_action_response.message)
                await interaction.followup.send(embed=embed)
                return

        # Generate the song metadata
        try:
            info = await self.bot.audio_service.extract_info(query)
            metadata = await self.bot.audio_service.get_metadata(info)
            metadata.text_channel = interaction.channel
            metadata.requested_by = interaction.user.name
            metadata.filter_preset = FilterPreset.from_value(filter)

            if not player.is_playing() and player.queue.empty():
                embed = self.bot.embed_service.create_success_embed(f"Preparing to play **{metadata.title}**", title="Initializing...")
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                queue_position = player.queue.qsize() + 1
                embed = self.bot.embed_service.create_added_to_queue_embed(metadata, queue_position)
                await interaction.followup.send(embed=embed, ephemeral=True)

            await player.add(metadata)
        except Exception as e:
            embed = self.bot.embed_service.create_error_embed(f"Failed to extract song info: {str(e)}")
            await interaction.followup.send(embed=embed)

    @app_commands.command(name="skip", description="Skip actively playing audio.")
    @log_command_usage()
    @require_voice_channel(ephemeral=True, allow_admin_bypass=True)
    @is_globally_blocked()
    async def skip(self, interaction: discord.Interaction):
        skip_action_response = await self.bot.music_queue_service.get_player(interaction.guild).skip()
        embed = self.bot.embed_service.create_action_embed(title="Track Skip", message=skip_action_response.message, is_success=skip_action_response.is_success)
        await interaction.response.send_message(embed=embed, ephemeral=not skip_action_response.is_success)

    @app_commands.command(name="pause", description="Pause the currently playing audio.")
    @log_command_usage()
    @require_voice_channel(ephemeral=True, allow_admin_bypass=True)
    @is_globally_blocked()
    async def pause(self, interaction: discord.Interaction):
        pause_action_response = await self.bot.music_queue_service.get_player(interaction.guild).pause()
        embed = self.bot.embed_service.create_action_embed(title="Playback Paused", message=pause_action_response.message, is_success=pause_action_response.is_success)
        await interaction.response.send_message(embed=embed, ephemeral=not pause_action_response.is_success)

    @app_commands.command(name="resume", description="Resume audio that was previously paused.")
    @log_command_usage()
    @require_voice_channel(ephemeral=True, allow_admin_bypass=True)
    @is_globally_blocked()
    async def resume(self, interaction: discord.Interaction):
        resume_action_response = await self.bot.music_queue_service.get_player(interaction.guild).resume()
        embed = self.bot.embed_service.create_action_embed(title="Playback Resumed", message=resume_action_response.message, is_success=resume_action_response.is_success)
        await interaction.response.send_message(embed=embed, ephemeral=not resume_action_response.is_success)

    @app_commands.command(name="leave", description="Have Juno leave the voice channel.")
    @log_command_usage()
    @require_voice_channel(ephemeral=True, allow_admin_bypass=True)
    @is_globally_blocked()
    async def leave(self, interaction: discord.Interaction):
        leave_action_response = await self.bot.music_queue_service.get_player(interaction.guild).leave()
        embed = self.bot.embed_service.create_action_embed(title="Disconnected", message=leave_action_response.message, is_success=leave_action_response.is_success)
        await interaction.response.send_message(embed=embed, ephemeral=not leave_action_response.is_success)

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

        if not player.current:
            embed = self.bot.embed_service.create_error_embed("No song is currently playing to apply a filter to.")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        self.logger.info(f"Filter called with {new_filter} to {player.current.title}")
        await player.filter(filter_preset)

        embed = self.bot.embed_service.create_success_embed(f"Applied filter: **{filter_preset.display_name}**", title="✨ Filter Engaged")
        await interaction.response.send_message(embed=embed)

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
            embed = self.bot.embed_service.create_error_embed("No song is currently playing.")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # Validate inputs
        if hours < 0 or minutes < 0 or seconds < 0:
            embed = self.bot.embed_service.create_error_embed("Please provide non-negative values for time components.")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # If no values were provided, default to beginning of the song
        if hours == 0 and minutes == 0 and seconds == 0:
            embed = self.bot.embed_service.create_error_embed("Please specify at least one time value (hours, minutes, or seconds).")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        action_response = await player.seek(hours, minutes, seconds)

        embed = self.bot.embed_service.create_action_embed(title="Temporal Shift", message=action_response.message, is_success=action_response.is_success)
        await interaction.response.send_message(embed=embed, ephemeral=not action_response.is_success)


async def setup(bot: "Juno"):
    await bot.add_cog(MusicCog(bot))
