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
