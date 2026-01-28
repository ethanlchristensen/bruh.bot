import logging
import re

import discord


class ResponseService:
    def __init__(self, names_to_ats: dict):
        self.names_to_ats = names_to_ats
        self.logger = logging.getLogger(__name__)

    def process_mentions(self, content: str) -> str:
        """Replace name mentions with Discord user IDs."""

        for name in self.names_to_ats.keys():
            # Remove backticks around the username
            backtick_pattern = r"`\b(" + re.escape(name) + r")\b`"
            content = re.sub(backtick_pattern, r"\1", content, flags=re.IGNORECASE)

        for name, user_id in self.names_to_ats.items():
            pattern = re.compile(r"\b" + re.escape(name) + r"\b", re.IGNORECASE)
            content = pattern.sub(f"{user_id}", content)
        return content

    def split_long_message(self, content: str, max_length: int = 2000) -> list[str]:
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

    async def send_response(self, message: discord.Message, content: str, image_file: discord.File | None = None, reply: bool = True):
        """Send the AI response, splitting if necessary."""
        processed_content = self.process_mentions(content)
        chunks = self.split_long_message(processed_content)

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
