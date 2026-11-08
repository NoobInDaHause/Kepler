import contextlib
import math
import random
from typing import Dict, List, Literal, Tuple

import discord
from discord import app_commands
from discord.ext import commands
import orjson

from keplerbot import Kepler, KeplerInteraction
from utilities.checks import bot_has_permissions, cooldown, has_permissions
from utilities.views import PaginatorView

from .leveling_data_manager import LevelingDataBase


class Leveling(commands.Cog):
    """
    Leveling cog.
    """

    def __init__(self, bot: Kepler):
        self.bot = bot
        self.db = LevelingDataBase(self.__class__.__name__)
        self.cooldowns: Dict[int, commands.CooldownMapping] = {}

    @staticmethod
    def make_progress_bar(exp: int, threshold: int, length: int = 20) -> str:
        progress = min(max(exp / threshold, 0.0), 1.0)
        units = round(progress * length * 2)
        full, half = divmod(units, 2)

        bar = "■" * full

        if half and full < length:
            bar += "▣"

        bar += "□" * (length - full - half)

        return f"{bar} {progress:.2%}"

    @staticmethod
    def threshold_for_level(level: int, base_exp: int, multiplier: float) -> int:
        return max(1, math.ceil(base_exp * (multiplier**level)))

    async def cog_load(self) -> None:
        await self.db.initialize()

    async def announce_levelup(
        self, message: discord.Message, old_level: int, new_level: int
    ) -> None:

        guild_data = await self.db.get_guild_data(message.guild.id)
        channel = (
            message.guild.get_channel(guild_data["levelup_channel"]) or message.channel
        )

        with contextlib.suppress(discord.errors.Forbidden):
            embed = discord.Embed(
                title="Level Up",
                description=f"**`{old_level}` -> `{new_level}`**",
                color=self.bot.colour,
                timestamp=discord.utils.utcnow(),
            )
            embed.set_thumbnail(url=message.author.display_avatar.url)
            await channel.send(
                content=f"Congratulations {message.author.mention}!", embed=embed
            )

    async def update_member_roles(
        self, guild: discord.Guild, member: discord.Member, new_level: int
    ) -> None:
        guild_data = await self.db.get_guild_data(guild.id)
        level_roles = guild_data["level_roles"]
        accumulate_roles = bool(guild_data["accumulate_level_roles"])

        configured_roles = {
            role.id: role
            for role_id in level_roles.values()
            if (role := guild.get_role(role_id)) is not None
        }
        unlocked_roles: List[Tuple[int, discord.Role]] = []
        for level, role_id in level_roles.items():
            if int(level) <= new_level:
                if (role := guild.get_role(role_id)) is not None:
                    unlocked_roles.append((int(level), role))

        unlocked_role_ids = {role.id for _, role in unlocked_roles}
        if accumulate_roles:
            member_role_ids = {role.id for role in member.roles}
            roles_to_add = [
                role
                for role_id, role in configured_roles.items()
                if role_id in unlocked_role_ids
                if role_id not in member_role_ids
            ]
            if roles_to_add:
                await member.add_roles(*roles_to_add, reason="Level-up role update")
            return

        highest_unlocked_level = max(
            (level for level, _ in unlocked_roles),
            default=None,
        )
        desired_role_ids = {
            role.id for level, role in unlocked_roles if level == highest_unlocked_level
        }
        member_role_ids = {role.id for role in member.roles}
        roles_to_add = [
            role
            for role_id, role in configured_roles.items()
            if role_id in desired_role_ids and role_id not in member_role_ids
        ]
        roles_to_remove = [
            role
            for role_id, role in configured_roles.items()
            if role_id in member_role_ids and role_id not in desired_role_ids
        ]

        if roles_to_add:
            await member.add_roles(*roles_to_add, reason="Level-up role update")
        if roles_to_remove:
            await member.remove_roles(*roles_to_remove, reason="Level-up role update")

    @commands.Cog.listener("on_message")
    async def get_exp(self, message: discord.Message) -> None:
        if message.author.bot or message.guild is None:
            return

        member_id = message.author.id
        guild_id = message.guild.id

        guild_data = await self.db.get_guild_data(guild_id)
        if guild_data["enabled"] == 0:
            return

        if (
            not self.cooldowns.setdefault(
                guild_id,
                commands.CooldownMapping.from_cooldown(
                    guild_data["rate"],
                    guild_data["cooldown"],
                    commands.BucketType.member,
                ),
            )
            .get_bucket(message)
            .update_rate_limit()
        ):
            member_data = await self.db.get_member_data(guild_id, member_id)
            now_exp = member_data["exp"] + random.randint(
                guild_data["min_exp"], guild_data["max_exp"]
            )
            old_level = member_data["level"]
            now_level = old_level

            threshold = self.threshold_for_level(
                now_level,
                guild_data["level_threshold"],
                guild_data["threshold_multiplier"],
            )

            while now_exp >= threshold:
                now_exp -= threshold
                now_level = now_level + 1
                threshold = self.threshold_for_level(
                    now_level,
                    guild_data["level_threshold"],
                    guild_data["threshold_multiplier"],
                )

            await self.db.execute(
                """
                INSERT INTO members (guild_id, member_id, exp, level)
                VALUES (?, ?, ?, ?)
                ON CONFLICT (guild_id, member_id)
                DO UPDATE SET exp = excluded.exp, level = excluded.level
                """,
                (guild_id, member_id, now_exp, now_level),
            )

            if now_level > old_level:
                if isinstance(message.author, discord.Member):
                    await self.update_member_roles(
                        message.guild, message.author, now_level
                    )
                await self.announce_levelup(message, old_level, now_level)

    @app_commands.command(
        name="rank", description="Check your or other member level and experience."
    )
    @app_commands.guild_only()
    @bot_has_permissions(embed_links=True)
    @cooldown(1, 5, key=lambda interaction: (interaction.guild_id, interaction.user.id))
    @app_commands.describe(member="The member to check the level of.")
    async def rank(
        self, interaction: KeplerInteraction, member: discord.Member = None
    ) -> None:
        member = member or interaction.user
        if member.bot:
            return await interaction.response_or_followup(
                "Bots can not have levels.", ephemeral=True
            )

        member_id = member.id
        guild_id = interaction.guild.id

        guild_data = await self.db.get_guild_data(guild_id)
        if guild_data["enabled"] == 0:
            return await interaction.response_or_followup(
                "Leveling system is not enabled for this guild. Ask an admin to enable it."
            )

        member_data = await self.db.get_member_data(guild_id, member_id)

        threshold = self.threshold_for_level(
            member_data["level"],
            guild_data["level_threshold"],
            guild_data["threshold_multiplier"],
        )

        exp = member_data["exp"]

        embed = discord.Embed(
            title=f"{member.name}'s Level",
            description=f"Level: {member_data['level']}\nExperience: {exp}/{threshold}\n"
            f"{self.make_progress_bar(exp, threshold)}",
            color=member.colour,
        )

        await interaction.response_or_followup(embed=embed)

    @app_commands.command(
        name="leaderboard",
        description="View the top members by level and experience.",
    )
    @app_commands.guild_only()
    @bot_has_permissions(embed_links=True)
    @cooldown(1, 5, key=lambda interaction: (interaction.guild_id, interaction.user.id))
    @app_commands.describe(
        members_per_page="The number of members to show per page. (max 20)"
    )
    async def leaderboard(
        self, interaction: KeplerInteraction, members_per_page: int = 10
    ) -> None:
        if members_per_page < 10 or members_per_page > 20:
            return await interaction.response_or_followup(
                content="The range to display members should only be 10-20."
            )

        guild_id = interaction.guild.id

        guild_data = await self.db.get_guild_data(guild_id)
        if guild_data["enabled"] == 0:
            return await interaction.response_or_followup(
                "Leveling system is not enabled for this guild. Ask an admin to enable it."
            )

        members = await self.db.execute(
            """
            SELECT member_id, exp, level
            FROM members
            WHERE guild_id = ?
            ORDER BY level DESC, exp DESC, member_id ASC
            """,
            (guild_id,),
            select=True,
            one_all="all",
        )

        if not members:
            return await interaction.response_or_followup(
                "No members have earned experience yet."
            )

        entries = ""
        pages = []

        for rank, (member_id, exp, level) in enumerate(members, start=1):
            threshold = self.threshold_for_level(
                level,
                guild_data["level_threshold"],
                guild_data["threshold_multiplier"],
            )
            entries += (
                f"**{rank}.** <@{member_id}> — Level **{level}** · "
                f"**{exp}/{threshold} EXP**\n"
            )
            if rank % members_per_page == 0:
                pages.append(entries)
                entries = ""

        if entries:
            pages.append(entries)

        embeds = []
        for index, page in enumerate(pages, start=1):
            embed = discord.Embed(
                title=f"Top member levels in `{interaction.guild.name}`.",
                description=page,
                color=self.bot.colour,
                timestamp=discord.utils.utcnow(),
            )
            embed.set_footer(text=f"Page ({index}/{len(pages)})")
            embeds.append(embed)

        await PaginatorView(interaction, embeds).start()

    # ------------------------------ Settings ----------------------------------------
    levelingsettings = app_commands.Group(
        name="levelingsettings",
        description="Manage leveling settings for this guild.",
        guild_only=True,
    )

    @levelingsettings.command(
        name="alterexp",
        description="Add or remove experience from a member.",
    )
    @has_permissions(manage_guild=True)
    @app_commands.describe(
        act="Add or remove experience from a member.",
        member="The target member.",
        exp="The amount of experience to add or remove.",
    )
    @app_commands.rename(act="action")
    async def alterexp(
        self,
        interaction: KeplerInteraction,
        act: Literal["add", "remove"],
        member: discord.Member,
        exp: int,
    ) -> None:
        if member.bot:
            return await interaction.response_or_followup(
                content="Can not add or remove exp from bots."
            )

        guild_id = interaction.guild.id
        member_id = member.id

        guild_data = await self.db.get_guild_data(guild_id)
        member_data = await self.db.get_member_data(guild_id, member_id)

        if exp < 0:
            return await interaction.response_or_followup(
                "Experience amount must be non-negative."
            )

        old_level = member_data["level"]
        new_level = old_level
        new_exp = member_data["exp"]

        if act == "add":
            new_exp += exp
            threshold = self.threshold_for_level(
                new_level,
                guild_data["level_threshold"],
                guild_data["threshold_multiplier"],
            )
            while new_exp >= threshold:
                new_exp -= threshold
                new_level += 1
                threshold = self.threshold_for_level(
                    new_level,
                    guild_data["level_threshold"],
                    guild_data["threshold_multiplier"],
                )
        else:
            exp_remaining = exp
            if exp_remaining <= new_exp:
                new_exp -= exp_remaining
                exp_remaining = 0
            else:
                exp_remaining -= new_exp
                new_exp = 0

                while exp_remaining > 0 and new_level > 0:
                    new_level -= 1
                    threshold = self.threshold_for_level(
                        new_level,
                        guild_data["level_threshold"],
                        guild_data["threshold_multiplier"],
                    )
                    if exp_remaining < threshold:
                        new_exp = threshold - exp_remaining
                        exp_remaining = 0
                    else:
                        exp_remaining -= threshold

        await self.db.execute(
            """
            INSERT INTO members (guild_id, member_id, exp, level)
            VALUES (?, ?, ?, ?)
            ON CONFLICT (guild_id, member_id)
            DO UPDATE SET exp = excluded.exp, level = excluded.level
            """,
            (guild_id, member_id, new_exp, new_level),
        )

        if new_level != old_level:
            await self.update_member_roles(interaction.guild, member, new_level)

        threshold = self.threshold_for_level(
            new_level,
            guild_data["level_threshold"],
            guild_data["threshold_multiplier"],
        )
        if act == "add":
            response = f"Added {exp} EXP to {member.mention}."
        else:
            removed_exp = exp - exp_remaining
            response = f"Removed {removed_exp} EXP from {member.mention}."

        response += (
            f" They are now level {new_level} with {new_exp}/{threshold} EXP "
            "toward the next level."
        )
        await interaction.response_or_followup(response)

    @levelingsettings.command(
        name="enable", description="Enable or disable leveling system for this guild."
    )
    @has_permissions(manage_guild=True)
    async def levelingsettings_enable(self, interaction: KeplerInteraction) -> None:
        guild_id = interaction.guild.id

        guild_data = await self.db.get_guild_data(guild_id)
        bool_conv = bool(guild_data["enabled"])

        await self.db.execute(
            """
            INSERT INTO guilds (guild_id, enabled)
            VALUES (?, ?)
            ON CONFLICT (guild_id)
            DO UPDATE SET enabled = excluded.enabled
            """,
            (guild_id, int(not bool_conv)),
        )

        await interaction.response_or_followup(
            f"Leveling system has been {'disabled' if bool_conv else 'enabled'} for this guild."
        )

    @levelingsettings.command(
        name="levelupchannel",
        description="Set or remove the level up announcement channel.",
    )
    @has_permissions(manage_guild=True)
    @app_commands.describe(
        channel="The channel to send level up announcements in. Leave empty to remove."
    )
    async def levelingsettings_levelupchannel(
        self, interaction: KeplerInteraction, channel: discord.TextChannel = None
    ) -> None:
        guild_id = interaction.guild.id

        if channel is None:
            await self.db.execute(
                """
                INSERT INTO guilds (guild_id, levelup_channel)
                VALUES (?, NULL)
                ON CONFLICT (guild_id)
                DO UPDATE SET levelup_channel = NULL
                """,
                (guild_id,),
            )
            await interaction.response_or_followup(
                "Level up announcement channel has been removed."
            )
        else:
            if (
                not channel.permissions_for(interaction.guild.me).send_messages
                or not channel.permissions_for(interaction.guild.me).embed_links
            ):
                return await interaction.response_or_followup(
                    f"I do not have permission to send messages and/or embed links in {channel.mention}.",
                )
            await self.db.execute(
                """
                INSERT INTO guilds (guild_id, levelup_channel)
                VALUES (?, ?)
                ON CONFLICT (guild_id)
                DO UPDATE SET levelup_channel = excluded.levelup_channel
                """,
                (guild_id, channel.id),
            )
            await interaction.response_or_followup(
                f"Level up announcement channel has been set to {channel.mention}.",
            )

    @levelingsettings.command(
        name="setexp", description="Set the experience range for leveling."
    )
    @has_permissions(manage_guild=True)
    @app_commands.describe(
        min_exp="The minimum experience a member can gain per message. (default: 15)",
        max_exp="The maximum experience a member can gain per message. (default: 25)",
    )
    async def levelingsettings_setexp(
        self,
        interaction: KeplerInteraction,
        min_exp: int = 15,
        max_exp: int = 25,
    ) -> None:
        guild_id = interaction.guild.id

        if min_exp < 0 or max_exp < 0 or min_exp > max_exp:
            return await interaction.response_or_followup(
                "Invalid experience range. Ensure that both values are non-negative and that the "
                "minimum is not greater than the maximum."
            )

        await self.db.execute(
            """
            INSERT INTO guilds (guild_id, min_exp, max_exp)
            VALUES (?, ?, ?)
            ON CONFLICT (guild_id)
            DO UPDATE SET min_exp = excluded.min_exp, max_exp = excluded.max_exp
            """,
            (guild_id, min_exp, max_exp),
        )

        await interaction.response_or_followup(
            f"Experience range has been set to {min_exp} - {max_exp}."
        )

    @levelingsettings.command(
        name="setcooldown", description="Set the cooldown for gaining experience."
    )
    @has_permissions(manage_guild=True)
    @app_commands.describe(
        rate="The number of messages a member can send before the cooldown is applied. (default: 1)",
        cd="The cooldown in seconds before a member can gain experience again. (default: 30)",
    )
    @app_commands.rename(cd="cooldown")
    async def levelingsettings_setcooldown(
        self, interaction: KeplerInteraction, rate: int = 1, cd: int = 30
    ) -> None:
        guild_id = interaction.guild.id

        if cd < 0 or rate < 0:
            return await interaction.response_or_followup(
                "Invalid cooldown or rate. Ensure that both values are non-negative."
            )

        await self.db.execute(
            """
            INSERT INTO guilds (guild_id, rate, cooldown)
            VALUES (?, ?, ?)
            ON CONFLICT (guild_id)
            DO UPDATE SET rate = excluded.rate, cooldown = excluded.cooldown
            """,
            (guild_id, rate, cd),
        )

        self.cooldowns.pop(guild_id, None)
        self.cooldowns[guild_id] = commands.CooldownMapping.from_cooldown(
            rate, cd, commands.BucketType.member
        )

        await interaction.response_or_followup(
            f"Cooldown for gaining experience has been set to {rate} time per {cd} seconds."
        )

    @levelingsettings.command(
        name="setthreshold", description="Set the exp needed per level."
    )
    @has_permissions(manage_guild=True)
    @app_commands.describe(
        base_exp="The base exp needed to level up. (default: 100)",
        multiplier="The multiplier that multiplies the base threshold per level. (default: 1.15)",
    )
    async def levelingsettings_setthreshold(
        self,
        interaction: KeplerInteraction,
        base_exp: int = 100,
        multiplier: float = 1.15,
    ) -> None:
        guild_id = interaction.guild.id

        if base_exp < 1 or multiplier < 0:
            return await interaction.response_or_followup(
                "Invalid base exp or multiplier. Ensure that base exp is not less than 1 and "
                "multiplier should not be lower than 0."
            )

        await self.db.execute(
            """
            INSERT INTO guilds (guild_id, level_threshold, threshold_multiplier)
            VALUES (?, ?, ?)
            ON CONFLICT (guild_id)
            DO UPDATE SET level_threshold = excluded.level_threshold, threshold_multiplier = excluded.threshold_multiplier
            """,
            (guild_id, base_exp, multiplier),
        )

        await interaction.response_or_followup(
            f"The base exp has been set to {base_exp} and will be multiplied by {multiplier} per level."
        )

    @levelingsettings.command(
        name="setlevelrole", description="Add/update/remove a role to a certain level."
    )
    @has_permissions(manage_guild=True)
    @app_commands.describe(
        action="Add/update or remove a role for a certain level.",
        level="The level to assign the role to.",
        role="The role to assign to the level. (Only for add/update)",
    )
    async def levelingsettings_setlevelrole(
        self,
        interaction: KeplerInteraction,
        action: Literal["add/update", "remove"],
        level: int,
        role: discord.Role = None,
    ) -> None:
        level_roles = (await self.db.get_guild_data(interaction.guild.id))[
            "level_roles"
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
            level_roles[str(level)] = role.id
            resp = "Added/updated"
        else:
            if str(level) not in level_roles:
                return await interaction.response_or_followup(
                    content=f"No role found for level {level}."
                )
            level_roles.pop(str(level), None)
            resp = "Removed"

        await self.db.execute(
            "INSERT INTO guilds (guild_id, level_roles) VALUES (?, ?) "
            "ON CONFLICT(guild_id) DO UPDATE SET level_roles = excluded.level_roles",
            (interaction.guild.id, orjson.dumps(level_roles).decode("utf-8")),
        )
        await interaction.response_or_followup(
            content=f"{resp} role **{role.name}** for level {level}."
        )

    @levelingsettings.command(
        name="setroleaccumulation",
        description="Set whether to accumulate or replace roles for levels.",
    )
    @has_permissions(manage_guild=True)
    async def levelingsettings_setroleaccumulation(
        self, interaction: KeplerInteraction
    ) -> None:
        guild_id = interaction.guild.id

        guild_data = await self.db.get_guild_data(guild_id)
        bool_conv = bool(guild_data["accumulate_level_roles"])

        await self.db.execute(
            """
            INSERT INTO guilds (guild_id, accumulate_level_roles)
            VALUES (?, ?)
            ON CONFLICT (guild_id)
            DO UPDATE SET accumulate_level_roles = excluded.accumulate_level_roles
            """,
            (guild_id, int(not bool_conv)),
        )

        await interaction.response_or_followup(
            f"Roles will now be {'accumulated' if bool_conv else 'replaced'} for levels."
        )

    @levelingsettings.command(
        name="viewsettings", description="View your guild leveling settings."
    )
    @has_permissions(manage_guild=True)
    @bot_has_permissions(embed_links=True)
    async def levelingsettings_viewsettings(
        self, interaction: KeplerInteraction
    ) -> None:
        guild_id = interaction.guild.id

        guild_data = await self.db.get_guild_data(guild_id)

        desc = (
            f"Enabled: {bool(guild_data['enabled'])}\n"
            f"EXP range per message: {guild_data['min_exp']} - {guild_data['max_exp']}\n"
            f"Message cooldown: {guild_data['rate']} per {guild_data['cooldown']} seconds.\n"
            f"Level threshold: base {guild_data['level_threshold']}, multiplier {guild_data['threshold_multiplier']}\n"
        )

        if c := guild_data.get("levelup_channel"):
            if chan := interaction.guild.get_channel(c):
                desc += f"Levelup announcement channel: {chan.mention}\n"
            else:
                desc += f"Levelup announcement channel: Channel not found (ID: {c})\n"
        else:
            desc += "Levelup announcement channel: None\n"

        desc += "Level roles:\n"

        if level_roles := guild_data.get("level_roles"):
            for lvl, rid in level_roles.items():
                if role := interaction.guild.get_role(rid):
                    desc += f"{lvl}: {role.mention}\n"
                else:
                    desc += f"{lvl}: Role not found (ID: {rid})\n"
        else:
            desc += "No level roles set.\n"

        desc += f"Accumulate/replace level roles: {'Accumulate' if guild_data.get('accumulate_level_roles') else 'Replace'}\n"

        embed = discord.Embed(
            title=f"Leveling settings for {interaction.guild}",
            description=desc,
            colour=self.bot.colour,
            timestamp=discord.utils.utcnow(),
        )
        embed.set_thumbnail(url=interaction.guild.icon)

        await interaction.response_or_followup(embed=embed)
