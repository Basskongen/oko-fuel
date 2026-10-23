"""Sensors for Øko-fuel: one price sensor per station and fuel type."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import Station
from .const import (
    ATTR_ADDRESS,
    ATTR_BRAND,
    ATTR_LAST_UPDATED,
    ATTR_RANKING,
    ATTR_STATION_ID,
    ATTR_STATION_NAME,
    DOMAIN,
    UNIT_NOK_PER_LITRE,
)
from .coordinator import DrivstoffappConfigEntry, DrivstoffappCoordinator

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DrivstoffappConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create entities for every selected station and fuel type."""
    coordinator = entry.runtime_data
    entities: list[SensorEntity] = []

    for station_id in coordinator.station_ids:
        entities.extend(
            StationPriceSensor(coordinator, station_id, fuel_type)
            for fuel_type in coordinator.fuel_types
        )
        entities.append(StationUpdatedSensor(coordinator, station_id))

    entities.extend(
        CheapestPriceSensor(coordinator, entry, fuel_type)
        for fuel_type in coordinator.fuel_types
    )

    async_add_entities(entities)


def _station_device(station: Station | None, station_id: str) -> DeviceInfo:
    name = station.display_name if station else f"Stasjon {station_id}"
    return DeviceInfo(
        identifiers={(DOMAIN, station_id)},
        name=name,
        manufacturer=station.brand if station and station.brand else "Drivstoffapp",
        model="Drivstoffstasjon",
    )


class StationEntity(CoordinatorEntity[DrivstoffappCoordinator]):
    """Base for entities that belong to one station."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: DrivstoffappCoordinator, station_id: str) -> None:
        """Initialise."""
        super().__init__(coordinator)
        self._station_id = station_id
        self._attr_device_info = _station_device(self.station, station_id)

    @property
    def station(self) -> Station | None:
        """Current data for this station, if the API returned it."""
        return (self.coordinator.data or {}).get(self._station_id)

    @property
    def available(self) -> bool:
        """Unavailable when the station is missing from the last update."""
        return super().available and self.station is not None


class StationPriceSensor(StationEntity, SensorEntity):
    """Price of one fuel type at one station."""

    _attr_native_unit_of_measurement = UNIT_NOK_PER_LITRE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 2
    _attr_icon = "mdi:gas-station"

    def __init__(
        self, coordinator: DrivstoffappCoordinator, station_id: str, fuel_type: str
    ) -> None:
        """Initialise."""
        super().__init__(coordinator, station_id)
        self._fuel_type = fuel_type
        self._attr_unique_id = f"{station_id}_{fuel_type}"
        self._attr_translation_key = fuel_type

    @property
    def native_value(self) -> float | None:
        """Return the price, or None when the station has no price for this fuel."""
        station = self.station
        if station is None:
            return None
        return station.prices.get(self._fuel_type)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose station details so dashboards and automations can use them."""
        station = self.station
        if station is None:
            return {}
        return {
            ATTR_STATION_ID: station.station_id,
            ATTR_STATION_NAME: station.display_name,
            ATTR_BRAND: station.brand,
            ATTR_ADDRESS: station.address,
            ATTR_LAST_UPDATED: (
                station.last_updated.isoformat() if station.last_updated else None
            ),
        }


class StationUpdatedSensor(StationEntity, SensorEntity):
    """When the API last saw a price change at this station."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "last_updated"

    def __init__(self, coordinator: DrivstoffappCoordinator, station_id: str) -> None:
        """Initialise."""
        super().__init__(coordinator, station_id)
        self._attr_unique_id = f"{station_id}_last_updated"

    @property
    def native_value(self) -> datetime | None:
        """Return the timestamp."""
        station = self.station
        return station.last_updated if station else None


class CheapestPriceSensor(CoordinatorEntity[DrivstoffappCoordinator], SensorEntity):
    """Lowest price for a fuel type across the selected stations."""

    _attr_has_entity_name = True
    _attr_native_unit_of_measurement = UNIT_NOK_PER_LITRE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 2
    _attr_icon = "mdi:gas-station-outline"

    def __init__(
        self,
        coordinator: DrivstoffappCoordinator,
        entry: DrivstoffappConfigEntry,
        fuel_type: str,
    ) -> None:
        """Initialise."""
        super().__init__(coordinator)
        self._fuel_type = fuel_type
        self._attr_unique_id = f"{entry.entry_id}_cheapest_{fuel_type}"
        self._attr_translation_key = f"cheapest_{fuel_type}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="Øko-fuel",
            model="Data: backend.drivstoffapp.no",
            entry_type=DeviceEntryType.SERVICE,
        )

    def _ranked(self) -> list[Station]:
        stations = [
            s
            for s in (self.coordinator.data or {}).values()
            if s.prices.get(self._fuel_type) is not None
        ]
        return sorted(stations, key=lambda s: s.prices[self._fuel_type])  # type: ignore[arg-type]

    @property
    def native_value(self) -> float | None:
        """Return the lowest price."""
        ranked = self._ranked()
        return ranked[0].prices[self._fuel_type] if ranked else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Which station is cheapest, plus the full ranking."""
        ranked = self._ranked()
        if not ranked:
            return {}
        best = ranked[0]
        return {
            ATTR_STATION_ID: best.station_id,
            ATTR_STATION_NAME: best.display_name,
            ATTR_BRAND: best.brand,
            ATTR_ADDRESS: best.address,
            ATTR_LAST_UPDATED: (
                best.last_updated.isoformat() if best.last_updated else None
            ),
            ATTR_RANKING: [
                {
                    ATTR_STATION_NAME: s.display_name,
                    "price": s.prices[self._fuel_type],
                }
                for s in ranked
            ],
        }
