import json
import logging
import os
import time

import discord
from discord.ext import commands

from bot.services import (
    AiOrchestrator,
    AiServiceFactory,
    AudioService,
    ConfigService,
    CooldownService,
    DiscordMessagesService,
    EmbedService,
    ImageGenerationService,
    MessageService,
    MongoImageLimitService,
    MongoMorningConfigService,
    MusicQueueService,
    ResponseService,
)
from bot.services.ai import (
    AIChatResponse,
    AnthropicService,
    GoogleAIService,
    ImageGenerationResponse,
    OllamaService,
    OpenAIService,
    UserIntent,
)
from bot.utils import JunoSlash


class Juno(commands.Bot):
    def __init__(self, intents, config_service: ConfigService):
        super().__init__(
            command_prefix="!",
            intents=intents,
            status=discord.Status.online,
            activity=None,
        )
        self.start_time = time.time()
        self.juno_slash = JunoSlash(self.tree)
        self.config_service = config_service
        self.logger = logging.getLogger(__name__)
        self._config_reload_lock = False
        self._prompts_cache: dict[str, dict] = {}

        # Services
        self.embed_service = EmbedService()
        self.audio_service = AudioService()
        self.music_queue_service = MusicQueueService(self)
        self.image_limit_service = MongoImageLimitService(self)
        self.morning_config_service = MongoMorningConfigService(self)
        self.discord_messages_service = DiscordMessagesService(self)
        self.response_service = ResponseService(self)
        self.message_service = MessageService(self, self.get_prompts(self.config_service.base.promptsPath))
        self.cooldown_service = CooldownService(self)
        self.ollama_service = OllamaService(self)
        self.openai_service = OpenAIService(self)
        self.anthropic_service = AnthropicService(self)
        self.google_service = GoogleAIService(self)
        self.ai_orchestrator = AiOrchestrator(self)
        self.image_generation_service = ImageGenerationService(self)

    def get_prompts(self, prompts_path: str) -> dict:
        """Get prompts from cache or load them."""
        if prompts_path not in self._prompts_cache:
            self._prompts_cache[prompts_path] = self._load_prompts(prompts_path)
        return self._prompts_cache[prompts_path]

    def _load_prompts(self, prompts_path: str) -> dict:
        """Load prompts from JSON file."""
        try:
            path = os.path.join(os.getcwd(), prompts_path)
            if not os.path.exists(path):
                self.logger.warning(f"Prompts file not found: {path}, using empty dict")
                return {}
            with open(path) as f:
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
        self.logger.info("✅ Juno is online!")

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

        if await self.message_service.should_delete_message(message.guild.id, message):
            await self.response_service.send_response(message, "L + RATIO", reply=False)
            await message.delete()

        # Check if bot is mentioned or message is a reply to the bot
        reference_message = await self.message_service.get_reference_message(message)
        if not await self.message_service.should_respond_to_message(message, reference_message):
            return

        # Apply cooldown check
        if not await self.cooldown_service.check_cooldown(message.author.id, message.guild.id, message.author.name):
            return

        # Update cooldown and log interaction
        await self.cooldown_service.update_cooldown(message.author.id, message.guild.id)
        user = message.author
        guild = message.guild
        self.logger.info(f"📝 {user.name} mentioned Juno in {message.channel.name if guild else 'DM'}: {message.content}")

        # Process and respond
        async with message.channel.typing():
            await self._handle_message_intent(message, reference_message)

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
        messages = await self.message_service.build_message_context(message, reference_message, message.author.name)
        response: AIChatResponse = await AiServiceFactory.get_service(self, aiConfig.preferredAiProvider).chat(guild_id=message.guild.id, messages=messages)
        await self.response_service.send_response(message, response.content)

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

        image_attachments = await self.message_service.get_image_attachments(message, reference_message)

        if image_attachments:
            self.logger.info(f"Editing/combining {len(image_attachments)} image(s)")
            image_urls = [att.url for att in image_attachments]
            image_generation_response: ImageGenerationResponse = await self.image_generation_service.edit_images_from_urls(
                guild_id=message.guild.id,
                prompt=message.content,
                image_urls=image_urls,
            )
        else:
            self.logger.info("No image attachments found, generating image with user prompt.")
            image_generation_response: ImageGenerationResponse = await self.image_generation_service.generate_image(guild_id=message.guild.id, prompt=message.content)

        if image_generation_response.generated_image:
            await self.image_limit_service.increment_usage(message.author.id, message.guild.id)
            image_bytes = self.image_generation_service.image_to_bytes(image=image_generation_response.generated_image)
            filename = "edited_image.png" if image_attachments else "generated_image.png"
            image_file = discord.File(image_bytes, filename=filename)
            await self.response_service.send_response(message, image_generation_response.text_response, image_file)
        else:
            await self.response_service.send_response(message, image_generation_response.text_response)
