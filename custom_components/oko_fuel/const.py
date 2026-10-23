"""Constants for the Øko-fuel integration."""

from __future__ import annotations

DOMAIN = "oko_fuel"

BASE_URL = "https://backend.drivstoffapp.no"
NEARBY_LIMIT = 100
REQUEST_TIMEOUT = 30

CONF_RADIUS = "radius"
CONF_STATIONS = "stations"
CONF_FUEL_TYPES = "fuel_types"
CONF_SCAN_INTERVAL = "scan_interval"

DEFAULT_RADIUS_KM = 10.0
MAX_RADIUS_KM = 100.0
DEFAULT_SCAN_INTERVAL_MINUTES = 30
MIN_SCAN_INTERVAL_MINUTES = 5

# How long to keep showing the last known prices when the API is unreachable,
# before letting the sensors go unavailable.
RETAIN_AFTER_FAILURE_HOURS = 12

# fuel type key -> field name in the API "prices" object
FUEL_TYPES: dict[str, str] = {
    "gasoline": "gasoline_price",
    "octane": "octane_price",
    "diesel": "diesel_price",
    "hvo100": "hvo100_price",
    "fd": "fd_price",
    "e10": "e10_price",
}
DEFAULT_FUEL_TYPES = ["gasoline", "diesel"]

UNIT_NOK_PER_LITRE = "NOK/L"

ATTR_STATION_ID = "station_id"
ATTR_STATION_NAME = "station_name"
ATTR_BRAND = "brand"
ATTR_ADDRESS = "address"
ATTR_LAST_UPDATED = "last_updated"
ATTR_RANKING = "ranking"
