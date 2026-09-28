from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING, List, Optional, Union

import discord

if TYPE_CHECKING:
    from keplerbot import KeplerInteraction


class PaginatorView(discord.ui.View):
    children: List[discord.ui.Button]

    def __init__(
        self,
        interaction: KeplerInteraction,
        pages: List[Union[str, discord.Embed]],
        timeout: float = 30.0,
    ):
        super().__init__(timeout=timeout)
        self.interaction = interaction
        self.pages = pages
        self.message: Optional[Union[discord.Message, discord.WebhookMessage]] = None
        self.current_page = 0
        self.update_button_visibility()
        self.update_button_states()

    async def start(self) -> None:
        content, embed = self.page_to_content(self.pages[self.current_page])
        self.message = await self.interaction.response_or_followup(
            content=content,
            embed=embed,
            view=self,
        )
        self.update_button_states()

    def page_to_content(
        self, page: Union[str, discord.Embed]
    ) -> tuple[Optional[str], Optional[discord.Embed]]:
        return (None, page) if isinstance(page, discord.Embed) else (page, None)

    def update_button_visibility(self) -> None:
        self.clear_items()

        if not self.pages:
            return
        if len(self.pages) == 1:
            self.add_item(self.close_button)
            return
        if len(self.pages) < 3:
            self.add_item(self.previous_button)
            self.add_item(self.close_button)
            self.add_item(self.next_page_button)
            return

        self.add_item(self.first_page_button)
        self.add_item(self.previous_button)
        self.add_item(self.close_button)
        self.add_item(self.next_page_button)
        self.add_item(self.last_page_button)

    def update_button_states(self) -> None:
        if not self.pages:
            return

        first_page_button: discord.ui.Button = getattr(self, "first_page_button", None)
        previous_button: discord.ui.Button = getattr(self, "previous_button", None)
        next_page_button: discord.ui.Button = getattr(self, "next_page_button", None)
        last_page_button: discord.ui.Button = getattr(self, "last_page_button", None)

        if first_page_button is not None:
            first_page_button.disabled = self.current_page == 0
        if previous_button is not None:
            previous_button.disabled = self.current_page == 0
        if next_page_button is not None:
            next_page_button.disabled = self.current_page >= len(self.pages) - 1
        if last_page_button is not None:
            last_page_button.disabled = self.current_page >= len(self.pages) - 1

    async def update_page(
        self, interaction: KeplerInteraction, page_index: int
    ) -> None:
        if not self.pages:
            return
        self.current_page = max(0, min(page_index, len(self.pages) - 1))
        content, embed = self.page_to_content(self.pages[self.current_page])
        self.update_button_states()
        await interaction.response.edit_message(content=content, embed=embed, view=self)

    @discord.ui.button(label="⏮", style=discord.ButtonStyle.secondary)
    async def first_page_button(
        self, interaction: KeplerInteraction, _button: discord.ui.Button
    ) -> None:
        await self.update_page(interaction, 0)

    @discord.ui.button(label="◀", style=discord.ButtonStyle.primary)
    async def previous_button(
        self, interaction: KeplerInteraction, _button: discord.ui.Button
    ) -> None:
        await self.update_page(interaction, self.current_page - 1)

    @discord.ui.button(label="✖", style=discord.ButtonStyle.danger)
    async def close_button(
        self, interaction: KeplerInteraction, _button: discord.ui.Button
    ) -> None:
        await interaction.response.defer()
        self.stop()
        await self.on_timeout()

    @discord.ui.button(label="▶", style=discord.ButtonStyle.primary)
    async def next_page_button(
        self, interaction: KeplerInteraction, _button: discord.ui.Button
    ) -> None:
        await self.update_page(interaction, self.current_page + 1)

    @discord.ui.button(label="⏭", style=discord.ButtonStyle.secondary)
    async def last_page_button(
        self, interaction: KeplerInteraction, _button: discord.ui.Button
    ) -> None:
        await self.update_page(interaction, len(self.pages) - 1)

    async def interaction_check(self, interaction: KeplerInteraction) -> bool:
        if not interaction.user:
            await interaction.response_or_followup(
                content="Hmmm no interaction user found... This interaction is now timed out.",
                ephemeral=True,
            )
            self.stop()
            await self.on_timeout()
            return False
        if await interaction.client.is_owner(interaction.user):
            return True
        if interaction.user.id != self.interaction.user.id:
            await interaction.response_or_followup(
                content="You are not authorized to interact with this interaction.",
                ephemeral=True,
            )
            return False
        return True

    async def on_timeout(self) -> None:
        for button in self.children:
            button.disabled = True
        if self.message:
            with contextlib.suppress(discord.errors.NotFound):
                await self.message.edit(view=self)


class ConfirmationView(discord.ui.View):
    children: List[discord.ui.Button]

    def __init__(
        self,
        interaction: KeplerInteraction,
        confirmed_content: str = "Action confirmed.",
        confirmed_embed: Optional[discord.Embed] = None,
        timeout: float = 30.0,
    ):
        super().__init__(timeout=timeout)
        self.message: Optional[Union[discord.Message, discord.WebhookMessage]] = None
        self.interaction = interaction
        self.confirmed_content = confirmed_content
        self.confirmed_embed = confirmed_embed
        self.value: Optional[bool] = None

    async def start(self, *args, **kwargs) -> None:
        self.message = await self.interaction.response_or_followup(*args, **kwargs)

    @discord.ui.button(emoji="✔️", style=discord.ButtonStyle.success)
    async def confirm_button(
        self, interaction: KeplerInteraction, button: discord.ui.Button
    ) -> None:
        self.value = True
        self.reject_button.style = discord.ButtonStyle.grey
        self.reject_button.disabled = True
        button.disabled = True
        await interaction.response.edit_message(
            content=self.confirmed_content, embed=self.confirmed_embed, view=self
        )
        self.stop()

    @discord.ui.button(emoji="✖️", style=discord.ButtonStyle.danger)
    async def reject_button(
        self, interaction: KeplerInteraction, button: discord.ui.Button
    ) -> None:
        self.value = False
        self.confirm_button.style = discord.ButtonStyle.grey
        self.confirm_button.disabled = True
        button.disabled = True
        await interaction.response.edit_message(
            content="Alright not doing that then.", embed=None, view=self
        )
        self.stop()

    async def interaction_check(self, interaction: KeplerInteraction) -> bool:
        if not interaction.user:
            await interaction.response_or_followup(
                content="Hmmm no interaction user found... This interaction is now timed out.",
                ephemeral=True,
            )
            self.stop()
            await self.on_timeout()
            return False
        if await interaction.client.is_owner(interaction.user):
            return True
        if interaction.user.id != self.interaction.user.id:
            await interaction.response_or_followup(
                content="You are not authorized to interact with this interaction.",
                ephemeral=True,
            )
            return False
        return True

    async def on_timeout(self) -> None:
        for button in self.children:
            button.disabled = True
        if self.message:
            with contextlib.suppress(discord.errors.NotFound):
                await self.message.edit(view=self)
