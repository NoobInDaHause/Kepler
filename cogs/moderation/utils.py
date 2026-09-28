from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Literal, Optional

import discord

if TYPE_CHECKING:
    from keplerbot import KeplerInteraction


def get_auditlog_reason(moderator: discord.Member, reason: str = None) -> str:
    audit_reason = f"Authorized by {moderator} ({moderator.id})."
    if reason:
        audit_reason += f" Reason: {reason}"
    return f"{audit_reason[:509]}..." if len(audit_reason) > 512 else audit_reason


def get_dm_embed(
    moderator: discord.Member,
    guild: discord.Guild,
    reason: str,
    action: Literal[
        "ban",
        "unban",
        "tempban",
        "kick",
        "timeout",
        "untimeout",
        "warn",
        "unwarn",
    ],
    until: Optional[datetime] = None,
) -> discord.Embed:
    action_descriptions = {
        "ban": ("banned", discord.Colour.red()),
        "unban": ("unbanned", discord.Colour.green()),
        "tempban": ("temporarily banned", discord.Colour.dark_orange()),
        "kick": ("kicked", discord.Colour.magenta()),
        "timeout": ("timed out", discord.Colour.light_grey()),
        "untimeout": ("untimed out", discord.Colour.blurple()),
        "warn": ("warned", discord.Colour.yellow()),
        "unwarn": ("unwarned", discord.Colour.default()),
    }

    act = action_descriptions[action]
    embed = discord.Embed(
        title=f"You have been **{act[0]}** from `{guild}`.",
        description=reason,
        colour=act[1],
        timestamp=datetime.now(timezone.utc),
    )

    embed.set_thumbnail(url=guild.icon)

    if until is not None:
        timestamp = int(until.timestamp())
        embed.add_field(
            name="Until:",
            value=f"<t:{timestamp}:F> (<t:{timestamp}:R>)",
            inline=False,
        )

    embed.add_field(
        name="Moderator:",
        value=f"{moderator} ({moderator.id})",
        inline=False,
    )

    return embed


def get_modlog_embed(
    action: str,
    case_id: int,
    offender: discord.User,
    moderator: discord.Member,
    reason: str = None,
    until_timestamp: int = None,
) -> discord.Embed:
    action_dict = {
        "ban": ("🔨", discord.Colour.red()),
        "unban": ("📜", discord.Colour.green()),
        "tempban": ("🔨⌛", discord.Colour.dark_orange()),
        "kick": ("👢", discord.Colour.magenta()),
        "timeout": ("🔇", discord.Colour.light_grey()),
        "untimeout": ("🔊", discord.Colour.blurple()),
        "warn": ("⚠️", discord.Colour.yellow()),
        "unwarn": ("🔃", discord.Colour.default()),
    }

    act = action_dict[action]
    embed = discord.Embed(
        title=f"{act[0]} | {action.title()}",
        description=f"```javascript\nCase #{case_id}\n```",
        colour=act[1],
        timestamp=datetime.now(timezone.utc),
    )
    embed.add_field(name="Offender:", value=f"{offender} ({offender.id})", inline=False)
    embed.add_field(
        name="Moderator:", value=f"{moderator} ({moderator.id})", inline=False
    )
    if until_timestamp:
        embed.add_field(
            name="Until:",
            value=f"<t:{until_timestamp}:F> (<t:{until_timestamp}:R>)",
            inline=False,
        )
    if reason:
        embed.add_field(name="Reason:", value=reason, inline=False)
    return embed


async def hierarchy_check(
    interaction: KeplerInteraction,
    offender: discord.Member,
    action: Literal["ban", "kick", "timeout", "untimeout", "warn", "unwarn"],
) -> Optional[str]:
    if (
        offender.top_role >= interaction.user.top_role
    ) and not await interaction.client.is_owner(interaction.user):
        return f"You can not {action} this member due to role hierarchy."
    if offender.top_role >= interaction.guild.me.top_role:
        return f"I can not {action} this member due to role hierarchy."
