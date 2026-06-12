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
    EmbedService,
    ImageGenerationService,
    MessageService,
    MongoImageLimitService,
    MongoMorningConfigService,
    MusicQueueService,
    ResponseService,
)
from bot.services.ai import (
    ImageGenerationResponse,
    UserIntent,
)
from bot.services.music.music_websocket_service import MusicWebSocketService
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

        # Services
        self.embed_service = EmbedService()
        self.audio_service = AudioService()
        self.music_queue_service = MusicQueueService(self)
        self.image_limit_service = MongoImageLimitService(self)
        self.morning_config_service = MongoMorningConfigService(self)
        self.discord_messages_service = DiscordMessagesService(self)
        self.response_service = ResponseService(self)
        self.message_service = MessageService(self)
        self.cooldown_service = CooldownService(self)
        self.ai_orchestrator = AiOrchestrator(self)
        self.image_generation_service = ImageGenerationService(self)
        self.music_websocket_service = MusicWebSocketService(self)

    async def setup_hook(self):
        await self.juno_slash.load_commands()
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

        # Populate dynamic guild names in MongoDB
        for guild in self.guilds:
            try:
                config = await self.config_service.get_config(str(guild.id))
                if config.guildName != guild.name:
                    await self.config_service.update(str(guild.id), {"guildName": guild.name})
                    self.logger.info(f"Updated guild name for {guild.name} ({guild.id}) in MongoDB")
            except Exception as e:
                self.logger.error(f"Failed to update guild name for {guild.name}: {e}")

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

        from bot.services.ai.gateway.gateway import get_mesh_gateway
        from bot.services.ai.gateway.schemas.request import NormalizedRequest

        provider = aiConfig.preferredAiProvider
        provider_config = getattr(aiConfig, provider, None) or aiConfig.openrouter
        api_key = provider_config.get_api_key()
        preferred_model = provider_config.preferredModel

        req = NormalizedRequest(provider=provider, model=preferred_model, messages=messages)
        gateway = get_mesh_gateway()
        response = await gateway.complete(req, credentials={"api_key": api_key})
        content = "".join(part.content for part in response.parts if part.type == "text")
        await self.response_service.send_response(message, content)

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
