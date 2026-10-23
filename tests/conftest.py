"""Shared fixtures."""

from __future__ import annotations

from collections.abc import Generator
import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from custom_components.oko_fuel.api import Station

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Let the test harness load custom_components/."""


@pytest.fixture
def nearby_raw() -> list[dict]:
    """Real API response for Tynset, captured 2026-10-23."""
    return json.loads((FIXTURES / "nearby.json").read_text(encoding="utf-8"))


@pytest.fixture
def nearby_stations(nearby_raw: list[dict]) -> list[Station]:
    """Parsed stations."""
    return [Station.from_api(item) for item in nearby_raw]


@pytest.fixture
def mock_api(nearby_stations: list[Station]) -> Generator[AsyncMock]:
    """Patch the API client so no network is used."""
    with (
        patch(
            "custom_components.oko_fuel.api.DrivstoffappApi.async_nearby",
            new_callable=AsyncMock,
            return_value=nearby_stations,
        ) as nearby,
        patch(
            "custom_components.oko_fuel.api.DrivstoffappApi.async_station",
            new_callable=AsyncMock,
            return_value=None,
        ),
    ):
        yield nearby
