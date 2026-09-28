from keplerbot import Kepler

from .owner import Owner


async def setup(bot: Kepler) -> None:
    await bot.add_cog(Owner(bot))
