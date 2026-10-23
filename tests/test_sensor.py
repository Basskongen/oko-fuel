"""Tests for the sensors."""

from __future__ import annotations

from unittest.mock import AsyncMock

from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant

from custom_components.oko_fuel.api import DrivstoffappApiError
from custom_components.oko_fuel.const import (
    CONF_FUEL_TYPES,
    CONF_RADIUS,
    CONF_STATIONS,
    DOMAIN,
)


async def _setup(hass: HomeAssistant, language: str = "nb") -> MockConfigEntry:
    hass.config.language = language
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Øko-fuel Tynset",
        data={
            CONF_LATITUDE: 62.276,
            CONF_LONGITUDE: 10.782,
            CONF_RADIUS: 15.0,
            CONF_STATIONS: ["aahh6100xzos3cd", "nhecf2vh28lth1o", "kbu0uswhn25olpy"],
            CONF_FUEL_TYPES: ["gasoline", "diesel"],
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_station_price_sensors(hass: HomeAssistant, mock_api: AsyncMock) -> None:
    """Each station gets a sensor per fuel type with the API price."""
    await _setup(hass)

    diesel = hass.states.get("sensor.circle_k_tynset_diesel")
    assert diesel is not None
    assert diesel.state == "27.44"
    assert diesel.attributes["unit_of_measurement"] == "NOK/L"
    assert diesel.attributes["station_name"] == "Circle K Tynset"
    assert diesel.attributes["address"] == "Brugata 10, 2500 Tynset"
    assert diesel.attributes["friendly_name"] == "Circle K Tynset Diesel"

    petrol = hass.states.get("sensor.uno_x_tynset_bensin_95")
    assert petrol is not None
    assert petrol.state == "25.99"

    # Station with no prices: entity exists, state unknown, not unavailable.
    none_price = hass.states.get("sensor.mer_alti_tynset_diesel")
    assert none_price is not None
    assert none_price.state == "unknown"

    updated = hass.states.get("sensor.circle_k_tynset_sist_oppdatert")
    assert updated is not None
    assert updated.state == "2026-10-23T10:10:40+00:00"


async def test_cheapest_sensor(hass: HomeAssistant, mock_api: AsyncMock) -> None:
    """Cheapest sensor picks the lowest price among selected stations only."""
    await _setup(hass)

    cheapest = hass.states.get("sensor.oko_fuel_tynset_billigste_diesel")
    assert cheapest is not None
    # Uno X 26.81 < Circle K 27.44; Max Bensin (27.10) is NOT selected.
    assert cheapest.state == "26.81"
    assert cheapest.attributes["station_name"] == "Uno X Tynset"
    assert [r["price"] for r in cheapest.attributes["ranking"]] == [26.81, 27.44]


async def test_unload(hass: HomeAssistant, mock_api: AsyncMock) -> None:
    """Entry unloads cleanly."""
    entry = await _setup(hass)
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.circle_k_tynset_diesel").state == "unavailable"


async def test_keeps_last_value_during_short_outage(
    hass: HomeAssistant, mock_api: AsyncMock, freezer
) -> None:
    """When the API fails, last known prices are kept for up to 12 hours."""
    entry = await _setup(hass)  # frozen at 2026-10-23T18:00Z
    coordinator = entry.runtime_data
    assert hass.states.get("sensor.circle_k_tynset_diesel").state == "27.44"

    mock_api.side_effect = DrivstoffappApiError("HTTP 502 from /stations/fuel/nearby")

    # 2 hours into the outage: still available, still the last known price.
    freezer.move_to("2026-10-23T20:00:00+00:00")
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert coordinator.last_update_success is True
    assert hass.states.get("sensor.circle_k_tynset_diesel").state == "27.44"

    # 13 hours after the last success: give up and go unavailable.
    freezer.move_to("2026-10-24T07:00:00+00:00")
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert coordinator.last_update_success is False
    assert hass.states.get("sensor.circle_k_tynset_diesel").state == "unavailable"


async def test_recovers_after_outage(
    hass: HomeAssistant, mock_api: AsyncMock, freezer
) -> None:
    """Sensors come back with fresh prices once the API answers again."""
    entry = await _setup(hass)
    coordinator = entry.runtime_data

    mock_api.side_effect = DrivstoffappApiError("HTTP 502")
    freezer.move_to("2026-10-23T22:00:00+00:00")
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get("sensor.circle_k_tynset_diesel").state == "27.44"

    mock_api.side_effect = None  # API back
    freezer.move_to("2026-10-23T22:30:00+00:00")
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert coordinator.last_update_success is True
    assert hass.states.get("sensor.circle_k_tynset_diesel").state == "27.44"
