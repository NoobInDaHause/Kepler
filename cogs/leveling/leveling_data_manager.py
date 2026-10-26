from typing import Dict, Union

from utilities.data_manager import DataManager


class LevelingDataBase(DataManager):
    def __init__(self, cog_name: str):
        super().__init__(cog_name)

    async def initialize(self) -> None:
        await self.executescript("""
            CREATE TABLE IF NOT EXISTS members (
                guild_id INTEGER NOT NULL,
                member_id INTEGER NOT NULL,
                exp INTEGER NOT NULL DEFAULT 0,
                level INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (guild_id, member_id)
            );

            CREATE TABLE IF NOT EXISTS guilds (
                guild_id INTEGER NOT NULL PRIMARY KEY,
                enabled INTEGER NOT NULL DEFAULT 1,
                min_exp INTEGER NOT NULL DEFAULT 15,
                max_exp INTEGER NOT NULL DEFAULT 25,
                rate INTEGER NOT NULL DEFAULT 1,
                cooldown INTEGER NOT NULL DEFAULT 30,
                threshold_multiplier FLOAT NOT NULL DEFAULT 1.15,
                level_threshold INTEGER NOT NULL DEFAULT 100,
                levelup_channel INTEGER
            );
            """)

    async def initialize_guild_or_member(self, is_guild: bool, _id: tuple) -> None:
        if is_guild:
            if not await self.execute(
                "SELECT * FROM guilds WHERE guild_id = ?",
                (_id[0],),
                select=True,
                one_all="all",
            ):
                await self.execute(
                    "INSERT INTO guilds (guild_id) VALUES (?)",
                    (_id[0],),
                )
        elif not await self.execute(
            "SELECT * FROM members WHERE guild_id = ? AND member_id = ?",
            (_id[0], _id[1]),
            select=True,
            one_all="all",
        ):
            await self.execute(
                "INSERT INTO members (guild_id, member_id) VALUES (?, ?)",
                (_id[0], _id[1]),
            )

    async def get_guild_exp_data(self, guild_id: int) -> Dict[str, Union[int, float]]:
        result = await self.execute(
            "SELECT min_exp, max_exp, rate, cooldown, threshold_multiplier, level_threshold FROM guilds WHERE guild_id = ?",
            (guild_id,),
            select=True,
            one_all="one",
        )

        return {
            "min_exp": result[0],
            "max_exp": result[1],
            "rate": result[2],
            "cooldown": result[3],
            "threshold_multiplier": result[4],
            "level_threshold": result[5],
        }

    async def get_member_data(self, guild_id: int, member_id: int) -> Dict[str, int]:
        result = await self.execute(
            "SELECT exp, level FROM members WHERE guild_id = ? AND member_id = ?",
            (guild_id, member_id),
            select=True,
            one_all="one",
        )

        return {"exp": result[0], "level": result[1]}

    async def insert_or_update_member_level(
        self, guild_id: int, member_id: int, exp: int, level: int
    ) -> None:
        await self.execute(
            """
            INSERT INTO members (guild_id, member_id, exp, level)
            VALUES (?, ?, ?, ?)
            ON CONFLICT (guild_id, member_id)
            DO UPDATE SET exp = members.exp + excluded.exp, level = excluded.level
            """,
            (guild_id, member_id, exp, level),
        )
