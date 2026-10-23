"""Data update coordinator for Øko-fuel."""

from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import DrivstoffappApi, DrivstoffappApiError, Station
from .const import (
    CONF_FUEL_TYPES,
    CONF_RADIUS,
    CONF_SCAN_INTERVAL,
    CONF_STATIONS,
    DEFAULT_FUEL_TYPES,
    DEFAULT_RADIUS_KM,
    DEFAULT_SCAN_INTERVAL_MINUTES,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

type DrivstoffappConfigEntry = ConfigEntry[DrivstoffappCoordinator]


class DrivstoffappCoordinator(DataUpdateCoordinator[dict[str, Station]]):
    """Fetch prices for the user's selected stations in one call."""

    config_entry: DrivstoffappConfigEntry

    def __init__(self, hass: HomeAssistant, entry: DrivstoffappConfigEntry) -> None:
        """Initialise."""
        opts = {**entry.data, **entry.options}
        minutes = int(opts.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_MINUTES))
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} {entry.title}",
            update_interval=timedelta(minutes=minutes),
        )
        self.api = DrivstoffappApi(async_get_clientsession(hass))
        self.latitude: float = float(opts[CONF_LATITUDE])
        self.longitude: float = float(opts[CONF_LONGITUDE])
        self.radius_km: float = float(opts.get(CONF_RADIUS, DEFAULT_RADIUS_KM))
        self.station_ids: list[str] = list(opts.get(CONF_STATIONS, []))
        self.fuel_types: list[str] = list(opts.get(CONF_FUEL_TYPES, DEFAULT_FUEL_TYPES))

    async def _async_update_data(self) -> dict[str, Station]:
        wanted = set(self.station_ids)
        try:
            nearby = await self.api.async_nearby(
                self.latitude, self.longitude, self.radius_km
            )
            result = {s.station_id: s for s in nearby if s.station_id in wanted}

            # A selected station can drop out of the radius search (API quirks,
            # coordinates nudged). Fetch those one by one so entities stay alive.
            for station_id in wanted - result.keys():
                station = await self.api.async_station(station_id)
                if station is not None:
                    result[station_id] = station
                else:
                    _LOGGER.warning(
                        "Station %s was not returned by the API; marking unavailable",
                        station_id,
                    )
        except DrivstoffappApiError as err:
            raise UpdateFailed(str(err)) from err

        return result
