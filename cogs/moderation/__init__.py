from keplerbot import Kepler

from .moderation import Moderation


async def setup(bot: Kepler):
    await bot.add_cog(Moderation(bot))
