import contextlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Union, cast

import aiohttp
import discord
from discord.ext import commands
from packaging.version import Version

from .settings import PROJECT_ROOT, Settings
from .tree import KeplerTree

GITHUB_REPOSITORY = "NoobInDaHause/Kepler"

INTENTS = discord.Intents.default()
INTENTS.message_content = True
INTENTS.presences = True
INTENTS.members = True


class Kepler(commands.AutoShardedBot):
    """
    Kepler Bot.
    """

    __version__ = (PROJECT_ROOT / "version.txt").read_text(encoding="utf-8").strip()

    def __init__(self, settings: Settings):
        super().__init__(
            command_prefix=commands.when_mentioned,
            intents=INTENTS,
            description="A Discord bot/app written in Python.",
            tree_cls=KeplerTree,
        )
        self.blacklisted_user_ids = settings.blacklisted_user_ids
        self.global_hex_colour = settings.global_hex_colour
        self.uptime = datetime.now(timezone.utc)
        self.custom_info = settings.custom_info
        self.log = logging.getLogger("Kepler")
        self.exit_code = 0

    @property
    def colour(self) -> discord.Colour:
        return discord.Colour.from_str(self.global_hex_colour)

    @property
    def color(self) -> discord.Colour:
        return self.colour

    async def get_updates(self) -> Dict[str, str]:
        """Get the latest GitHub version and compare it with the bot version."""
        releases_url = (
            f"https://api.github.com/repos/{GITHUB_REPOSITORY}/releases/latest"
        )
        latest_version = ""
        release_url = releases_url

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(releases_url) as response:
                    if response.status == 200:
                        release = cast(Dict[str, str], await response.json())
                        latest_version = release.get("tag_name", "")
                        release_url = release.get("html_url", releases_url)
                    elif response.status == 404:
                        tags_url = (
                            f"https://api.github.com/repos/{GITHUB_REPOSITORY}/tags"
                        )
                        async with session.get(tags_url) as tags_response:
                            if tags_response.status != 200:
                                return {
                                    "status": "error",
                                    "message": (
                                        "GitHub returned "
                                        f"HTTP {tags_response.status} while checking tags."
                                    ),
                                }
                            tags = cast(
                                List[Dict[str, str]], await tags_response.json()
                            )
                        if tags:
                            latest_tag = tags[0].get("name", "")
                            latest_version = latest_tag
                            release_url = f"https://github.com/{GITHUB_REPOSITORY}/releases/tag/{latest_tag}"
                    else:
                        return {
                            "status": "error",
                            "message": (
                                "GitHub returned "
                                f"HTTP {response.status} while checking updates."
                            ),
                        }
        except aiohttp.ClientError:
            return {
                "status": "error",
                "message": "Unable to connect to GitHub while checking for updates.",
            }

        if not latest_version:
            return {"status": "error", "message": "GitHub did not provide a version."}

        return {
            "status": (
                "update_available"
                if Version(latest_version) > Version(self.__version__)
                else "up_to_date"
            ),
            "current_version": self.__version__,
            "latest_version": latest_version,
            "release_url": release_url,
        }

    async def setup_hook(self) -> None:
        await super().setup_hook()
        app_info = await self.application_info()
        members = app_info.team.members if app_info.team else [app_info.owner]
        self.owner_ids = {member.id for member in members}

        cogs_path = Path(__file__).parents[1] / "cogs"
        for cog_folder in cogs_path.iterdir():
            if cog_folder.is_dir() and (cog_folder / "__init__.py").is_file():
                try:
                    await self.load_extension(f"cogs.{cog_folder.name}")
                except commands.ExtensionFailed as e:
                    self.log.exception(
                        "Error loading cog: %s",
                        cog_folder.name,
                        exc_info=(type(e), e, e.__traceback__),
                    )

        if cog_names := list(self.cogs):
            plural = "s" if len(cog_names) > 1 else ""
            self.log.info(
                "Loaded cog%s: %s",
                plural,
                discord.utils._human_join(cog_names, final="and"),
            )

        self.log.info("Syncing commands...")
        await self.tree.sync()
        self.log.info(
            "Successfully synced %s command(s).", len(self.tree.get_commands())
        )

        self.log.info("Logged in as %s (ID: %s).", self.user, self.user.id)
        self.log.info("--------------------------------------------------")

        update = await self.get_updates()
        self.log.info("Checking for updates.")
        if update["status"] == "error":
            self.log.warning(update["message"])
        elif update["status"] == "update_available":
            self.log.info(
                f"Update detected: `{update['current_version']}` -> `{update['latest_version']}`"
            )
            embed = discord.Embed(
                title="Hey there :wave:. I have detected a newer version of the upstream project on GitHub.",
                description=(
                    f"`{update['current_version']}` -> `{update['latest_version']}`\n"
                    f"[View release]({update['release_url']})"
                ),
                colour=self.colour,
                timestamp=discord.utils.utcnow(),
            )
            await self.send_to_owners(
                embed=embed,
            )
        else:
            self.log.info("Kepler is up to date.")

    async def on_message(self, message: discord.Message):
        if await self.is_owner(message.author):
            return await super().on_message(message)

    async def get_or_fetch_user(self, user_id: int) -> discord.User:
        return self.get_user(user_id) or await self.fetch_user(user_id)

    async def get_or_fetch_member(
        self, guild: discord.Guild, user_id: int
    ) -> discord.Member:
        return guild.get_member(user_id) or await guild.fetch_member(user_id)

    async def get_or_fetch_guild(self, guild_id: int) -> discord.Guild:
        return self.get_guild(guild_id) or await self.fetch_guild(guild_id)

    async def get_or_fetch_channel(
        self, guild_id: int, channel_id: int
    ) -> discord.TextChannel:
        guild = await self.get_or_fetch_guild(guild_id)
        return guild.get_channel(channel_id) or await guild.fetch_channel(channel_id)

    async def send_to_owners(self, *args, **kwargs) -> None:
        for o_id in self.owner_ids:
            with contextlib.suppress(
                discord.errors.Forbidden,
                discord.errors.NotFound,
                discord.errors.HTTPException,
            ):
                await (await self.get_or_fetch_user(o_id)).send(*args, **kwargs)

    def is_blacklisted(
        self, user_or_user_id: Union[discord.Member, discord.User, int]
    ) -> bool:
        return (
            getattr(user_or_user_id, "id", user_or_user_id) in self.blacklisted_user_ids
        )

    def add_user_to_blacklist(
        self, user_or_user_id: Union[discord.Member, discord.User, int]
    ) -> bool:
        uid = getattr(user_or_user_id, "id", user_or_user_id)
        if uid in self.blacklisted_user_ids:
            return False
        self.blacklisted_user_ids.append(uid)
        return True

    def remove_user_from_blacklist(
        self, user_or_user_id: Union[discord.Member, discord.User, int]
    ) -> bool:
        uid = getattr(user_or_user_id, "id", user_or_user_id)
        if uid not in self.blacklisted_user_ids:
            return False
        self.blacklisted_user_ids.remove(uid)
        return True

    async def close(self, restart: bool = False) -> None:
        if restart:
            self.exit_code = 26

        self.log.info(
            "Cleaning up before %s.", ("restarting" if restart else "shutting down")
        )
        self.save_settings()
        return await super().close()

    def save_settings(self):
        with open(PROJECT_ROOT / "config.json", "w", encoding="utf-8") as conf:
            data = {
                "global_hex_colour": self.global_hex_colour,
                "blacklisted_user_ids": self.blacklisted_user_ids,
                "custom_info": self.custom_info,
            }
            json.dump(data, conf, indent=4)
            self.log.info("Settings successfully saved.")
