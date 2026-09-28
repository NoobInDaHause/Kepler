from dataclasses import dataclass
from datetime import datetime, timezone

import discord


@dataclass(slots=True)
class TempbanObject:
    offender: discord.User
    moderator: discord.User
    guild: discord.Guild
    timestamp: int

    @property
    def until(self) -> datetime:
        return datetime.fromtimestamp(
            self.timestamp,
            tz=timezone.utc,
        )
