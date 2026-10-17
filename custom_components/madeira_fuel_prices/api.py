"""Read the price feed (its format is described in docs/feed.md)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

import aiohttp

from .const import FEED_TIMEOUT, FEED_URL

PETROL_95 = "petrol_95"
DIESEL = "diesel"
COLOURED_DIESEL = "coloured_diesel"
FUELS = (PETROL_95, DIESEL, COLOURED_DIESEL)


class FeedError(Exception):
    """The feed could not be fetched, or what it holds is not valid."""


@dataclass(frozen=True)
class PriceOrder:
    """One weekly order: the maximum prices that apply from a date."""

    valid_from: date
    prices: dict[str, float | None]
    portaria: str | None
    source: str


@dataclass(frozen=True)
class Feed:
    """What the feed holds: up to two orders, and how the last run went."""

    updated_at: datetime
    warnings: list[dict[str, str]]
    orders: list[PriceOrder]


def _order(data: dict[str, Any]) -> PriceOrder:
    prices: dict[str, float | None] = {}
    for fuel in FUELS:
        price = data.get(fuel)
        if price is not None and (
            isinstance(price, bool) or not isinstance(price, (int, float))
        ):
            raise ValueError(f"{fuel} is not a number")
        prices[fuel] = None if price is None else float(price)
    portaria = data.get("portaria")
    return PriceOrder(
        valid_from=date.fromisoformat(data["valid_from"]),
        prices=prices,
        portaria=None if portaria is None else str(portaria),
        source=str(data["source"]),
    )


def parse_feed(data: Any) -> Feed:
    """Check the feed's content and return it. Unknown fields are ignored."""
    try:
        updated_at = datetime.fromisoformat(data["updated_at"])
        if updated_at.tzinfo is None:
            raise ValueError("updated_at has no time zone")
        return Feed(
            updated_at=updated_at,
            warnings=[
                {"code": str(item["code"]), "message": str(item.get("message", ""))}
                for item in data.get("warnings") or []
            ],
            orders=[
                _order(data[key])
                for key in ("current", "next")
                if data.get(key) is not None
            ],
        )
    except (AttributeError, KeyError, TypeError, ValueError) as err:
        raise FeedError(f"the price feed is not valid ({err!r})") from err


async def async_fetch_feed(session: aiohttp.ClientSession) -> Any:
    """Return the feed's content as fetched; parse_feed checks it."""
    try:
        async with session.get(
            FEED_URL, timeout=aiohttp.ClientTimeout(total=FEED_TIMEOUT)
        ) as response:
            response.raise_for_status()
            return await response.json()
    except (aiohttp.ClientError, TimeoutError, ValueError) as err:
        raise FeedError(f"could not fetch the price feed ({err!r})") from err
