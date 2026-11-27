import logging

from discord import app_commands
from discord.ext import commands

from keplerbot import Kepler, KeplerInteraction
from utilities.checks import has_permissions

from .views import VerificationView


class GuildTools(commands.GroupCog):
    """
    Various tools for guilds.
    """

    def __init__(self, bot: Kepler):
        super().__init__()
        self.bot = bot
        self.log = logging.getLogger(f"Kepler.{self.__class__.__name__}")

    @app_commands.command(name="verification", description="Verification for guild.")
    @has_permissions(manage_guild=True)
    async def guildtools_verification(self, interaction: KeplerInteraction) -> None:
        await VerificationView(interaction).start()
