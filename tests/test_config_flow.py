"""Tests for the config and options flows."""

from __future__ import annotations

from unittest.mock import AsyncMock

from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant import config_entries
from homeassistant.const import CONF_LATITUDE, CONF_LOCATION, CONF_LONGITUDE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr

from custom_components.oko_fuel.api import DrivstoffappApiError
from custom_components.oko_fuel.const import (
    CONF_FUEL_TYPES,
    CONF_RADIUS,
    CONF_SCAN_INTERVAL,
    CONF_STATIONS,
    DOMAIN,
)

LOCATION = {CONF_LATITUDE: 62.276, CONF_LONGITUDE: 10.782, CONF_RADIUS: 15000}


async def test_full_flow(hass: HomeAssistant, mock_api: AsyncMock) -> None:
    """Map step, then station step, creates an entry titled after the city."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_LOCATION: LOCATION}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "stations"
    mock_api.assert_awaited_once_with(62.276, 10.782, 15.0)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_STATIONS: ["aahh6100xzos3cd", "nhecf2vh28lth1o"],
            CONF_FUEL_TYPES: ["gasoline", "diesel"],
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Øko-fuel Tynset"
    assert result["data"] == {
        CONF_LATITUDE: 62.276,
        CONF_LONGITUDE: 10.782,
        CONF_RADIUS: 15.0,
        CONF_STATIONS: ["aahh6100xzos3cd", "nhecf2vh28lth1o"],
        CONF_FUEL_TYPES: ["gasoline", "diesel"],
    }


async def test_cannot_connect(hass: HomeAssistant, mock_api: AsyncMock) -> None:
    """An API error shows an error on the first step."""
    mock_api.side_effect = DrivstoffappApiError("boom")
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_LOCATION: LOCATION}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_no_stations(hass: HomeAssistant, mock_api: AsyncMock) -> None:
    """An empty result asks for a larger radius."""
    mock_api.return_value = []
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_LOCATION: LOCATION}
    )
    assert result["errors"] == {"base": "no_stations"}


async def test_options_flow(hass: HomeAssistant, mock_api: AsyncMock) -> None:
    """Options flow stores new stations and interval, and the entry reloads."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Øko-fuel Tynset",
        data={
            CONF_LATITUDE: 62.276,
            CONF_LONGITUDE: 10.782,
            CONF_RADIUS: 15.0,
            CONF_STATIONS: ["aahh6100xzos3cd"],
            CONF_FUEL_TYPES: ["diesel"],
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_STATIONS: ["aahh6100xzos3cd", "p2m9i4rdraz6c5g"],
            CONF_FUEL_TYPES: ["diesel", "gasoline"],
            CONF_SCAN_INTERVAL: 15,
        },
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_SCAN_INTERVAL] == 15
    assert hass.states.get("sensor.max_bensin_tynset_diesel") is not None
    assert hass.states.get("sensor.max_bensin_tynset_petrol_95") is not None


async def test_options_flow_removes_deselected(
    hass: HomeAssistant, mock_api: AsyncMock
) -> None:
    """Deselecting a station or fuel type removes its entities and device."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Øko-fuel Tynset",
        data={
            CONF_LATITUDE: 62.276,
            CONF_LONGITUDE: 10.782,
            CONF_RADIUS: 15.0,
            CONF_STATIONS: ["aahh6100xzos3cd", "p2m9i4rdraz6c5g"],
            CONF_FUEL_TYPES: ["diesel", "gasoline"],
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.max_bensin_tynset_diesel") is not None
    assert hass.states.get("sensor.circle_k_tynset_petrol_95") is not None

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_STATIONS: ["aahh6100xzos3cd"],
            CONF_FUEL_TYPES: ["diesel"],
            CONF_SCAN_INTERVAL: 30,
        },
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY

    assert hass.states.get("sensor.circle_k_tynset_diesel") is not None
    assert hass.states.get("sensor.circle_k_tynset_petrol_95") is None
    assert hass.states.get("sensor.max_bensin_tynset_diesel") is None
    assert hass.states.get("sensor.oko_fuel_tynset_cheapest_petrol_95") is None

    device_registry = dr.async_get(hass)
    assert device_registry.async_get_device({(DOMAIN, "p2m9i4rdraz6c5g")}) is None
    assert device_registry.async_get_device({(DOMAIN, "aahh6100xzos3cd")}) is not None
