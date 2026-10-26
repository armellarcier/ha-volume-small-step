"""Tests for the volume_small_step services."""

import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_mock_service,
)

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import area_registry as ar, entity_registry as er
from homeassistant.setup import async_setup_component

from custom_components.volume_small_step import DOMAIN

ENTITY = "media_player.test"


@pytest.fixture
async def volume_set_calls(hass: HomeAssistant):
    """Set up the integration and capture media_player.volume_set calls."""
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()
    # Mock after setup, otherwise media_player registers the real service over it
    return async_mock_service(hass, "media_player", "volume_set")


@pytest.mark.parametrize(
    ("service", "start", "data", "expected"),
    [
        ("volume_up_small", 0.5, {}, 0.52),
        ("volume_down_small", 0.5, {}, 0.48),
        ("volume_up_small", 0.5, {"step": 0.01}, 0.51),
        ("volume_up_small", 0.99, {"step": 0.05}, 1.0),
        ("volume_down_small", 0.01, {"step": 0.05}, 0.0),
    ],
)
async def test_volume_step(
    hass: HomeAssistant, volume_set_calls, service, start, data, expected
) -> None:
    hass.states.async_set(ENTITY, "playing", {"volume_level": start})

    await hass.services.async_call(
        DOMAIN, service, {"entity_id": ENTITY, **data}, blocking=True
    )

    assert len(volume_set_calls) == 1
    assert volume_set_calls[0].data == {"entity_id": ENTITY, "volume_level": expected}


async def test_entity_without_volume_is_skipped(
    hass: HomeAssistant, volume_set_calls
) -> None:
    hass.states.async_set(ENTITY, "off", {})

    await hass.services.async_call(
        DOMAIN, "volume_up_small", {"entity_id": ENTITY}, blocking=True
    )

    assert volume_set_calls == []


async def test_config_flow_single_instance(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_unload_removes_services(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(domain=DOMAIN, unique_id=DOMAIN)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    assert hass.services.has_service(DOMAIN, "volume_up_small")

    assert await hass.config_entries.async_unload(entry.entry_id)
    assert not hass.services.has_service(DOMAIN, "volume_up_small")


async def test_area_target(hass: HomeAssistant, volume_set_calls) -> None:
    area = ar.async_get(hass).async_create("Salon")
    er.async_get(hass).async_get_or_create(
        "media_player", "test", "unique", suggested_object_id="test"
    )
    er.async_get(hass).async_update_entity(ENTITY, area_id=area.id)
    hass.states.async_set(ENTITY, "playing", {"volume_level": 0.5})

    await hass.services.async_call(
        DOMAIN, "volume_up_small", target={"area_id": area.id}, blocking=True
    )

    assert len(volume_set_calls) == 1
    assert volume_set_calls[0].data == {"entity_id": ENTITY, "volume_level": 0.52}
