import contextlib
from typing import List, Self

import discord

from keplerbot import KeplerInteraction


class VerificationView(discord.ui.View):
    children: List[discord.ui.Button, discord.ui.Select]

    def __init__(self, interaction: KeplerInteraction):
        super().__init__()
        self.interaction = interaction
        self.message: discord.Message = None

    async def start(self) -> None:
        embed = discord.Embed(
            title=f"Verification settings for {self.interaction.guild}",
            description="test",
            colour=self.interaction.client.colour,
        )
        self.message = await self.interaction.response_or_followup(
            embed=embed, view=self
        )

    @discord.ui.button(emoji="✖", style=discord.ButtonStyle.danger)
    async def close_button(
        self, interaction: KeplerInteraction, _button: discord.ui.Button[Self]
    ) -> None:
        await interaction.response.defer()
        self.stop()
        await self.on_timeout()

    async def interaction_check(self, interaction: KeplerInteraction) -> bool:
        if not self.interaction.user or not interaction.user:
            await interaction.response_or_followup(
                content="Hmmm no interaction user found... This interaction is now timed out.",
                ephemeral=True,
            )
            self.stop()
            await self.on_timeout()
            return False

        if await interaction.client.is_owner(interaction.user):
            return True

        if interaction.user.id != self.interaction.user.id:
            await interaction.response_or_followup(
                content="Access denied.", ephemeral=True
            )
            return False

        return True

    async def on_timeout(self) -> None:
        for button in self.children:
            button.disabled = True
        if self.message:
            with contextlib.suppress(discord.errors.NotFound):
                await self.message.edit(view=self)
