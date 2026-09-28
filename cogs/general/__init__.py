from keplerbot import Kepler

from .general import General


async def setup(bot: Kepler) -> None:
    await bot.add_cog(General(bot))
