import contextlib
import math
import random
from typing import Dict, Literal

import discord
from discord import app_commands
from discord.ext import commands

from keplerbot import Kepler, KeplerInteraction
from utilities.checks import bot_has_permissions, cooldown, has_permissions
from utilities.views import PaginatorView

from .leveling_data_manager import LevelingDataBase


@app_commands.guild_only()
class LevelingSettings(app_commands.Group):
    def __init__(self):
        super().__init__(
            name="levelingsettings",
            description="Manage leveling settings for this guild.",
        )


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
    leveling_settings = LevelingSettings()

    @leveling_settings.command(
        name="enable", description="Enable or disable leveling system for this guild."
    )
    @has_permissions(manage_guild=True)
    async def leveling_settings_enable(self, interaction: KeplerInteraction) -> None:
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

    @leveling_settings.command(
        name="levelupchannel",
        description="Set or remove the level up announcement channel.",
    )
    @has_permissions(manage_guild=True)
    @app_commands.describe(
        channel="The channel to send level up announcements in. Leave empty to remove."
    )
    async def leveling_settings_levelupchannel(
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

    @leveling_settings.command(
        name="setexp", description="Set the experience range for leveling."
    )
    @has_permissions(manage_guild=True)
    @app_commands.describe(
        min_exp="The minimum experience a member can gain per message. (default: 15)",
        max_exp="The maximum experience a member can gain per message. (default: 25)",
    )
    async def leveling_settings_setexp(
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

    @leveling_settings.command(
        name="setcooldown", description="Set the cooldown for gaining experience."
    )
    @has_permissions(manage_guild=True)
    @app_commands.describe(
        rate="The number of messages a member can send before the cooldown is applied. (default: 1)",
        cd="The cooldown in seconds before a member can gain experience again. (default: 30)",
    )
    @app_commands.rename(cd="cooldown")
    async def leveling_settings_setcooldown(
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

    @leveling_settings.command(
        name="setthreshold", description="Set the exp needed per level."
    )
    @has_permissions(manage_guild=True)
    @app_commands.describe(
        base_exp="The base exp needed to level up. (default: 100)",
        multiplier="The multiplier that multiplies the base threshold per level. (default: 1.15)",
    )
    async def level_settings_setthreshold(
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

    @leveling_settings.command(
        name="viewsettings", description="View your guild leveling settings."
    )
    @has_permissions(manage_guild=True)
    @bot_has_permissions(embed_links=True)
    async def leveling_settings_viewsettings(
        self, interaction: KeplerInteraction
    ) -> None:
        guild_id = interaction.guild.id

        guild_data = await self.db.get_guild_data(guild_id)

        desc = (
            f"Enabled: {bool(guild_data['enabled'])}\n"
            f"Minimum exp per message: {guild_data['min_exp']}\n"
            f"Maximum exp per message: {guild_data['max_exp']}\n"
            f"Message cooldown: {guild_data['rate']} per {guild_data['cooldown']} seconds.\n"
            f"Level threshold: base {guild_data['level_threshold']}, multiplier {guild_data['threshold_multiplier']}\n"
            "Levelup announcement channel: "
        )

        if guild_data["levelup_channel"]:
            if chan := interaction.guild.get_channel(guild_data["levelup_channel"]):
                desc += chan.mention
        else:
            desc += "None"

        embed = discord.Embed(
            title=f"Leveling settings for {interaction.guild}",
            description=desc,
            colour=self.bot.colour,
            timestamp=discord.utils.utcnow(),
        )
        embed.set_thumbnail(url=interaction.guild.icon)

        await interaction.response_or_followup(embed=embed)

    @app_commands.command(
        name="setexp",
        description="Add or remove experience from a member.",
    )
    @app_commands.guild_only()
    @has_permissions(manage_guild=True)
    @app_commands.describe(
        act="Add or remove experience from a member.",
        member="The target member.",
        exp="The amount of experience to add or remove.",
    )
    @app_commands.rename(act="action")
    async def setexp(
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
