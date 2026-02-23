import logging
from collections.abc import Awaitable, Callable
from functools import wraps
from typing import TYPE_CHECKING, ParamSpec, TypeVar, cast

import discord

from bot.services.embed_service import EmbedService

P = ParamSpec("P")
T = TypeVar("T")

logger = logging.getLogger(__name__)
embed_service = EmbedService()

if TYPE_CHECKING:
    from bot.juno import Juno


def is_admin() -> Callable[[Callable[P, Awaitable[T]]], Callable[P, Awaitable[T]]]:
    """
    Decorator that checks if the user is in the ADMINS list from environment variables.
    """

    def decorator(func: Callable[P, Awaitable[T]]) -> Callable[P, Awaitable[T]]:
        @wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            # Find the interaction object
            interaction = next(
                (arg for arg in args if isinstance(arg, discord.Interaction)),
                kwargs.get("interaction", None),
            )

            if not interaction:
                # If there's no interaction, just call the original function
                return await func(*args, **kwargs)

            await interaction.response.defer(ephemeral=True)

            bot: Juno = interaction.client

            config = await bot.config_service.get_config(str(interaction.guild.id))

            if str(interaction.user.id) in config.adminIds:
                return await func(*args, **kwargs)
            else:
                logger.warning(f"User '{interaction.user.name}' of '{interaction.guild.name}' attempted to run an Admin command.")
                embed = embed_service.create_error_embed(error_message="You don't have permission to use this command.")
                await interaction.followup.send(embed=embed, ephemeral=True)
                return cast(T, None)

        return wrapper

    return decorator
