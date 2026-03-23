class BAError(Exception):
    """Base application error."""


class ConfigError(BAError):
    """Invalid configuration."""


class NetworkError(BAError):
    """Network failure while fetching remote content."""


class DecodeError(BAError):
    """Resource decoding failure."""


class ExtractError(BAError):
    """Resource extraction failure."""


class ExternalToolError(BAError):
    """External command or SDK failure."""
