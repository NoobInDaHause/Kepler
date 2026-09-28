from pathlib import Path
from typing import List, Literal, Optional, Tuple, Union

import aiosqlite
import discord

from utilities.exceptions import DataManagerException


class DataManager:
    """Manages database operations for cogs.

    This class handles SQLite database connections and executes SQL commands for storing and retrieving cog-specific data.
    """

    def __init__(self, cog_name: str) -> None:
        """Initialize the DataManager instance.

        Parameters
        ----------
        cog_name : str
            The name of the cog for which the database is created.
        """
        self.path = Path(__file__).parents[1] / "cogs_data" / f"{cog_name}.db"

    # for now its only for creating multiple tables
    async def executescript(
        self,
        sql_command: str,
    ) -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.executescript(sql_command)
            await db.commit()

    async def execute(
        self,
        sql_command: str,
        args: tuple = None,
        select: bool = False,
        one_all: Literal["one", "all"] = "one",
    ) -> Optional[List[Tuple[Union[str, int]]]]:
        """Execute a SQL command.

        Parameters
        ----------
        sql_command : str
            The SQL command to execute.
        args : tuple, optional
            Arguments to pass to the SQL command. Defaults to None.
        select : bool, optional
            Whether this is a SELECT query. Defaults to False.
        one_all : Literal["one", "all"], optional
            Whether to return one result or all results. Defaults to "one".

        Returns
        -------
        Optional[Any]
            The query result for SELECT queries, None otherwise.

        Raises
        ------
        DataManagerException
            If one_all is not "one" or "all" when select is True.
        """
        accepted = {"one", "all"}
        if select and one_all not in accepted:
            raise DataManagerException(
                f"Parameter 'one_all_many' should only be {discord.utils._human_join(list(accepted), final='and')}."
            )

        async with aiosqlite.connect(self.path) as db:
            if args is not None:
                cursor = await db.execute(sql_command, args)
            else:
                cursor = await db.execute(sql_command)

            if select:
                return (
                    await cursor.fetchone()
                    if one_all == "one"
                    else await cursor.fetchall()
                )

            await db.commit()
