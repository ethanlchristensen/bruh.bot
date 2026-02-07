import logging

from ..ai.ai_service_factory import AiServiceFactory
from ..config_service import DynamicConfig
from .types import Message, UserIntent

logger = logging.getLogger(__name__)


class AiOrchestrator:
    def __init__(self, config: DynamicConfig):
        self.ai_service = AiServiceFactory.get_service(provider=config.aiConfig.orchestrator.preferredAiProvider, config=config)
        self.model = config.aiConfig.orchestrator.preferredModel
        logger.info(f"Initialized AiOrchestrator with provider={config.aiConfig.orchestrator.preferredAiProvider}, model={self.model}")

    async def detect_intent(self, user_message: str, is_replying_to_bot_image: bool = False) -> UserIntent:
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
            Message(role="system", content=system_prompt),
            Message(role="user", content=user_message),
        ]

        try:
            intent = await self.ai_service.chat_with_schema(messages=messages, schema=UserIntent, model=self.model)

            logger.info(f"Detected intent: {intent.intent} (replying_to_image={is_replying_to_bot_image})")
            return intent

        except Exception as e:
            logger.error(f"Error detecting intent: {e}")
            # Default to chat on error
            return UserIntent(intent="chat", reasoning="Fallback due to error in intent detection")
