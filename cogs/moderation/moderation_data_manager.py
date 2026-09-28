from typing import List, Literal, Optional

import discord

from utilities.data_manager import DataManager


class ModerationDataBase(DataManager):
    def __init__(self, cog_name: str):
        super().__init__(cog_name)

    # -------------------------------------------- tempbans -------------------------------------------------------
    async def initialize(self) -> None:
        await self.executescript("""
            CREATE TABLE IF NOT EXISTS tempbans (
                guild_id INTEGER NOT NULL,
                offender_id INTEGER NOT NULL,
                banned_until_timestamp INTEGER NOT NULL,
                moderator_id INTEGER,
                PRIMARY KEY (guild_id, offender_id)
            );

            CREATE TABLE IF NOT EXISTS warnings (
                guild_id INTEGER NOT NULL,
                warn_id INTEGER NOT NULL,
                offender_id INTEGER NOT NULL,
                moderator_id INTEGER,
                reason TEXT,
                PRIMARY KEY (guild_id, warn_id)
            );

            CREATE TABLE IF NOT EXISTS modlog_channel (
                guild_id INTEGER PRIMARY KEY NOT NULL,
                channel_id INTEGER
            );

            CREATE TABLE IF NOT EXISTS modlogs (
                guild_id INTEGER NOT NULL,
                case_id INTEGER NOT NULL,
                action TEXT NOT NULL,
                offender_id INTEGER NOT NULL,
                moderator_id INTEGER,
                reason TEXT,
                until INTEGER,
                PRIMARY KEY (guild_id, case_id)
            );
            """)

    async def insert_tempban(
        self,
        guild_id: int,
        offender_id: int,
        banned_until_timestamp: int,
        moderator_id: int,
    ) -> None:
        await self.execute(
            """
            INSERT INTO tempbans
                (guild_id, offender_id, banned_until_timestamp, moderator_id)
            VALUES (?, ?, ?, ?)
            """,
            (guild_id, offender_id, banned_until_timestamp, moderator_id),
        )

    async def get_tempban(self, guild_id: int, offender_id: int) -> Optional[tuple]:
        return await self.execute(
            """
            SELECT banned_until_timestamp, moderator_id
            FROM tempbans
            WHERE guild_id = ? AND offender_id = ?
            """,
            (guild_id, offender_id),
            select=True,
        )

    async def delete_tempban(self, guild_id: int, offender_id: int) -> None:
        await self.execute(
            "DELETE FROM tempbans WHERE guild_id = ? AND offender_id = ?",
            (guild_id, offender_id),
        )

    async def get_all_tempbans_from_guild(self, guild_id: int) -> List[tuple]:
        return await self.execute(
            """
            SELECT offender_id, banned_until_timestamp, moderator_id
            FROM tempbans
            WHERE guild_id = ?
            ORDER BY offender_id
            """,
            (guild_id,),
            select=True,
            one_all="all",
        )

    async def get_all_tempbans(self) -> List[tuple]:
        return await self.execute(
            """
            SELECT guild_id, offender_id, banned_until_timestamp, moderator_id
            FROM tempbans
            ORDER BY guild_id, offender_id
            """,
            select=True,
            one_all="all",
        )

    # -------------------------------------------- warnings -------------------------------------

    async def insert_warning(
        self,
        guild_id: int,
        offender_id: int,
        moderator_id: int,
        reason: str = None,
    ) -> None:
        await self.execute(
            """
            INSERT INTO warnings
                (guild_id, warn_id, offender_id, moderator_id, reason)
            VALUES (
                ?,
                (SELECT COALESCE(MAX(warn_id), 0) + 1 FROM warnings WHERE guild_id = ?),
                ?,
                ?,
                ?
            )
            """,
            (guild_id, guild_id, offender_id, moderator_id, reason),
        )

    async def get_warning(self, guild_id: int, warn_id: int) -> List[tuple]:
        return await self.execute(
            "SELECT * FROM warnings WHERE guild_id = ? AND warn_id = ?",
            (guild_id, warn_id),
            select=True,
            one_all="all",
        )

    async def delete_warning(self, guild_id: int, warn_id: int) -> None:
        await self.execute(
            "DELETE FROM warnings WHERE guild_id = ? AND warn_id = ?",
            (guild_id, warn_id),
        )

    # reserved
    async def get_all_warnings_from_guild(self, guild_id: int) -> List[tuple]:
        return await self.execute(
            "SELECT * FROM warnings WHERE guild_id = ?",
            (guild_id,),
            select=True,
            one_all="all",
        )

    async def get_all_warnings_from_offender(
        self, guild_id: int, offender_id: int
    ) -> List[tuple]:
        return await self.execute(
            "SELECT * FROM warnings WHERE guild_id = ? AND offender_id = ?",
            (guild_id, offender_id),
            select=True,
            one_all="all",
        )

    # reserved for the future
    async def get_all_warnings(self) -> List[tuple]:
        return await self.execute(
            """
            SELECT * FROM warnings
            ORDER BY guild_id, warn_id
            """,
            select=True,
            one_all="all",
        )

    # ---------------------------------------- modlog channel -----------------------------------
    async def modlog_channel(
        self,
        action: Literal["insert", "get", "delete", "update"],
        guild_id: int = None,
        channel_id: int = None,
    ) -> Optional[List[tuple]]:
        if action == "insert":
            if all([guild_id, channel_id]):
                return await self.execute(
                    """
                    INSERT INTO modlog_channel (guild_id, channel_id) VALUES (?, ?)
                    """,
                    (guild_id, channel_id),
                )
            raise TypeError(
                "Argument 'guild_id' and 'channel_id' are required for inserting modlog."
            )
        elif action in {"get", "delete"}:
            if guild_id:
                cmd = "SELECT channel_id FROM" if action == "get" else "DELETE FROM"
                return await self.execute(
                    f"""
                    {cmd} modlog_channel WHERE guild_id = ?
                    """,
                    (guild_id,),
                    select=(action != "delete"),
                    one_all="all",
                )
            raise TypeError(
                "Argument 'guild_id' is required for getting or deleting modlog."
            )
        elif action == "update":
            if all([guild_id, channel_id]):
                return await self.execute(
                    """
                    UPDATE modlog_channel SET channel_id = ? WHERE guild_id = ?
                    """,
                    (channel_id, guild_id),
                )
            raise TypeError(
                "Argument 'guild_id' and 'channel_id' are required for inserting modlog."
            )
        else:
            ACTIONS = ["insert", "get", "delete", "update"]
            raise TypeError(
                f"Argument 'action' must only be {discord.utils._human_join(ACTIONS)}."
            )

    # ------------------------------------------ modlogs -------------------------------------------
    async def insert_modlog(
        self,
        guild_id: int,
        action: str,
        offender_id: int,
        moderator_id: int,
        reason: str = None,
        until_timestamp: int = None,
    ) -> int:
        await self.execute(
            """
            INSERT INTO modlogs
                (guild_id, case_id, action, offender_id, moderator_id, reason, until)
            VALUES (
                ?,
                (SELECT COALESCE(MAX(case_id), 0) + 1 FROM modlogs WHERE guild_id = ?),
                ?,
                ?,
                ?,
                ?,
                ?
            )
            """,
            (
                guild_id,
                guild_id,
                action,
                offender_id,
                moderator_id,
                reason,
                until_timestamp,
            ),
        )
        return await self.get_current_case_id(guild_id)

    async def get_current_case_id(self, guild_id: int) -> int:
        l = await self.execute(
            """
            SELECT MAX(case_id) FROM modlogs WHERE guild_id = ?
            """,
            (guild_id,),
            select=True,
            one_all="all",
        )
        return l[0][0]

    async def get_all_modlogs_from_guild(self, guild_id: int) -> List[tuple]:
        return await self.execute(
            "SELECT * FROM modlogs WHERE guild_id = ?",
            (guild_id,),
            select=True,
            one_all="all",
        )
