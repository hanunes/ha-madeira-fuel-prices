"""Tests for setup, the sensors and the weekly roll-over."""
from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

from freezegun.api import FrozenDateTimeFactory
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from custom_components.madeira_fuel_prices.api import parse_feed
from custom_components.madeira_fuel_prices.const import DOMAIN, FEED_URL, SCAN_INTERVAL
from custom_components.madeira_fuel_prices.coordinator import select_orders

from .conftest import FEED

MADEIRA = ZoneInfo("Atlantic/Madeira")
PETROL = "sensor.madeira_fuel_prices_petrol_95"
NEXT_PETROL = "sensor.madeira_fuel_prices_next_petrol_95"


async def _setup(hass: HomeAssistant, entry: MockConfigEntry | None = None) -> MockConfigEntry:
    if entry is None:
        # Options left by the versions that had a check interval are ignored.
        entry = MockConfigEntry(domain=DOMAIN, options={"scan_interval": 12})
        entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def _next_fetch(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


def test_select_orders() -> None:
    feed = parse_feed(FEED)
    old, new = feed.orders
    assert select_orders(feed, date(2026, 10, 3)).current == old
    assert select_orders(feed, date(2026, 10, 3)).upcoming == new
    assert select_orders(feed, date(2026, 9, 27)).current is None
    # On the day the new order starts the feed can still call it `next`.
    assert select_orders(feed, date(2026, 10, 5)).current == new
    assert select_orders(feed, date(2026, 10, 5)).upcoming is None
    # A week with no order: the last one stays in force.
    assert select_orders(feed, date(2026, 10, 14)).current == new

    empty = select_orders(parse_feed({**FEED, "current": None, "next": None}), date(2026, 10, 3))
    assert empty.current is None
    assert empty.upcoming is None


async def test_sensors(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, aioclient_mock: AiohttpClientMocker
) -> None:
    freezer.move_to(datetime(2026, 10, 3, 12, 0, tzinfo=MADEIRA))
    aioclient_mock.get(FEED_URL, json=FEED)
    entry = await _setup(hass)
    assert entry.state is ConfigEntryState.LOADED

    petrol = hass.states.get(PETROL)
    assert petrol.state == "2.029"
    assert petrol.attributes["unit_of_measurement"] == "€/L"
    assert petrol.attributes["valid_from"] == "2026-09-28"
    assert petrol.attributes["portaria"] == "25/2022"
    assert petrol.attributes["source"] == "IISerie-174-2026-09-25Supl3.pdf"
    assert petrol.attributes["source_url"] == FEED["current"]["source"]
    assert hass.states.get("sensor.madeira_fuel_prices_diesel").state == "2.148"
    assert hass.states.get("sensor.madeira_fuel_prices_coloured_diesel").state == "1.7"
    assert hass.states.get("sensor.madeira_fuel_prices_valid_from").state == "2026-09-28"
    assert hass.states.get(NEXT_PETROL).state == "2.021"
    assert hass.states.get("sensor.madeira_fuel_prices_next_diesel").state == "2.12"
    assert hass.states.get("sensor.madeira_fuel_prices_next_coloured_diesel").state == "1.672"
    assert hass.states.get("sensor.madeira_fuel_prices_next_valid_from").state == "2026-10-05"

    updated = hass.states.get("sensor.madeira_fuel_prices_data_updated")
    assert updated.state == "2026-10-03T14:40:25+00:00"
    warnings = hass.states.get("sensor.madeira_fuel_prices_warnings")
    assert warnings.state == "0"
    assert warnings.attributes["codes"] == []


async def test_warnings_and_a_missing_price(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, aioclient_mock: AiohttpClientMocker
) -> None:
    freezer.move_to(datetime(2026, 10, 3, 12, 0, tzinfo=MADEIRA))
    warning = {"code": "fuel_missing", "message": "No coloured diesel."}
    feed = {
        **FEED,
        "warnings": [warning],
        "current": {**FEED["current"], "coloured_diesel": None},
    }
    aioclient_mock.get(FEED_URL, json=feed)
    await _setup(hass)

    assert hass.states.get("sensor.madeira_fuel_prices_coloured_diesel").state == "unknown"
    warnings = hass.states.get("sensor.madeira_fuel_prices_warnings")
    assert warnings.state == "1"
    assert warnings.attributes["codes"] == ["fuel_missing"]
    assert warnings.attributes["messages"] == ["No coloured diesel."]


async def test_roll_over_at_midnight_in_madeira(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, aioclient_mock: AiohttpClientMocker
) -> None:
    await hass.config.async_set_time_zone("Asia/Tokyo")
    freezer.move_to(datetime(2026, 10, 4, 23, 50, tzinfo=MADEIRA))
    aioclient_mock.get(FEED_URL, json=FEED)
    await _setup(hass)
    assert hass.states.get(PETROL).state == "2.029"
    assert aioclient_mock.call_count == 1

    freezer.move_to(datetime(2026, 10, 5, 0, 0, 6, tzinfo=MADEIRA))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert aioclient_mock.call_count == 1  # switched without a fetch
    assert hass.states.get(PETROL).state == "2.021"
    assert hass.states.get("sensor.madeira_fuel_prices_valid_from").state == "2026-10-05"
    assert hass.states.get(NEXT_PETROL).state == "unknown"
    assert hass.states.get("sensor.madeira_fuel_prices_next_valid_from").state == "unknown"


async def test_feed_behind_on_the_day_an_order_starts(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, aioclient_mock: AiohttpClientMocker
) -> None:
    # Monday 01:00 in Madeira: the feed still has the new order under `next`.
    freezer.move_to(datetime(2026, 10, 5, 1, 0, tzinfo=MADEIRA))
    aioclient_mock.get(FEED_URL, json=FEED)
    await _setup(hass)
    assert hass.states.get(PETROL).state == "2.021"
    assert hass.states.get(NEXT_PETROL).state == "unknown"


async def test_no_feed_retries_setup(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    aioclient_mock.get(FEED_URL, status=503)
    entry = await _setup(hass)
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_known_prices_survive_restart_and_feed_outage(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, aioclient_mock: AiohttpClientMocker
) -> None:
    freezer.move_to(datetime(2026, 10, 3, 12, 0, tzinfo=MADEIRA))
    aioclient_mock.get(FEED_URL, json=FEED)
    entry = await _setup(hass)
    assert await hass.config_entries.async_unload(entry.entry_id)

    # Second start: the feed is down, the stored copy is used.
    aioclient_mock.clear_requests()
    aioclient_mock.get(FEED_URL, status=503)
    await _setup(hass, entry)
    assert entry.state is ConfigEntryState.LOADED
    assert hass.states.get(PETROL).state == "2.029"
    assert hass.states.get(NEXT_PETROL).state == "2.021"

    # An answer that is not valid changes nothing either.
    aioclient_mock.clear_requests()
    aioclient_mock.get(FEED_URL, json={**FEED, "current": {"petrol_95": 9.999}})
    await _next_fetch(hass, freezer)
    assert hass.states.get(PETROL).state == "2.029"

    # The feed is back, with a change.
    aioclient_mock.clear_requests()
    aioclient_mock.get(
        FEED_URL, json={**FEED, "current": {**FEED["current"], "petrol_95": 2.03}}
    )
    await _next_fetch(hass, freezer)
    assert hass.states.get(PETROL).state == "2.03"
