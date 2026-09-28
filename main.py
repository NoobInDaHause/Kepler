import asyncio
import logging
import os
from pathlib import Path

import discord
from dotenv import find_dotenv, load_dotenv

from keplerbot import Kepler, Settings
from keplerbot.interaction import KeplerInteraction


def setup_lopgging():
    logging.basicConfig(
        level=logging.INFO,
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(Path(__file__).parent / "logs.log", "w"),
        ],
        format="[{asctime}] [{levelname}] {name:<20}: {message}",
        datefmt="%Y-%m-%d %H:%M:%S",
        style="{",
    )


async def run_bot() -> int:
    setup_lopgging()
    load_dotenv(find_dotenv(raise_error_if_not_found=True))
    setattr(
        discord.Interaction,
        "response_or_followup",
        KeplerInteraction.response_or_followup,
    )

    settings = await Settings.initialize()
    async with Kepler(settings) as bot:
        try:
            await bot.start(token=os.getenv("TOKEN"))
        except discord.errors.LoginFailure as L:
            bot.log.critical(
                "Error logging in. Might have wrong token please double check.",
                exc_info=(type(L), L, L.__traceback__),
            )

        return bot.exit_code


if __name__ == "__main__":
    exit_code = asyncio.run(run_bot())
    delattr(discord.Interaction, "response_or_followup")
    raise SystemExit(exit_code)
