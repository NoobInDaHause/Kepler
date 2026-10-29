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
                enabled INTEGER NOT NULL DEFAULT 0,
                min_exp INTEGER NOT NULL DEFAULT 15,
                max_exp INTEGER NOT NULL DEFAULT 25,
                rate INTEGER NOT NULL DEFAULT 1,
                cooldown INTEGER NOT NULL DEFAULT 30,
                threshold_multiplier FLOAT NOT NULL DEFAULT 1.15,
                level_threshold INTEGER NOT NULL DEFAULT 100,
                levelup_channel INTEGER
            );
            """)

    async def get_guild_data(self, guild_id: int) -> Dict[str, Union[int, float, None]]:
        result = await self.execute(
            "SELECT * FROM guilds WHERE guild_id = ?",
            (guild_id,),
            select=True,
            one_all="one",
        )

        if not result:
            return {
                "enabled": 0,
                "min_exp": 15,
                "max_exp": 25,
                "rate": 1,
                "cooldown": 30,
                "threshold_multiplier": 1.15,
                "level_threshold": 100,
                "levelup_channel": None,
            }

        return {
            "enabled": result[1],
            "min_exp": result[2],
            "max_exp": result[3],
            "rate": result[4],
            "cooldown": result[5],
            "threshold_multiplier": result[6],
            "level_threshold": result[7],
            "levelup_channel": result[8],
        }

    async def get_member_data(self, guild_id: int, member_id: int) -> Dict[str, int]:
        result = await self.execute(
            "SELECT exp, level FROM members WHERE guild_id = ? AND member_id = ?",
            (guild_id, member_id),
            select=True,
            one_all="one",
        )

        if not result:
            return {"exp": 0, "level": 0}

        return {"exp": result[0], "level": result[1]}
