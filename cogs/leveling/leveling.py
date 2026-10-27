import contextlib
import math
import random
from typing import Dict

import discord
from discord import app_commands
from discord.ext import commands

from keplerbot import Kepler, KeplerInteraction
from utilities.checks import bot_has_permissions, cooldown, has_permissions

from .leveling_data_manager import LevelingDataBase


@app_commands.guild_only()
@has_permissions(manage_guild=True)
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

    async def cog_load(self) -> None:
        await self.db.initialize()

    async def announce_levelup(
        self, message: discord.Message, old_level: int, new_level: int
    ) -> None:

        levelup_channel_id = await self.db.execute(
            "SELECT levelup_channel FROM guilds WHERE guild_id = ?",
            (message.guild.id,),
            select=True,
            one_all="one",
        )

        channel = (
            message.guild.get_channel(levelup_channel_id[0])
            if levelup_channel_id[0] is not None
            else message.channel
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

        await self.db.initialize_guild_or_member(True, (guild_id,))

        enabled = await self.db.execute(
            "SELECT enabled FROM guilds WHERE guild_id = ?",
            (guild_id,),
            select=True,
            one_all="one",
        )

        if enabled[0] == 0:
            return

        await self.db.initialize_guild_or_member(False, (guild_id, member_id))

        guild_exp_data = await self.db.get_guild_exp_data(guild_id)

        if (
            not self.cooldowns.setdefault(
                guild_id,
                commands.CooldownMapping.from_cooldown(
                    guild_exp_data["rate"],
                    guild_exp_data["cooldown"],
                    commands.BucketType.member,
                ),
            )
            .get_bucket(message)
            .update_rate_limit()
        ):
            member_data = await self.db.get_member_data(guild_id, member_id)
            now_exp = member_data["exp"] + random.randint(
                guild_exp_data["min_exp"], guild_exp_data["max_exp"]
            )
            old_level = member_data["level"]
            now_level = old_level

            threshold = math.ceil(
                guild_exp_data["level_threshold"]
                * (guild_exp_data["threshold_multiplier"] ** member_data["level"])
            )

            while now_exp >= threshold:
                now_exp -= threshold
                now_level = now_level + 1
                threshold = math.ceil(
                    guild_exp_data["level_threshold"]
                    * (guild_exp_data["threshold_multiplier"] ** now_level)
                )

            await self.db.insert_or_update_member_level(
                guild_id, member_id, now_exp, now_level
            )

            if now_level > old_level:
                await self.announce_levelup(message, old_level, now_level)

    @app_commands.command(
        name="level", description="Check your or other member level and experience."
    )
    @app_commands.guild_only()
    @bot_has_permissions(embed_links=True)
    @cooldown(
        1, 10, key=lambda interaction: (interaction.guild_id, interaction.user.id)
    )
    async def level(
        self, interaction: KeplerInteraction, member: discord.Member = None
    ) -> None:
        member = member or interaction.user
        if member.bot:
            return await interaction.response_or_followup(
                "Bots can not have levels.", ephemeral=True
            )

        member_id = member.id
        guild_id = interaction.guild.id

        await self.db.initialize_guild_or_member(True, (guild_id,))

        enabled = await self.db.execute(
            "SELECT enabled FROM guilds WHERE guild_id = ?",
            (guild_id,),
            select=True,
            one_all="one",
        )

        if enabled[0] == 0:
            return await interaction.response_or_followup(
                "Leveling system is not enabled for this guild. Ask an admin to enable it."
            )

        await self.db.initialize_guild_or_member(False, (guild_id, member_id))

        member_data = await self.db.get_member_data(guild_id, member_id)
        guild_exp_data = await self.db.get_guild_exp_data(guild_id)

        threshold = math.ceil(
            guild_exp_data["level_threshold"]
            * (guild_exp_data["threshold_multiplier"] ** member_data["level"])
        )

        embed = discord.Embed(
            title=f"{member.name}'s Level",
            description=f"Level: {member_data['level']}\nExperience: {member_data['exp']}/{threshold}",
            color=member.colour,
        )

        await interaction.response_or_followup(embed=embed)

    leveling_settings = LevelingSettings()

    @leveling_settings.command(
        name="enable", description="Enable or disable leveling system for this guild."
    )
    async def levelingsettings_enable(self, interaction: KeplerInteraction) -> None:
        guild_id = interaction.guild.id

        await self.db.initialize_guild_or_member(True, (guild_id,))

        enabled = await self.db.execute(
            "SELECT enabled FROM guilds WHERE guild_id = ?",
            (guild_id,),
            select=True,
            one_all="one",
        )
        bool_conv = bool(enabled[0])

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
    async def levelingsettings_levelupchannel(
        self, interaction: KeplerInteraction, channel: discord.TextChannel = None
    ) -> None:
        guild_id = interaction.guild.id

        await self.db.initialize_guild_or_member(True, (guild_id,))

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
