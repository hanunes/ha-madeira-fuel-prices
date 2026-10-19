"""Tests for the notify blueprint, run by a real automation on set sensor states."""
from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from freezegun.api import FrozenDateTimeFactory
from pytest_homeassistant_custom_component.common import (
    async_capture_events,
    async_fire_time_changed,
)

from homeassistant.core import Event, HomeAssistant
from homeassistant.setup import async_setup_component

MADEIRA = ZoneInfo("Atlantic/Madeira")
BLUEPRINT = (
    Path(__file__).parents[1]
    / "blueprints/automation/hanunes/madeira_fuel_prices_notify.yaml"
)
SENSOR = "sensor.madeira_fuel_prices_"


@pytest.fixture
def expected_lingering_timers() -> bool:
    """The automation's daily time triggers stay scheduled after a test."""
    return True


async def _setup(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    now: datetime,
    next_petrol: str,
    next_valid_from: str = "2026-10-26",
    **inputs: Any,
) -> list[Event]:
    """Set the sensors, then create an automation from the blueprint.

    Petrol 95 is 2.000 €/L now; diesel is 2.000 €/L now and next week.
    Messages are sent as test_msg events instead of to a phone.
    """
    await hass.config.async_set_time_zone("Atlantic/Madeira")
    freezer.move_to(now)
    folder = Path(hass.config.path("blueprints/automation/hanunes"))
    folder.mkdir(parents=True, exist_ok=True)
    shutil.copy(BLUEPRINT, folder / BLUEPRINT.name)
    next_known = next_valid_from != "unknown"
    for key, state in {
        "petrol_95": "2.000",
        "diesel": "2.000",
        "next_petrol_95": next_petrol,
        "next_diesel": "2.000" if next_known else "unknown",
        "valid_from": "2026-10-19",
        "next_valid_from": next_valid_from,
        "warnings": "0",
        "data_updated": now.isoformat(),
    }.items():
        hass.states.async_set(SENSOR + key, state)
    events = async_capture_events(hass, "test_msg")
    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": {
                "use_blueprint": {
                    "path": f"hanunes/{BLUEPRINT.name}",
                    "input": {
                        "notify_problems": False,
                        "custom_actions": [
                            {
                                "event": "test_msg",
                                "event_data": {
                                    "title": "{{ title }}",
                                    "message": "{{ message }}",
                                },
                            }
                        ],
                        **inputs,
                    },
                }
            }
        },
    )
    await hass.async_block_till_done()
    return events


async def _at(hass: HomeAssistant, freezer: FrozenDateTimeFactory, when: datetime) -> None:
    freezer.move_to(when)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


async def test_new_order(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    events = await _setup(
        hass, freezer, datetime(2026, 10, 23, 15, tzinfo=MADEIRA), "unknown", "unknown"
    )
    hass.states.async_set(SENSOR + "next_petrol_95", "2.050")
    hass.states.async_set(SENSOR + "next_diesel", "2.000")
    hass.states.async_set(SENSOR + "next_valid_from", "2026-10-26")
    await hass.async_block_till_done()

    assert [e.data for e in events] == [
        {
            "title": "New fuel prices",
            "message": "From Mon 26 Oct:\nPetrol 95: 2.050 €/L (+5.0 c)\nDiesel: 2.000 €/L (unchanged)",
        }
    ]


async def test_reminder(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    events = await _setup(
        hass, freezer, datetime(2026, 10, 25, 12, tzinfo=MADEIRA), "2.050",
        notify_reminder=True,
    )
    await _at(hass, freezer, datetime(2026, 10, 25, 18, 0, 1, tzinfo=MADEIRA))

    assert [e.data for e in events] == [
        {
            "title": "Fill up before prices change",
            "message": "From Mon 26 Oct:\nPetrol 95: 2.050 €/L (+5.0 c)\nDiesel: 2.000 €/L (unchanged)",
        }
    ]


async def test_reminder_days_time_language(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    events = await _setup(
        hass, freezer, datetime(2026, 10, 24, 8, tzinfo=MADEIRA), "2.050",
        notify_reminder=True, reminder_days=2, reminder_time="10:00:00", language="pt",
    )
    await _at(hass, freezer, datetime(2026, 10, 24, 10, 0, 1, tzinfo=MADEIRA))

    assert [e.data for e in events] == [
        {
            "title": "Abasteça antes da mudança de preços",
            "message": "A partir de seg 26 out:\nGasolina 95: 2.050 €/L (+5.0 c)\nGasóleo: 2.000 €/L (sem alteração)",
        }
    ]


@pytest.mark.parametrize(
    ("day", "next_petrol", "next_valid_from", "inputs", "sent"),
    [
        # Prices go down: only with "only if prices go up" off.
        (25, "1.950", "2026-10-26", {}, False),
        (25, "1.950", "2026-10-26", {"reminder_only_increase": False}, True),
        # Prices unchanged: never.
        (25, "2.000", "2026-10-26", {"reminder_only_increase": False}, False),
        # Two days before the change, with the default of one day.
        (24, "2.050", "2026-10-26", {}, False),
        # No next order known yet.
        (25, "unknown", "unknown", {}, False),
        # The reminder is off.
        (25, "2.050", "2026-10-26", {"notify_reminder": False}, False),
    ],
)
async def test_reminder_conditions(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    day: int,
    next_petrol: str,
    next_valid_from: str,
    inputs: dict[str, Any],
    sent: bool,
) -> None:
    events = await _setup(
        hass, freezer, datetime(2026, 10, day, 12, tzinfo=MADEIRA), next_petrol,
        next_valid_from, **{"notify_reminder": True, **inputs},
    )
    await _at(hass, freezer, datetime(2026, 10, day, 18, 0, 1, tzinfo=MADEIRA))

    assert bool(events) is sent
