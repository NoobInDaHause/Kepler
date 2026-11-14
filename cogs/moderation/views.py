from __future__ import annotations

import asyncio
import contextlib
from typing import TYPE_CHECKING, List, Union

import discord
from discord.ext import commands

from keplerbot import KeplerInteraction

if TYPE_CHECKING:
    from .moderation import Moderation


class HoneyPotSettingsView(discord.ui.View):
    children: List[Union[discord.ui.Button, discord.ui.Select]]

    def __init__(self, cog: Moderation, interaction: KeplerInteraction) -> None:
        super().__init__(timeout=60.0)
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

        desc += f"Action: **{hs['action']}**\n"

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
        hs = await self.cog.db.get_honeypot_settings(self.interaction.guild.id)

        self.enable_honeypot_button.label = "Enabled" if hs["enabled"] else "Disabled"
        self.enable_honeypot_button.style = (
            discord.ButtonStyle.success if hs["enabled"] else discord.ButtonStyle.danger
        )
        self.action_button.emoji = "👢" if hs["action"] == "kick" else "🔨"
        self.action_button.style = (
            discord.ButtonStyle.grey
            if hs["action"] == "kick"
            else discord.ButtonStyle.danger
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

    @discord.ui.button(label="Set HoneyPot Channels", style=discord.ButtonStyle.blurple)
    async def sethoneypotchannels_button(
        self,
        interaction: KeplerInteraction,
        button: discord.ui.Button["HoneyPotSettingsView"],
    ) -> None:
        # too lazy for now
        await interaction.response.defer()

    @discord.ui.button(label="Action", style=discord.ButtonStyle.grey, emoji="👢")
    async def action_button(
        self,
        interaction: KeplerInteraction,
        button: discord.ui.Button["HoneyPotSettingsView"],
    ) -> None:
        hs = (await self.cog.db.get_honeypot_settings(interaction.guild.id))["action"]

        new_act = "ban" if hs == "kick" else "kick"
        button.emoji = "👢" if new_act == "kick" else "🔨"
        button.style = (
            discord.ButtonStyle.grey
            if new_act == "kick"
            else discord.ButtonStyle.danger
        )

        await self.cog.db.execute(
            """
            INSERT INTO honeypot_settings (guild_id, action)
            VALUES (?, ?)
            ON CONFLICT(guild_id) DO UPDATE SET action = excluded.action
            """,
            (interaction.guild.id, new_act),
        )

        embed = await self.get_hp_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Log Channel", style=discord.ButtonStyle.blurple)
    async def logchannel_button(
        self,
        interaction: KeplerInteraction,
        button: discord.ui.Button["HoneyPotSettingsView"],
    ) -> None:
        init_msg = await interaction.response_or_followup(
            content="Please mention the channel or input channel id after this message. (pass 'none' to clear the log channel)"
        )

        try:
            ans = await self.cog.bot.wait_for(
                "message",
                check=lambda x: x.author.id == interaction.user.id,
                timeout=30.0,
            )
        except asyncio.TimeoutError:
            await init_msg.edit(content="You took too long to respond.")
            await init_msg.delete(delay=5.0)
            return

        try:
            channel = await commands.TextChannelConverter().convert(
                await interaction.client.get_context(self.interaction), ans.content
            )
        except commands.BadArgument:
            await init_msg.edit(content="That does not seem to be a valid channel.")
            await init_msg.delete(delay=5.0)
            return

        if not channel:
            await init_msg.edit(content="That does not seem to be a valid channel.")
            await init_msg.delete(delay=5.0)
            return
        if not isinstance(channel, discord.TextChannel):
            await init_msg.edit(
                content="You can only set a TextChannel for the log channel."
            )
            await init_msg.delete(delay=5.0)
            return
        if (
            not channel.permissions_for(interaction.guild.me).send_messages
            or not channel.permissions_for(interaction.guild.me).view_channel
        ):
            await init_msg.edit(
                content="I can not seem to view or send messages in that channel."
            )
            await init_msg.delete(delay=5.0)
            return

        await self.cog.db.execute(
            """
            INSERT INTO honeypot_settings (guild_id, logchannel_id)
            VALUES (?, ?)
            ON CONFLICT(guild_id) DO UPDATE SET logchannel_id = excluded.logchannel_id
            """,
            (interaction.guild.id, channel.id),
        )

        embed = await self.get_hp_embed()
        await interaction.message.edit(embed=embed, view=self)

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
