from keplerbot import Kepler

from .merits import Merits


async def setup(bot: Kepler) -> None:
    await bot.add_cog(Merits(bot))
