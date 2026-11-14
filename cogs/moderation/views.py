from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING, List, Union

import discord

from keplerbot import KeplerInteraction

if TYPE_CHECKING:
    from .moderation import Moderation


class HoneyPotSettingsView(discord.ui.View):
    children: List[Union[discord.ui.Button, discord.ui.Select]]

    def __init__(self, interaction: KeplerInteraction) -> None:
        self.interaction = interaction
        self.message: discord.Message = None

    async def start(self) -> None:
        cog: Moderation = self.interaction.client.get_cog("Moderation")

        hs = await cog.db.get_honeypot_settings(self.interaction.guild.id)

        desc = f"Enabled: {hs['enabled']}\n" "Honeypot Channels: "

        if chans := [
            self.interaction.guild.get_channel(c_id) for c_id in hs["channel_ids"]
        ]:
            desc += ", ".join(
                ch.mention if ch else f"Unknown Channel (ID: {ch})" for ch in chans
            )
            desc += "\n"
        else:
            desc += "None\n"

        desc += f"Action: {hs['action']}\n"

        lcid = hs["logchannel_id"]
        lc = self.interaction.guild.get_channel(lcid) if lcid else discord.utils.MISSING
        desc += (
            "Honeypot Log Channel: "
            f"{'None' if lc == discord.utils.MISSING else lc.mention if lc else f'Unknown Channel (ID: {lcid})'}\n"
        )

        embed = discord.Embed(
            title=f"{self.interaction.guild}'s auto ban settings.",
            description=desc,
            colour=self.interaction.client.colour,
        )
        self.message = await self.interaction.response_or_followup(
            embed=embed, view=self
        )

    @discord.ui.button(label="✖️", style=discord.ButtonStyle.danger)
    async def close_button(
        self,
        interaction: KeplerInteraction,
        button: discord.ui.Button["HoneyPotSettingsView"],
    ) -> None:
        await interaction.response.defer()
        self.stop()
        await self.on_timeout()

    async def interaction_check(self, interaction: KeplerInteraction) -> bool:
        if not self.interaction.user:
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

    async def on_timeout(self):
        for button in self.children:
            button.disabled = True
        if self.message:
            with contextlib.suppress(discord.errors.NotFound):
                await self.message.edit(view=self)
