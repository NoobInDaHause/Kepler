from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from utilities.data_manager import DataManager

PROJECT_ROOT = Path(__file__).parents[1]
COGS_DATA_PATH = Path(__file__).parents[1] / "cogs_data"


@dataclass
class Settings:
    global_hex_colour: str
    blacklisted_user_ids: List[int]
    custom_info: Optional[str]

    # migrate from sqlite to json v0.5.0 -> v1.0.0
    @staticmethod
    async def migrate_custom_info() -> Optional[str]:
        path = COGS_DATA_PATH / "General.db"
        if path.exists():
            dm = DataManager("General")
            custom_info = await dm.execute(
                "SELECT value FROM general_data WHERE name = ?",
                ("custom_info",),
                select=True,
            )
            path.unlink(True)
            return custom_info[0] if custom_info else None

    @classmethod
    async def initialize(cls) -> Settings:
        with open(PROJECT_ROOT / "config.json", "r", encoding="utf-8") as config_file:
            data: dict = json.load(config_file)
            data.pop(
                "__version__", None
            )  # versioning moved from config.json to version.txt in v0.0.3
            data.pop("default_prefixes", None)  # Removed in v1.0.0
            data.pop("guild_prefixes", None)  # Removed in v1.0.0
            data.setdefault(
                "custom_info", await cls.migrate_custom_info()
            )  # custom info moved from general to bot config in v1.0.0

        return cls(**data)
