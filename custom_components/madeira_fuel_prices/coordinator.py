"""DataUpdateCoordinator for the Madeira Fuel Prices integration."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
import logging
from typing import Any
from zoneinfo import ZoneInfo

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import Feed, FeedError, PriceOrder, async_fetch_feed, parse_feed
from .const import (
    DOMAIN,
    MADEIRA_TIME_ZONE,
    SCAN_INTERVAL,
    STORAGE_KEY,
    STORAGE_VERSION,
)

_LOGGER = logging.getLogger(__name__)

_MADEIRA = ZoneInfo(MADEIRA_TIME_ZONE)


@dataclass(frozen=True)
class FuelPrices:
    """The order in force today and the next one, and the state of the feed."""

    current: PriceOrder | None
    upcoming: PriceOrder | None
    updated_at: datetime
    warnings: list[dict[str, str]]


def select_orders(feed: Feed, today: date) -> FuelPrices:
    """Pick the order in force on `today` and the first one that starts later.

    The feed's own `current` can be a few hours behind on the day an order
    starts, so the dates decide, not the field an order came in.
    """
    started = [order for order in feed.orders if order.valid_from <= today]
    later = [order for order in feed.orders if order.valid_from > today]
    return FuelPrices(
        current=max(started, key=lambda order: order.valid_from, default=None),
        upcoming=min(later, key=lambda order: order.valid_from, default=None),
        updated_at=feed.updated_at,
        warnings=feed.warnings,
    )


def _today() -> date:
    return dt_util.now(_MADEIRA).date()


class MadeiraFuelPricesCoordinator(DataUpdateCoordinator[FuelPrices]):
    """Keeps the last valid copy of the feed and picks today's order from it."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialise the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
            config_entry=entry,
        )
        self._session = async_get_clientsession(hass)
        self._store: Store[dict[str, Any]] = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self._feed: Feed | None = None
        self._feed_failing = False

    async def _async_setup(self) -> None:
        """Load the copy of the feed saved by an earlier run."""
        stored = await self._store.async_load()
        if stored is None:
            return
        try:
            self._feed = parse_feed(stored)
        except FeedError as err:
            # Versions that read the journal themselves stored something else.
            _LOGGER.debug("Ignoring the stored data: %s", err)

    async def _async_update_data(self) -> FuelPrices:
        """Fetch the feed; keep the copy already held if that fails."""
        try:
            raw = await async_fetch_feed(self._session)
            feed = parse_feed(raw)
        except FeedError as err:
            if self._feed is None:
                raise UpdateFailed(str(err)) from err
            if not self._feed_failing:
                _LOGGER.warning("%s; keeping the prices already known", err)
                self._feed_failing = True
            return select_orders(self._feed, _today())
        if self._feed_failing:
            _LOGGER.info("The price feed can be read again")
            self._feed_failing = False

        if feed != self._feed:
            self._feed = feed
            await self._store.async_save(raw)
        return select_orders(feed, _today())

    @callback
    def async_roll_over(self, _now: datetime) -> None:
        """At midnight in Madeira, switch to the order that starts today, if any."""
        if self._feed is None:
            return
        prices = select_orders(self._feed, _today())
        if prices != self.data:
            self.async_set_updated_data(prices)


type MadeiraFuelPricesConfigEntry = ConfigEntry[MadeiraFuelPricesCoordinator]
