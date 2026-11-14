from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING, List, Union

import discord

from keplerbot import KeplerInteraction

if TYPE_CHECKING:
    from .moderation import Moderation


class HoneyPotSettingsView(discord.ui.View):
    children: List[Union[discord.ui.Button, discord.ui.Select]]

    def __init__(self, cog: Moderation, interaction: KeplerInteraction) -> None:
        super().__init__()
        self.cog = cog
        self.interaction = interaction
        self.message: discord.Message = None

    async def get_hp_embed(self) -> discord.Embed:
        hs = await self.cog.db.get_honeypot_settings(self.interaction.guild.id)

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
        if lcid is None:
            lc = "None"
        elif r_lc := self.interaction.guild.get_channel(lcid):
            lc = r_lc.mention
        else:
            lc = f"Unknown Channel (ID: {lcid})"

        desc += f"Honeypot Log Channel: {lc}"

        return discord.Embed(
            title=f"{self.interaction.guild}'s HoneyPot settings.",
            description=desc,
            colour=self.interaction.client.colour,
        )

    async def start(self) -> None:
        enabled = (await self.cog.db.get_honeypot_settings(self.interaction.guild.id))[
            "enabled"
        ]

        self.enable_honeypot_button.label = "Enabled" if enabled else "Disabled"
        self.enable_honeypot_button.style = (
            discord.ButtonStyle.success if enabled else discord.ButtonStyle.danger
        )

        embed = await self.get_hp_embed()
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

    @discord.ui.button(label="Enabled", style=discord.ButtonStyle.success)
    async def enable_honeypot_button(
        self,
        interaction: KeplerInteraction,
        button: discord.ui.Button["HoneyPotSettingsView"],
    ) -> None:
        enabled = int(
            not (await self.cog.db.get_honeypot_settings(interaction.guild.id))[
                "enabled"
            ]
        )

        await self.cog.db.execute(
            """
            INSERT INTO honeypot_settings (guild_id, enabled)
            VALUES (?, ?)
            ON CONFLICT(guild_id) DO UPDATE SET enabled = excluded.enabled
            """,
            (interaction.guild.id, enabled),
        )

        button.label = "Enabled" if enabled else "Disabled"
        button.style = (
            discord.ButtonStyle.success if enabled else discord.ButtonStyle.danger
        )

        embed = await self.get_hp_embed()
        await interaction.response.edit_message(embed=embed, view=self)

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
