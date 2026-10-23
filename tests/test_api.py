"""Tests for parsing the API payload."""

from __future__ import annotations

from custom_components.oko_fuel.api import Station


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

    assert mer.label("nb").endswith("– lading")
    assert mer.label("en").endswith("– EV charging")
    assert moller.label("nb").endswith("– ingen drivstoffpris")
    assert circle_k.label("nb") == "Circle K Tynset (Brugata 10, 2500 Tynset)"
