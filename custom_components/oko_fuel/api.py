"""Thin async client for the open backend.drivstoffapp.no API."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
import logging
from typing import Any

import aiohttp

from homeassistant.util import dt as dt_util

from .const import BASE_URL, FUEL_TYPES, NEARBY_LIMIT, REQUEST_TIMEOUT

_LOGGER = logging.getLogger(__name__)

# The API uses these as a catch-all "brand" for independent stations.
GENERIC_BRANDS = {"diverse", "ukjent", "unknown", "other", "annet"}

# The fuel endpoint also returns EV charging sites, but gives no reliable flag
# for them (station_type is always "road", has_electric always false). These
# operators only do charging, so we use the brand as the tell.
CHARGING_BRANDS = {
    "mer",
    "kople",
    "ionity",
    "tesla",
    "recharge",
    "eviny",
    "elton",
    "fortum",
    "plugsurfing",
    "lyse",
    "bkk",
    "supercharge",
    "circle k charge",
    "uno-x lading",
}
CHARGING_NAME_HINTS = ("supercharger", "lading", "ladestasjon", "charger", "charging")


class DrivstoffappApiError(Exception):
    """Raised when the API cannot be reached or returns an unexpected payload."""


@dataclass(slots=True)
class Station:
    """A fuel station with its current prices."""

    station_id: str
    name: str
    brand: str
    address: str
    latitude: float | None
    longitude: float | None
    prices: dict[str, float | None] = field(default_factory=dict)
    last_updated: datetime | None = None
    city: str = ""

    @property
    def display_name(self) -> str:
        """Human friendly name, e.g. 'Circle K Tynset'."""
        brand = "" if self.brand.lower() in GENERIC_BRANDS else self.brand
        if brand and self.name and brand.lower() not in self.name.lower():
            return f"{brand} {self.name}"
        return self.name or brand or self.station_id

    @property
    def has_fuel_price(self) -> bool:
        """True when at least one fuel price is known."""
        return any(value is not None for value in self.prices.values())

    @property
    def is_charging_site(self) -> bool:
        """Best-effort guess that this is an EV charging site, not a fuel station."""
        if self.has_fuel_price:
            return False
        if self.brand.lower() in CHARGING_BRANDS:
            return True
        name = self.name.lower()
        return any(hint in name for hint in CHARGING_NAME_HINTS)

    def label(self, language: str = "en") -> str:
        """Label used in the config flow pick list, with a hint for odd entries."""
        text = f"{self.display_name} ({self.address})" if self.address else self.display_name
        norwegian = language.lower().startswith(("nb", "nn", "no"))
        if self.is_charging_site:
            text += " – lading" if norwegian else " – EV charging"
        elif not self.has_fuel_price:
            text += " – ingen drivstoffpris" if norwegian else " – no fuel price"
        return text

    @classmethod
    def from_api(cls, raw: dict[str, Any]) -> Station:
        """Build a Station from one API item."""
        location = raw.get("location") or {}
        raw_prices = raw.get("prices") or {}
        prices: dict[str, float | None] = {}
        for key, api_field in FUEL_TYPES.items():
            value = raw_prices.get(api_field)
            try:
                prices[key] = float(value) if value is not None else None
            except (TypeError, ValueError):
                prices[key] = None

        last_updated = None
        if raw_prices.get("last_updated"):
            last_updated = dt_util.parse_datetime(str(raw_prices["last_updated"]))
            if last_updated is not None and last_updated.tzinfo is None:
                last_updated = last_updated.replace(tzinfo=dt_util.UTC)

        city = ""
        expand = raw.get("expand")
        if isinstance(expand, dict) and isinstance(expand.get("city"), dict):
            city = str(expand["city"].get("name") or "")

        return cls(
            city=city,
            station_id=str(raw.get("id") or ""),
            name=str(raw.get("name") or ""),
            brand=str(raw.get("brand") or ""),
            address=str(location.get("address") or ""),
            latitude=location.get("latitude"),
            longitude=location.get("longitude"),
            prices=prices,
            last_updated=last_updated,
        )


class DrivstoffappApi:
    """Minimal client. The API is public and needs no key."""

    def __init__(self, session: aiohttp.ClientSession) -> None:
        """Initialise with a shared aiohttp session."""
        self._session = session

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        url = f"{BASE_URL}{path}"
        try:
            async with asyncio.timeout(REQUEST_TIMEOUT):
                async with self._session.get(url, params=params) as resp:
                    if resp.status != 200:
                        raise DrivstoffappApiError(f"HTTP {resp.status} from {path}")
                    return await resp.json(content_type=None)
        except (aiohttp.ClientError, TimeoutError) as err:
            raise DrivstoffappApiError(f"Error talking to {url}: {err}") from err
        except ValueError as err:
            raise DrivstoffappApiError(f"Invalid JSON from {url}") from err

    async def async_nearby(
        self, latitude: float, longitude: float, radius_km: float
    ) -> list[Station]:
        """Return all stations within radius_km of a point."""
        data = await self._get(
            "/stations/fuel/nearby",
            {
                "lat": latitude,
                "lng": longitude,
                "radius": radius_km,
                "limit": NEARBY_LIMIT,
                "include_no_price": "true",
                "sort_by": "distance",
            },
        )
        if not isinstance(data, list):
            raise DrivstoffappApiError("Unexpected response shape from nearby endpoint")
        stations = [Station.from_api(item) for item in data if isinstance(item, dict)]
        return [s for s in stations if s.station_id]

    async def async_station(self, station_id: str) -> Station | None:
        """Return a single station, or None if it no longer exists."""
        try:
            data = await self._get(f"/stations/fuel/{station_id}")
        except DrivstoffappApiError as err:
            if "HTTP 404" in str(err):
                return None
            raise
        if not isinstance(data, dict):
            raise DrivstoffappApiError("Unexpected response shape from station endpoint")
        return Station.from_api(data)
