import json
from typing import Dict, Union

from utilities.data_manager import DataManager


class MeritsDataBase(DataManager):
    def __init__(self, cog_name: str):
        super().__init__(cog_name)

    async def initialize(self) -> None:
        # merit_roles data is stored as a JSON string in the database,
        # so we need to convert it to a Python object when retrieving it and back to a JSON string when storing it.
        # it should store {str(merit_threshold): role_id}
        await self.executescript("""
            CREATE TABLE IF NOT EXISTS members (
                guild_id INTEGER NOT NULL,
                member_id INTEGER NOT NULL,
                merits INTEGER DEFAULT 0,
                PRIMARY KEY (guild_id, member_id)
            );

            CREATE TABLE IF NOT EXISTS guilds (
                guild_id INTEGER NOT NULL PRIMARY KEY,
                merit_roles TEXT DEFAULT '{}'
            );
            """)

    async def get_guild_data(
        self, guild_id: int
    ) -> Dict[str, Union[int, Dict[str, int], None]]:
        result = await self.execute(
            "SELECT * FROM guilds WHERE guild_id = ?",
            (guild_id,),
            select=True,
        )

        return (
            {
                "merit_roles": json.loads(result[2]),
            }
            if result
            else {
                "merit_roles": {},
            }
        )

    async def get_member_data(
        self, guild_id: int, member_id: int
    ) -> Dict[str, Union[int, None]]:
        result = await self.execute(
            "SELECT * FROM members WHERE guild_id = ? AND member_id = ?",
            (guild_id, member_id),
            select=True,
        )

        return (
            {
                "merits": result[2],
            }
            if result
            else {
                "merits": 0,
            }
        )
