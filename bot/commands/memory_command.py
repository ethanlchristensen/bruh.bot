from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bot.juno import Juno

import discord
from discord import app_commands

from bot.services.embed_service import EmbedService
from bot.services.mongo_memory_service import VALID_CATEGORIES
from bot.utils.decarators.admin_check import is_admin
from bot.utils.decarators.command_logging import log_command_usage
from bot.utils.decarators.global_block_check import is_globally_blocked

embed_service = EmbedService()

MEMORIES_PER_PAGE = 10


class MemoryCommand:
    def __init__(self, tree: app_commands.CommandTree, args=None):
        memories_group = app_commands.Group(
            name="memories",
            description="View and manage your AI-generated memories",
        )

        @memories_group.command(
            name="view",
            description="View the memories stored about you",
        )
        @app_commands.describe(page="Page number to display")
        @log_command_usage()
        @is_globally_blocked()
        async def view_memories(interaction: discord.Interaction, page: int = 1):
            await interaction.response.defer(ephemeral=True)

            bot: Juno = interaction.client

            try:
                memories = await bot.memory_service.get_memories_for_user(
                    guild_id=interaction.guild.id,
                    user_id=interaction.user.id,
                )

                if not memories:
                    await interaction.followup.send("No memories have been stored about you yet.", ephemeral=True)
                    return

                total_pages = max(1, (len(memories) + MEMORIES_PER_PAGE - 1) // MEMORIES_PER_PAGE)
                page = max(1, min(page, total_pages))
                start = (page - 1) * MEMORIES_PER_PAGE
                page_memories = memories[start : start + MEMORIES_PER_PAGE]

                current_count = len(memories)
                config = await bot.config_service.get_config(str(interaction.guild.id))

                embed = discord.Embed(
                    title=f"🧠 Memories about {interaction.user.display_name}",
                    description=f"Page {page}/{total_pages} · {current_count} total memories (max {config.memoryConfig.maxMemoriesPerUser})\nThese are AI-generated and may not be fully accurate.",
                    color=discord.Color.blue(),
                )

                grouped: dict[str, list[str]] = {}
                for m in page_memories:
                    cat = m.get("category", "unknown")
                    if cat not in grouped:
                        grouped[cat] = []
                    confidence = m.get("confidence", 0.0)
                    grouped[cat].append(f"• {m['memory']} *(confidence: {confidence:.0%})*")

                for cat in sorted(grouped.keys()):
                    embed.add_field(
                        name=f"{cat.title()} ({len(grouped[cat])})",
                        value="\n".join(grouped[cat])[:1024],
                        inline=False,
                    )

                if not page_memories:
                    embed.add_field(name="Empty", value="No memories on this page.", inline=False)

                await interaction.followup.send(embed=embed, ephemeral=True)

            except Exception as e:
                bot.logger.error(f"Error viewing memories: {e}")
                await interaction.followup.send("Failed to retrieve memories.", ephemeral=True)

        admin_group = app_commands.Group(
            name="admin",
            description="Admin commands for managing user memories",
            parent=memories_group,
            default_permissions=discord.Permissions(administrator=True),
        )

        @admin_group.command(
            name="add",
            description="Manually add a memory about a user",
        )
        @app_commands.describe(
            user="The user to add a memory about",
            text="The memory content",
            category=f"The memory category ({', '.join(VALID_CATEGORIES)})",
            target_user="Target user for relationship memories (who the memory is about)",
        )
        @is_admin()
        @log_command_usage()
        @is_globally_blocked()
        async def add_memory(interaction: discord.Interaction, user: discord.User, text: str, category: str = "fact", target_user: discord.User | None = None):
            await interaction.response.defer(ephemeral=True)

            bot: Juno = interaction.client

            try:
                if category not in VALID_CATEGORIES:
                    await interaction.followup.send(f"Invalid category. Valid options: {', '.join(VALID_CATEGORIES)}", ephemeral=True)
                    return

                memory_id = await bot.memory_service.save_memory(
                    guild_id=interaction.guild.id,
                    user_id=user.id,
                    memory=text,
                    category=category,
                    confidence=1.0,
                    created_by="admin",
                    target_user_id=target_user.id if target_user else None,
                )

                embed = discord.Embed(
                    title="✅ Memory Added",
                    description=f"Memory for {user.mention}:\n> {text}\n\nCategory: **{category}** · ID: `{memory_id}`",
                    color=discord.Color.green(),
                )
                await interaction.followup.send(embed=embed, ephemeral=True)

            except Exception as e:
                bot.logger.error(f"Error adding memory: {e}")
                await interaction.followup.send("Failed to add memory.", ephemeral=True)

        @admin_group.command(
            name="remove",
            description="Remove a specific memory by ID",
        )
        @app_commands.describe(memory_id="The ID of the memory to remove")
        @is_admin()
        @log_command_usage()
        @is_globally_blocked()
        async def remove_memory(interaction: discord.Interaction, memory_id: str):
            await interaction.response.defer(ephemeral=True)

            bot: Juno = interaction.client

            try:
                memory = await bot.memory_service.get_memory_by_id(memory_id=memory_id, guild_id=interaction.guild.id)
                if not memory:
                    await interaction.followup.send(f"No memory found with ID `{memory_id}`.", ephemeral=True)
                    return

                deleted = await bot.memory_service.delete_memory(memory_id=memory_id, guild_id=interaction.guild.id)
                if deleted:
                    embed = discord.Embed(
                        title="🗑️ Memory Removed",
                        description=f"Removed: *{memory['memory'][:200]}*\nID: `{memory_id}`",
                        color=discord.Color.orange(),
                    )
                    await interaction.followup.send(embed=embed, ephemeral=True)
                else:
                    await interaction.followup.send("Failed to remove memory.", ephemeral=True)

            except Exception as e:
                bot.logger.error(f"Error removing memory: {e}")
                await interaction.followup.send("Failed to remove memory.", ephemeral=True)

        @admin_group.command(
            name="list",
            description="List all memories for a user",
        )
        @app_commands.describe(
            user="The user to list memories for",
            category=f"Filter by category ({', '.join(VALID_CATEGORIES)}) or leave empty for all",
            page="Page number",
        )
        @is_admin()
        @log_command_usage()
        @is_globally_blocked()
        async def list_memories(interaction: discord.Interaction, user: discord.User, category: str | None = None, page: int = 1):
            await interaction.response.defer(ephemeral=True)

            bot: Juno = interaction.client

            try:
                categories = [category] if category and category in VALID_CATEGORIES else None
                memories = await bot.memory_service.get_memories_for_user(
                    guild_id=interaction.guild.id,
                    user_id=user.id,
                    categories=categories,
                )

                if not memories:
                    await interaction.followup.send(f"No memories found for {user.mention}.", ephemeral=True)
                    return

                total_pages = max(1, (len(memories) + MEMORIES_PER_PAGE - 1) // MEMORIES_PER_PAGE)
                page = max(1, min(page, total_pages))
                start = (page - 1) * MEMORIES_PER_PAGE
                page_memories = memories[start : start + MEMORIES_PER_PAGE]

                embed = discord.Embed(
                    title=f"📋 Memories for {user.display_name}",
                    description=f"Page {page}/{total_pages} · {len(memories)} total",
                    color=discord.Color.blurple(),
                )

                for m in page_memories:
                    embed.add_field(
                        name=f"[{m.get('category', '?')}] {m.get('confidence', 0):.0%} · ID: `{m['_id']}`",
                        value=m["memory"][:1024],
                        inline=False,
                    )

                await interaction.followup.send(embed=embed, ephemeral=True)

            except Exception as e:
                bot.logger.error(f"Error listing memories: {e}")
                await interaction.followup.send("Failed to list memories.", ephemeral=True)

        @admin_group.command(
            name="clear",
            description="Remove all memories for a user",
        )
        @app_commands.describe(user="The user to clear memories for")
        @is_admin()
        @log_command_usage()
        @is_globally_blocked()
        async def clear_memories(interaction: discord.Interaction, user: discord.User):
            await interaction.response.defer(ephemeral=True)

            bot: Juno = interaction.client

            try:
                count = await bot.memory_service.clear_user_memories(
                    guild_id=interaction.guild.id,
                    user_id=user.id,
                )

                embed = discord.Embed(
                    title="🧹 Memories Cleared",
                    description=f"Removed **{count}** memories for {user.mention}.",
                    color=discord.Color.orange(),
                )
                await interaction.followup.send(embed=embed, ephemeral=True)

            except Exception as e:
                bot.logger.error(f"Error clearing memories: {e}")
                await interaction.followup.send("Failed to clear memories.", ephemeral=True)

        @admin_group.command(
            name="toggle",
            description="Enable or disable automatic memory extraction",
        )
        @app_commands.describe(enabled="Whether to enable or disable memory extraction")
        @is_admin()
        @log_command_usage()
        @is_globally_blocked()
        async def toggle_memory(interaction: discord.Interaction, enabled: bool):
            await interaction.response.defer(ephemeral=True)

            bot: Juno = interaction.client

            try:
                guild_id = str(interaction.guild.id)
                config = await bot.config_service.get_config(guild_id)
                await bot.config_service.update(guild_id, {"memoryConfig": {**config.memoryConfig.model_dump(), "enabled": enabled}})

                status = "enabled" if enabled else "disabled"
                embed = discord.Embed(
                    title=f"🔧 Memory Extraction {status.title()}",
                    description=f"Automatic memory extraction is now **{status}**.",
                    color=discord.Color.green() if enabled else discord.Color.red(),
                )
                await interaction.followup.send(embed=embed, ephemeral=True)

            except Exception as e:
                bot.logger.error(f"Error toggling memory extraction: {e}")
                await interaction.followup.send("Failed to toggle memory extraction.", ephemeral=True)

        @admin_group.command(
            name="extract_now",
            description="Force immediate memory extraction for all users",
        )
        @is_admin()
        @log_command_usage()
        @is_globally_blocked()
        async def extract_now(interaction: discord.Interaction):
            await interaction.response.defer(ephemeral=True)

            bot: Juno = interaction.client

            try:
                count = await bot.memory_extraction_service.force_extract_all(
                    guild_id=str(interaction.guild.id),
                )

                embed = discord.Embed(
                    title="⚡ Extraction Triggered",
                    description=f"Memory extraction completed for **{count}** user(s).",
                    color=discord.Color.green(),
                )
                await interaction.followup.send(embed=embed, ephemeral=True)

            except Exception as e:
                bot.logger.error(f"Error force extracting: {e}")
                await interaction.followup.send("Failed to trigger memory extraction.", ephemeral=True)

        @admin_group.command(
            name="extract_user",
            description="Force immediate memory extraction for a specific user",
        )
        @app_commands.describe(user="The user to extract memories for")
        @is_admin()
        @log_command_usage()
        @is_globally_blocked()
        async def extract_user(interaction: discord.Interaction, user: discord.User):
            await interaction.response.defer(ephemeral=True)

            bot: Juno = interaction.client

            try:
                success = await bot.memory_extraction_service.force_extract_user(
                    guild_id=str(interaction.guild.id),
                    user_id=user.id,
                )

                if success:
                    embed = discord.Embed(
                        title="⚡ User Extraction Complete",
                        description=f"Memory extraction completed for {user.mention}.",
                        color=discord.Color.green(),
                    )
                else:
                    embed = discord.Embed(
                        title="⚠️ No Messages Buffered",
                        description=f"No buffered messages found for {user.mention}. They need to send messages first.",
                        color=discord.Color.yellow(),
                    )
                await interaction.followup.send(embed=embed, ephemeral=True)

            except Exception as e:
                bot.logger.error(f"Error force extracting user: {e}")
                await interaction.followup.send("Failed to extract user memories.", ephemeral=True)

        tree.add_command(memories_group)
