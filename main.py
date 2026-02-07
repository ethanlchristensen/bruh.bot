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

    # Initialize config service with MongoDB support
    config_service = get_config_service("config/base_config.yaml")
    await config_service.initialize(environment=environment)
    config_service.environment = environment

    # Create bot instance
    client = Juno(intents=discord.Intents.all(), config=config_service.dynamic, config_service=config_service)
    client.status = discord.Status.invisible if config_service.dynamic.invisible else discord.Status.online

    # Start config watcher
    await config_service.start_watcher(interval=5)
    logger.info("Config watcher started (checks every 5 seconds)")

    try:
        await client.start(config_service.discord_token, reconnect=True)
    finally:
        # Cleanup
        await config_service.stop_watcher()
        logger.info("Config watcher stopped")


if __name__ == "__main__":
    asyncio.run(main())
