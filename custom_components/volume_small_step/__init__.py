"""Volume Small Step — custom integration for Home Assistant.

Adds two actions to the media_player domain:
  - volume_small_step.volume_up_small
  - volume_small_step.volume_down_small

Both actions accept an optional `step` parameter (float, 0.01–0.5, default 0.02).

No configuration.yaml entry required: the integration is set up via the UI.
"""

from __future__ import annotations

import inspect
import logging

import voluptuous as vol

from homeassistant.components.media_player import DOMAIN as MEDIA_PLAYER_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.service import async_extract_entity_ids

_LOGGER = logging.getLogger(__name__)

DOMAIN = "volume_small_step"

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

ATTR_STEP = "step"
DEFAULT_STEP = 0.02
MIN_STEP = 0.01
MAX_STEP = 0.5

SERVICE_VOLUME_UP_SMALL = "volume_up_small"
SERVICE_VOLUME_DOWN_SMALL = "volume_down_small"

SERVICE_SCHEMA = vol.Schema(
    {
        **cv.TARGET_SERVICE_FIELDS,
        vol.Optional(ATTR_STEP, default=DEFAULT_STEP): vol.All(
            vol.Coerce(float),
            vol.Range(min=MIN_STEP, max=MAX_STEP),
        ),
    }
)

# HA 2025+ dropped the `hass` argument of async_extract_entity_ids
_EXTRACT_NEEDS_HASS = "hass" in inspect.signature(async_extract_entity_ids).parameters


def _register_services(hass: HomeAssistant) -> None:
    """Register the volume_up_small and volume_down_small services."""

    # Avoid double-registration if setup is called multiple times
    if hass.services.has_service(DOMAIN, SERVICE_VOLUME_UP_SMALL):
        return

    async def _handle_volume_change(call: ServiceCall, direction: int) -> None:
        """Handle volume_up_small / volume_down_small service calls.

        Args:
            call: The service call data.
            direction: +1 for up, -1 for down.
        """
        step: float = call.data.get(ATTR_STEP, DEFAULT_STEP)

        # Resolves entity, device and area targets (and expands groups)
        if _EXTRACT_NEEDS_HASS:
            target_entities = await async_extract_entity_ids(hass, call)
        else:
            target_entities = await async_extract_entity_ids(call)

        if not target_entities:
            _LOGGER.warning(
                "%s called without any target entity.",
                SERVICE_VOLUME_UP_SMALL if direction == 1 else SERVICE_VOLUME_DOWN_SMALL,
            )
            return

        for entity_id in sorted(target_entities):
            state = hass.states.get(entity_id)
            if state is None:
                _LOGGER.warning("Entity %s not found, skipping.", entity_id)
                continue

            current_volume: float | None = state.attributes.get("volume_level")
            if current_volume is None:
                _LOGGER.warning(
                    "Entity %s has no volume_level attribute, skipping.", entity_id
                )
                continue

            new_volume = round(
                max(0.0, min(1.0, current_volume + direction * step)), 4
            )

            _LOGGER.debug(
                "Entity %s: volume %s → %s (step=%s, direction=%s)",
                entity_id,
                current_volume,
                new_volume,
                step,
                direction,
            )

            await hass.services.async_call(
                MEDIA_PLAYER_DOMAIN,
                "volume_set",
                {ATTR_ENTITY_ID: entity_id, "volume_level": new_volume},
                blocking=True,
            )

    async def handle_volume_up_small(call: ServiceCall) -> None:
        await _handle_volume_change(call, direction=1)

    async def handle_volume_down_small(call: ServiceCall) -> None:
        await _handle_volume_change(call, direction=-1)

    hass.services.async_register(
        DOMAIN,
        SERVICE_VOLUME_UP_SMALL,
        handle_volume_up_small,
        schema=SERVICE_SCHEMA,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_VOLUME_DOWN_SMALL,
        handle_volume_down_small,
        schema=SERVICE_SCHEMA,
    )

    _LOGGER.info(
        "volume_small_step: services registered (%s.%s, %s.%s)",
        DOMAIN, SERVICE_VOLUME_UP_SMALL,
        DOMAIN, SERVICE_VOLUME_DOWN_SMALL,
    )


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Register services at HA startup — no configuration.yaml entry needed."""
    _register_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Called when the user adds the integration via the UI (no-op, services already up)."""
    _register_services(hass)  # idempotent, safe to call again
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry and remove services if no entries remain."""
    # Only remove services when the last entry is unloaded
    remaining = hass.config_entries.async_entries(DOMAIN)
    if len(remaining) <= 1:
        for service in (SERVICE_VOLUME_UP_SMALL, SERVICE_VOLUME_DOWN_SMALL):
            hass.services.async_remove(DOMAIN, service)
        _LOGGER.info("volume_small_step: services removed")
    return True