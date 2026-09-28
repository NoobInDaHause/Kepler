from discord import app_commands


class FormattingException(Exception):
    pass


class PagifyException(FormattingException):
    pass


class FormatTimeException(FormattingException):
    pass


class DataManagerException(Exception):
    pass


class UserIsBlacklisted(app_commands.CheckFailure):
    pass


class UserIsNotOwner(app_commands.CheckFailure):
    pass


class BadArgument(app_commands.AppCommandError):
    pass
