"""Config flow for Øko-fuel: pick an area on the map, then pick stations."""

from __future__ import annotations

from collections import Counter
import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.const import CONF_LATITUDE, CONF_LOCATION, CONF_LONGITUDE
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    LocationSelector,
    LocationSelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

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
    FUEL_TYPES,
    MAX_RADIUS_KM,
    MIN_SCAN_INTERVAL_MINUTES,
)

_LOGGER = logging.getLogger(__name__)


def _fuel_type_selector() -> SelectSelector:
    return SelectSelector(
        SelectSelectorConfig(
            options=list(FUEL_TYPES),
            multiple=True,
            mode=SelectSelectorMode.LIST,
            translation_key="fuel_type",
        )
    )


def _station_selector(stations: list[Station]) -> SelectSelector:
    """Real fuel stations first, then price-less ones, then EV charging sites."""

    def group(station: Station) -> int:
        if station.has_fuel_price:
            return 0
        return 2 if station.is_charging_site else 1

    ordered = sorted(stations, key=group)  # stable: keeps API distance order
    # Plain names only; add the address where two stations share a name
    # (case-insensitive: the API has both "YX Tolga" and "Yx Tolga").
    name_counts = Counter(s.display_name.casefold() for s in ordered)
    return SelectSelector(
        SelectSelectorConfig(
            options=[
                SelectOptionDict(
                    value=s.station_id,
                    label=s.label(name_counts[s.display_name.casefold()] > 1),
                )
                for s in ordered
            ],
            multiple=True,
            mode=SelectSelectorMode.LIST,
        )
    )


def _radius_km_from_location(location: dict[str, Any]) -> float:
    """The location selector reports the radius in metres; we store km."""
    metres = location.get("radius")
    if not metres:
        return DEFAULT_RADIUS_KM
    return round(min(max(float(metres) / 1000.0, 0.1), MAX_RADIUS_KM), 2)


def _suggest_title(stations: list[Station], selected: list[str]) -> str:
    chosen = [s for s in stations if s.station_id in selected]
    cities = Counter(s.city for s in chosen if s.city)
    if cities:
        return f"Øko-fuel {cities.most_common(1)[0][0]}"
    return "Øko-fuel"


class OkoFuelConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the initial setup."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialise flow state."""
        self._location: dict[str, float] = {}
        self._stations: list[Station] = []

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OkoFuelOptionsFlow:
        """Return the options flow handler."""
        return OkoFuelOptionsFlow()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step 1: choose the search area."""
        errors: dict[str, str] = {}

        if user_input is not None:
            location = user_input[CONF_LOCATION]
            latitude = float(location[CONF_LATITUDE])
            longitude = float(location[CONF_LONGITUDE])
            radius_km = _radius_km_from_location(location)

            await self.async_set_unique_id(f"{latitude:.3f},{longitude:.3f}")
            self._abort_if_unique_id_configured()

            api = DrivstoffappApi(async_get_clientsession(self.hass))
            try:
                stations = await api.async_nearby(latitude, longitude, radius_km)
            except DrivstoffappApiError:
                _LOGGER.exception("Could not fetch stations")
                errors["base"] = "cannot_connect"
            else:
                if not stations:
                    errors["base"] = "no_stations"
                else:
                    self._location = {
                        CONF_LATITUDE: latitude,
                        CONF_LONGITUDE: longitude,
                        CONF_RADIUS: radius_km,
                    }
                    self._stations = stations
                    return await self.async_step_stations()

        default_location = {
            CONF_LATITUDE: self.hass.config.latitude,
            CONF_LONGITUDE: self.hass.config.longitude,
            CONF_RADIUS: DEFAULT_RADIUS_KM * 1000,
        }
        schema = vol.Schema(
            {
                vol.Required(CONF_LOCATION, default=default_location): LocationSelector(
                    LocationSelectorConfig(radius=True)
                )
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_stations(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step 2: choose stations and fuel types."""
        errors: dict[str, str] = {}

        if user_input is not None:
            selected = list(user_input.get(CONF_STATIONS, []))
            fuel_types = list(user_input.get(CONF_FUEL_TYPES, []))
            if not selected:
                errors[CONF_STATIONS] = "no_selection"
            elif not fuel_types:
                errors[CONF_FUEL_TYPES] = "no_selection"
            else:
                return self.async_create_entry(
                    title=_suggest_title(self._stations, selected),
                    data={
                        **self._location,
                        CONF_STATIONS: selected,
                        CONF_FUEL_TYPES: fuel_types,
                    },
                )

        schema = vol.Schema(
            {
                vol.Required(CONF_STATIONS): _station_selector(self._stations),
                vol.Required(
                    CONF_FUEL_TYPES, default=DEFAULT_FUEL_TYPES
                ): _fuel_type_selector(),
            }
        )
        return self.async_show_form(
            step_id="stations",
            data_schema=schema,
            errors=errors,
            description_placeholders={
                "count": str(sum(1 for s in self._stations if s.has_fuel_price)),
                "total": str(len(self._stations)),
            },
        )


class OkoFuelOptionsFlow(OptionsFlowWithReload):
    """Change stations, fuel types and polling interval after setup."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show the single options form."""
        errors: dict[str, str] = {}
        current = {**self.config_entry.data, **self.config_entry.options}

        if user_input is not None:
            selected = list(user_input.get(CONF_STATIONS, []))
            fuel_types = list(user_input.get(CONF_FUEL_TYPES, []))
            if not selected:
                errors[CONF_STATIONS] = "no_selection"
            elif not fuel_types:
                errors[CONF_FUEL_TYPES] = "no_selection"
            else:
                return self.async_create_entry(
                    data={
                        CONF_STATIONS: selected,
                        CONF_FUEL_TYPES: fuel_types,
                        CONF_SCAN_INTERVAL: int(user_input[CONF_SCAN_INTERVAL]),
                    }
                )

        api = DrivstoffappApi(async_get_clientsession(self.hass))
        try:
            stations = await api.async_nearby(
                float(current[CONF_LATITUDE]),
                float(current[CONF_LONGITUDE]),
                float(current.get(CONF_RADIUS, DEFAULT_RADIUS_KM)),
            )
        except DrivstoffappApiError:
            _LOGGER.exception("Could not fetch stations for options")
            return self.async_abort(reason="cannot_connect")

        # Keep previously selected stations selectable even if the radius
        # search no longer returns them.
        known = {s.station_id for s in stations}
        for station_id in current.get(CONF_STATIONS, []):
            if station_id not in known:
                stations.append(
                    Station(
                        station_id=station_id,
                        name=station_id,
                        brand="",
                        address="",
                        latitude=None,
                        longitude=None,
                    )
                )

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_STATIONS, default=list(current.get(CONF_STATIONS, []))
                ): _station_selector(stations),
                vol.Required(
                    CONF_FUEL_TYPES,
                    default=list(current.get(CONF_FUEL_TYPES, DEFAULT_FUEL_TYPES)),
                ): _fuel_type_selector(),
                vol.Required(
                    CONF_SCAN_INTERVAL,
                    default=int(
                        current.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_MINUTES)
                    ),
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=MIN_SCAN_INTERVAL_MINUTES,
                        max=24 * 60,
                        step=1,
                        unit_of_measurement="min",
                        mode=NumberSelectorMode.BOX,
                    )
                ),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema, errors=errors)
