from keplerbot import Kepler

from .guildtools import GuildTools


async def setup(bot: Kepler) -> None:
    await bot.add_cog(GuildTools(bot))
