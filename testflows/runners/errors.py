"""
Exception classes for testflows runners.
"""


class LocationError(Exception):
    pass


class ImageError(Exception):
    pass


class SetupScriptError(Exception):
    pass


class StartupScriptError(Exception):
    pass


class ServerTypeError(Exception):
    pass


class ConfigError(Exception):
    pass


class RetryableError(Exception):
    """Error that can be retried"""

    pass


class MaxNumberOfServersReached(Exception):
    """Exception to indicate that scale up service
    reached maximum number of servers."""

    pass


class MaxNumberOfServersForLabelReached(Exception):
    """Exception to indicate that server can't be created
    because label-specific limit has been reached."""

    pass


class CanceledServerCreation(Exception):
    """Exception to indicate that server creation was canceled."""

    pass
