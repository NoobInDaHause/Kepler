from __future__ import annotations

import re
from datetime import timedelta
from typing import TYPE_CHECKING, Union

from discord import app_commands
from discord.ext import commands

from utilities.exceptions import BadArgument

if TYPE_CHECKING:
    from keplerbot import KeplerInteraction

TIME_PATTERN = re.compile(
    r"""
    \s*
    (?P<value>\d+)
    \s*
    (?P<unit>
        years?|yrs?|y|
        months?|mons?|mo|
        weeks?|w|
        days?|d|
        hours?|hrs?|h|
        minutes?|mins?|m|
        seconds?|secs?|s
    )
    \s*
    """,
    re.IGNORECASE | re.VERBOSE,
)


class ParseBoolTransformer(app_commands.Transformer):
    async def transform(
        self, _interaction: KeplerInteraction, value: Union[str, int, bool]
    ) -> bool:
        if isinstance(value, bool):
            return value

        s = str(value).strip().lower()

        truthy = {"yes", "y", "1", "true", "t", "enable", "enabled", "on", "yeah"}
        falsy = {"no", "n", "0", "false", "f", "disable", "disabled", "off", "nah"}

        if s in truthy:
            return True
        if s in falsy:
            return False

        raise BadArgument(f"Cannot convert {value!r} to boolean.")


class UserTransformer(app_commands.Transformer):
    async def transform(self, interaction: KeplerInteraction, value: str):
        try:
            return await commands.UserConverter().convert(
                await commands.Context.from_interaction(interaction), value
            )
        except commands.BadArgument as e:
            raise BadArgument(str(e)) from e


class _TimeDeltaTransformer(app_commands.Transformer):
    async def transform(self, interaction: KeplerInteraction, value: str) -> timedelta:
        value = value.strip()

        total = timedelta()
        position = 0
        found = False

        for match in TIME_PATTERN.finditer(value):
            if value[position : match.start()].strip():
                raise BadArgument(
                    f"'{value[position:match.start()]!r}' is not a valid duration."
                )

            amount = int(match.group("value"))
            unit = match.group("unit").lower()

            if unit in {"y", "yr", "yrs", "year", "years"}:
                total += timedelta(days=amount * 365)

            elif unit in {"mo", "mon", "mons", "month", "months"}:
                total += timedelta(days=amount * 30)

            elif unit in {"w", "week", "weeks"}:
                total += timedelta(days=amount * 7)

            elif unit in {"d", "day", "days"}:
                total += timedelta(days=amount)

            elif unit in {"h", "hr", "hrs", "hour", "hours"}:
                total += timedelta(hours=amount)

            elif unit in {"m", "min", "mins", "minute", "minutes"}:
                total += timedelta(minutes=amount)

            elif unit in {"s", "sec", "secs", "second", "seconds"}:
                total += timedelta(seconds=amount)

            position = match.end()
            found = True

        if not found:
            raise BadArgument(f"'{value!r}' is not a valid duration.")

        if value[position:].strip():
            raise BadArgument(f"'{value[position:]!r}' is not a valid duration.")

        return total


# sourcery skip: assign-if-exp
if TYPE_CHECKING:
    TimeDeltaTransformer = timedelta
else:
    TimeDeltaTransformer = _TimeDeltaTransformer
