from typing import Literal, Optional

import discord
from discord import app_commands
from discord.ext import commands

from keplerbot import Kepler, KeplerInteraction
from utilities.checks import bot_has_permissions, has_permissions

from .merits_data_manager import MeritsDataBase


class Merits(commands.Cog):
    """
    Give merits to members.
    """

    def __init__(self, bot: Kepler):
        self.bot = bot
        self.db = MeritsDataBase(self.__class__.__name__)

    async def initialize(self) -> None:
        await self.db.initialize()

    async def _get_new_merits(
        self,
        interaction: KeplerInteraction,
        action: Literal["add", "remove"],
        member: discord.Member,
        amount: int,
    ) -> Optional[int]:
        current_merits = (
            await self.db.get_member_data(interaction.guild.id, member.id)
        )["merits"]
        new_merits = (
            current_merits + amount if action == "add" else current_merits - amount
        )

        if new_merits < 0:
            await interaction.response_or_followup(
                content=(
                    f"Can not remove {amount} merits from {member.mention} "
                    f"as they only have {current_merits} merits."
                ),
            )
            return None

        return new_merits

    async def _update_roles(
        self,
        guild: discord.Guild,
        member: discord.Member,
        merit_roles: dict,
        merits: int,
        action: Literal["add", "remove"],
    ) -> None:
        roles = []
        for threshold, role_id in merit_roles.items():
            role = guild.get_role(role_id)
            if not role:
                continue

            should_add = action == "add" and merits >= threshold
            should_remove = action == "remove" and merits < threshold
            if (should_add and role not in member.roles) or (
                should_remove and role in member.roles
            ):
                roles.append(role)

        if not roles:
            return

        update_roles = member.add_roles if action == "add" else member.remove_roles
        operation = "addition" if action == "add" else "removal"
        await update_roles(*roles, reason=f"Merits role {operation}.")

    async def _save_merits(
        self,
        guild_id: int,
        member_id: int,
        merits: int,
    ) -> None:
        await self.db.execute(
            """
            INSERT INTO members (guild_id, member_id, merits)
            VALUES (?, ?, ?)
            ON CONFLICT(guild_id, member_id) DO UPDATE SET merits = excluded.merits
            """,
            (guild_id, member_id, merits),
        )

    @app_commands.command(
        name="merits", description="Show your or other member merits."
    )
    @app_commands.describe(member="The member to show merits for.")
    async def merits(
        self,
        interaction: KeplerInteraction,
        member: discord.Member = None,
    ) -> None:
        member = member or interaction.user
        if member.bot:
            return await interaction.response_or_followup(
                content="Bots can not have merits."
            )
        member_data = await self.db.get_member_data(interaction.guild.id, member.id)
        merits = member_data["merits"]

        await interaction.response_or_followup(
            content=f"Member **{member.name}** has {merits} merits.",
        )

    @app_commands.command(name="merit", description="Give merits to a member.")
    @app_commands.describe(
        action="Whether to add or remove merits.",
        member="The member to give merits to.",
        amount="The amount of merits to give.",
    )
    @has_permissions(manage_guild=True)
    @bot_has_permissions(manage_roles=True)
    async def merit(
        self,
        interaction: KeplerInteraction,
        action: Literal["add", "remove"],
        member: discord.Member,
        amount: int = 1,
    ) -> None:
        if amount <= 0:
            return await interaction.response_or_followup(
                content="Amount must be greater than 0."
            )
        if member.bot:
            return await interaction.response_or_followup(
                content="You cannot give merits to a bot."
            )

        new_merits = await self._get_new_merits(interaction, action, member, amount)
        if new_merits is None:
            return

        guild_id = interaction.guild.id
        guild_data = await self.db.get_guild_data(guild_id)
        await self._update_roles(
            interaction.guild,
            member,
            guild_data["merit_roles"],
            new_merits,
            action,
        )
        await self._save_merits(guild_id, member.id, new_merits)

        verb = "Added" if action == "add" else "Removed"
        direction = "to" if action == "add" else "from"
        await interaction.response_or_followup(
            content=(
                f"{verb} {amount} merits {direction} {member.mention}. "
                f"They now have {new_merits} merits."
            ),
        )
