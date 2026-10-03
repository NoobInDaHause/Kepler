from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import List, Tuple

import discord
from discord import app_commands
from discord.ext import commands

from keplerbot import Kepler, KeplerInteraction
from utilities.checks import bot_has_permissions, is_owner
from utilities.exceptions import BadArgument
from utilities.formatting import pagify
from utilities.transformers import UserTransformer
from utilities.views import ConfirmationView, PaginatorView

from .views import OwnerView


class Owner(commands.Cog):
    """
    Owner only.

    No peasants allowed.
    """

    def __init__(self, bot: Kepler):
        super().__init__()
        self.bot = bot

    @staticmethod
    def cog_exists(cog_name: str) -> bool:
        cogs_path = Path(__file__).parents[2] / "cogs"
        return (cogs_path / cog_name).is_dir() and (
            cogs_path / cog_name / "__init__.py"
        ).is_file()

    async def manage_cog(self, action: str, cog_name: str) -> Tuple[bool, str]:
        extension = f"cogs.{cog_name}"
        try:
            existing_cogs = dict(self.bot.cogs)
            if action == "load":
                await self.bot.load_extension(extension)
            elif action == "unload":
                await self.bot.unload_extension(extension)
            else:
                await self.bot.reload_extension(extension)

            if action != "unload":
                cog_class_names = [
                    class_name
                    for class_name, cog in self.bot.cogs.items()
                    if existing_cogs.get(class_name) is not cog
                ]
                if all(
                    class_name.casefold() != cog_name.casefold()
                    for class_name in cog_class_names
                ):
                    await self.bot.unload_extension(extension)
                    actual_names = (
                        discord.utils._human_join(cog_class_names, final="and")
                        or "none"
                    )
                    return (
                        False,
                        f"cog class name must match folder name "
                        f"(expected {cog_name}, got {actual_names})",
                    )
        except commands.ExtensionNotFound:
            return False, "extension not found"
        except commands.ExtensionAlreadyLoaded:
            return False, "already loaded"
        except commands.ExtensionNotLoaded:
            return False, "not loaded"
        except commands.ExtensionFailed as error:
            return False, str(error)

        return True, ""

    async def manage_cogs(
        self, interaction: KeplerInteraction, action: str, cog_names: List[str]
    ) -> None:
        protected = []
        missing = []
        successful = []
        failed = []

        for cog_name in cog_names:
            if cog_name.casefold() == "owner":
                protected.append(cog_name)
                continue

            if not self.cog_exists(cog_name):
                missing.append(cog_name)
                continue

            succeeded, reason = await self.manage_cog(action, cog_name)
            if succeeded:
                successful.append(cog_name)
            else:
                failed.append((cog_name, reason))

        messages = []
        verb = f"{action}ed"
        if successful:
            cog_label = "cog" if len(successful) == 1 else "cogs"
            messages.append(
                f"{verb.capitalize()} {cog_label}: {discord.utils._human_join(successful, final='and')}"
            )
        if failed:
            cog_label = "cog" if len(failed) == 1 else "cogs"
            failed_details = discord.utils._human_join(
                [f"{cog_name} ({reason})" for cog_name, reason in failed], final="and"
            )
            messages.append(
                f"The following {cog_label} failed to {action}: {failed_details}"
            )
        if missing:
            cog_label = "cog" if len(missing) == 1 else "cogs"
            exist_verb = "does not exist" if len(missing) == 1 else "do not exist"
            messages.append(
                f"The following {cog_label} {exist_verb}: {discord.utils._human_join(missing, final='and')}"
            )
        if protected:
            cog_label = "cog" if len(protected) == 1 else "cogs"
            messages.append(
                f"The following {cog_label} cannot be {verb}: {discord.utils._human_join(protected, final='and')}"
            )
        await interaction.response_or_followup(content="\n".join(messages))

    async def restart_or_shutdown(
        self, interaction: KeplerInteraction, restart: bool
    ) -> None:
        done_msg = (
            "Restarting... :arrows_counterclockwise:"
            if restart
            else "Shutting down. :wave:"
        )
        confirm_view = ConfirmationView(interaction, done_msg)

        await confirm_view.start(
            content=f"Are you sure you want me to {'restart' if restart else 'shutdown'}?",
            view=confirm_view,
        )
        await confirm_view.wait()

        if confirm_view.value:
            confirm_view.stop()
            await interaction.client.close(restart)

    async def _guilds(self, interaction: KeplerInteraction) -> None:
        guilds: List[discord.Guild] = sorted(
            self.bot.guilds, key=lambda g: g.member_count, reverse=True
        )
        guild_list = "\n".join(
            f"{index}. **{guild.name}** (`{guild.id}`) - {guild.member_count} members"
            for index, guild in enumerate(guilds, start=1)
        )

        pagified_guilds = pagify(guild_list)

        if len(pagified_guilds) == 1:
            guild_len = len(guilds)
            embed = discord.Embed(
                title=f"{self.bot.user.name} is in `{guild_len}` guild{'' if guild_len == 1 else 's'}.",
                description=pagified_guilds[0],
                colour=self.bot.colour,
                timestamp=datetime.now(timezone.utc),
            )
            await interaction.response_or_followup(embed=embed)
        else:
            embeds = [
                discord.Embed(
                    title=f"{self.bot.user.name} is in `{len(guilds)}` guilds.",
                    description=page,
                    colour=self.bot.colour,
                    timestamp=datetime.now(timezone.utc),
                ).set_footer(text=f"Page ({index}/{len(pagified_guilds)})")
                for index, page in enumerate(pagified_guilds, start=1)
            ]

            await PaginatorView(interaction, embeds).start()

    async def _cog_list(self, interaction: KeplerInteraction) -> None:
        cogs_path = Path(__file__).parents[2] / "cogs"
        cog_names = sorted(
            cog_folder.name
            for cog_folder in cogs_path.iterdir()
            if cog_folder.is_dir() and (cog_folder / "__init__.py").is_file()
        )
        loaded_extensions = {extension.casefold() for extension in self.bot.extensions}
        loaded = [
            cog_name
            for cog_name in cog_names
            if f"cogs.{cog_name}".casefold() in loaded_extensions
        ]
        unloaded = [cog_name for cog_name in cog_names if cog_name not in loaded]

        loaded_list = "\n".join(f"- `{l}`" for l in loaded) or "- None"
        unloaded_list = "\n".join(f"- `{ul}`" for ul in unloaded) or "- None"
        markdown = (
            "# Cogs\n\n"
            f"## Loaded ({len(loaded)})\n\n"
            f"{loaded_list}\n\n"
            f"## Unloaded ({len(unloaded)})\n\n"
            f"{unloaded_list}\n"
        )
        cog_file = discord.File(BytesIO(markdown.encode("utf-8")), filename="cogs.md")
        await interaction.response_or_followup(file=cog_file)

    async def _colour(self, interaction: KeplerInteraction, colour: str):
        dc = discord.Colour.from_str(colour)
        self.bot.global_hex_colour = str(dc)
        embed = discord.Embed(
            description=f"Successfully changed bot colour to {dc}.",
            colour=self.bot.colour,
        )
        self.bot.save_settings()
        await interaction.response_or_followup(embed=embed)

    async def blacklist_or_unblacklist(
        self, what: str, interaction: KeplerInteraction, users: List[str]
    ):
        verified: List[discord.User] = []
        failed = []
        for u in users:
            try:
                verified.append(await UserTransformer().transform(interaction, u))
            except BadArgument:
                failed.append(f"Unknown User (`{u}`)")
                continue

        added_or_removed = []
        for v in verified:
            if what == "blacklist":
                (
                    added_or_removed.append(f"{v} (`{v.id}`)")
                    if self.bot.add_user_to_blacklist(v)
                    else failed.append(f"{v} (`{v.id}`)")
                )
            else:
                (
                    added_or_removed.append(f"{v} (`{v.id}`)")
                    if self.bot.remove_user_from_blacklist(v)
                    else failed.append(f"{v} (`{v.id}`)")
                )

        if added_or_removed:
            self.bot.save_settings()
            a2_msg = discord.utils._human_join(added_or_removed, final="and")
            await interaction.response_or_followup(
                content=f"{what.title()}ed: {a2_msg}"
            )
        if failed:
            b2_msg = discord.utils._human_join(failed, final="and")
            await interaction.response_or_followup(
                content=f"Users already {what}ed or unknown: {b2_msg}"
            )

    async def naughty_list(self, interaction: KeplerInteraction):
        blacklisted = []

        for x in self.bot.blacklisted_user_ids:
            try:
                user = await self.bot.get_or_fetch_user(x)
            except discord.errors.NotFound:
                user = None

            if user is None:
                blacklisted.append(f"**Unknown User** (`{x}`)")
            else:
                blacklisted.append(f"**{user}** (`{user.id}`)")

        embed = discord.Embed(
            title="List of users in the naughty list.",
            description="\n".join(blacklisted) or "No users in the naughty list.",
            colour=self.bot.colour,
        )
        await interaction.response_or_followup(embed=embed)

    @app_commands.command(name="owner", description="Owner only commands.")
    @is_owner()
    @bot_has_permissions(attach_files=True, embed_links=True)
    async def owner(self, interaction: KeplerInteraction) -> None:
        """
        No peasants allowed.
        """
        desc = """
            Command names highlighted as bold require an argument.
            Params wrapped around <> are required while [] are optional.
            
            Available owner commands:
            > restart: Restarts the bot.
            `Usage: command:restart`
            > shutdown: Shuts down the bot.
            `Usage: command:shutdown`
            > guilds: Shows the list of guilds the bot is in.
            `Usage: command:guilds`
            > **loadcog**: Loads a cog. Separate cog names with spaces.
            `Usage: command:loadcog argument:<cog_names...>`
            > **unloadcog**: Unloads a cog. Separate cog names with spaces.
            `Usage:command:unloadcog argument:<cog_names...>` 
            > **reloadcog**: Reloads a cog. Separate cog names with spaces.
            `Usage: command:reloadcog argument:<cog_names...>`
            > coglist: Shows the list of loaded/unloaded cogs.
            `Usage: command:coglist`
            > **botcolour**: Change the bot global embed hex colour, leave argument blank to set it back to default.
            `Usage: command:botcolour argument:[hex_code=#276a8a]`
            `Aliases: botcolor`
            > **blacklist**: Blacklist one or more user. Leave argument blank to check list.
            `Usage: command:blacklist argument:[users...]`
            > **unblacklist**: Unblacklist one or more user. Leave argument blank to check list.
            `Usage: command:unblacklist argument:[users...]`
            > **custominfo**: Add/change/remove a custom info from the /botinfo slash command. Leave argument blank to remove.
            `Usage: command:custominfo argument:[new_info]`
            """
        embed = discord.Embed(
            title="Owner command pannel", description=desc, colour=self.bot.colour
        )

        await OwnerView(self, interaction).start(embed=embed)
