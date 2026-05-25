"""Azure cost estimation implementation."""

from github.Repository import Repository
from ...config import Config


def get_server_price(
    server_prices: dict[str, dict[str, float]],
    server_type: str,
    server_location: str,
    ipv4_price: float,
    ipv6_price: float,
) -> float:
    """Get server price for Azure."""
    raise NotImplementedError("Azure cost estimation is not yet implemented")


def get_runner_server_price_per_second(
    server_prices: dict[str, dict[str, float]],
    runner_name: str,
    ipv4_price: float,
    ipv6_price: float,
) -> tuple[float, str, str]:
    """Get runner server price per second for Azure."""
    raise NotImplementedError("Azure cost estimation is not yet implemented")


def login_and_get_prices(
    args, config: Config
) -> tuple[Repository, dict[str, dict[str, float]]]:
    """Login and get prices for Azure."""
    raise NotImplementedError("Azure cost estimation is not yet implemented")
