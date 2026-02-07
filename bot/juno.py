import asyncio
import json
import logging
import os
import time

import discord
from discord.ext import commands

from bot.services import AiOrchestrator, AiServiceFactory, AudioService, ConfigService, CooldownService, DiscordMessagesService, DynamicConfig, EmbedService, ImageGenerationService, MessageService, MongoImageLimitService, MusicQueueService, ResponseService
from bot.utils import JunoSlash


class Juno(commands.Bot):
    def __init__(self, intents, config: DynamicConfig, config_service: ConfigService):
        status = discord.Status.invisible if config.invisible else discord.Status.online
        super().__init__(command_prefix="!", intents=intents, status=status, activity=None)
        self.start_time = time.time()
        self.juno_slash = JunoSlash(self.tree)
        self.config = config
        self.config_service = config_service
        self.logger = logging.getLogger(__name__)
        self._config_reload_lock = False

        # Load prompts
        self.prompts = self._load_prompts(config.promptsPath)

        # Services
        self.ai_service = AiServiceFactory.get_service(provider=config.aiConfig.preferredAiProvider, config=config)
        self.embed_service = EmbedService()
        self.audio_service = AudioService()
        self.music_queue_service = MusicQueueService(self)
        self.ai_orchestrator = AiOrchestrator(config=config)
        self.image_generation_service = ImageGenerationService(self)
        self.message_service = MessageService(self, self.prompts, config.idToUsers)
        self.response_service = ResponseService(config.usersToId)
        self.cooldown_service = CooldownService(config.mentionCooldown, config.cooldownBypassList)
        self.image_limit_service = MongoImageLimitService(self, config.aiConfig.maxDailyImages)
        self.discord_messages_service = DiscordMessagesService(self)

    def _load_prompts(self, prompts_path: str) -> dict:
        """Load prompts from JSON file."""
        try:
            with open(os.path.join(os.getcwd(), prompts_path)) as f:
                prompts = json.load(f)
                self.logger.info(f"Loaded {len(prompts)} prompts from prompts_path={prompts_path}")
                return prompts
        except Exception as e:
            self.logger.error(f"Failed to load prompts from {prompts_path}: {e}")
            return {}

    async def setup_hook(self):
        await self.juno_slash.load_commands()
        await self.load_cogs()

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
        self.logger.info(f"📝 Config version: {self.config_service.dynamic.configVersion}")
        self.logger.info("✅ Juno is online!")

        # Start background task to check for config changes
        self.loop.create_task(self._config_reload_handler())

    async def _config_reload_handler(self):
        """Background task to reload services when config changes."""
        current_version = self.config_service.dynamic.configVersion

        while not self.is_closed():
            await asyncio.sleep(6)  # Check slightly after the watcher checks

            new_version = self.config_service.dynamic.configVersion

            if new_version > current_version and not self._config_reload_lock:
                self._config_reload_lock = True
                try:
                    self.logger.info(f"🔄 Config changed (v{current_version} -> v{new_version}), reloading services...")
                    await self._reload_services()
                    current_version = new_version
                    self.logger.info("✅ Services reloaded successfully")
                except Exception as e:
                    self.logger.error(f"❌ Failed to reload services: {e}", exc_info=True)
                finally:
                    self._config_reload_lock = False

    async def _reload_services(self):
        """Reload services that depend on config."""
        # Update config reference
        self.config = self.config_service.dynamic

        # Reload AI service with new provider/settings
        self.ai_service = AiServiceFactory.get_service(provider=self.config.aiConfig.preferredAiProvider, config=self.config)

        # Update other services that depend on config
        self.cooldown_service = CooldownService(self.config.mentionCooldown, self.config.cooldownBypassList)

        self.message_service = MessageService(self, self.prompts, self.config.idToUsers)
        self.response_service = ResponseService(self.config.usersToId)
        self.image_limit_service = MongoImageLimitService(self, self.config.aiConfig.maxDailyImages)

        await self.change_presence(status=discord.Status.invisible if self.config_service.dynamic.invisible else discord.Status.online)

        self.logger.info(f"🤖 AI Provider: {self.config.aiConfig.preferredAiProvider}")
        self.logger.info(f"⏱️  Mention Cooldown: {self.config.mentionCooldown}s")

    async def on_message(self, message: discord.Message):
        # Early returns for invalid messages
        if message.author == self.user:
            return

        if message.author.bot and message.author.id not in self.config.allowedBotsToRespondTo:
            return

        if self.message_service.should_delete_message(message):
            await self.response_service.send_response(message, "L + RATIO", reply=False)
            await message.delete()

        if message.author.id in self.config.globalBlockList:
            return

        # Check if bot is mentioned or message is a reply to the bot
        reference_message = await self.message_service.get_reference_message(message)
        if not self.message_service.should_respond_to_message(message, reference_message):
            return

        # Apply cooldown check
        if not self.cooldown_service.check_cooldown(message.author.id, message.author.name):
            return

        # Update cooldown and log interaction
        self.cooldown_service.update_cooldown(message.author.id)
        user = message.author
        guild = message.guild
        self.logger.info(f"📝 {user.name} mentioned Juno in {message.channel.name}: {message.content}")

        # Process and respond
        async with message.channel.typing():
            await self._handle_message_intent(message, reference_message, user, guild)

    async def _handle_message_intent(self, message: discord.Message, reference_message: discord.Message, user: discord.User, guild: discord.Guild):
        """Handle the user's message based on detected intent."""
        # Determine if replying to bot's image for intent detection
        is_replying_to_bot_image = self.message_service.is_replying_to_bot_image(reference_message)

        user_intent = await self.ai_orchestrator.detect_intent(
            user_message=message.content,
            is_replying_to_bot_image=is_replying_to_bot_image,
        )

        if user_intent.intent == "chat":
            await self._handle_chat_intent(message, reference_message, user, user_intent)
        elif user_intent.intent == "image_generation":
            await self._handle_image_generation_intent(message, reference_message, user, guild)

    async def _handle_chat_intent(self, message, reference_message, user, user_intent):
        """Handle chat intent."""
        self.logger.info(f"Chatting with intent: {user_intent.intent} for reason of: {user_intent.reasoning}")
        messages = await self.message_service.build_message_context(message, reference_message, user)
        response = await self.ai_service.chat(messages=messages)
        await self.response_service.send_response(message, response.content)

    async def _handle_image_generation_intent(self, message, reference_message, user: discord.User, guild: discord.Guild):
        """Handle image generation intent."""
        can_generate, limit_message = self.image_limit_service.can_generate_image(user, guild)

        self.logger.info(f"[HANDLEIMAGEGENERATIONINTENT] - {can_generate} - {limit_message}")

        if not can_generate:
            await self.response_service.send_response(message, limit_message)
            return

        image_attachments = self.message_service.get_image_attachments(message, reference_message)

        if image_attachments:
            self.logger.info(f"Editing/combining {len(image_attachments)} image(s)")
            image_urls = [att.url for att in image_attachments]
            image_generation_response = await self.image_generation_service.edit_images_from_urls(prompt=message.content, image_urls=image_urls)
        else:
            self.logger.info("No image attachments found, generating image with user prompt.")
            image_generation_response = await self.image_generation_service.generate_image(prompt=message.content)

        if image_generation_response.generated_image:
            self.image_limit_service.increment_usage(message.author.id, message.guild.id)
            image_bytes = self.image_generation_service.image_to_bytes(image=image_generation_response.generated_image)
            filename = "edited_image.png" if image_attachments else "generated_image.png"
            image_file = discord.File(image_bytes, filename=filename)
            await self.response_service.send_response(message, image_generation_response.text_response, image_file)
        else:
            await self.response_service.send_response(message, image_generation_response.text_response)
