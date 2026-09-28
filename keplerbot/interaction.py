from __future__ import annotations

from typing import TYPE_CHECKING

import discord

if TYPE_CHECKING:
    from .bot import Kepler


class KeplerInteraction(discord.Interaction):
    client: Kepler

    async def response_or_followup(self, *args, **kwargs) -> discord.InteractionMessage:
        if self.response.is_done():
            return await self.followup.send(*args, **kwargs)
        await self.response.send_message(*args, **kwargs)
        return await self.original_response()
