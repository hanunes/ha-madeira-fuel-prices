"""The Madeira Fuel Prices integration."""
from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_utc_time_change

from .const import PLATFORMS
from .coordinator import MadeiraFuelPricesConfigEntry, MadeiraFuelPricesCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: MadeiraFuelPricesConfigEntry
) -> bool:
    """Set up Madeira Fuel Prices from a config entry."""
    coordinator = MadeiraFuelPricesCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    # A new order starts at 0:00 in Madeira, between two fetches of the feed.
    # That is 0:00 UTC in winter and 23:00 UTC in summer; the wrong one of the
    # two finds nothing to switch.
    entry.async_on_unload(
        async_track_utc_time_change(
            hass, coordinator.async_roll_over, hour=(0, 23), minute=0, second=5
        )
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: MadeiraFuelPricesConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
