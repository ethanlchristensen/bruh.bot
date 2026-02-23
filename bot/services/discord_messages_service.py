import datetime
import logging
from typing import TYPE_CHECKING

import discord
from bson import Int64

from .ai.types import Message

if TYPE_CHECKING:
    from bot.juno import Juno


class DiscordMessagesService:
    def __init__(self, bot: "Juno"):
        self.bot = bot
        self.messages_collection = self.bot.config_service.client[self.bot.config_service.base.mongoDiscordScrapeBot.databaseName][self.bot.config_service.base.mongoDiscordScrapeBot.collectionName]
        self.logger = logging.getLogger(__name__)
        self.logger.info("Initialized DiscordMessagesService")

    async def get_last_n_messages_within_n_minutes(self, message: discord.Message, n: int, minutes: int) -> list[dict]:
        """Returns raw message data instead of Message objects"""
        time_threshold = (datetime.datetime.now(datetime.UTC) - datetime.timedelta(minutes=minutes)).replace(tzinfo=None)
        query = {
            "guild_id": Int64(message.guild.id) if message.guild else "dm",
            "channel_id": Int64(message.channel.id),
            "timestamp": {"$gte": time_threshold},
            "message_id": {"$ne": Int64(message.id)},
            "deleted": False,
        }

        cursor = self.messages_collection.find(query).sort("timestamp", 1).limit(n)
        messages = await cursor.to_list(length=n)

        self.logger.info(f"Fetched {len(messages)} messages for channel {message.channel.id}")
        return messages

    async def convert_db_message_to_ai_message(self, db_message) -> Message:
        idToUsers = (await self.bot.config_service.get_config(db_message["guild_id"])).idToUsers

        role = "user" if db_message["author_id"] != self.bot.user.id else "assistant"
        user = idToUsers.get(str(db_message["author_id"]), db_message["author_name"])
        return Message(role=role, content=f"{user}: {db_message['content']}")
