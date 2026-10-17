"""Config flow for the Madeira Fuel Prices integration."""
from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import FeedError, async_fetch_feed, parse_feed
from .const import DOMAIN, NAME


class MadeiraFuelPricesConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the configuration flow. There is nothing to set."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm, and check that the feed can be read."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                parse_feed(await async_fetch_feed(async_get_clientsession(self.hass)))
            except FeedError:
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(title=NAME, data={})

        return self.async_show_form(step_id="user", errors=errors)
