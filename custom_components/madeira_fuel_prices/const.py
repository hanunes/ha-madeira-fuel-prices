"""Constants for the Madeira Fuel Prices integration."""
from __future__ import annotations

from datetime import timedelta

from homeassistant.const import Platform

DOMAIN = "madeira_fuel_prices"
NAME = "Madeira Fuel Prices"

PLATFORMS: list[Platform] = [Platform.SENSOR]

# The price feed, described in docs/feed.md. One job reads JORAM for everyone
# and publishes what it finds as a small static file.
FEED_URL = "https://madeirafuelprices.fyi/api/v1/prices.json"

# The file changes about twice a week, so there is no reason to ask more often.
SCAN_INTERVAL = timedelta(hours=1)

# Seconds allowed for a fetch of the feed.
FEED_TIMEOUT = 30

# An order starts at 0:00 in Madeira, whatever Home Assistant's own time zone.
MADEIRA_TIME_ZONE = "Atlantic/Madeira"

# JORAM, the official journal of the Autonomous Region of Madeira, where the
# orders are published.
JORAM_URL = "https://joram.madeira.gov.pt"

STORAGE_VERSION = 1
STORAGE_KEY = DOMAIN
