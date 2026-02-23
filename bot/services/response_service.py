import logging
import re
from typing import TYPE_CHECKING

import discord

if TYPE_CHECKING:
    from bot.juno import Juno


class ResponseService:
    def __init__(self, bot: "Juno"):
        self.bot = bot
        self.logger = logging.getLogger(__name__)

    async def process_mentions(self, guild_id: int, content: str) -> str:
        """Replace name mentions with Discord user IDs."""
        usersToIds = (await self.bot.config_service.get_config(str(guild_id))).usersToId

        for name in usersToIds:
            backtick_pattern = r"`\b(" + re.escape(name) + r")\b`"
            content = re.sub(backtick_pattern, r"\1", content, flags=re.IGNORECASE)

        for name, user_id in usersToIds.items():
            pattern = re.compile(r"\b" + re.escape(name) + r"\b", re.IGNORECASE)
            content = pattern.sub(f"<@{user_id}>", content)
        return content

    async def split_long_message(self, content: str, max_length: int = 2000) -> list[str]:
        """Split messages longer than max_length characters."""
        if len(content) <= max_length:
            return [content]

        chunks = []
        while len(content) > max_length:
            chunk = content[:max_length]
            last_space = chunk.rfind(" ")

            if last_space != -1:
                chunks.append(content[:last_space])
                content = content[last_space + 1 :]
            else:
                chunks.append(content[:max_length])
                content = content[max_length:]

        if content:
            chunks.append(content)

        return chunks

    async def send_response(self, message: discord.Message, content: str, image_file: discord.File | None = None, reply: bool = True, ephemeral: bool = False):
        """Send the AI response, splitting if necessary."""
        processed_content = await self.process_mentions(message.guild.id, content)
        chunks = await self.split_long_message(processed_content)

        try:
            if image_file:
                if reply:
                    await message.reply(content=processed_content, file=image_file)
                else:
                    await message.channel.send(content=processed_content, file=image_file)
            else:
                for idx, chunk in enumerate(chunks):
                    if idx == 0:
                        if reply:
                            await message.reply(chunk)
                        else:
                            await message.channel.send(chunk)
                    else:
                        await message.channel.send("...")
                        await message.channel.send(chunk)
        except Exception:
            if image_file:
                await message.channel.send(content=processed_content, file=image_file)
            else:
                for idx, chunk in enumerate(chunks):
                    if idx == 0:
                        await message.channel.send(chunk)
                    else:
                        await message.channel.send("...")
                        await message.channel.send(chunk)
