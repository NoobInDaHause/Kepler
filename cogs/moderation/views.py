from __future__ import annotations

from typing import TYPE_CHECKING

import discord

from keplerbot import KeplerInteraction

if TYPE_CHECKING:
    from .moderation import Moderation


class HoneyPotSettingsView(discord.ui.View):
    def __init__(self, interaction: KeplerInteraction) -> None:
        self.interaction = interaction
        self.message: discord.Message = None

    async def start(self) -> None:
        cog: Moderation = self.interaction.client.get_cog("Moderation")
        
        embed = discord.Embed(
            title=f"{self.interaction.guild}'s auto ban settings.",
            description="",
            colour=self.interaction.client.colour,
        )
        self.message = await self.interaction.response_or_followup(embed=embed, view=self)
