import logging
from typing import TYPE_CHECKING

from .ai_service_factory import AiServiceFactory
from .types import Message, Role, UserIntent

if TYPE_CHECKING:
    from bot.juno import Juno


class AiOrchestrator:
    def __init__(self, bot: "Juno"):
        self.bot = bot
        self.logger = logging.getLogger(__name__)

    async def detect_intent(self, guild_id: int, user_message: str, is_replying_to_bot_image: bool = False) -> UserIntent:
        """
        Detect if the user wants to chat or generate an image.

        Args:
            user_message: The user's message
            is_replying_to_bot_image: Whether the user is replying to a bot message containing an image

        Returns:
            UserIntent: Either "chat" or "image_generation"
        """
        context_note = ""
        if is_replying_to_bot_image:
            context_note = "\n\nIMPORTANT: The user is replying to a bot message that contains an image. This strongly suggests they want to edit or modify that image, unless their message clearly indicates otherwise (e.g., asking a question about the image)."

        system_prompt = f"""You are an intent classifier. Determine if the user wants to:
- chat: Have a conversation, ask questions, get information
- image_generation: Create, generate, make, edit, or modify an image/picture/photo

Examples of image_generation:
- "generate an image of a cat"
- "create a picture of a sunset"
- "make me a logo"
- "draw a dragon"
- "make it darker" (when replying to an image)
- "add a hat to this" (when replying to an image)
- "change the background to blue" (when replying to an image)

Everything else is chat.{context_note}"""

        messages = [
            Message(role=Role.SYSTEM, content=system_prompt),
            Message(role=Role.USER, content=user_message),
        ]

        orchestrator_config = (await self.bot.config_service.get_config(str(guild_id))).aiConfig.orchestrator

        ai_service = AiServiceFactory.get_service(self.bot, orchestrator_config.preferredAiProvider)

        try:
            intent = await ai_service.chat_with_schema(guild_id=guild_id, messages=messages, schema=UserIntent, model=orchestrator_config.preferredModel)

            self.logger.info(f"Detected intent: {intent.intent} (replying_to_image={is_replying_to_bot_image})")
            return intent

        except Exception as e:
            self.logger.error(f"Error detecting intent: {e}")
            return UserIntent(intent="chat", reasoning="Fallback due to error in intent detection")
