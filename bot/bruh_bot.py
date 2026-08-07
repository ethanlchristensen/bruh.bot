import logging
import os
import time

import discord
from discord.ext import commands

from bot.services import (
    AiOrchestrator,
    AudioService,
    ConfigService,
    CooldownService,
    DiscordMessagesService,
    EmbeddingService,
    EmbedService,
    ImageGenerationService,
    MemoryExtractionService,
    MessageService,
    MongoAIUsageService,
    MongoAIUsageTrackingService,
    MongoChatService,
    MongoEconomyService,
    MongoExtractionQueueService,
    MongoGuildMemberService,
    MongoImageLimitService,
    MongoMemoryService,
    MongoMorningConfigService,
    MongoReputationQueueService,
    MongoReputationService,
    MusicQueueService,
    ReputationExtractionService,
    ResponseService,
)
from bot.services.ai import (
    ImageGenerationResponse,
    UserIntent,
)
from bot.services.music.music_websocket_service import MusicWebSocketService
from bot.utils import SlashLoader


class BruhBot(commands.Bot):
    def __init__(self, intents, config_service: ConfigService):
        super().__init__(
            command_prefix="!",
            intents=intents,
            status=discord.Status.online,
            activity=None,
        )
        self.start_time = time.time()
        self.slash_loader = SlashLoader(self.tree)
        self.config_service = config_service
        self.logger = logging.getLogger(__name__)
        self._config_reload_lock = False

        # Services
        self.embed_service = EmbedService()
        self.embedding_service = EmbeddingService(self)
        self.audio_service = AudioService()
        self.music_queue_service = MusicQueueService(self)
        self.image_limit_service = MongoImageLimitService(self)
        self.morning_config_service = MongoMorningConfigService(self)
        self.chat_service = MongoChatService(self)
        self.discord_messages_service = DiscordMessagesService(self)
        self.response_service = ResponseService(self)
        self.message_service = MessageService(self)
        self.cooldown_service = CooldownService(self)
        self.ai_orchestrator = AiOrchestrator(self)
        self.image_generation_service = ImageGenerationService(self)
        self.music_websocket_service = MusicWebSocketService(self)
        self.memory_service = MongoMemoryService(self)
        self.memory_extraction_service = MemoryExtractionService(self)
        self.extraction_queue_service = MongoExtractionQueueService(self)
        self.ai_usage_service = MongoAIUsageService(self)
        self.ai_usage_tracking_service = MongoAIUsageTrackingService(self)
        self.economy_service = MongoEconomyService(self)
        self.guild_member_service = MongoGuildMemberService(self)
        self.reputation_queue_service = MongoReputationQueueService(self)
        self.reputation_service = MongoReputationService(self)
        self.reputation_extraction_service = ReputationExtractionService(self)

    async def setup_hook(self):
        # Initialize database services
        try:
            await self.image_limit_service.initialize()
        except Exception as e:
            self.logger.warning(f"Failed to initialize image_limit_service: {e}")

        try:
            await self.morning_config_service.initialize()
        except Exception as e:
            self.logger.warning(f"Failed to initialize morning_config_service: {e}")

        try:
            await self.chat_service.initialize()
        except Exception as e:
            self.logger.warning(f"Failed to initialize chat_service: {e}")

        try:
            await self.memory_service.initialize()
        except Exception as e:
            self.logger.warning(f"Failed to initialize memory_service: {e}")

        try:
            await self.ai_usage_service.initialize()
        except Exception as e:
            self.logger.warning(f"Failed to initialize ai_usage_service: {e}")

        try:
            await self.ai_usage_tracking_service.initialize()
        except Exception as e:
            self.logger.warning(f"Failed to initialize ai_usage_tracking_service: {e}")

        try:
            await self.economy_service.initialize()
        except Exception as e:
            self.logger.warning(f"Failed to initialize economy_service: {e}")

        try:
            await self.guild_member_service.initialize()
        except Exception as e:
            self.logger.warning(f"Failed to initialize guild_member_service: {e}")

        try:
            await self.extraction_queue_service.initialize()
        except Exception as e:
            self.logger.warning(f"Failed to initialize extraction_queue_service: {e}")

        try:
            await self.memory_extraction_service.start_extraction_loops()
        except Exception as e:
            self.logger.warning(f"Failed to start memory extraction loops: {e}")

        for service in (self.reputation_queue_service, self.reputation_service):
            try:
                await service.initialize()
            except Exception as e:
                self.logger.warning(f"Failed to initialize reputation service: {e}")
        try:
            await self.reputation_extraction_service.start_extraction_loops()
        except Exception as e:
            self.logger.warning(f"Failed to start reputation extraction loop: {e}")

        await self.slash_loader.load_commands()
        await self.load_cogs()
        await self.music_websocket_service.start_server(port=int(os.getenv("WS_PORT", 8001)))

    async def load_cogs(self):
        cogs_dir = os.path.join(os.getcwd(), "bot", "cogs")
        self.logger.info(f"📁 Looking for cogs in: {cogs_dir}")

        cog_files = [f[:-3] for f in os.listdir(cogs_dir) if f.endswith(".py") and f != "__init__.py"]

        total = len(cog_files)
        loaded_successfully = 0

        self.logger.info(f"📁 Found {total} cogs to load")

        for cog_name in cog_files:
            extension_path = f"bot.cogs.{cog_name}"

            try:
                await self.load_extension(extension_path)
                loaded_successfully += 1
                self.logger.info(f"✅ Successfully loaded cog: {cog_name}")
            except Exception as e:
                self.logger.error(f"❌ Failed to load cog {cog_name}: {str(e)}")

        if loaded_successfully == total:
            self.logger.info(f"🎉 All {loaded_successfully} cogs loaded successfully!")
        else:
            self.logger.info(f"📊 Cogs loaded: {loaded_successfully}/{total}")

    async def on_ready(self):
        startup_time = time.time() - self.start_time

        self.logger.info(f"Logged in as {self.user} (ID: {self.user.id})")
        self.logger.info(f"Startup completed in {startup_time:.2f} seconds")

        guild_count = len(self.guilds)
        user_count = sum(g.member_count for g in self.guilds)

        self.logger.info(f"🌐 Connected to {guild_count} guilds with access to {user_count} users")

        # Populate dynamic guild names and icons in MongoDB
        for guild in self.guilds:
            try:
                config = await self.config_service.get_config(str(guild.id))
                updates = {}
                if config.guildName != guild.name:
                    updates["guildName"] = guild.name
                icon_url = str(guild.icon.url) if guild.icon else ""
                if config.guildIcon != icon_url:
                    updates["guildIcon"] = icon_url
                if updates:
                    await self.config_service.update(str(guild.id), updates)
                    self.logger.info(f"Updated guild info for {guild.name} ({guild.id}) in MongoDB")
            except Exception as e:
                self.logger.error(f"Failed to update guild name for {guild.name}: {e}")

        # Sync guild members
        for guild in self.guilds:
            try:
                await self.guild_member_service.sync_all_members(guild)
            except Exception as e:
                self.logger.error(f"Failed to sync members for {guild.name}: {e}")

        for guild in self.guilds:
            try:
                config = await self.config_service.get_config(str(guild.id))
                queued = await self.reputation_queue_service.count(guild.id)
                rep_cfg = config.reputationConfig
                self.logger.info(
                    "Reputation extraction status for %s (%s): enabled=%s, eligible_queued=%s, min_batch=%s, interval=%sm",
                    guild.name,
                    guild.id,
                    rep_cfg.enabled,
                    queued,
                    rep_cfg.minMessagesForExtraction,
                    rep_cfg.extractionIntervalMinutes,
                )
            except Exception:
                self.logger.exception("Failed to report reputation status for guild %s", guild.id)

        self.logger.info("✅ bruh.bot is online!")

    async def on_message(self, message: discord.Message):
        # Early returns for invalid messages
        if message.author == self.user:
            return

        author_id = str(message.author.id)
        guild_id = str(message.guild.id) if message.guild else "dm"

        config = await self.config_service.get_config(guild_id=guild_id)

        if message.author.bot and author_id not in config.allowedBotsToRespondTo:
            return

        if author_id in config.globalBlockList:
            return

        if message.guild:
            await self.memory_extraction_service.enqueue_message(message)

            econ_config = config.economyConfig
            if econ_config.xpEnabled:
                has_attachment = bool(message.attachments)
                is_bot_mention = self.user in message.mentions
                old_level, new_level, leveled_up = await self.economy_service.handle_message_event(
                    guild_id=message.guild.id,
                    user_id=message.author.id,
                    config=econ_config,
                    has_attachment=has_attachment,
                    is_bot_mention=is_bot_mention,
                )
                if leveled_up and econ_config.levelUpAnnounceInChannel:
                    profile = await self.economy_service.get_profile(message.guild.id, message.author.id)
                    next_xp = profile["xp_for_next_level"]
                    embed = self.embed_service.create_success_embed(
                        f"{message.author.mention} reached **Level {new_level}**! 🎉\nTotal XP: **{profile['xp']:,}** · Next level: **{next_xp:,} XP**",
                        title="Level Up!",
                    )
                    await message.channel.send(embed=embed)

        if await self.message_service.should_delete_message(message.guild.id, message):
            await self.response_service.send_response(message, "L + RATIO", reply=False)
            await message.delete()

        # Check if bot is mentioned or message is a reply to the bot
        reference_message = await self.message_service.get_reference_message(message)
        if not await self.message_service.should_respond_to_message(message, reference_message):
            return

        # Reputation only evaluates interactions that explicitly involve the bot.
        if reference_message and reference_message.author.id == self.user.id:
            context = reference_message.content or "[bruh.bot sent an attachment]"
            await self.reputation_extraction_service.enqueue_bot_context(reference_message, context)
        await self.reputation_extraction_service.enqueue_message(message)

        can_respond, reputation = await self.reputation_service.can_respond(message.guild.id, message.author.id)
        if not can_respond:
            reputation = await self.reputation_service.refresh_block(message.guild.id, message.author.id)
            await self._send_reputation_notice(message, reputation, blocked=True, force=True)
            return
        if reputation.get("status") == "warning":
            await self._send_reputation_notice(message, reputation, blocked=False)

        # Apply cooldown check
        if not await self.cooldown_service.check_cooldown(message.author.id, message.guild.id, message.author.display_name):
            return

        # Update cooldown and log interaction
        await self.cooldown_service.update_cooldown(message.author.id, message.guild.id)
        user = message.author
        guild = message.guild
        self.logger.info(f"📝 {user.name} mentioned bruh.bot in {message.channel.name if guild else 'DM'}: {message.content}")

        # Process and respond
        async with message.channel.typing():
            await self._handle_message_intent(message, reference_message)

    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        """Handle voice state updates for bot disconnection and empty channel cleanup."""
        if not member.guild:
            return

        if member.id == self.user.id and before.channel and not after.channel:
            self.logger.info(f"Bot was disconnected from {before.channel.name} in '{member.guild.name}'")
            self.music_queue_service.remove_player(member.guild)
            return
        if before.channel:
            player = self.music_queue_service.players.get(member.guild.id)
            if player and player.voice_client and player.voice_client.channel == before.channel:
                # If only bots are left in the channel
                if not any(not m.bot for m in before.channel.members):
                    self.logger.info(f"No users left in {before.channel.name}, cleaning up.")
                    await player.leave()
                    self.music_queue_service.remove_player(member.guild)

    async def on_reaction_add(self, reaction: discord.Reaction, user: discord.User):
        if user.bot or not reaction.message.guild:
            return
        try:
            await self.economy_service.handle_reaction_event(
                guild_id=reaction.message.guild.id,
                user_id=user.id,
            )
        except Exception:
            self.logger.debug("Failed to handle reaction event", exc_info=True)

    async def on_member_join(self, member: discord.Member):
        try:
            await self.guild_member_service.upsert_member(member)
        except Exception:
            self.logger.debug("Failed to upsert member on join", exc_info=True)

    async def on_member_update(self, before: discord.Member, after: discord.Member):
        try:
            await self.guild_member_service.upsert_member(after)
        except Exception:
            self.logger.debug("Failed to upsert member on update", exc_info=True)

    async def on_user_update(self, before: discord.User, after: discord.User):
        for guild in self.guilds:
            if guild.get_member(after.id):
                try:
                    await self.guild_member_service.upsert_user(after, guild)
                except Exception:
                    self.logger.debug("Failed to upsert user on update", exc_info=True)

    async def _handle_message_intent(self, message: discord.Message, reference_message):
        """Handle the user's message based on detected intent."""
        is_replying_to_bot_image = await self.message_service.is_replying_to_bot_image(reference_message)

        user_intent: UserIntent = await self.ai_orchestrator.detect_intent(
            message.guild.id,
            user_message=message.content,
            is_replying_to_bot_image=is_replying_to_bot_image,
        )

        if user_intent.intent == "chat":
            await self._handle_chat_intent(message, reference_message, user_intent)
        elif user_intent.intent == "image_generation":
            await self._handle_image_generation_intent(message, reference_message)

    async def _handle_chat_intent(self, message: discord.Message, reference_message, user_intent: UserIntent):
        """Handle chat intent."""
        self.logger.info(f"Chatting with intent: {user_intent.intent} for reason of: {user_intent.reasoning}")
        aiConfig = (await self.config_service.get_config(str(message.guild.id))).aiConfig

        can_request, limit_msg = await self.ai_usage_service.consume_request(message.author.id, message.guild.id)
        if not can_request:
            await self.response_service.send_response(message, limit_msg)
            return

        messages = await self.message_service.build_message_context(message, reference_message, message.author.display_name)

        from bot.services.ai.gateway.gateway import get_mesh_gateway
        from bot.services.ai.gateway.schemas.request import NormalizedRequest

        provider = aiConfig.preferredAiProvider
        provider_config = getattr(aiConfig, provider, None) or aiConfig.openrouter
        api_key = provider_config.get_api_key()
        preferred_model = provider_config.preferredModel

        # Check if messages contain image attachments
        has_images = any(isinstance(m.parts, list) and any(p.type == "image" for p in m.parts) for m in messages)

        if has_images:
            supports_vision = False
            gateway = get_mesh_gateway()
            try:
                # Fetch models list for current provider to check capabilities
                if provider == "ollama":
                    ollama_endpoint = getattr(provider_config, "endpoint", "http://localhost:11434")
                    models = await gateway.get_models("ollama", credentials={"endpoint": ollama_endpoint})
                else:
                    models = await gateway.get_models("openrouter", credentials={"api_key": api_key})

                model_info = next((m for m in models if m.id == preferred_model), None)
                if model_info:
                    supports_vision = model_info.capabilities.vision
            except Exception as e:
                self.logger.warning(f"Error fetching model list for vision check: {e}")

            # Fallback to string heuristic check if list lookup is uncertain
            if not supports_vision:
                model_lower = preferred_model.lower()
                supports_vision = "gemini" in model_lower or "gpt-4o" in model_lower or "claude-3" in model_lower or "vision" in model_lower or "pixtral" in model_lower or "llava" in model_lower

            if not supports_vision:
                self.logger.info(f"Model '{preferred_model}' on provider '{provider}' does not support image input. Routing request to OpenRouter with 'google/gemini-3.1-flash-lite'.")
                provider = "openrouter"
                provider_config = aiConfig.openrouter
                api_key = provider_config.get_api_key()
                preferred_model = "google/gemini-3.1-flash-lite"

        req = NormalizedRequest(provider=provider, model=preferred_model, messages=messages)
        gateway = get_mesh_gateway()
        response = await gateway.complete(req, credentials={"api_key": api_key})

        if response.usage:
            await self.ai_usage_tracking_service.track_usage(
                user_id=message.author.id,
                guild_id=message.guild.id,
                input_tokens=response.usage.get("input_tokens", 0),
                output_tokens=response.usage.get("output_tokens", 0),
                cost=response.usage.get("cost", 0),
                model=response.model or preferred_model,
            )

        content = self.message_service.strip_assistant_prefix("".join(part.content for part in response.parts if part.type == "text"))
        sent_msg = await self.response_service.send_response(message, content)
        if sent_msg:
            await self.chat_service.save_message(
                message_id=sent_msg.id,
                channel_id=message.channel.id,
                parent_id=message.id,
                role="assistant",
                content=content,
                author_id=self.user.id,
            )
            await self.memory_extraction_service.enqueue_bot_context(sent_msg, content)
            await self.reputation_extraction_service.enqueue_bot_context(sent_msg, content)

    async def _handle_image_generation_intent(self, message: discord.Message, reference_message):
        """Handle image generation intent."""
        if not message.guild:
            await self.response_service.send_response(message, "Image generation is only available in servers.")
            return

        can_generate, limit_message = await self.image_limit_service.can_generate_image(message)

        self.logger.info(f"[HANDLEIMAGEGENERATIONINTENT] - {can_generate} - {limit_message}")

        if not can_generate:
            await self.response_service.send_response(message, limit_message)
            return

        can_request, limit_msg = await self.ai_usage_service.consume_request(message.author.id, message.guild.id)
        if not can_request:
            await self.response_service.send_response(message, limit_msg)
            return

        # Image requests share the same persisted branch history and memories as chat.
        messages = await self.message_service.build_message_context(message, reference_message, message.author.display_name, include_current_images=False)
        image_attachments = await self.message_service.get_image_attachments(message, reference_message)

        if image_attachments:
            self.logger.info(f"Editing/combining {len(image_attachments)} image(s)")
            image_urls = [att.url for att in image_attachments]
            image_generation_response: ImageGenerationResponse = await self.image_generation_service.edit_images_from_urls(
                guild_id=message.guild.id,
                prompt=message.content,
                image_urls=image_urls,
                messages=messages,
                user_id=message.author.id,
            )
        else:
            self.logger.info("No image attachments found, generating image with user prompt.")
            image_generation_response: ImageGenerationResponse = await self.image_generation_service.generate_image(guild_id=message.guild.id, prompt=message.content, messages=messages, user_id=message.author.id)

        content = self.message_service.strip_assistant_prefix(image_generation_response.text_response)

        if image_generation_response.generated_image:
            await self.image_limit_service.increment_usage(message.author.id, message.guild.id)
            image_bytes = self.image_generation_service.image_to_bytes(image=image_generation_response.generated_image)
            filename = "edited_image.png" if image_attachments else "generated_image.png"
            image_file = discord.File(image_bytes, filename=filename)
            sent_msg = await self.response_service.send_response(message, content, image_file)
        else:
            sent_msg = await self.response_service.send_response(message, content)

        if sent_msg:
            await self.chat_service.save_message(
                message_id=sent_msg.id,
                channel_id=message.channel.id,
                parent_id=message.id,
                role="assistant",
                content=content,
                author_id=self.user.id,
            )
            await self.memory_extraction_service.enqueue_bot_context(sent_msg, content)
            await self.reputation_extraction_service.enqueue_bot_context(sent_msg, content)

    async def _send_reputation_notice(self, message: discord.Message, profile: dict, blocked: bool, force: bool = False):
        if not force and not await self.reputation_service.should_send_notice(message.guild.id, message.author.id):
            return
        events = await self.reputation_service.get_recent_events(message.guild.id, message.author.id)
        audit_lines = [f"- {event['summary']} (+{event['score_delta']})" for event in events]
        audit = "\n".join(audit_lines) or "No recent audit entries are available."
        if blocked:
            until = profile.get("blocked_until")
            expiry = f"Your block has been extended until <t:{int(until.timestamp())}:R>." if until else "This is a manual block."
            embed = self.embed_service.create_error_embed(f"{message.author.mention}, bruh.bot will not respond to you right now. {expiry}\n\n**Recent audit entries:**\n{audit}\n\nContact a server administrator if you believe this is incorrect.")
            embed.title = "Interaction Blocked"
        else:
            embed = self.embed_service.create_warning_embed("Interaction Warning", f"{message.author.mention}, your recent interactions have lowered your reputation with bruh.bot.\n\n**Recent audit entries:**\n{audit}\n\nFurther harmful interactions may cause bruh.bot to stop responding.")
        await message.reply(embed=embed, files=self.embed_service.get_brand_files(embed=embed))
