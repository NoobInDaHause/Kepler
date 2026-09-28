from typing import Iterable, List, Optional, Union

import discord

from utilities.exceptions import FormatTimeException, PagifyException


def pagify(
    text: str,
    delims: Optional[Union[str, Iterable[str]]] = None,
    page_length: Optional[int] = 2000,
) -> List[str]:
    """Split text into pages no longer than ``page_length`` characters.

    Parameters
    ----------
    text : str
        The text that you want to pagify.
    delims : Optional[Union[str, Iterable[str]]]
        Can be a string or list of strings that marks where the text splits. (optional)
        Example: '\n' or ['\n', ' ', '.']
        Default: ['\n', ' ']
    page_length : Optional[int]
        The length of the text per page. (optional)
        Default: 2000

    Returns
    -------
    List[str]
        The pagified list of the text.

    Raises
    ------
    PagifyException
        If the page_length is less than 1 and delims contains empty strings.

    """
    if page_length <= 0:
        raise PagifyException("Parameter 'page_length' must be greater than zero")

    if delims is None:
        delims = ["\n"]
    elif isinstance(delims, str):
        delims = [delims]
    else:
        delims = list(delims)

    if not all(delims):
        raise PagifyException("Parameter 'delims' cannot contain empty strings")

    pages = []
    remaining = text

    while remaining:
        if len(remaining) <= page_length:
            pages.append(remaining)
            break

        split_at = -1
        delimiter_length = 0
        for delim in delims:
            candidate = remaining.rfind(delim, 0, page_length + 1)
            if candidate > split_at:
                split_at = candidate
                delimiter_length = len(delim)

        if split_at <= 0:
            pages.append(remaining[:page_length])
            remaining = remaining[page_length:]
            continue

        pages.append(remaining[:split_at])
        remaining = remaining[split_at + delimiter_length :]

    return pages


def format_time(seconds: int) -> str:
    """Convert a number of seconds into human-readable duration text.

    Parameters
    ----------
    seconds : int
        The seconds to convert to human-readable text.

    Raises
    ------
    FormatTimeException
        When seconds is lower than 0.

    """
    if seconds < 0:
        raise FormatTimeException("Parameter 'seconds' cannot be less than 0")

    remaining = seconds
    units = (
        ("century", "centuries", 100 * 365 * 86400),
        ("year", "years", 365 * 86400),
        ("month", "months", 30 * 86400),
        ("day", "days", 86400),
        ("hour", "hours", 3600),
        ("minute", "minutes", 60),
        ("second", "seconds", 1),
    )
    parts = []

    for singular, plural, unit_length in units[:-1]:
        unit_value, remaining = divmod(remaining, unit_length)
        if unit_value:
            unit_name = singular if unit_value == 1 else plural
            parts.append(f"{unit_value} {unit_name}")

    if remaining:
        parts.append(f"{remaining} seconds")

    return discord.utils._human_join(parts, final="and") or "0 seconds"
