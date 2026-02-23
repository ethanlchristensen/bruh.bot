import asyncio
import logging
import os

import discord

from bot import settings
from bot.juno import Juno
from bot.services import get_config_service

logger = logging.getLogger("bot")


async def main():
    settings.print_startup_banner()

    environment = os.getenv("ENVIRONMENT", "dev").lower()

    config_service = get_config_service("config/base_config.yaml")
    await config_service.initialize(environment=environment)

    client = Juno(intents=discord.Intents.all(), config_service=config_service)

    await config_service.start_watcher(interval=5)

    try:
        await client.start(config_service.discord_token, reconnect=True)
    finally:
        await config_service.stop_watcher()
        logger.info("Config watcher stopped")


if __name__ == "__main__":
    asyncio.run(main())
