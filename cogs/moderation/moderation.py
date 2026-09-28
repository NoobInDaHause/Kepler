import asyncio
import contextlib
import logging
import time
from datetime import datetime, timezone
from functools import partial
from typing import Any, Awaitable, Callable, Dict, Literal, Optional, Tuple, Union

import discord
from discord import app_commands
from discord.ext import commands

from keplerbot import Kepler, KeplerInteraction
from utilities.checks import bot_has_permissions, has_permissions
from utilities.formatting import pagify
from utilities.transformers import TimeDeltaTransformer
from utilities.views import PaginatorView

from .moderation_data_manager import ModerationDataBase
from .objects import TempbanObject
from .utils import get_auditlog_reason, get_dm_embed, get_modlog_embed, hierarchy_check


@app_commands.guild_only()
class Moderation(commands.GroupCog, group_name="moderation"):
    """Moderation commands and moderation event handlers."""

    def __init__(self, bot: Kepler):
        super().__init__()
        self.bot = bot
        self.db = ModerationDataBase(self.__class__.__name__)
        self.log = logging.getLogger(f"Kepler.{self.__class__.__name__}")
        self.initialized = asyncio.Event()
        self.tempban_tasks: Dict[Tuple[int, int], asyncio.Task] = {}
        self._recent_mod_actions: Dict[Tuple[int, int, str], float] = {}

    def _mark_recent_mod_action(self, guild_id: int, user_id: int, action: str) -> None:
        self._recent_mod_actions[(guild_id, user_id, action)] = time.monotonic()

    def _is_recent_mod_action(
        self, guild_id: int, user_id: int, action: str, ttl: float = 5.0
    ) -> bool:
        key = (guild_id, user_id, action)
        now = time.monotonic()
        last_seen = self._recent_mod_actions.get(key)

        if last_seen is None:
            return False
        if now - last_seen > ttl:
            self._recent_mod_actions.pop(key, None)
            return False
        return True

    async def _notify_member(
        self,
        interaction: KeplerInteraction,
        offender: Union[discord.Member, discord.User],
        action: Literal[
            "ban", "unban", "tempban", "kick", "timeout", "untimeout", "warn", "unwarn"
        ],
        reason: str = None,
        until: Optional[datetime] = None,
    ) -> None:
        with contextlib.suppress(
            discord.errors.Forbidden, discord.errors.HTTPException
        ):
            await offender.send(
                embed=get_dm_embed(
                    interaction.user,
                    interaction.guild,
                    reason or "No reason was given.",
                    action,
                    until,
                )
            )

    async def _handle_modlog_error(self, interaction: KeplerInteraction) -> None:
        with contextlib.suppress(discord.errors.Forbidden, discord.errors.NotFound):
            await interaction.channel.send(
                content=(
                    "Could not send log to modlog channel, it is either deleted or "
                    "missing permission."
                )
            )

    async def _log_mod_action(
        self,
        interaction: KeplerInteraction,
        action: str,
        offender: discord.User,
        reason: str = None,
        until_timestamp: int = None,
    ) -> None:
        try:
            await self.send_to_modlog(
                interaction.guild.id,
                action,
                offender,
                interaction.user,
                reason,
                until_timestamp,
            )
        except (discord.errors.Forbidden, discord.errors.NotFound):
            await self._handle_modlog_error(interaction)

    async def send_to_modlog(
        self,
        guild_id: int,
        action: str,
        offender: discord.User,
        moderator: Union[discord.Member, discord.User],
        reason: str = None,
        until_timestamp: int = None,
    ) -> None:
        if not (modlog := await self.db.modlog_channel("get", guild_id)):
            return

        channel = await self.bot.get_or_fetch_channel(guild_id, modlog[0][0])
        if channel is None:
            return

        case_id = await self.db.insert_modlog(
            guild_id,
            action,
            offender.id,
            moderator.id,
            reason,
            until_timestamp,
        )
        await channel.send(
            embed=get_modlog_embed(
                action,
                case_id,
                offender,
                moderator,
                reason,
                until_timestamp,
            )
        )

    def suicide(self, action: str, offender_id: int, user_id: int) -> Optional[str]:
        if offender_id == user_id:
            return f"You can not {action} yourself idiot."
        if offender_id == self.bot.user.id:
            return f"I can not {action} myself idiot."

    async def _ensure_not_banned(
        self,
        interaction: KeplerInteraction,
        offender: Union[discord.Member, discord.User],
    ) -> Optional[str]:
        with contextlib.suppress(discord.errors.NotFound):
            await interaction.guild.fetch_ban(offender)
            return f"User **{offender}** (`{offender.id}`) is already banned from this guild."

    async def _run_member_action(
        self,
        interaction: KeplerInteraction,
        offender: Union[discord.Member, discord.User],
        action: Literal["ban", "kick", "timeout", "untimeout", "unban"],
        reason: str = None,
        *,
        action_fn: Callable[[], Awaitable[Any]],
        success_message: str,
        until: Optional[datetime] = None,
    ) -> None:
        if s := self.suicide(action, offender.id, interaction.user.id):
            return await interaction.response_or_followup(content=s)

        if isinstance(offender, discord.Member) and (
            higher := await hierarchy_check(interaction, offender, action)
        ):
            return await interaction.response_or_followup(content=higher)

        await self._notify_member(interaction, offender, action, reason, until)
        self._mark_recent_mod_action(interaction.guild.id, offender.id, action)
        await action_fn()
        await self._log_mod_action(interaction, action, offender, reason)
        await interaction.response_or_followup(content=success_message)

    @commands.Cog.listener("on_member_ban")
    async def log_bans(self, guild: discord.Guild, user: discord.User):
        if self._is_recent_mod_action(guild.id, user.id, "ban"):
            return

        async for entry in guild.audit_logs(limit=5, action=discord.AuditLogAction.ban):
            if entry.target.id == user.id:
                with contextlib.suppress(
                    discord.errors.Forbidden, discord.errors.NotFound
                ):
                    await self.send_to_modlog(
                        guild.id, "ban", user, entry.user, entry.reason
                    )
                break

    @commands.Cog.listener("on_member_unban")
    async def log_unban(self, guild: discord.Guild, user: discord.User):
        if self._is_recent_mod_action(guild.id, user.id, "unban"):
            return

        async for entry in guild.audit_logs(
            limit=5, action=discord.AuditLogAction.unban
        ):
            if entry.target.id == user.id:
                if task := self.tempban_tasks.get((guild.id, user.id)):
                    task.cancel()

                with contextlib.suppress(
                    discord.errors.Forbidden, discord.errors.NotFound
                ):
                    await self.send_to_modlog(
                        guild.id, "unban", user, entry.user, entry.reason
                    )
                break

    @commands.Cog.listener("on_member_update")
    async def log_timeouts(self, before: discord.Member, after: discord.Member):
        if self._is_recent_mod_action(
            before.guild.id, before.id, "timeout"
        ) or self._is_recent_mod_action(before.guild.id, before.id, "untimeout"):
            return

        was_timed_out = before.is_timed_out()
        is_timed_out = after.is_timed_out()

        if not was_timed_out and is_timed_out:
            action = "timeout"
        elif was_timed_out and not is_timed_out:
            action = "untimeout"
        else:
            return

        async for entry in after.guild.audit_logs(
            limit=5,
            action=discord.AuditLogAction.member_update,
        ):
            if entry.target.id == after.id:
                with contextlib.suppress(
                    discord.errors.Forbidden, discord.errors.NotFound
                ):
                    await self.send_to_modlog(
                        after.guild.id,
                        action,
                        after,
                        entry.user,
                        entry.reason,
                    )
                break

    @commands.Cog.listener("on_member_remove")
    async def log_kicks(self, member: discord.Member):
        if self._is_recent_mod_action(member.guild.id, member.id, "kick"):
            return

        async for entry in member.guild.audit_logs(
            limit=5, action=discord.AuditLogAction.kick
        ):
            if entry.target.id == member.id:
                with contextlib.suppress(
                    discord.errors.Forbidden, discord.errors.NotFound
                ):
                    await self.send_to_modlog(
                        member.guild.id,
                        "kick",
                        member,
                        entry.user,
                        entry.reason,
                    )
                break

    async def init_tempbans(self) -> None:
        await self.bot.wait_until_ready()

        for (
            guild_id,
            offender_id,
            banned_until,
            moderator_id,
        ) in await self.db.get_all_tempbans():
            try:
                guild = await self.bot.get_or_fetch_guild(guild_id)
                offender = await self.bot.get_or_fetch_user(offender_id)
                moderator = await self.bot.get_or_fetch_user(moderator_id)
            except discord.errors.NotFound:
                continue

            self.tempban_tasks[(guild.id, offender.id)] = self.bot.loop.create_task(
                self.tempban_loop(
                    TempbanObject(
                        offender=offender,
                        moderator=moderator,
                        guild=guild,
                        timestamp=banned_until,
                    )
                )
            )

        self.initialized.set()

    async def cog_load(self) -> None:
        await self.db.initialize()
        self.bot.loop.create_task(self.init_tempbans())

    async def cog_unload(self):
        for task in self.tempban_tasks.values():
            task.cancel()
        self.initialized.clear()

    async def tempban_loop(self, obj: TempbanObject):
        await self.initialized.wait()

        try:
            while True:
                seconds_left = (obj.until - datetime.now(timezone.utc)).total_seconds()
                if seconds_left <= 0:
                    try:
                        self._mark_recent_mod_action(
                            obj.guild.id, obj.offender.id, "unban"
                        )
                        await obj.guild.unban(
                            obj.offender,
                            reason=(
                                f"Tempban issued by {obj.moderator} "
                                f"({obj.moderator.id}) has expired."
                            ),
                        )

                        with contextlib.suppress(
                            discord.errors.Forbidden, discord.errors.NotFound
                        ):
                            await self.send_to_modlog(
                                obj.guild.id,
                                "unban",
                                obj.offender,
                                obj.moderator,
                                "Temporary ban has expired.",
                            )
                    except discord.errors.Forbidden:
                        self.log.warning(
                            "Could not unban %s from %s due to missing permissions.",
                            obj.offender,
                            obj.guild,
                        )
                        return
                    except discord.errors.NotFound:
                        pass
                    except discord.errors.HTTPException as exc:
                        self.log.warning(
                            "Could not unban %s from %s: %s. Retrying in 5 minutes.",
                            obj.offender,
                            obj.guild,
                            exc,
                        )
                        await asyncio.sleep(300)
                        continue

                    await self.db.delete_tempban(obj.guild.id, obj.offender.id)
                    return

                await asyncio.sleep(min(seconds_left, 300))
        except asyncio.CancelledError:
            raise
        finally:
            self.tempban_tasks.pop((obj.guild.id, obj.offender.id), None)

    def _timeout_validation_message(
        self,
        act: Literal["timeout", "untimeout"],
        offender: discord.Member,
        duration: Optional[TimeDeltaTransformer],
    ) -> Optional[str]:
        if act == "untimeout":
            if not offender.is_timed_out():
                return f"Member {offender} (`{offender.id}`) is not timed out."
            return None

        if offender.is_timed_out():
            return f"Member {offender} (`{offender.id}`) is already timed out."
        if duration is None:
            return "You must provide a duration if you want to timeout a member."

        seconds = int(duration.total_seconds())
        if seconds < 60:
            return "Duration must not be less than 1 minute."
        if seconds > 604800 * 4:
            return "Duration must not be longer than 28 days."
        return None

    @app_commands.command(name="kick", description="Kick a member from this guild.")
    @bot_has_permissions(kick_members=True)
    @has_permissions(kick_members=True)
    @app_commands.describe(
        offender="The offending member that you want to kick.",
        reason="The optional reason for the kick.",
    )
    async def moderation_kick(
        self,
        interaction: KeplerInteraction,
        offender: discord.Member,
        reason: str = None,
    ) -> None:
        await self._run_member_action(
            interaction,
            offender,
            "kick",
            reason,
            action_fn=partial(
                interaction.guild.kick,
                offender,
                reason=get_auditlog_reason(interaction.user, reason),
            ),
            success_message=f"Member **{offender}** (`{offender.id}`) has been kicked from the guild.",
        )

    @app_commands.command(name="ban", description="Ban a member from this guild.")
    @bot_has_permissions(ban_members=True)
    @has_permissions(ban_members=True)
    @app_commands.describe(
        offender="The offending member or user that you want to ban.",
        reason="The optional reason for the ban.",
    )
    async def moderation_ban(
        self,
        interaction: KeplerInteraction,
        offender: Union[discord.Member, discord.User],
        reason: str = None,
    ) -> None:
        if s := self.suicide("ban", offender.id, interaction.user.id):
            return await interaction.response_or_followup(content=s)

        if isinstance(offender, discord.Member) and (
            higher := await hierarchy_check(interaction, offender, "ban")
        ):
            return await interaction.response_or_followup(content=higher)

        if already_banned := await self._ensure_not_banned(interaction, offender):
            return await interaction.response_or_followup(content=already_banned)

        await self._notify_member(interaction, offender, "ban", reason)

        self._mark_recent_mod_action(interaction.guild.id, offender.id, "ban")
        await interaction.guild.ban(
            offender, reason=get_auditlog_reason(interaction.user, reason)
        )

        await self._log_mod_action(interaction, "ban", offender, reason)

        kind = "Member" if isinstance(offender, discord.Member) else "User"
        await interaction.response_or_followup(
            content=f"{kind} **{offender}** (`{offender.id}`) has been banned from the guild."
        )

    @app_commands.command(name="unban", description="Unban a user from this guild.")
    @bot_has_permissions(ban_members=True)
    @has_permissions(ban_members=True)
    @app_commands.describe(
        offender="The user that you want to unban.",
        reason="The optional reason for the unban.",
    )
    @app_commands.rename(offender="offender_id")
    async def moderation_unban(
        self,
        interaction: KeplerInteraction,
        offender: discord.User,
        reason: str = None,
    ) -> None:
        if s := self.suicide("unban", offender.id, interaction.user.id):
            return await interaction.response_or_followup(content=s)

        try:
            await interaction.guild.fetch_ban(offender)
        except discord.errors.NotFound:
            return await interaction.response_or_followup(
                content=f"User **{offender}** (`{offender.id}`) is not banned from this guild."
            )

        await self._run_member_action(
            interaction,
            offender,
            "unban",
            reason,
            action_fn=partial(
                interaction.guild.unban,
                offender,
                reason=get_auditlog_reason(interaction.user, reason),
            ),
            success_message=f"User **{offender}** (`{offender.id}`) has been unbanned from the guild.",
        )

        if task := self.tempban_tasks.get((interaction.guild.id, offender.id)):
            task.cancel()
        await self.db.delete_tempban(interaction.guild.id, offender.id)

    @app_commands.command(
        name="timeout",
        description="Timeout or untimeout a naughty member from this guild.",
    )
    @bot_has_permissions(moderate_members=True)
    @has_permissions(moderate_members=True)
    @app_commands.describe(
        act="Timeout or untimeout.",
        offender="The offending member that you want to timeout/untimeout.",
        duration="The duration of the timeout. Example: `1h25m30s` -> 1 hour, 25 minutes and 30 seconds.",
        reason="The optional reason for the timeout/untimeout.",
    )
    @app_commands.rename(act="action")
    async def moderation_timeout(
        self,
        interaction: KeplerInteraction,
        act: Literal["timeout", "untimeout"],
        offender: discord.Member,
        duration: TimeDeltaTransformer = None,
        reason: str = None,
    ) -> None:
        if s := self.suicide(act, offender.id, interaction.user.id):
            return await interaction.response_or_followup(content=s)

        if higher := await hierarchy_check(interaction, offender, act):
            return await interaction.response_or_followup(content=higher)

        if message := self._timeout_validation_message(act, offender, duration):
            return await interaction.response_or_followup(content=message)

        until = datetime.now(timezone.utc) + duration if act == "timeout" else None

        await self._run_member_action(
            interaction,
            offender,
            act,
            reason,
            action_fn=partial(
                offender.timeout,
                until,
                reason=get_auditlog_reason(interaction.user, reason),
            ),
            success_message=(
                (
                    f"Member {offender} (`{offender.id}`) has been timed out until "
                    f"<t:{int(until.timestamp())}:F> (<t:{int(until.timestamp())}:R>)"
                )
                if act == "timeout"
                else f"Member {offender} (`{offender.id}`) has been untimed out."
            ),
            until=until,
        )

    @app_commands.command(name="tempban", description="Temporarily bans an offender.")
    @bot_has_permissions(ban_members=True)
    @has_permissions(ban_members=True)
    @app_commands.describe(
        offender="The offending member or user.",
        duration="The duration of the tempban. (minimum 10s)",
        reason="The optional reason for the tempban.",
    )
    async def moderation_tempban(
        self,
        interaction: KeplerInteraction,
        offender: Union[discord.Member, discord.User],
        duration: TimeDeltaTransformer,
        reason: str = None,
    ) -> None:
        if s := self.suicide("tempban", offender.id, interaction.user.id):
            return await interaction.response_or_followup(content=s)

        if isinstance(offender, discord.Member) and (
            higher := await hierarchy_check(interaction, offender, "ban")
        ):
            return await interaction.response_or_followup(content=higher)

        kind = "User" if isinstance(offender, discord.User) else "Member"

        if await self._ensure_not_banned(interaction, offender):
            return await interaction.response_or_followup(
                content=f"{kind} **{offender}** (`{offender.id}`) is already banned from this guild."
            )

        if int(duration.total_seconds()) < 10:
            return await interaction.response_or_followup(
                content="Duration must not be less than 10 seconds."
            )

        until = datetime.now(timezone.utc) + duration
        await self._notify_member(interaction, offender, "tempban", reason, until)

        self._mark_recent_mod_action(interaction.guild.id, offender.id, "tempban")
        await interaction.guild.ban(
            offender, reason=get_auditlog_reason(interaction.user, reason)
        )

        timestamp = int(until.timestamp())
        await self.db.insert_tempban(
            interaction.guild.id,
            offender.id,
            timestamp,
            interaction.user.id,
        )
        self.tempban_tasks[(interaction.guild.id, offender.id)] = (
            self.bot.loop.create_task(
                self.tempban_loop(
                    TempbanObject(
                        offender=offender,
                        moderator=interaction.user,
                        guild=interaction.guild,
                        timestamp=timestamp,
                    )
                )
            )
        )
        await self._log_mod_action(
            interaction,
            "tempban",
            offender,
            reason,
            timestamp,
        )

        await interaction.response_or_followup(
            content=(
                f"{kind} **{offender}** (`{offender.id}`) has been temporarily banned from the guild till "
                f"<t:{int(until.timestamp())}:F> (<t:{int(until.timestamp())}:R>)"
            )
        )

    @app_commands.command(name="warning", description="Warn a member.")
    @has_permissions(manage_messages=True)
    @app_commands.describe(
        action="The action that you want to perform.",
        offender="The offending member.",
        reason="The optional reason.",
    )
    async def moderation_warning(
        self,
        interaction: KeplerInteraction,
        action: Literal["add", "remove", "list"],
        offender: discord.Member,
        reason: str = None,
    ) -> None:
        await interaction.response.defer(thinking=True)

        act = "warn" if action == "add" else "unwarn"
        if action != "list":
            if s := self.suicide(act, offender.id, interaction.user.id):
                return await interaction.response_or_followup(content=s)
            if higher := await hierarchy_check(interaction, offender, act):
                return await interaction.response_or_followup(content=higher)

        match action:
            case "add":
                await self.db.insert_warning(
                    interaction.guild.id,
                    offender.id,
                    interaction.user.id,
                    reason,
                )
            case "remove":
                warnings = await self.db.get_all_warnings_from_offender(
                    interaction.guild.id,
                    offender.id,
                )
                if not warnings:
                    return await interaction.response_or_followup(
                        content="This member has no warnings."
                    )
                await self.db.delete_warning(
                    interaction.guild.id, max(item[1] for item in warnings)
                )
            case "list":
                warnings = await self.db.get_all_warnings_from_offender(
                    interaction.guild.id,
                    offender.id,
                )
                if not warnings:
                    return await interaction.response_or_followup(
                        content="This member has no warnings."
                    )

                pages = pagify(
                    "".join(
                        f"#{warn_id}\nModerator: <@{moderator_id}>\nReason: {reason_text}\n\n"
                        for _, warn_id, _, moderator_id, reason_text in warnings
                    ),
                    "\n\n",
                )
                embeds = []
                for index, page in enumerate(pages, 1):
                    embed = discord.Embed(
                        title=f"Warnings for **{offender}** (`{offender.id}`)",
                        description=page,
                        colour=offender.colour,
                    )
                    embed.set_footer(text=f"Page ({index}/{len(pages)})")
                    embeds.append(embed)
                return await PaginatorView(interaction, embeds).start()

        await self._notify_member(interaction, offender, act, reason)

        await self._log_mod_action(interaction, act, offender, reason)

        await interaction.response_or_followup(
            content=f"Member **{offender}** (`{offender.id}`) has been {act}ed."
        )

    @app_commands.command(
        name="modlog",
        description="Set the logging channel for mod actions.",
    )
    @has_permissions(manage_channels=True)
    @app_commands.describe(
        action="Action to perform.",
        channel="The channel that you want to set.",
    )
    async def moderation_modlog(
        self,
        interaction: KeplerInteraction,
        action: Literal["set", "remove", "view"],
        channel: discord.TextChannel = None,
    ) -> None:
        guild_id = interaction.guild.id
        existing = await self.db.modlog_channel("get", guild_id)

        if action == "set":
            if channel is None:
                return await interaction.response_or_followup(
                    content="Channel is required to set modlog."
                )
            if not channel.permissions_for(interaction.guild.me).send_messages:
                return await interaction.response_or_followup(
                    content=f"I cannot send messages to {channel.mention}. Please check my permissions."
                )

            await self.db.modlog_channel(
                "update" if existing else "insert",
                guild_id,
                channel.id,
            )
            return await interaction.response_or_followup(
                content=f"{channel.mention} has been set as the modlog channel."
            )

        if action == "remove":
            if not existing:
                return await interaction.response_or_followup(
                    content="There is no modlog channel currently set to remove."
                )
            await self.db.modlog_channel("delete", guild_id)
            return await interaction.response_or_followup(
                content="The modlog channel has been cleared."
            )

        if existing:
            return await interaction.response_or_followup(
                content=f"<#{existing[0][0]}> is the set modlog channel."
            )
        return await interaction.response_or_followup(
            content="No modlog channel has been set."
        )
