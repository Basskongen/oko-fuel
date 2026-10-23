"""The Øko-fuel integration: Norwegian fuel prices from backend.drivstoffapp.no."""

from __future__ import annotations

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .const import DOMAIN
from .coordinator import DrivstoffappConfigEntry, DrivstoffappCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: DrivstoffappConfigEntry) -> bool:
    """Set up Øko-fuel from a config entry."""
    coordinator = DrivstoffappCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    _remove_stale_registry_entries(hass, entry, coordinator)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: DrivstoffappConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


def _remove_stale_registry_entries(
    hass: HomeAssistant,
    entry: DrivstoffappConfigEntry,
    coordinator: DrivstoffappCoordinator,
) -> None:
    """Drop entities and devices for stations/fuel types the user deselected."""
    expected_unique_ids: set[str] = set()
    for station_id in coordinator.station_ids:
        expected_unique_ids.add(f"{station_id}_last_updated")
        expected_unique_ids.update(
            f"{station_id}_{fuel_type}" for fuel_type in coordinator.fuel_types
        )
    expected_unique_ids.update(
        f"{entry.entry_id}_cheapest_{fuel_type}" for fuel_type in coordinator.fuel_types
    )

    entity_registry = er.async_get(hass)
    for entity_entry in er.async_entries_for_config_entry(entity_registry, entry.entry_id):
        if entity_entry.unique_id not in expected_unique_ids:
            entity_registry.async_remove(entity_entry.entity_id)

    expected_devices = {(DOMAIN, entry.entry_id)} | {
        (DOMAIN, station_id) for station_id in coordinator.station_ids
    }
    device_registry = dr.async_get(hass)
    for device in dr.async_entries_for_config_entry(device_registry, entry.entry_id):
        if not device.identifiers & expected_devices:
            device_registry.async_update_device(
                device.id, remove_config_entry_id=entry.entry_id
            )
