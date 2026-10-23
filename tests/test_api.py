"""Tests for parsing the API payload."""

from __future__ import annotations

from custom_components.oko_fuel.api import Station, dedupe_stations


def test_parse_station_with_prices(nearby_raw: list[dict]) -> None:
    """Circle K Tynset has prices and a Z-suffixed timestamp."""
    raw = next(s for s in nearby_raw if s["id"] == "aahh6100xzos3cd")
    station = Station.from_api(raw)

    assert station.display_name == "Circle K Tynset"
    assert station.address == "Brugata 10, 2500 Tynset"
    assert station.prices["gasoline"] == 30.11
    assert station.prices["diesel"] == 27.44
    assert station.prices["e10"] is None
    assert station.last_updated is not None
    assert station.last_updated.tzinfo is not None
    assert station.city == "Tynset"


def test_parse_station_without_prices(nearby_raw: list[dict]) -> None:
    """Stations with null prices parse to None, not 0."""
    raw = next(s for s in nearby_raw if s["id"] == "kbu0uswhn25olpy")
    station = Station.from_api(raw)
    assert all(v is None for v in station.prices.values())
    assert station.display_name == "Mer Alti Tynset"


def test_generic_brand_is_not_prefixed(nearby_raw: list[dict]) -> None:
    """'Diverse' is the API's catch-all brand and should not appear in names."""
    raw = next(s for s in nearby_raw if s["id"] == "23wudwc0lp2grj5")
    assert Station.from_api(raw).display_name == "Energitransport Tynset"


def test_display_name_avoids_duplicate_brand() -> None:
    """'Circle K' + 'Circle K Tynset' should not become 'Circle K Circle K Tynset'."""
    station = Station.from_api(
        {"id": "x", "name": "Circle K Tynset", "brand": "Circle K", "prices": {}}
    )
    assert station.display_name == "Circle K Tynset"


def test_charging_sites_are_flagged(nearby_stations: list[Station]) -> None:
    """Operators that only do EV charging are marked, fuel stations are not."""
    by_id = {s.station_id: s for s in nearby_stations}
    mer = by_id["kbu0uswhn25olpy"]  # Mer Alti Tynset, no prices
    kople = by_id["iy2siux47ezc2rp"]  # Kople EXTRA Tynset, no prices
    circle_k = by_id["aahh6100xzos3cd"]
    moller = by_id["qr9z047kjuct92o"]  # Møller Bil, no prices, not a charger brand

    assert mer.is_charging_site and kople.is_charging_site
    assert not circle_k.is_charging_site and circle_k.has_fuel_price
    assert not moller.is_charging_site and not moller.has_fuel_price

    assert mer.label().endswith("– lading")
    assert moller.label().endswith("– ingen drivstoffpris")
    assert circle_k.label() == "Circle K Tynset"
    assert circle_k.label(with_address=True) == "Circle K Tynset (Brugata 10, 2500 Tynset)"


def test_brandless_station_gets_address(nearby_stations: list[Station]) -> None:
    """A bare place name like "Tynset" always carries its address."""
    by_id = {s.station_id: s for s in nearby_stations}
    bare = by_id["4gsjfi0208rdcx9"]  # brand "Diverse", name "Tynset"
    assert not bare.has_brand
    assert bare.label().startswith("Tynset (Industriveien 9, Tynset)")


def test_stale_price_hint(nearby_stations: list[Station]) -> None:
    """Prices older than two weeks get a 'last updated' hint."""
    from datetime import datetime, timezone

    by_id = {s.station_id: s for s in nearby_stations}
    stale = by_id["4gsjfi0208rdcx9"]  # last_updated 2026-09-18
    fresh = by_id["aahh6100xzos3cd"]  # last_updated 2026-10-23
    now = datetime(2026, 10, 23, 18, 0, tzinfo=timezone.utc)
    assert stale.is_stale(now) and not fresh.is_stale(now)
    from homeassistant.util import dt as dt_util

    day = dt_util.as_local(stale.last_updated).strftime("%d.%m.%Y")
    assert stale.label().endswith(f"– sist oppdatert {day}")


def test_dedupe_keeps_freshest_record() -> None:
    """The API's stale brand-less copies of a station are dropped."""
    fresh = Station.from_api(
        {
            "id": "fresh",
            "name": "Tylldal",
            "brand": "DRIV",
            "location": {"latitude": 62.120266, "longitude": 10.799557, "address": "x"},
            "prices": {"diesel_price": 28.06, "last_updated": "2026-10-23T06:14:04Z"},
        }
    )
    stale = Station.from_api(
        {
            "id": "stale",
            "name": "DRIV Tylldal",
            "brand": None,
            "location": {"latitude": 62.1376694, "longitude": 10.7937845, "address": "y"},
            "prices": {"diesel_price": 22.0, "last_updated": "2026-05-04T02:42:47.791000Z"},
        }
    )
    far_away = Station.from_api(
        {
            "id": "far",
            "name": "DRIV Tylldal",
            "brand": None,
            "location": {"latitude": 60.0, "longitude": 10.0, "address": "z"},
            "prices": {"last_updated": "2026-10-23T06:14:04Z"},
        }
    )
    assert fresh.display_name.casefold() == stale.display_name.casefold()
    # Order of input must not matter for which one survives.
    assert [s.station_id for s in dedupe_stations([stale, fresh, far_away])] == ["fresh", "far"]
    assert [s.station_id for s in dedupe_stations([fresh, stale])] == ["fresh"]


def test_known_address_fix() -> None:
    """2510 is Tylldalen, whatever the API says."""
    station = Station.from_api(
        {"id": "x", "name": "Tylldal", "brand": "DRIV",
         "location": {"address": "Tylldalsveien 1975, 2510 Folldal"}, "prices": {}}
    )
    assert station.address == "Tylldalsveien 1975, 2510 Tylldalen"
