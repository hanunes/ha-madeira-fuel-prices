"""Sensors for the Madeira Fuel Prices integration."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import CURRENCY_EURO, EntityCategory, UnitOfVolume
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import FUELS, PriceOrder
from .const import DOMAIN, JORAM_URL, NAME
from .coordinator import (
    FuelPrices,
    MadeiraFuelPricesConfigEntry,
    MadeiraFuelPricesCoordinator,
)

PRICE_UNIT = f"{CURRENCY_EURO}/{UnitOfVolume.LITERS}"


@dataclass(frozen=True, kw_only=True)
class MadeiraFuelSensorDescription(SensorEntityDescription):
    """Describes a sensor: its value, and the attributes that go with it."""

    value_fn: Callable[[FuelPrices], float | int | date | datetime | None]
    attributes_fn: Callable[[FuelPrices], dict[str, Any] | None]


def _current(prices: FuelPrices) -> PriceOrder | None:
    return prices.current


def _upcoming(prices: FuelPrices) -> PriceOrder | None:
    return prices.upcoming


def _order_sensor(
    key: str,
    order_fn: Callable[[FuelPrices], PriceOrder | None],
    value_fn: Callable[[PriceOrder], float | date | None],
    **kwargs: Any,
) -> MadeiraFuelSensorDescription:
    """Describe a sensor for one value of an order; unknown without the order."""

    def value(prices: FuelPrices) -> float | date | None:
        order = order_fn(prices)
        return None if order is None else value_fn(order)

    def attributes(prices: FuelPrices) -> dict[str, Any] | None:
        """Return where the value comes from."""
        order = order_fn(prices)
        if order is None:
            return None
        return {
            "valid_from": order.valid_from.isoformat(),
            "portaria": order.portaria,
            "source": order.source.rsplit("/", 1)[-1],
            "source_url": order.source,
        }

    return MadeiraFuelSensorDescription(
        key=key, translation_key=key, value_fn=value, attributes_fn=attributes, **kwargs
    )


def _price_of(fuel: str) -> Callable[[PriceOrder], float | None]:
    return lambda order: order.prices[fuel]


def _valid_from(order: PriceOrder) -> date:
    return order.valid_from


SENSORS: tuple[MadeiraFuelSensorDescription, ...] = (
    *(
        _order_sensor(
            fuel,
            _current,
            _price_of(fuel),
            native_unit_of_measurement=PRICE_UNIT,
            state_class=SensorStateClass.MEASUREMENT,
            suggested_display_precision=3,
        )
        for fuel in FUELS
    ),
    *(
        _order_sensor(
            f"next_{fuel}",
            _upcoming,
            _price_of(fuel),
            native_unit_of_measurement=PRICE_UNIT,
            suggested_display_precision=3,
        )
        for fuel in FUELS
    ),
    _order_sensor(
        "valid_from", _current, _valid_from, device_class=SensorDeviceClass.DATE
    ),
    _order_sensor(
        "next_valid_from", _upcoming, _valid_from, device_class=SensorDeviceClass.DATE
    ),
    # The state of the feed, for an automation to notify on: data more than
    # 8 days old, or any warning.
    MadeiraFuelSensorDescription(
        key="updated_at",
        translation_key="updated_at",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda prices: prices.updated_at,
        attributes_fn=lambda prices: None,
    ),
    MadeiraFuelSensorDescription(
        key="warnings",
        translation_key="warnings",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda prices: len(prices.warnings),
        attributes_fn=lambda prices: {
            "codes": [warning["code"] for warning in prices.warnings],
            "messages": [warning["message"] for warning in prices.warnings],
        },
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MadeiraFuelPricesConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensors."""
    coordinator = entry.runtime_data
    async_add_entities(
        MadeiraFuelSensor(coordinator, description) for description in SENSORS
    )


class MadeiraFuelSensor(
    CoordinatorEntity[MadeiraFuelPricesCoordinator], SensorEntity
):
    """A price, the date an order starts, or the state of the feed."""

    entity_description: MadeiraFuelSensorDescription
    _attr_has_entity_name = True
    _attr_attribution = "JORAM - Jornal Oficial da Região Autónoma da Madeira"

    def __init__(
        self,
        coordinator: MadeiraFuelPricesCoordinator,
        description: MadeiraFuelSensorDescription,
    ) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{DOMAIN}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, DOMAIN)},
            name=NAME,
            manufacturer="Região Autónoma da Madeira",
            model="JORAM",
            entry_type=DeviceEntryType.SERVICE,
            configuration_url=JORAM_URL,
        )

    @property
    def native_value(self) -> float | int | date | datetime | None:
        """Return the sensor's value; unknown while there is no such order."""
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the attributes that go with the value."""
        return self.entity_description.attributes_fn(self.coordinator.data)
