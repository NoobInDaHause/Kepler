from keplerbot import Kepler

from .leveling import Leveling


async def setup(bot: Kepler) -> None:
    await bot.add_cog(Leveling(bot))
