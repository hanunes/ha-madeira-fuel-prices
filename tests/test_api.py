"""Tests for reading the feed."""
from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from custom_components.madeira_fuel_prices.api import (
    FeedError,
    async_fetch_feed,
    parse_feed,
)
from custom_components.madeira_fuel_prices.const import FEED_URL

from .conftest import FEED


def test_parse_feed() -> None:
    feed = parse_feed(FEED)
    assert feed.updated_at == datetime(2026, 10, 3, 14, 40, 25, tzinfo=UTC)
    assert feed.warnings == []
    current, upcoming = feed.orders
    assert current.valid_from == date(2026, 9, 28)
    assert current.prices == {"petrol_95": 2.029, "diesel": 2.148, "coloured_diesel": 1.7}
    assert current.portaria == "25/2022"
    assert current.source == FEED["current"]["source"]
    assert upcoming.valid_from == date(2026, 10, 5)


def test_parse_feed_without_a_next_order_and_with_unknowns() -> None:
    feed = parse_feed(
        {
            **FEED,
            "next": None,
            "checked_at": "2026-10-04T06:17:00Z",
            "current": {**FEED["current"], "coloured_diesel": None, "portaria": None},
            "warnings": [
                {"code": "fuel_missing", "message": "No coloured diesel."},
                {"code": "something_new", "message": "A code added later."},
            ],
        }
    )
    (order,) = feed.orders
    assert order.prices["coloured_diesel"] is None
    assert order.portaria is None
    assert [warning["code"] for warning in feed.warnings] == [
        "fuel_missing",
        "something_new",
    ]


def test_parse_feed_with_no_orders() -> None:
    assert parse_feed({**FEED, "current": None, "next": None}).orders == []


@pytest.mark.parametrize(
    "data",
    [
        None,
        [],
        "prices",
        {},
        {**FEED, "updated_at": "yesterday"},
        {**FEED, "updated_at": "2026-10-03T14:40:25"},
        {**FEED, "current": "2.029"},
        {**FEED, "current": {**FEED["current"], "valid_from": "28/09/2026"}},
        {**FEED, "current": {**FEED["current"], "petrol_95": "2,029"}},
        {**FEED, "current": {**FEED["current"], "diesel": True}},
        {**FEED, "next": {"valid_from": "2026-10-05"}},
        {**FEED, "warnings": ["no_new_order"]},
        # What the versions that read the journal themselves kept in storage.
        {"orders": [], "read": ["IISerie-179-2026-10-02Supl.pdf"]},
    ],
)
def test_parse_feed_rejects(data) -> None:
    with pytest.raises(FeedError):
        parse_feed(data)


async def test_fetch(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    aioclient_mock.get(FEED_URL, json=FEED)
    assert await async_fetch_feed(async_get_clientsession(hass)) == FEED


@pytest.mark.parametrize(
    "answer", [{"status": 503}, {"exc": TimeoutError}, {"text": "<html>"}]
)
async def test_fetch_fails(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, answer
) -> None:
    aioclient_mock.get(FEED_URL, **answer)
    with pytest.raises(FeedError):
        await async_fetch_feed(async_get_clientsession(hass))
