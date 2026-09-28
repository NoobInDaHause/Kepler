import platform
from time import perf_counter

import discord
from discord import app_commands
from discord.ext import commands

from keplerbot import Kepler, KeplerInteraction
from utilities.checks import bot_has_permissions, cooldown


class General(commands.Cog):
    """
    General Cog.

    Various general commands for your needs.
    """

    def __init__(self, bot: Kepler):
        super().__init__()
        self.bot = bot

    @staticmethod
    def latency_colour(latency_ms: float) -> discord.Colour:
        if latency_ms < 100:
            return discord.Colour.green()
        return discord.Colour.yellow() if latency_ms < 250 else discord.Colour.red()

    @app_commands.command(name="ping", description="Pong.")
    @bot_has_permissions(embed_links=True)
    @cooldown(1, 5, key=lambda i: i.user.id, owner_bypass=True)
    async def ping(self, interaction: KeplerInteraction) -> None:
        send_started = perf_counter()
        initial_message = await interaction.response_or_followup(content="Pinging...")
        send_latency = (perf_counter() - send_started) * 1000

        edit_started = perf_counter()
        heartbeat_latency = self.bot.latency * 1000
        measuring_embed = discord.Embed(
            title=":ping_pong: Pong!",
            colour=self.latency_colour(heartbeat_latency),
        )
        measuring_embed.add_field(
            name=f"{self.bot.user} latency",
            value=f"{heartbeat_latency:.2f} ms",
            inline=True,
        )
        measuring_embed.add_field(
            name="Message latency",
            value=f"{send_latency:.2f} ms",
            inline=True,
        )
        measuring_embed.add_field(
            name="Message edit latency",
            value="measuring...",
            inline=True,
        )
        await initial_message.edit(content="", embed=measuring_embed)
        edit_latency = (perf_counter() - edit_started) * 1000

        heartbeat_latency = self.bot.latency * 1000
        result_embed = discord.Embed(
            title=":ping_pong: Pong!",
            colour=self.latency_colour(heartbeat_latency),
        )
        result_embed.add_field(
            name=f"{self.bot.user} latency",
            value=f"{heartbeat_latency:.2f} ms",
            inline=True,
        )
        result_embed.add_field(
            name="Message latency",
            value=f"{send_latency:.2f} ms",
            inline=True,
        )
        result_embed.add_field(
            name="Message edit latency",
            value=f"{edit_latency:.2f} ms",
            inline=True,
        )
        await initial_message.edit(embed=result_embed)

    @app_commands.command(name="botinfo", description="Check info about the bot.")
    @bot_has_permissions(embed_links=True)
    async def info(self, interaction: KeplerInteraction) -> None:
        await interaction.response.defer(thinking=True)

        app_info = await self.bot.application_info()
        embed = discord.Embed(
            title=f"Instance owned by `{f'Team {app_info.team.name}' if app_info.team else app_info.owner}`",
            description=(
                "This is a custom instance of **Kepler**, based on [Martin](https://github.com/NoobInDaHause/Martin), "
                "an open-source Discord ~~BOT~~ APP built with [Python](https://www.python.org/) & "
                "[discord.py](https://pypi.org/project/discord.py/).\n\n"
                "• **Source:** [GitHub](https://github.com/NoobInDaHause/Martin)\n"
                "• **License:** [MIT](https://github.com/NoobInDaHause/Martin/blob/master/LICENSE)\n"
                "• **Community:** [Discord Server](https://discord.com/invite/8vPBQ3UJQQ)\n\n"
                "Want your own copy? Check out the repo to host one yourself!"
            ),
            timestamp=self.bot.user.created_at,
            colour=self.bot.colour,
        )
        if self.bot.custom_info:
            embed.add_field(
                name="Custom Info:", value=self.bot.custom_info, inline=False
            )

        embed.set_thumbnail(
            url=app_info.team.icon if app_info.team else app_info.owner.display_avatar
        )
        embed.set_footer(
            text=f"{self.bot.user} was created at",
            icon_url=self.bot.user.display_avatar,
        )

        embed.add_field(name="Discord.py Version:", value=discord.__version__)
        embed.add_field(name="Python Version:", value=platform.python_version())
        ver = self.bot.__version__.removeprefix("v")
        update = await self.bot.get_updates()
        if update["status"] == "update_available":
            ver += f"\n[New version available: {update['latest_version'].removeprefix('v')}]({update['release_url']})"

        embed.add_field(
            name="Kepler Version:",
            value=ver,
        )

        embed.add_field(
            name="Uptime:",
            value=f"<t:{int(self.bot.uptime.timestamp())}:F> (<t:{int(self.bot.uptime.timestamp())}:R>).",
            inline=False,
        )

        await interaction.response_or_followup(embed=embed)

    @app_commands.command(name="invite", description="Invite the bot.")
    async def invite(self, interaction: KeplerInteraction) -> None:
        await interaction.response_or_followup(
            content=f"https://discord.com/oauth2/authorize?client_id={self.bot.user.id}"
            "&permissions=8866461766385655&integration_type=0&scope=bot+applications.commands"
        )
