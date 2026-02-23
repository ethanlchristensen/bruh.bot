import logging
from typing import TYPE_CHECKING

from .base_service import BaseService

logger = logging.getLogger(__name__)


if TYPE_CHECKING:
    from bot.juno import Juno


class AiServiceFactory:
    @staticmethod
    def get_service(bot: "Juno", provider: str) -> BaseService:
        if provider == "ollama":
            return bot.ollama_service
        elif provider == "openai":
            return bot.openai_service
        elif provider == "google":
            return bot.google_service
        elif provider == "anthropic":
            return bot.anthropic_service
        else:
            raise ValueError(f"Invalid provider: {provider}")
