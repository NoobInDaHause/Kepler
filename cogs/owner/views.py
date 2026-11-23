import contextlib
from dataclasses import dataclass
from math import ceil
from typing import TYPE_CHECKING, List, Optional, Union

import discord

from keplerbot import KeplerInteraction

if TYPE_CHECKING:
    from .owner import Owner


@dataclass(frozen=True)
class OwnerCommand:
    name: str
    description: str
    usage: Optional[str] = None
    argument_label: Optional[str] = None
    argument_placeholder: str = ""
    argument_required: bool = False


OWNER_COMMANDS = (
    OwnerCommand("restart", "Restarts the bot."),
    OwnerCommand("shutdown", "Shuts down the bot."),
    OwnerCommand("guilds", "Shows the list of guilds the bot is in."),
    OwnerCommand(
        "loadcog",
        "Loads one or more cogs.",
        "loadcog <cog_names...>",
        "Cog names",
        "Separate cog names with spaces",
        True,
    ),
    OwnerCommand(
        "unloadcog",
        "Unloads one or more cogs.",
        "unloadcog <cog_names...>",
        "Cog names",
        "Separate cog names with spaces",
        True,
    ),
    OwnerCommand(
        "reloadcog",
        "Reloads one or more cogs.",
        "reloadcog <cog_names...>",
        "Cog names",
        "Separate cog names with spaces",
        True,
    ),
    OwnerCommand("coglist", "Shows the list of loaded and unloaded cogs."),
    OwnerCommand(
        "consolelogs",
        "Shows the console logs, with pagination when needed.",
    ),
    OwnerCommand(
        "botcolour",
        "Changes the bot's embed colour. Leave blank to reset to the default.",
        "botcolour [hex_code=#276a8a]",
        "Hex colour (optional)",
        "For example: #276a8a",
    ),
    OwnerCommand(
        "blacklist",
        "Blacklists users, or shows the list when left blank.",
        "blacklist [users...]",
        "Users (optional)",
        "User IDs, mentions, or names separated by spaces",
    ),
    OwnerCommand(
        "unblacklist",
        "Unblacklists users, or shows the list when left blank.",
        "unblacklist [users...]",
        "Users (optional)",
        "User IDs, mentions, or names separated by spaces",
    ),
    OwnerCommand(
        "custominfo",
        "Sets custom info for /botinfo. Leave blank to remove it.",
        "custominfo [new_info]",
        "Custom info (optional)",
        "Leave blank to remove custom info",
    ),
    OwnerCommand(
        "botstatus",
        "Changes the bot's status.",
        "botstatus <status>,<activity_type>,<status_name>",
        "Status, activity, and name",
        "For example: online,playing,Kepler",
        True,
    ),
)


class CommandModal(discord.ui.Modal):
    def __init__(self, owner_view: "OwnerView", command: OwnerCommand):
        super().__init__(title=f"{command.name.title()} arguments", timeout=60.0)
        self.owner_view = owner_view
        self.command = command
        self.argument = discord.ui.TextInput(
            label=command.argument_label or "Argument",
            style=discord.TextStyle.long,
            required=command.argument_required,
            placeholder=command.argument_placeholder or None,
            max_length=4000,
        )
        self.add_item(self.argument)

    async def on_submit(self, interaction: KeplerInteraction) -> None:
        await interaction.response.defer()
        await self.owner_view.execute_command(
            interaction, self.command, self.argument.value
        )


class OwnerView(discord.ui.View):
    children: List[discord.ui.Button]
    commands_per_page = 10

    def __init__(self, cog: "Owner", interaction: KeplerInteraction):
        super().__init__()
        self.message: Optional[
            Union[discord.Message, discord.InteractionMessage, discord.WebhookMessage]
        ] = None
        self.interaction = interaction
        self.cog = cog
        self.current_page = 0
        self.page_count = ceil(len(OWNER_COMMANDS) / self.commands_per_page)
        self._build_items()

    async def start(self) -> None:
        self.message = await self.interaction.response_or_followup(
            embed=self.build_embed(),
            view=self,
        )

    def build_embed(self) -> discord.Embed:
        start = self.current_page * self.commands_per_page
        commands = OWNER_COMMANDS[start : start + self.commands_per_page]
        lines = []
        for number, command in enumerate(commands, start=1):
            line = f"**{number}. `{command.name}`:** {command.description}"
            if command.usage:
                line += f" Usage: `{command.usage}`"
            lines.append(line)

        return discord.Embed(
            title="Owner commands",
            description="\n".join(lines),
            colour=self.cog.bot.colour,
        ).set_footer(
            text=f"Page {self.current_page + 1}/{self.page_count} • Select a command below."
        )

    def _build_items(self) -> None:
        self.clear_items()
        start = self.current_page * self.commands_per_page
        commands = OWNER_COMMANDS[start : start + self.commands_per_page]

        for index, command in enumerate(commands):
            button = discord.ui.Button(
                label=str(index + 1),
                style=discord.ButtonStyle.primary,
                row=index // 5,
            )

            async def callback(
                interaction: KeplerInteraction,
                selected_command: OwnerCommand = command,
            ) -> None:
                await self.select_command(interaction, selected_command)

            button.callback = callback
            self.add_item(button)

        if self.page_count >= 3:
            first = discord.ui.Button(
                label="⏮",
                style=discord.ButtonStyle.secondary,
                row=2,
                disabled=self.current_page == 0,
            )
            first.callback = self.first_page
            self.add_item(first)

        if self.page_count > 1:
            previous = discord.ui.Button(
                label="◀",
                style=discord.ButtonStyle.primary,
                row=2,
                disabled=self.current_page == 0,
            )
            previous.callback = self.previous_page
            self.add_item(previous)

        close = discord.ui.Button(label="✖", style=discord.ButtonStyle.danger, row=2)
        close.callback = self.close
        self.add_item(close)

        if self.page_count > 1:
            next_page = discord.ui.Button(
                label="▶",
                style=discord.ButtonStyle.primary,
                row=2,
                disabled=self.current_page == self.page_count - 1,
            )
            next_page.callback = self.next_page
            self.add_item(next_page)

        if self.page_count >= 3:
            last = discord.ui.Button(
                label="⏭",
                style=discord.ButtonStyle.secondary,
                row=2,
                disabled=self.current_page == self.page_count - 1,
            )
            last.callback = self.last_page
            self.add_item(last)

    async def select_command(
        self, interaction: KeplerInteraction, command: OwnerCommand
    ) -> None:
        if command.argument_label:
            await interaction.response.send_modal(CommandModal(self, command))
            return
        await self.execute_command(interaction, command, "")

    async def previous_page(self, interaction: KeplerInteraction) -> None:
        await self.update_page(interaction, self.current_page - 1)

    async def first_page(self, interaction: KeplerInteraction) -> None:
        await self.update_page(interaction, 0)

    async def next_page(self, interaction: KeplerInteraction) -> None:
        await self.update_page(interaction, self.current_page + 1)

    async def last_page(self, interaction: KeplerInteraction) -> None:
        await self.update_page(interaction, self.page_count - 1)

    async def update_page(self, interaction: KeplerInteraction, page: int) -> None:
        self.current_page = max(0, min(page, self.page_count - 1))
        self._build_items()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    async def close(self, interaction: KeplerInteraction) -> None:
        await interaction.response.defer()
        self.stop()
        await self.on_timeout()

    async def execute_command(
        self,
        interaction: KeplerInteraction,
        command: OwnerCommand,
        argument: str,
    ) -> None:
        name = command.name
        try:
            if name in {"restart", "shutdown"}:
                self.stop()
                await self.on_timeout()
                await self.cog.restart_or_shutdown(
                    interaction, restart=name == "restart"
                )
                return

            if name == "guilds":
                await self.cog._guilds(interaction)
                return

            if name in {"loadcog", "unloadcog", "reloadcog"}:
                await self.cog.manage_cogs(
                    interaction, name.removesuffix("cog"), argument.split()
                )
                return

            if name == "coglist":
                await self.cog._cog_list(interaction)
                return

            if name == "consolelogs":
                await self.cog.console_logs(interaction)
                return

            if name == "botcolour":
                await self.cog._colour(interaction, argument or "#276a8a")
                return

            if name in {"blacklist", "unblacklist"}:
                if not argument:
                    await self.cog.naughty_list(interaction)
                    return
                await self.cog.blacklist_or_unblacklist(
                    name, interaction, argument.split()
                )
                return

            if name == "custominfo":
                interaction.client.custom_info = argument or None
                interaction.client.save_settings()
                await interaction.response_or_followup(content="Done.")
                return

            if name == "botstatus":
                await self.cog.update_bot_status(interaction, argument)
                interaction.client.save_settings()
                return
        except ValueError as error:
            await interaction.response_or_followup(content=str(error))

    async def interaction_check(self, interaction: KeplerInteraction) -> bool:
        if not self.interaction.user:
            await interaction.response_or_followup(
                content="Hmmm no interaction user found... This interaction is now timed out.",
                ephemeral=True,
            )
            self.stop()
            await self.on_timeout()
            return False

        is_owner = await interaction.client.is_owner(interaction.user)
        if not is_owner:
            await interaction.response_or_followup(
                content="You are not an owner of this bot. 🖕🖕🖕", ephemeral=True
            )
            return is_owner
        return is_owner

    async def on_timeout(self) -> None:
        for button in self.children:
            button.disabled = True
        if self.message:
            with contextlib.suppress(discord.errors.NotFound):
                await self.message.edit(view=self)
