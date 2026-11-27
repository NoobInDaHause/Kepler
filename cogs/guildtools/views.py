import contextlib
from typing import List, Self

import discord

from keplerbot import KeplerInteraction


class VerificationView(discord.ui.View):
    children: List[discord.ui.Button, discord.ui.Select]

    def __init__(self):
        super().__init__()
        self.message: discord.Message = None

    async def start(self, interaction: KeplerInteraction) -> None:
        embed = discord.Embed(
            title=f"Verification settings for {interaction.guild}",
            description="test",
            colour=interaction.client.colour,
        )
        self.message = await interaction.response_or_followup(embed=embed)

    @discord.ui.button(emoji="✖", style=discord.ButtonStyle.danger)
    async def close_button(
        self, interaction: KeplerInteraction, button: discord.ui.Button[Self]
    ) -> None:
        await interaction.response.defer()
        self.stop()
        await self.on_timeout()

    async def interaction_check(self, interaction) -> bool:
        return await super().interaction_check(interaction)

    async def on_timeout(self) -> None:
        for button in self.children:
            button.disabled = True
        if self.message:
            with contextlib.suppress(discord.errors.NotFound):
                await self.message.edit(view=self)
