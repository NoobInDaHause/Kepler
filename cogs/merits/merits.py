import json
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

    async def cog_load(self) -> None:
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
                    f"Can not remove {amount} merits from **{member.name}** "
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
            threshold = int(threshold)
            role = guild.get_role(role_id)
            if not role:
                continue

            should_add = action == "add" and merits >= (threshold)
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
        name="mymerits", description="Show your or other member merits."
    )
    @app_commands.describe(member="The member to show merits for.")
    @app_commands.guild_only()
    async def mymerits(
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

    @app_commands.command(name="merits", description="Give merits to a member.")
    @app_commands.describe(
        action="Whether to add or remove merits.",
        member="The member to add/remove merits to.",
        amount="The amount of merits to add/remove.",
    )
    @app_commands.guild_only()
    @has_permissions(manage_guild=True)
    @bot_has_permissions(manage_roles=True)
    async def merits(
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
                f"{verb} {amount} merits {direction} **{member.name}**. "
                f"They now have {new_merits} merits."
            ),
        )

    # ------------------------------ Settings -----------------------------------
    merits_settings = app_commands.Group(
        name="meritssettings", description="Manage merits settings.", guild_only=True
    )

    @merits_settings.command(
        name="roles",
        description="Manage adding or removing a role for a certain merit threshold.",
    )
    @app_commands.describe(
        action="Whether to add/update or remove a role for a certain merit threshold.",
        threshold="The merit threshold for the role.",
        role="The role to add. (Only required for add/update action.)",
    )
    @has_permissions(manage_guild=True)
    async def merits_settings_roles(
        self,
        interaction: KeplerInteraction,
        action: Literal["add/update", "remove"],
        threshold: int,
        role: discord.Role = None,
    ) -> None:

        merit_roles = (await self.db.get_guild_data(interaction.guild.id))[
            "merit_roles"
        ]

        if action == "add/update":
            if not role:
                return await interaction.response_or_followup(
                    content="You must provide a role to add/update."
                )
            if role.is_bot_managed():
                return await interaction.response_or_followup(
                    content="I cannot manage bot managed roles."
                )
            if not role.is_assignable():
                return await interaction.response_or_followup(
                    content="I cannot manage that role as it is higher than or equal to my top role."
                )
            if interaction.user.top_role <= role:
                return await interaction.response_or_followup(
                    content="You cannot manage a role higher than or equal to your top role."
                )
            merit_roles[str(threshold)] = role.id
            resp = "Added/updated"
        else:
            if str(threshold) not in merit_roles:
                return await interaction.response_or_followup(
                    content=f"No role found for merit threshold {threshold}."
                )
            merit_roles.pop(str(threshold), None)
            resp = "Removed"

        await self.db.execute(
            "INSERT INTO guilds (guild_id, merit_roles) VALUES (?, ?) "
            "ON CONFLICT(guild_id) DO UPDATE SET merit_roles = excluded.merit_roles",
            (interaction.guild.id, json.dumps(merit_roles)),
        )
        await interaction.response_or_followup(
            content=f"{resp} role **{role.name}** for merits threshold {threshold}."
        )

    @merits_settings.command(
        name="view",
        description="View the merits settings for this guild.",
    )
    @has_permissions(manage_guild=True)
    @bot_has_permissions(embed_links=True)
    async def merits_settings_view(
        self,
        interaction: KeplerInteraction,
    ) -> None:
        guild_data = await self.db.get_guild_data(interaction.guild.id)
        desc = "**Merit Roles**\n"
        if merit_roles := guild_data["merit_roles"]:
            for threshold, role_id in sorted(
                merit_roles.items(), key=lambda x: int(x[0])
            ):
                if role := interaction.guild.get_role(role_id):
                    desc += f"• {threshold} merits: {role.mention}\n"
        else:
            desc += "No merit roles have been set for this guild."

        embed = discord.Embed(
            title="Merits Settings",
            description=desc,
            color=discord.Color.blurple(),
        )

        await interaction.response_or_followup(embed=embed)
